from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agent.match import best_match, classify, field_diffs
from app.agent.sources import harvest_all
from app.models import AgentCandidate, ScanRun, Service, ServiceSource

OFFICIAL = {"moh", "molsa", "gov", "municipality", "btl"}


def _log(lines: list[str], message: str) -> None:
    lines.append(f"{datetime.now().strftime('%H:%M:%S')}  {message}")


def run_scan(db: Session) -> ScanRun:
    scan = ScanRun(status="running", log_text="")
    db.add(scan)
    db.commit()
    db.refresh(scan)
    lines: list[str] = []
    stats = {"fetched": 0, "new": 0, "update": 0, "duplicate": 0, "conflict": 0, "errors": 0, "skipped": 0, "imported": 0}
    try:
        _log(lines, "מתחיל סריקה מול מאגרים רשמיים ואתרי רשויות מקומיות")
        all_rows, harvest_log = harvest_all()
        for item in harvest_log:
            _log(lines, item)
        stats["fetched"] = len(all_rows)
        _log(lines, f"סה״כ נרשמו לחילוץ {len(all_rows)} רשומות. מתחיל הצלבה וייבוא.")

        for payload in all_rows:
            name = (payload.get("name") or "").strip()
            if not name:
                stats["skipped"] += 1
                continue
            weak_html = (
                payload.get("confidence") == "low"
                and not payload.get("phone")
                and not payload.get("address")
                and not payload.get("external_id")
            )
            if weak_html:
                stats["skipped"] += 1
                continue
            if payload.get("_auto_import"):
                imported = upsert_official(db, payload)
                stats["imported"] = stats.get("imported", 0) + (1 if imported else 0)
                continue
            match, score = best_match(db, payload)
            diffs = field_diffs(payload, match) if match else []
            action = classify(match, score, diffs)
            if action == "duplicate" and match and match.status == "approved" and not diffs:
                stats["duplicate"] += 1
                stats["skipped"] += 1
                continue
            if match and payload.get("authority") in OFFICIAL and match.authority not in OFFICIAL:
                for diff in diffs:
                    diff["winner"] = "incoming"
                if action == "duplicate":
                    action = "update"
            elif match and payload.get("authority") not in OFFICIAL and match.authority in OFFICIAL:
                for diff in diffs:
                    diff["winner"] = "existing"

            existing_pending = (
                db.query(AgentCandidate)
                .filter(
                    AgentCandidate.status == "pending",
                    AgentCandidate.name == payload["name"],
                    AgentCandidate.source_url == (payload.get("source_url") or ""),
                )
                .first()
            )
            if existing_pending:
                stats["skipped"] += 1
                continue

            notes = f"התאמה {score}%" if match else "לא נמצאה רשומה קיימת"
            if match:
                notes += f" → {match.name}"
            candidate = AgentCandidate(
                scan_id=scan.id,
                action=action,
                status="pending",
                matched_service_id=match.id if match else None,
                name=payload["name"],
                payload_json=json.dumps(payload, ensure_ascii=False),
                diff_json=json.dumps(diffs, ensure_ascii=False),
                source_name=payload.get("source_name") or "",
                source_url=payload.get("source_url") or "",
                authority=payload.get("authority") or "ngo",
                confidence=payload.get("confidence") or "medium",
                notes=notes,
            )
            db.add(candidate)
            stats[action] = stats.get(action, 0) + 1
        db.commit()
        _log(lines, f"יובאו אוטומטית {stats.get('imported', 0)} רשומות רשמיות. השאר ממתינות לאישור עו״ס.")
        scan.status = "done"
    except Exception as exc:
        stats["errors"] += 1
        _log(lines, f"הסריקה נכשלה: {exc}")
        scan.status = "error"
        db.rollback()
        db.add(scan)
    scan.finished_at = datetime.utcnow()
    scan.stats_json = json.dumps(stats, ensure_ascii=False)
    scan.log_text = "\n".join(lines)
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def payload_to_service_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    langs = payload.get("languages") or []
    types = payload.get("addiction_types") or []
    return {
        "external_id": payload.get("external_id") or "",
        "name": payload.get("name") or "",
        "org_type": payload.get("org_type") or "private",
        "kind": payload.get("kind") or "other",
        "address": payload.get("address") or "",
        "city": payload.get("city") or "",
        "district": payload.get("district") or "",
        "lat": _float_or_none(payload.get("lat")),
        "lng": _float_or_none(payload.get("lng")),
        "phone": payload.get("phone") or "",
        "phone2": payload.get("phone2") or "",
        "email": payload.get("email") or "",
        "website": payload.get("website") or "",
        "hours": payload.get("hours") or "",
        "cost_type": payload.get("cost_type") or "",
        "cost_info": payload.get("cost_info") or "",
        "eligibility": payload.get("eligibility") or "",
        "waitlist_info": payload.get("waitlist_info") or "",
        "languages": json.dumps(langs, ensure_ascii=False) if isinstance(langs, list) else str(langs),
        "referral_process": payload.get("referral_process") or "",
        "target_audience": payload.get("target_audience") or "",
        "licensing": payload.get("licensing") or "",
        "addiction_types": json.dumps(types, ensure_ascii=False) if isinstance(types, list) else str(types),
        "age_group": payload.get("age_group") or "all",
        "gender": payload.get("gender") or "all",
        "sector": payload.get("sector") or "general",
        "manager": payload.get("manager") or "",
        "notes": payload.get("notes") or "",
        "source_name": payload.get("source_name") or "",
        "source_url": payload.get("source_url") or "",
        "authority": payload.get("authority") or "ngo",
        "confidence": payload.get("confidence") or "medium",
        "operator_type": payload.get("operator_type") or "",
        "operator_name": payload.get("operator_name") or payload.get("parent_org") or "",
        "supervision_text": payload.get("supervision_text") or "",
        "service_types": json.dumps(payload.get("service_types") or [], ensure_ascii=False)
        if isinstance(payload.get("service_types"), list)
        else (payload.get("service_types") or "[]"),
        "population": json.dumps(payload.get("population") or [], ensure_ascii=False)
        if isinstance(payload.get("population"), list)
        else (payload.get("population") or "[]"),
        "status": "approved",
        "last_updated": datetime.utcnow(),
        "last_verified": datetime.utcnow(),
    }


