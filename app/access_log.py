from __future__ import annotations

import asyncio
import ipaddress
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AccessEvent

log = logging.getLogger("maaneim.access")

SESSION_GAP = timedelta(minutes=30)
ISRAEL = timezone(timedelta(hours=3))
_SKIP_PREFIXES = ("/static", "/admin", "/agent")
_SKIP_PATHS = {"/favicon.ico", "/robots.txt", "/openapi.json", "/docs", "/redoc"}
_SKIP_UA = ("render", "health-check", "kube-probe", "googlehc", "uptime", "pingdom", "uptimerobot")

_buffer: list[dict[str, Any]] = []
_lock = threading.Lock()
_task: asyncio.Task | None = None


def client_ip(request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:80]
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real[:80]
    host = request.client.host if request.client else ""
    return (host or "")[:80]


def _is_private(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


def should_record(request) -> bool:
    path = request.url.path or "/"
    if path.startswith(_SKIP_PREFIXES) or path in _SKIP_PATHS:
        return False
    method = (request.method or "GET").upper()
    if method not in {"GET", "POST"}:
        return False
    ua = (request.headers.get("user-agent") or "").lower()
    if any(token in ua for token in _SKIP_UA):
        return False
    ip = client_ip(request)
    if not ip or _is_private(ip):
        return False
    return True


def record(request, status: int) -> None:
    if not should_record(request):
        return
    with _lock:
        _buffer.append(
            {
                "occurred_at": datetime.utcnow(),
                "method": (request.method or "GET")[:12],
                "path": (request.url.path or "/")[:500],
                "status": int(status or 0),
                "ip": client_ip(request),
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
                    ip=item.get("ip") or "",
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


def israel_day(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ISRAEL).strftime("%Y-%m-%d")


def sessionize(events: list[tuple[datetime, str]]) -> list[tuple[datetime, str]]:
    """Return (session_start, ip) for each visit. Same IP within 30 minutes is one visit."""
    by_ip: dict[str, list[datetime]] = defaultdict(list)
    for occurred_at, ip in events:
        ip = (ip or "").strip()
        if not ip or not occurred_at:
            continue
        by_ip[ip].append(occurred_at)
    visits: list[tuple[datetime, str]] = []
    for ip, times in by_ip.items():
        times.sort()
        previous = None
        for moment in times:
            if previous is None or (moment - previous) >= SESSION_GAP:
                visits.append((moment, ip))
            previous = moment
    visits.sort(key=lambda item: item[0])
    return visits


def usage_report(events: list[tuple[datetime, str]], *, today: str | None = None) -> dict[str, Any]:
    visits = sessionize(events)
    today = today or israel_day(datetime.utcnow())
    by_day: dict[str, dict[str, Any]] = {}
    for started, ip in visits:
        day = israel_day(started)
        bucket = by_day.setdefault(day, {"visits": 0, "ips": set()})
        bucket["visits"] += 1
        bucket["ips"].add(ip)
    days = [
        {
            "day": day,
            "visits": data["visits"],
            "people": len(data["ips"]),
        }
        for day, data in sorted(by_day.items())
    ]
    max_visits = max((row["visits"] for row in days), default=1) or 1
    for row in days:
        row["pct"] = round(100 * row["visits"] / max_visits)
    today_row = by_day.get(today, {"visits": 0, "ips": set()})
    return {
        "today": today,
        "today_visits": int(today_row["visits"]),
        "today_people": len(today_row["ips"]),
        "total_visits": len(visits),
        "total_people": len({ip for _, ip in visits}),
        "days": days,
    }


def usage_from_db(db: Session, *, days: int = 30) -> dict[str, Any]:
    flush(db)
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(AccessEvent.occurred_at, AccessEvent.ip)
        .filter(AccessEvent.occurred_at >= since)
        .filter(AccessEvent.ip != "")
        .filter(AccessEvent.ip.isnot(None))
        .all()
    )
    return usage_report([(occurred_at, ip or "") for occurred_at, ip in rows])


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
