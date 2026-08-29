from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.catalogs import (
    ADDICTION_TYPES,
    AGE_GROUPS,
    CONFIDENCE,
    COST_TYPES,
    DISTRICTS,
    GENDERS,
    ORG_TYPES,
    RATINGS,
    SECTORS,
    SERVICE_KINDS,
)
from app.agent.import_url import ImportUrlError, import_org_from_url, save_imported_org
from app.db import get_db
from app.models import Favorite, Rating, Service, ServiceSource
from app.query import apply_filters, as_list, unique_cities
from app.templates_env import templates

router = APIRouter()


def _ctx(request: Request, db: Session, extra: dict | None = None) -> dict:
    pending = 0
    from app.models import AgentCandidate

    pending = db.query(AgentCandidate).filter(AgentCandidate.status == "pending").count()
    data = {
        "request": request,
        "org_types": ORG_TYPES,
        "addiction_types": ADDICTION_TYPES,
        "kinds": SERVICE_KINDS,
        "districts": DISTRICTS,
        "ratings": RATINGS,
        "confidence": CONFIDENCE,
        "cost_types": COST_TYPES,
        "age_groups": AGE_GROUPS,
        "genders": GENDERS,
        "sectors": SECTORS,
        "pending_count": pending,
        "as_list": as_list,
        "cities": unique_cities(db),
    }
    if extra:
        data.update(extra)
    return data


@router.get("/services/new", response_class=HTMLResponse)
def new_service_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "edit.html",
        _ctx(
            request,
            db,
            {
                "service": None,
                "title": "הוספת שירות ידנית",
                "import_error": "",
                "import_url": "",
            },
        ),
    )


@router.post("/services/import-url")
async def import_service_from_url(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    raw_url = str(form.get("source_url") or "").strip()
    try:
        payload = import_org_from_url(raw_url)
        service, _created = save_imported_org(db, payload)
    except ImportUrlError as exc:
        return templates.TemplateResponse(
            request,
            "edit.html",
            _ctx(
                request,
                db,
                {
                    "service": None,
                    "title": "הוספת שירות ידנית",
                    "import_error": str(exc),
                    "import_url": raw_url,
                },
            ),
            status_code=400,
        )
    return RedirectResponse(f"/services/{service.id}", status_code=303)


@router.get("/", response_class=HTMLResponse)
def search(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    query = apply_filters(db.query(Service), params)
    services = query.all()
    fav_ids = {row.service_id for row in db.query(Favorite).all()}
    return templates.TemplateResponse(
        request,
        "index.html",
        _ctx(
            request,
            db,
            {
                "services": services,
                "fav_ids": fav_ids,
                "params": params,
                "partial": request.headers.get("HX-Request") == "true",
            },
        ),
    )


@router.get("/favorites", response_class=HTMLResponse)
def favorites(request: Request, db: Session = Depends(get_db)):
    favs = db.query(Favorite).all()
    ids = [f.service_id for f in favs]
    services = db.query(Service).filter(Service.id.in_(ids)).all() if ids else []
    return templates.TemplateResponse(
        request,
        "index.html",
        _ctx(
            request,
            db,
            {
                "services": services,
                "fav_ids": set(ids),
                "params": {"favorites": "1"},
                "partial": False,
            },
        ),
    )


@router.get("/services/{service_id}", response_class=HTMLResponse)
def service_card(request: Request, service_id: int, db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if not service:
        return RedirectResponse("/", status_code=302)
    is_fav = db.query(Favorite).filter(Favorite.service_id == service_id).first() is not None
    return templates.TemplateResponse(
        request,
        "service.html",
        _ctx(request, db, {"service": service, "is_fav": is_fav, "sources": service.sources, "conflicts": service.conflicts}),
    )


@router.get("/services/{service_id}/edit", response_class=HTMLResponse)
def edit_service_form(request: Request, service_id: int, db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if not service:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request,
        "edit.html",
        _ctx(request, db, {"service": service, "title": "עריכת שירות"}),
    )


def _form_to_service(form: dict, service: Service | None) -> Service:
    import json
    from datetime import datetime

    types = form.getlist("addiction_types") if hasattr(form, "getlist") else []
    langs = [p.strip() for p in (form.get("languages") or "").split(",") if p.strip()]
    target = service or Service()
    mapping = {
        "name": form.get("name") or "",
        "org_type": form.get("org_type") or "private",
        "kind": form.get("kind") or "other",
        "address": form.get("address") or "",
        "city": form.get("city") or "",
        "district": form.get("district") or "",
        "phone": form.get("phone") or "",
        "phone2": form.get("phone2") or "",
        "email": form.get("email") or "",
        "website": form.get("website") or "",
        "hours": form.get("hours") or "",
        "cost_type": form.get("cost_type") or "",
        "cost_info": form.get("cost_info") or "",
        "eligibility": form.get("eligibility") or "",
        "waitlist_info": form.get("waitlist_info") or "",
        "referral_process": form.get("referral_process") or "",
        "target_audience": form.get("target_audience") or "",
        "licensing": form.get("licensing") or "",
        "age_group": form.get("age_group") or "all",
        "gender": form.get("gender") or "all",
        "sector": form.get("sector") or "general",
        "manager": form.get("manager") or "",
        "notes": form.get("notes") or "",
        "source_name": form.get("source_name") or "הזנה ידנית",
        "source_url": form.get("source_url") or "",
        "authority": form.get("authority") or "seed",
        "confidence": form.get("confidence") or "medium",
    }
    for key, value in mapping.items():
        setattr(target, key, value)
    target.addiction_types = json.dumps(types, ensure_ascii=False)
    target.languages = json.dumps(langs, ensure_ascii=False)
    target.status = "approved"
    target.last_updated = datetime.utcnow()
    from app.catalogs import city_coords

    coords = city_coords(target.city)
    if coords:
        target.lat, target.lng = coords
    return target


@router.post("/services/save")
async def save_service(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    service_id = form.get("id")
    service = db.get(Service, int(service_id)) if service_id else None
    target = _form_to_service(form, service)
    if service is None:
        db.add(target)
        db.flush()
        db.add(ServiceSource(service_id=target.id, name=target.source_name, url=target.source_url, authority=target.authority, excerpt="הזנה ידנית של עו״ס"))
    db.commit()
    return RedirectResponse(f"/services/{target.id}", status_code=303)


@router.post("/services/{service_id}/rating")
def set_rating(service_id: int, score: str = Form(...), comment: str = Form(""), db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if service and score in RATINGS:
        service.rating = score
        service.rating_comment = comment
        db.add(Rating(service_id=service_id, score=score, comment=comment))
        db.commit()
    return RedirectResponse(f"/services/{service_id}", status_code=303)


@router.post("/services/{service_id}/favorite")
def toggle_favorite(service_id: int, db: Session = Depends(get_db)):
    existing = db.query(Favorite).filter(Favorite.service_id == service_id).first()
    if existing:
        db.delete(existing)
    else:
        db.add(Favorite(service_id=service_id))
    db.commit()
    return RedirectResponse(f"/services/{service_id}", status_code=303)
