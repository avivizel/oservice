from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.agent.normalize import digits, normalize_name
from app.models import Service

COMPARE_FIELDS = (
    "name",
    "phone",
    "phone2",
    "email",
    "address",
    "city",
    "hours",
    "eligibility",
    "cost_info",
    "referral_process",
    "website",
    "manager",
)


def _phone_score(a: str, b: str) -> int:
    da, db = digits(a), digits(b)
    if not da or not db:
        return 0
    if da == db or da.endswith(db) or db.endswith(da):
        return 100
    return fuzz.ratio(da[-7:], db[-7:]) if len(da) >= 7 and len(db) >= 7 else 0


def similarity(payload: dict[str, Any], service: Service) -> int:
    name_score = fuzz.token_set_ratio(normalize_name(payload.get("name") or ""), normalize_name(service.name))
    phone_score = max(
        _phone_score(payload.get("phone") or "", service.phone),
        _phone_score(payload.get("phone") or "", service.phone2),
        _phone_score(payload.get("phone2") or "", service.phone),
    )
    city_score = fuzz.ratio(payload.get("city") or "", service.city or "") if payload.get("city") and service.city else 0
    ext = payload.get("external_id") or ""
    if ext and service.external_id and ext == service.external_id:
        return 100
    return int(0.55 * name_score + 0.30 * phone_score + 0.15 * city_score)


def best_match(db: Session, payload: dict[str, Any]) -> tuple[Service | None, int]:
    ext = payload.get("external_id") or ""
    if ext:
        hit = db.query(Service).filter(Service.external_id == ext).first()
        if hit:
            return hit, 100
    best: Service | None = None
    score = 0
    city = payload.get("city") or ""
    q = db.query(Service)
    if city:
        rows = q.filter(Service.city == city).all() or q.all()
    else:
        rows = q.all()
    for service in rows:
        current = similarity(payload, service)
        if current > score:
            best, score = service, current
    return best, score


def field_diffs(payload: dict[str, Any], service: Service) -> list[dict[str, str]]:
    diffs = []
    for field in COMPARE_FIELDS:
        incoming = str(payload.get(field) or "").strip()
        existing = str(getattr(service, field) or "").strip()
        if incoming and existing and incoming != existing:
            diffs.append({"field": field, "incoming": incoming, "existing": existing})
        elif incoming and not existing:
            diffs.append({"field": field, "incoming": incoming, "existing": ""})
    return diffs


def classify(match: Service | None, score: int, diffs: list[dict[str, str]]) -> str:
    if match is None or score < 70:
        return "new"
    if score >= 92 and not diffs:
        return "duplicate"
    if score >= 82 and diffs:
        official_conflict = any(d["existing"] and d["incoming"] for d in diffs)
        return "conflict" if official_conflict else "update"
    if score >= 70:
        return "duplicate"
    return "new"