def apply_update(service: Service, payload: dict[str, Any], diffs: list[dict[str, str]]) -> None:
    incoming = payload_to_service_kwargs(payload)
    incoming.pop("status", None)
    official_in = payload.get("authority") in OFFICIAL
    existing_official = service.authority in OFFICIAL
    for field, value in incoming.items():
        if field in {"last_updated", "last_verified"}:
            setattr(service, field, value)
            continue
        current = getattr(service, field, None)
        if value in (None, "", "[]") and current:
            continue
        if not current:
            setattr(service, field, value)
            continue
        if official_in and not existing_official:
            setattr(service, field, value)
        elif official_in and existing_official and str(value) != str(current):
            setattr(service, field, value)
        elif not official_in and existing_official:
            continue
        else:
            setattr(service, field, value)
    if official_in:
        service.authority = payload.get("authority") or service.authority
        service.confidence = "high"
    service.last_updated = datetime.utcnow()
    service.last_verified = datetime.utcnow()


def upsert_official(db: Session, payload: dict[str, Any]) -> bool:
    kwargs = payload_to_service_kwargs(payload)
    ext = kwargs.get("external_id") or ""
    service = db.query(Service).filter(Service.external_id == ext).first() if ext else None
    if service is None:
        match, score = best_match(db, payload)
        if match and score >= 92:
            service = match
    if service is None:
        service = Service(**kwargs)
        db.add(service)
        db.flush()
        db.add(
            ServiceSource(
                service_id=service.id,
                name=payload.get("source_name") or "סריקה רשמית",
                url=payload.get("source_url") or "",
                authority=payload.get("authority") or "gov",
                excerpt=(payload.get("supervision_text") or payload.get("notes") or "")[:500],
            )
        )
        return True
    apply_update(service, payload, field_diffs(payload, service))
    return False
