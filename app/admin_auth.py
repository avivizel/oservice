from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AdminSetting, AdminUser

log = logging.getLogger("maaneim.admin")

BOOTSTRAP_USERNAME = "16527681"
BOOTSTRAP_PASSWORD = "2768"
SESSION_SECRET_KEY = "session_secret"
LOCKOUT_AFTER = 8
LOCKOUT_SECONDS = 300

_login_failures: dict[str, list[float]] = {}
_session_secret = ""


def set_session_secret(value: str) -> None:
    global _session_secret
    _session_secret = value


def current_session_secret() -> str:
    return _session_secret


class BoundSessionMiddleware:
    """SessionMiddleware bound after the COS/DB secret is loaded in lifespan."""

    def __init__(self, app):
        self.app = app
        self._inner = None
        self._key = ""

    async def __call__(self, scope, receive, send):
        from starlette.middleware.sessions import SessionMiddleware

        secret = current_session_secret()
        if not secret:
            await self.app(scope, receive, send)
            return
        if self._inner is None or self._key != secret:
            self._inner = SessionMiddleware(
                self.app,
                secret_key=secret,
                session_cookie="maaneim_admin",
                same_site="lax",
                https_only=False,
                max_age=60 * 60 * 12,
            )
            self._key = secret
        await self._inner(scope, receive, send)


def hash_password(plain: str) -> str:
    salt = os.urandom(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        algo, iter_s, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iter_s),
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def _failure_key(username: str) -> str:
    return (username or "").strip()


def is_locked(username: str) -> bool:
    now = time.time()
    stamps = [t for t in _login_failures.get(_failure_key(username), []) if now - t < LOCKOUT_SECONDS]
    _login_failures[_failure_key(username)] = stamps
    return len(stamps) >= LOCKOUT_AFTER


def record_failure(username: str) -> None:
    _login_failures.setdefault(_failure_key(username), []).append(time.time())


def clear_failures(username: str) -> None:
    _login_failures.pop(_failure_key(username), None)


def seed_admin(db: Session) -> None:
    if db.query(AdminUser).count() > 0:
        return
    user = AdminUser(
        username=BOOTSTRAP_USERNAME,
        password_hash=hash_password(BOOTSTRAP_PASSWORD),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    log.info("Seeded initial admin user.")


def ensure_session_secret(db: Session) -> str:
    row = db.query(AdminSetting).filter(AdminSetting.key == SESSION_SECRET_KEY).first()
    if row and row.value.strip():
        return row.value.strip()
    value = secrets.token_urlsafe(48)
    if row is None:
        db.add(AdminSetting(key=SESSION_SECRET_KEY, value=value))
    else:
        row.value = value
    db.commit()
    return value
