from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from app.config import (
    COS_API_KEY,
    COS_BUCKET,
    COS_ENABLED,
    COS_ENDPOINT,
    COS_INSTANCE_CRN,
    COS_OBJECT_KEY,
    DB_PATH,
)

log = logging.getLogger("maaneim.cos")
_lock = threading.Lock()
_skip_persist = False


def _wal_path():
    return DB_PATH.parent / f"{DB_PATH.name}-wal"


def _shm_path():
    return DB_PATH.parent / f"{DB_PATH.name}-shm"


def _client():
    import ibm_boto3
    from ibm_botocore.client import Config

    kwargs: dict[str, Any] = {
        "service_name": "s3",
        "ibm_api_key_id": COS_API_KEY,
        "ibm_auth_endpoint": "https://iam.cloud.ibm.com/identity/token",
        "config": Config(signature_version="oauth"),
        "endpoint_url": COS_ENDPOINT if COS_ENDPOINT.startswith("http") else f"https://{COS_ENDPOINT}",
    }
    if COS_INSTANCE_CRN:
        kwargs["ibm_service_instance_id"] = COS_INSTANCE_CRN
    return ibm_boto3.client(**kwargs)


def remote_size() -> int | None:
    if not COS_ENABLED:
        return None
    try:
        meta = _client().head_object(Bucket=COS_BUCKET, Key=COS_OBJECT_KEY)
        return int(meta.get("ContentLength") or 0)
    except Exception as exc:
        resp = getattr(exc, "response", None) or {}
        err = resp.get("Error") or {}
        code = str(err.get("Code") or "")
        status = (resp.get("ResponseMetadata") or {}).get("HTTPStatusCode")
        if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
            return 0
        raise


def restore_from_cos() -> bool:
    """Download the bucket DB before the app opens SQLite. Returns True if a remote file was restored."""
    global _skip_persist
    if not COS_ENABLED:
        return False
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        size = remote_size()
    except Exception as exc:
        raise RuntimeError(f"Cannot reach COS bucket {COS_BUCKET}: {exc}") from exc
    if not size:
        log.info("COS bucket has no database yet; local file will be created then uploaded.")
        return False
    tmp = DB_PATH.with_suffix(".db.download")
    _skip_persist = True
    try:
        _client().download_file(COS_BUCKET, COS_OBJECT_KEY, str(tmp))
        if tmp.stat().st_size == 0:
            raise RuntimeError("Downloaded an empty database from COS; refusing to start.")
        tmp.replace(DB_PATH)
        _wal_path().unlink(missing_ok=True)
        _shm_path().unlink(missing_ok=True)
        log.info("Restored SQLite from COS (%s bytes).", DB_PATH.stat().st_size)
        return True
    finally:
        _skip_persist = False
        tmp.unlink(missing_ok=True)


def persist_to_cos() -> None:
    """Upload the local SQLite file to COS. Never replaces a non-empty remote with an empty local file."""
    if not COS_ENABLED or _skip_persist:
        return
    with _lock:
        if not DB_PATH.exists():
            return
        snapshot = DB_PATH.with_suffix(".db.cos-snapshot")
        try:
            _consistent_copy(DB_PATH, snapshot)
            local = snapshot.stat().st_size
            remote = remote_size() or 0
            if local < 64 and remote > 0:
                log.error("Refusing to upload empty/tiny local DB over COS object of %s bytes.", remote)
                return
            if remote > 200_000 and local < remote * 0.5:
                log.error(
                    "Refusing to upload local DB (%s bytes) over much larger COS object (%s bytes).",
                    local,
                    remote,
                )
                return
            _client().upload_file(str(snapshot), COS_BUCKET, COS_OBJECT_KEY)
            log.info("Uploaded SQLite to COS (%s bytes).", local)
        finally:
            snapshot.unlink(missing_ok=True)


def _consistent_copy(src: Path, dest: Path) -> None:
    import sqlite3

    dest.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{src.resolve().as_posix()}?mode=ro", uri=True)
    try:
        dest_conn = sqlite3.connect(str(dest))
        try:
            source.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        source.close()


def bootstrap_upload(local_path: Path) -> None:
    """First-time copy of an existing SQLite file into an empty COS object. Never overwrites a populated object."""
    if not COS_ENABLED:
        raise RuntimeError("COS is not configured (COS_API_KEY / COS_BUCKET).")
    local_path = Path(local_path)
    if not local_path.exists() or local_path.stat().st_size < 64:
        raise RuntimeError(f"No SQLite file to bootstrap at {local_path}")
    remote = remote_size() or 0
    if remote > 0:
        log.info(
            "COS already has %s (%s bytes); leaving it untouched.",
            COS_OBJECT_KEY,
            remote,
        )
        return
    snapshot = local_path.with_suffix(".db.cos-snapshot")
    try:
        _consistent_copy(local_path, snapshot)
        _client().upload_file(str(snapshot), COS_BUCKET, COS_OBJECT_KEY)
        log.info("Bootstrapped %s to COS (%s bytes).", COS_OBJECT_KEY, snapshot.stat().st_size)
    finally:
        snapshot.unlink(missing_ok=True)
