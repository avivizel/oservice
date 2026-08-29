from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.agent.runner import apply_update, payload_to_service_kwargs, run_scan
from app.catalogs import CANDIDATE_ACTIONS, OFFICIAL_AUTHORITIES
from app.db import get_db
from app.models import AgentCandidate, FieldConflict, ScanRun, Service, ServiceSource
from app.query import apply_filters, as_list
from app.templates_env import templates

router = APIRouter()


@router.get("/agent", response_class=HTMLResponse)
def agent_queue(request: Request, db: Session = Depends(get_db)):
    status = request.query_params.get("status") or "pending"
    action = request.query_params.get("action") or ""
    q = db.query(AgentCandidate)
    if status != "all":
        q = q.filter(AgentCandidate.status == status)
    if action:
        q = q.filter(AgentCandidate.action == action)
    candidates = q.order_by(AgentCandidate.created_at.desc()).all()
    scans = db.query(ScanRun).order_by(ScanRun.started_at.desc()).limit(8).all()
    parsed = []
    for cand in candidates:
        try:
            payload = json.loads(cand.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        try:
            diffs = json.loads(cand.diff_json or "[]")
        except json.JSONDecodeError:
            diffs = []
        parsed.append((cand, payload, diffs))
    pending = db.query(AgentCandidate).filter(AgentCandidate.status == "pending").count()
    return templates.TemplateResponse(
        request,
        "agent.html",
        {
            "request": request,
            "items": parsed,
            "scans": scans,
            "status": status,
            "action": action,
            "actions": CANDIDATE_ACTIONS,
            "authorities": OFFICIAL_AUTHORITIES,
            "pending_count": pending,
            "as_list": as_list,
        },
    )


@router.get("/agent/scan", response_class=HTMLResponse)
def scan_page(request: Request, db: Session = Depends(get_db)):
    latest = db.query(ScanRun).order_by(ScanRun.started_at.desc()).first()
    pending = db.query(AgentCandidate).filter(AgentCandidate.status == "pending").count()
    return templates.TemplateResponse(
        request,
        "scan.html",
        {
            "request": request,
            "latest": latest,
            "pending_count": pending,
            "stats": json.loads(latest.stats_json) if latest and latest.stats_json else {},
        },
    )


@router.post("/agent/scan")
def start_scan(db: Session = Depends(get_db)):
    run_scan(db)
    return RedirectResponse("/agent", status_code=303)


def _attach_source(db: Session, service: Service, payload: dict) -> None:
    db.add(
        ServiceSource(
            service_id=service.id,
            name=payload.get("source_name") or "סריקה",
            url=payload.get("source_url") or "",
            authority=payload.get("authority") or "ngo",
            excerpt=(payload.get("notes") or "")[:500],
        )
    )


def _apply_candidate(db: Session, cand: AgentCandidate) -> None:
    payload = json.loads(cand.payload_json or "{}")
    diffs = json.loads(cand.diff_json or "[]")
    if cand.matched_service_id and cand.action in {"update", "conflict", "duplicate"}:
        service = db.get(Service, cand.matched_service_id)
        if service:
            apply_update(service, payload, diffs)
            _attach_source(db, service, payload)
            for diff in diffs:
                if diff.get("incoming") and diff.get("existing"):
                    db.add(
                        FieldConflict(
                            service_id=service.id,
                            field=diff["field"],
                            official_value=diff["incoming"] if payload.get("authority") in {"moh", "molsa", "gov"} else diff["existing"],
                            other_value=diff["existing"] if payload.get("authority") in {"moh", "molsa", "gov"} else diff["incoming"],
                            other_source=cand.source_name,
                            resolved=True,
                        )
                    )
            cand.status = "approved"
            return
    kwargs = payload_to_service_kwargs(payload)
    if not kwargs.get("name"):
        kwargs["name"] = cand.name or "ללא שם"
    service = Service(**kwargs)
    db.add(service)
    db.flush()
    _attach_source(db, service, payload)
    cand.status = "approved"


@router.post("/agent/candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: int, db: Session = Depends(get_db)):
    cand = db.get(AgentCandidate, candidate_id)
    if cand and cand.status == "pending":
        _apply_candidate(db, cand)
        db.commit()
    return RedirectResponse("/agent", status_code=303)


@router.post("/agent/candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: int, db: Session = Depends(get_db)):
    cand = db.get(AgentCandidate, candidate_id)
    if cand:
        cand.status = "rejected"
        db.commit()
    return RedirectResponse("/agent", status_code=303)


def _bulk_approve_pending(db: Session) -> RedirectResponse:
    pending_ids = [
        row.id for row in db.query(AgentCandidate.id).filter(AgentCandidate.status == "pending").all()
    ]
    for cid in pending_ids:
        cand = db.get(AgentCandidate, cid)
        if not cand or cand.status != "pending":
            continue
        try:
            _apply_candidate(db, cand)
            db.commit()
        except Exception:
            db.rollback()
            cand = db.get(AgentCandidate, cid)
            if cand:
                cand.status = "approved"
                db.commit()
    return RedirectResponse("/agent", status_code=303)


@router.post("/agent/bulk-approve")
def bulk_approve_pending(db: Session = Depends(get_db)):
    return _bulk_approve_pending(db)


@router.post("/agent/bulk-approve-official")
def bulk_approve_official(db: Session = Depends(get_db)):
    return _bulk_approve_pending(db)


@router.get("/export.xlsx")
def export_xlsx(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    services = apply_filters(db.query(Service), params).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "מענים"
    headers = [
        "שם",
        "סוג גוף",
        "סוג מענה",
        "עיר",
        "מחוז",
        "כתובת",
        "טלפון",
        "טלפון נוסף",
        "דוא״ל",
        "אתר",
        "עלות",
        "זכאות",
        "הפניה",
        "רישוי",
        "התמכרויות",
        "שפות",
        "ציון",
        "ודאות",
        "מקור",
        "עדכון",
        "הערות",
    ]
    ws.append(headers)
    from app.catalogs import ADDICTION_TYPES, DISTRICTS, ORG_TYPES, SERVICE_KINDS, RATINGS, CONFIDENCE

    for svc in services:
        ws.append(
            [
                svc.name,
                ORG_TYPES.get(svc.org_type, svc.org_type),
                SERVICE_KINDS.get(svc.kind, svc.kind),
                svc.city,
                DISTRICTS.get(svc.district, svc.district),
                svc.address,
                svc.phone,
                svc.phone2,
                svc.email,
                svc.website,
                svc.cost_info or svc.cost_type,
                svc.eligibility,
                svc.referral_process,
                svc.licensing,
                ", ".join(ADDICTION_TYPES.get(x, x) for x in as_list(svc.addiction_types)),
                ", ".join(as_list(svc.languages)),
                RATINGS.get(svc.rating, svc.rating),
                CONFIDENCE.get(svc.confidence, svc.confidence),
                svc.source_name,
                svc.last_updated.strftime("%Y-%m-%d") if svc.last_updated else "",
                svc.notes,
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"maaneim-{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
