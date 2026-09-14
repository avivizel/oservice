from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AccessEvent

log = logging.getLogger("maaneim.access")

_buffer: list[dict[str, Any]] = []
_lock = threading.Lock()
_task: asyncio.Task | None = None


def record(method: str, path: str, status: int) -> None:
    if path.startswith("/static"):
        return
    with _lock:
        _buffer.append(
            {
                "occurred_at": datetime.utcnow(),
                "method": (method or "GET")[:12],
                "path": (path or "/")[:500],
                "status": int(status or 0),
            }
        )


def flush(db: Session | None = None) -> int:
    from app.db import SessionLocal

    with _lock:
        batch = list(_buffer)
        _buffer.clear()
    if not batch:
        return 0
    own = db is None
    session = db or SessionLocal()
    try:
        session.add_all(
            [
                AccessEvent(
                    occurred_at=item["occurred_at"],
                    method=item["method"],
                    path=item["path"],
                    status=item["status"],
                )
                for item in batch
            ]
        )
        session.commit()
        return len(batch)
    except Exception:
        session.rollback()
        with _lock:
            _buffer[:0] = batch
        log.exception("Failed to flush access events")
        return 0
    finally:
        if own:
            session.close()


async def _loop() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            flush()
        except Exception:
            log.exception("Access log flush loop failed")


def start_flusher() -> None:
    global _task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _task is None or _task.done():
        _task = loop.create_task(_loop())


def stop_flusher() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        _task = None
    flush()
