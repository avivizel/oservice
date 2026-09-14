from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import DateTime, Float, Integer, Boolean, Text, inspect as sa_inspect, func
from sqlalchemy.orm import Session, selectinload

from app.admin_auth import (
    clear_failures,
    hash_password,
    is_locked,
    record_failure,
    verify_password,
)
from app.catalogs import (
    ADDICTION_TYPES,
    AGE_GROUPS,
    CONFIDENCE,
    COST_TYPES,
    DISTRICTS,
    GENDERS,
    OFFICIAL_AUTHORITIES,
    OPERATOR_TYPES,
    ORG_TYPES,
    RATINGS,
    SECTORS,
    SERVICE_KINDS,
    SERVICE_TYPES,
    STATUSES,
)
from app.db import get_db
from app.models import AccessEvent, AdminUser, Base, Service, ServiceSource
from app.query import as_list
from app.templates_env import templates

router = APIRouter(prefix="/admin")

TABLE_LABELS = {
    "services": "מענים",
    "organizations": "ארגונים",
    "localities": "יישובים",
    "service_sources": "מקורות",
    "field_conflicts": "סתירות",
    "ratings": "ציונים",
    "favorites": "מועדפים",
    "scan_runs": "סריקות",
    "municipality_sites": "אתרי רשויות",
    "agent_candidates": "מועמדי סוכן",
    "admin_users": "משתמשי ניהול",
    "admin_settings": "הגדרות ניהול",
    "access_events": "אירועי גישה",
}

PASSWORD_FIELDS = {"password_hash"}

SERVICE_SELECTS = {
    "org_type": ORG_TYPES,
    "kind": SERVICE_KINDS,
    "district": DISTRICTS,
    "cost_type": COST_TYPES,
    "age_group": AGE_GROUPS,
    "gender": GENDERS,
    "sector": SECTORS,
    "authority": OFFICIAL_AUTHORITIES,
    "confidence": CONFIDENCE,
    "status": STATUSES,
    "rating": RATINGS,
    "operator_type": OPERATOR_TYPES,
}

SERVICE_LISTS = {
    "addiction_types": ADDICTION_TYPES,
    "languages": None,
    "service_types": SERVICE_TYPES,
    "population": None,
}

SERVICE_GROUPS = [
    {
        "id": "identity",
        "title": "פרטים",
        "fields": [
            {"key": "id", "label": "מס׳", "kind": "readonly", "cls": "col-id"},
            {"key": "name", "label": "שם המענה", "kind": "text", "cls": "col-name", "required": True},
            {"key": "kind", "label": "סוג מסגרת", "kind": "select", "cls": "col-select"},
            {"key": "org_type", "label": "סוג גוף", "kind": "select", "cls": "col-select"},
            {"key": "city", "label": "יישוב", "kind": "text", "cls": "col-city"},
            {"key": "district", "label": "מחוז", "kind": "select", "cls": "col-select"},
            {"key": "licensing", "label": "רישוי", "kind": "text", "cls": "col-mid"},
            {"key": "supervision_text", "label": "פיקוח / הערה על המסגרת", "kind": "textarea", "cls": "col-wide"},
            {"key": "operator_type", "label": "מפעיל", "kind": "select", "cls": "col-select"},
            {"key": "operator_name", "label": "שם המפעיל", "kind": "text", "cls": "col-mid"},
            {"key": "status", "label": "סטטוס", "kind": "select", "cls": "col-select"},
        ],
    },
    {
        "id": "contact",
        "title": "פרטי קשר והפניה",
        "fields": [
            {"key": "address", "label": "כתובת", "kind": "text", "cls": "col-wide"},
            {"key": "phone", "label": "טלפון", "kind": "ltr", "cls": "col-phone"},
            {"key": "phone2", "label": "טלפון נוסף", "kind": "ltr", "cls": "col-phone"},
            {"key": "email", "label": "דוא״ל", "kind": "ltr", "cls": "col-mid"},
            {"key": "website", "label": "אתר", "kind": "ltr", "cls": "col-wide"},
            {"key": "hours", "label": "שעות", "kind": "text", "cls": "col-mid"},
            {"key": "referral_process", "label": "דרך הפניה", "kind": "textarea", "cls": "col-wide"},
            {"key": "manager", "label": "מנהל/ת", "kind": "text", "cls": "col-mid"},
        ],
    },
    {
        "id": "audience",
        "title": "זכאות, עלות וקהל יעד",
        "fields": [
            {"key": "cost_type", "label": "סוג עלות", "kind": "select", "cls": "col-select"},
            {"key": "cost_info", "label": "פירוט עלות", "kind": "textarea", "cls": "col-wide"},
            {"key": "eligibility", "label": "זכאות", "kind": "textarea", "cls": "col-wide"},
            {"key": "waitlist_info", "label": "רשימת המתנה", "kind": "textarea", "cls": "col-mid"},
            {"key": "target_audience", "label": "קהל יעד", "kind": "textarea", "cls": "col-wide"},
            {"key": "age_group", "label": "גיל", "kind": "select", "cls": "col-select"},
            {"key": "gender", "label": "מגדר", "kind": "select", "cls": "col-select"},
            {"key": "sector", "label": "מגזר", "kind": "select", "cls": "col-select"},
            {"key": "languages", "label": "שפות", "kind": "list", "cls": "col-mid"},
        ],
    },
    {
        "id": "types",
        "title": "סוגי מענה",
        "fields": [
            {"key": "addiction_types", "label": "סוגי מענה", "kind": "list", "cls": "col-wide"},
            {"key": "service_types", "label": "סוג טיפול", "kind": "list", "cls": "col-wide"},
            {"key": "population", "label": "אוכלוסיות", "kind": "list", "cls": "col-mid"},
            {"key": "notes", "label": "הערות", "kind": "textarea", "cls": "col-wide"},
        ],
    },
    {
        "id": "source",
        "title": "מקור, עדכון וודאות",
        "fields": [
            {"key": "source_name", "label": "מקור מוביל", "kind": "text", "cls": "col-mid"},
            {"key": "source_url", "label": "קישור למקור", "kind": "ltr", "cls": "col-wide"},
            {"key": "authority", "label": "סמכות", "kind": "select", "cls": "col-select"},
            {"key": "confidence", "label": "רמת ודאות", "kind": "select", "cls": "col-select"},
            {"key": "last_updated", "label": "עדכון אחרון", "kind": "readonly", "cls": "col-date"},
            {"key": "last_verified", "label": "אומת בתאריך", "kind": "datetime", "cls": "col-date"},
            {"key": "sources_text", "label": "מקורות נוספים", "kind": "readonly", "cls": "col-wide"},
        ],
    },
    {
        "id": "rating",
        "title": "ציון איכות של עו״ס",
        "fields": [
            {"key": "rating", "label": "ציון", "kind": "select", "cls": "col-select"},
            {"key": "rating_comment", "label": "הערת ציון", "kind": "textarea", "cls": "col-wide"},
        ],
    },
]


def _list_display(value: Any, catalog: dict[str, str] | None) -> str:
    items = as_list(value if isinstance(value, str) else ("" if value is None else str(value)))
    if not catalog:
        return ", ".join(items)
    return ", ".join(catalog.get(item, item) for item in items)


def _parse_list_field(raw: str, catalog: dict[str, str] | None) -> str:
    parts = [part.strip() for part in (raw or "").replace(";", ",").split(",") if part.strip()]
    if catalog:
        reverse = {label: key for key, label in catalog.items()}
        parsed = []
        for part in parts:
            if part in catalog:
                parsed.append(part)
            elif part in reverse:
                parsed.append(reverse[part])
            else:
                parsed.append(part)
        parts = parsed
    return json.dumps(parts, ensure_ascii=False)


def _fmt_dt(value: Any, with_time: bool = True) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M") if with_time else value.strftime("%d.%m.%Y")
    return str(value)


def _service_values(service: Service | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if service is None:
        for group in SERVICE_GROUPS:
            for field in group["fields"]:
                values[field["key"]] = ""
        values["status"] = "approved"
        values["age_group"] = "all"
        values["gender"] = "all"
        values["sector"] = "general"
        values["confidence"] = "medium"
        values["org_type"] = "private"
        values["kind"] = "other"
        values["authority"] = "seed"
        values["languages"] = "עברית"
        return values
    for group in SERVICE_GROUPS:
        for field in group["fields"]:
            key = field["key"]
            if key == "sources_text":
                values[key] = " · ".join(
                    f"{src.name}" + (f" ({src.fetched_at.strftime('%d.%m.%Y')})" if src.fetched_at else "")
                    for src in (service.sources or [])
                ) or "—"
                continue
            raw = getattr(service, key, None)
            if field["kind"] == "list":
                values[key] = _list_display(raw, SERVICE_LISTS.get(key))
            elif key == "last_updated":
                values[key] = _fmt_dt(raw)
            elif field["kind"] == "datetime":
                values[key] = _datetime_input(raw)
            elif raw is None:
                values[key] = ""
            else:
                values[key] = str(raw)
    return values


def _service_row(service: Service | None, *, creating: bool = False, notice: str = "", error: str = "") -> dict[str, Any]:
    name = (service.name if service else "") or ""
    city = (service.city if service else "") or ""
    phone = (service.phone if service else "") or ""
    return {
        "id": None if service is None else service.id,
        "creating": creating,
        "field_values": _service_values(service),
        "search": " ".join([name, city, phone, (service.address if service else "") or ""]).lower(),
        "notice": notice,
        "error": error,
    }


def _apply_service_form(service: Service, form) -> None:
    from app.catalogs import city_coords

    text_keys = {
        "name",
        "address",
        "city",
        "phone",
        "phone2",
        "email",
        "website",
        "hours",
        "cost_info",
        "eligibility",
        "waitlist_info",
        "referral_process",
        "target_audience",
        "licensing",
        "manager",
        "notes",
        "source_name",
        "source_url",
        "operator_name",
        "supervision_text",
        "rating_comment",
    }
    for key in text_keys:
        if key in form:
            setattr(service, key, str(form.get(key) or "").strip())
    for key, options in SERVICE_SELECTS.items():
        if key not in form:
            continue
        raw = str(form.get(key) or "").strip()
        if key == "rating" and not raw:
            service.rating = ""
            continue
        if key in {"district", "cost_type", "operator_type"} and not raw:
            setattr(service, key, "")
            continue
        if raw in options or not raw:
            setattr(service, key, raw)
    for key, catalog in SERVICE_LISTS.items():
        if key in form:
            setattr(service, key, _parse_list_field(str(form.get(key) or ""), catalog))
    verified = str(form.get("last_verified") or "").strip()
    if "last_verified" in form:
        service.last_verified = _parse_value("datetime", verified, True) if verified else None
    service.last_updated = datetime.utcnow()
    coords = city_coords(service.city)
    if coords:
        service.lat, service.lng = coords
    if not service.source_name:
        service.source_name = "הזנה ידנית"
    if not service.authority:
        service.authority = "seed"


class AdminAuthRequired(Exception):
    def __init__(self, next_path: str = "/admin"):
        self.next_path = next_path


def _models_by_table() -> dict[str, type]:
    return {mapper.class_.__tablename__: mapper.class_ for mapper in Base.registry.mappers}


def _model(table: str) -> type | None:
    return _models_by_table().get(table)


def _eager_options(model: type):
    mapper = sa_inspect(model)
    return [selectinload(getattr(model, rel.key)) for rel in mapper.relationships]


def _admin_from_session(request: Request, db: Session) -> AdminUser | None:
    uid = request.session.get("admin_user_id")
    if not uid:
        return None
    try:
        return db.get(AdminUser, int(uid))
    except (TypeError, ValueError):
        return None


def require_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    admin = _admin_from_session(request, db)
    if admin is None:
        raise AdminAuthRequired(str(request.url.path))
    return admin


def _ctx(request: Request, extra: dict | None = None) -> dict:
    data = {
        "request": request,
        "tables": [
            {"name": name, "label": TABLE_LABELS.get(name, name)}
            for name in sorted(_models_by_table())
        ],
    }
    if extra:
        data.update(extra)
    return data


def _rel_label(obj: Any) -> str:
    for attr in ("name", "username", "title", "code", "key"):
        value = getattr(obj, attr, None)
        if value:
            return str(value)
    return f"#{getattr(obj, 'id', '?')}"


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _column_fields(model: type) -> list[dict[str, Any]]:
    mapper = sa_inspect(model)
    fields = []
    for col in mapper.columns:
        typ = col.type
        kind = "text"
        if col.primary_key:
            kind = "pk"
        elif col.key in PASSWORD_FIELDS:
            kind = "password"
        elif isinstance(typ, Boolean):
            kind = "bool"
        elif isinstance(typ, DateTime):
            kind = "datetime"
        elif isinstance(typ, Integer):
            kind = "int"
        elif isinstance(typ, Float):
            kind = "float"
        elif isinstance(typ, Text) or (getattr(typ, "length", None) or 0) >= 300:
            kind = "textarea"
        fields.append(
            {
                "key": col.key,
                "kind": kind,
                "nullable": bool(col.nullable),
                "primary_key": bool(col.primary_key),
                "fk": bool(col.foreign_keys),
            }
        )
    return fields


def _row_values(obj: Any, model: type) -> list[dict[str, Any]]:
    mapper = sa_inspect(model)
    rows = []
    for col in mapper.columns:
        value = getattr(obj, col.key)
        display = _stringify(value)
        if col.key in PASSWORD_FIELDS and display:
            display = "(hash)"
        extra = ""
        if col.foreign_keys:
            for fk in col.foreign_keys:
                parent = fk.column.table.name
                extra = f"FK → {parent}"
                rel = None
                for relationship in mapper.relationships:
                    if col.key in [c.name for c in (relationship.local_columns or [])]:
                        rel = getattr(obj, relationship.key)
                        break
                if rel is not None and not isinstance(rel, list):
                    extra = f"{extra}: {_rel_label(rel)}"
        rows.append({"key": col.key, "value": display, "extra": extra})
    for rel in mapper.relationships:
        related = getattr(obj, rel.key)
        if related is None:
            label = "—"
        elif isinstance(related, list):
            label = ", ".join(_rel_label(item) for item in related) or "—"
        else:
            label = _rel_label(related)
        rows.append({"key": rel.key, "value": label, "extra": "relationship"})
    return rows


def _parse_value(kind: str, raw: str, nullable: bool):
    text = (raw or "").strip()
    if kind == "bool":
        return raw in {"1", "on", "true", "True"}
    if not text:
        if nullable or kind in {"datetime", "int", "float"}:
            return None
        return ""
    if kind == "int":
        return int(text)
    if kind == "float":
        return float(text)
    if kind == "datetime":
        text = text.replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return datetime.fromisoformat(text)
    return raw


def _apply_form(obj: Any, model: type, form, *, creating: bool) -> None:
    fields = _column_fields(model)
    for field in fields:
        key = field["key"]
        if field["primary_key"]:
            continue
        if key in PASSWORD_FIELDS:
            secret = str(form.get("password") or form.get(key) or "")
            if secret:
                obj.password_hash = hash_password(secret)
            elif creating:
                raise ValueError("נדרשת סיסמה")
            continue
        raw = form.get(key)
        if field["kind"] == "bool":
            setattr(obj, key, raw in {"1", "on", "true", "True"})
            continue
        if raw is None:
            continue
        setattr(obj, key, _parse_value(field["kind"], str(raw), field["nullable"]))
    mapper = sa_inspect(model)
    keys = {c.key for c in mapper.columns}
    if "updated_at" in keys:
        obj.updated_at = datetime.utcnow()
    if creating and "last_updated" in keys and not getattr(obj, "last_updated", None):
        obj.last_updated = datetime.utcnow()


def _datetime_input(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    return str(value)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if _admin_from_session(request, db):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin/login.html",
        _ctx(request, {"error": "", "username": ""}),
    )


@router.post("/login")
async def login_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    username = str(form.get("username") or "").strip()
    password = str(form.get("password") or "")
    nxt = str(form.get("next") or request.query_params.get("next") or "/admin/services")
    if not nxt.startswith("/admin"):
        nxt = "/admin/services"
    if is_locked(username):
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            _ctx(request, {"error": "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות.", "username": username}),
            status_code=429,
        )
    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None or not verify_password(password, user.password_hash):
        record_failure(username)
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            _ctx(request, {"error": "שם משתמש או סיסמה שגויים.", "username": username}),
            status_code=401,
        )
    clear_failures(username)
    request.session["admin_user_id"] = user.id
    return RedirectResponse(nxt, status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    since = datetime.utcnow() - timedelta(days=30)
    day_rows = (
        db.query(func.date(AccessEvent.occurred_at), func.count())
        .filter(AccessEvent.occurred_at >= since)
        .group_by(func.date(AccessEvent.occurred_at))
        .order_by(func.date(AccessEvent.occurred_at))
        .all()
    )
    total = db.query(func.count(AccessEvent.id)).scalar() or 0
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_count = (
        db.query(func.count(AccessEvent.id)).filter(func.date(AccessEvent.occurred_at) == today).scalar() or 0
    )
    top_paths = (
        db.query(AccessEvent.path, func.count())
        .filter(AccessEvent.occurred_at >= since)
        .group_by(AccessEvent.path)
        .order_by(func.count().desc())
        .limit(20)
        .all()
    )
    max_day = max((int(c) for _, c in day_rows), default=1) or 1
    days = [
        {"day": str(day), "count": int(count), "pct": round(100 * int(count) / max_day)}
        for day, count in day_rows
    ]
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        _ctx(
            request,
            {
                "admin": admin,
                "total": total,
                "today_count": today_count,
                "days": days,
                "top_paths": [{"path": p, "count": int(c)} for p, c in top_paths],
            },
        ),
    )


@router.get("/account", response_class=HTMLResponse)
def account_form(request: Request, admin: AdminUser = Depends(require_admin)):
    return templates.TemplateResponse(
        request,
        "admin/account.html",
        _ctx(request, {"admin": admin, "error": "", "notice": ""}),
    )


@router.post("/account")
async def account_save(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    form = await request.form()
    current = str(form.get("current_password") or "")
    new_username = str(form.get("username") or "").strip()
    new_password = str(form.get("new_password") or "")
    confirm = str(form.get("confirm_password") or "")
    if not verify_password(current, admin.password_hash):
        return templates.TemplateResponse(
            request,
            "admin/account.html",
            _ctx(request, {"admin": admin, "error": "הסיסמה הנוכחית שגויה.", "notice": ""}),
            status_code=400,
        )
    if new_username:
        clash = db.query(AdminUser).filter(AdminUser.username == new_username, AdminUser.id != admin.id).first()
        if clash:
            return templates.TemplateResponse(
                request,
                "admin/account.html",
                _ctx(request, {"admin": admin, "error": "שם המשתמש כבר תפוס.", "notice": ""}),
                status_code=400,
            )
        admin.username = new_username
    if new_password:
        if new_password != confirm:
            return templates.TemplateResponse(
                request,
                "admin/account.html",
                _ctx(request, {"admin": admin, "error": "הסיסמאות החדשות אינן תואמות.", "notice": ""}),
                status_code=400,
            )
        admin.password_hash = hash_password(new_password)
    admin.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(admin)
    return templates.TemplateResponse(
        request,
        "admin/account.html",
        _ctx(request, {"admin": admin, "error": "", "notice": "הפרטים עודכנו."}),
    )


def _services_page(request: Request, admin: AdminUser, db: Session, extra: dict | None = None):
    rows = (
        db.query(Service)
        .options(selectinload(Service.sources))
        .order_by(Service.name, Service.city, Service.id)
        .all()
    )
    data = {
        "admin": admin,
        "groups": SERVICE_GROUPS,
        "selects": SERVICE_SELECTS,
        "new_row": _service_row(None, creating=True),
        "rows": [_service_row(service) for service in rows],
        "count": len(rows),
        "notice": "",
        "error": "",
    }
    if extra:
        data.update(extra)
    return templates.TemplateResponse(request, "admin/services.html", _ctx(request, data))


@router.get("/services", response_class=HTMLResponse)
def services_sheet(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    return _services_page(request, admin, db)


@router.post("/services/new")
async def services_create(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    form = await request.form()
    name = str(form.get("name") or "").strip()
    if not name:
        return _services_page(request, admin, db, {"error": "יש למלא שם למענה החדש."})
    service = Service()
    _apply_service_form(service, form)
    service.name = name
    service.status = service.status or "approved"
    db.add(service)
    db.flush()
    db.add(
        ServiceSource(
            service_id=service.id,
            name=service.source_name or "הזנה ידנית",
            url=service.source_url or "",
            authority=service.authority or "seed",
            excerpt="הזנה ידנית ממסך הניהול",
        )
    )
    db.commit()
    return RedirectResponse(f"/admin/services#row-{service.id}", status_code=303)


@router.post("/services/{row_id}")
async def services_update(
    request: Request, row_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)
):
    service = db.query(Service).options(selectinload(Service.sources)).filter(Service.id == row_id).first()
    if service is None:
        if request.headers.get("x-requested-with") == "fetch":
            return JSONResponse({"ok": False, "error": "המענה לא נמצא."}, status_code=404)
        return RedirectResponse("/admin/services", status_code=303)
    form = await request.form()
    name = str(form.get("name") or "").strip()
    if not name:
        if request.headers.get("x-requested-with") == "fetch":
            return JSONResponse({"ok": False, "error": "שם המענה הוא שדה חובה."}, status_code=400)
        return _services_page(request, admin, db, {"error": "שם המענה הוא שדה חובה."})
    _apply_service_form(service, form)
    service.name = name
    db.commit()
    db.refresh(service)
    if request.headers.get("x-requested-with") == "fetch":
        return JSONResponse({"ok": True, "notice": "נשמר", "last_updated": _fmt_dt(service.last_updated)})
    return RedirectResponse(f"/admin/services#row-{service.id}", status_code=303)


@router.post("/services/{row_id}/delete")
async def services_delete(
    request: Request, row_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)
):
    service = db.get(Service, row_id)
    if service is not None:
        db.delete(service)
        db.commit()
    if request.headers.get("x-requested-with") == "fetch":
        return JSONResponse({"ok": True})
    return RedirectResponse("/admin/services", status_code=303)


@router.get("/db", response_class=HTMLResponse)
def tables_index(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    counts = []
    for name, model in sorted(_models_by_table().items()):
        counts.append(
            {
                "name": name,
                "label": TABLE_LABELS.get(name, name),
                "count": db.query(model).count(),
            }
        )
    return templates.TemplateResponse(
        request,
        "admin/tables.html",
        _ctx(request, {"admin": admin, "counts": counts}),
    )


@router.get("/db/{table}", response_class=HTMLResponse)
def table_list(request: Request, table: str, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    model = _model(table)
    if model is None:
        return RedirectResponse("/admin/db", status_code=303)
    query = db.query(model)
    opts = _eager_options(model)
    if opts:
        query = query.options(*opts)
    rows = query.all()
    fields = [f for f in _column_fields(model) if f["kind"] != "password"]
    display_rows = []
    for obj in rows:
        cells = []
        for field in fields:
            value = getattr(obj, field["key"])
            cells.append(_stringify(value)[:120])
        display_rows.append({"id": getattr(obj, "id", None), "cells": cells})
    return templates.TemplateResponse(
        request,
        "admin/table_list.html",
        _ctx(
            request,
            {
                "admin": admin,
                "table": table,
                "label": TABLE_LABELS.get(table, table),
                "fields": fields,
                "rows": display_rows,
                "count": len(display_rows),
            },
        ),
    )


@router.get("/db/{table}/new", response_class=HTMLResponse)
def row_new(request: Request, table: str, admin: AdminUser = Depends(require_admin)):
    model = _model(table)
    if model is None:
        return RedirectResponse("/admin/db", status_code=303)
    fields = [f for f in _column_fields(model) if not f["primary_key"]]
    return templates.TemplateResponse(
        request,
        "admin/form.html",
        _ctx(
            request,
            {
                "admin": admin,
                "table": table,
                "label": TABLE_LABELS.get(table, table),
                "fields": fields,
                "values": {},
                "creating": True,
                "error": "",
            },
        ),
    )


@router.post("/db/{table}/new")
async def row_create(request: Request, table: str, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    model = _model(table)
    if model is None:
        return RedirectResponse("/admin/db", status_code=303)
    form = await request.form()
    obj = model()
    try:
        _apply_form(obj, model, form, creating=True)
        db.add(obj)
        db.commit()
    except Exception as exc:
        db.rollback()
        fields = [f for f in _column_fields(model) if not f["primary_key"]]
        return templates.TemplateResponse(
            request,
            "admin/form.html",
            _ctx(
                request,
                {
                    "admin": admin,
                    "table": table,
                    "label": TABLE_LABELS.get(table, table),
                    "fields": fields,
                    "values": {k: str(form.get(k) or "") for k in (f["key"] for f in fields)},
                    "creating": True,
                    "error": str(exc),
                },
            ),
            status_code=400,
        )
    pk = getattr(obj, "id", None)
    if pk is not None:
        return RedirectResponse(f"/admin/db/{table}/{pk}", status_code=303)
    return RedirectResponse(f"/admin/db/{table}", status_code=303)


@router.get("/db/{table}/{row_id}", response_class=HTMLResponse)
def row_view(request: Request, table: str, row_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    model = _model(table)
    if model is None:
        return RedirectResponse("/admin/db", status_code=303)
    query = db.query(model)
    opts = _eager_options(model)
    if opts:
        query = query.options(*opts)
    obj = query.filter(model.id == row_id).first()
    if obj is None:
        return RedirectResponse(f"/admin/db/{table}", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin/row.html",
        _ctx(
            request,
            {
                "admin": admin,
                "table": table,
                "label": TABLE_LABELS.get(table, table),
                "row_id": row_id,
                "pairs": _row_values(obj, model),
            },
        ),
    )


@router.get("/db/{table}/{row_id}/edit", response_class=HTMLResponse)
def row_edit(request: Request, table: str, row_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    model = _model(table)
    if model is None:
        return RedirectResponse("/admin/db", status_code=303)
    obj = db.get(model, row_id)
    if obj is None:
        return RedirectResponse(f"/admin/db/{table}", status_code=303)
    fields = [f for f in _column_fields(model) if not f["primary_key"]]
    values = {}
    for field in fields:
        value = getattr(obj, field["key"])
        if field["kind"] == "datetime":
            values[field["key"]] = _datetime_input(value)
        elif field["kind"] == "bool":
            values[field["key"]] = bool(value)
        elif field["kind"] == "password":
            values[field["key"]] = ""
        else:
            values[field["key"]] = "" if value is None else str(value)
    return templates.TemplateResponse(
        request,
        "admin/form.html",
        _ctx(
            request,
            {
                "admin": admin,
                "table": table,
                "label": TABLE_LABELS.get(table, table),
                "fields": fields,
                "values": values,
                "creating": False,
                "row_id": row_id,
                "error": "",
            },
        ),
    )


@router.post("/db/{table}/{row_id}/edit")
async def row_update(request: Request, table: str, row_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    model = _model(table)
    if model is None:
        return RedirectResponse("/admin/db", status_code=303)
    obj = db.get(model, row_id)
    if obj is None:
        return RedirectResponse(f"/admin/db/{table}", status_code=303)
    form = await request.form()
    try:
        _apply_form(obj, model, form, creating=False)
        db.commit()
    except Exception as exc:
        db.rollback()
        fields = [f for f in _column_fields(model) if not f["primary_key"]]
        return templates.TemplateResponse(
            request,
            "admin/form.html",
            _ctx(
                request,
                {
                    "admin": admin,
                    "table": table,
                    "label": TABLE_LABELS.get(table, table),
                    "fields": fields,
                    "values": {k: str(form.get(k) or "") for k in (f["key"] for f in fields)},
                    "creating": False,
                    "row_id": row_id,
                    "error": str(exc),
                },
            ),
            status_code=400,
        )
    return RedirectResponse(f"/admin/db/{table}/{row_id}", status_code=303)


@router.post("/db/{table}/{row_id}/delete")
def row_delete(request: Request, table: str, row_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(require_admin)):
    model = _model(table)
    if model is None:
        return RedirectResponse("/admin/db", status_code=303)
    if table == "admin_users" and db.query(AdminUser).count() <= 1:
        return RedirectResponse(f"/admin/db/{table}/{row_id}?err={quote('לא ניתן למחוק את המשתמש האחרון')}", status_code=303)
    obj = db.get(model, row_id)
    if obj is not None:
        if table == "admin_users" and getattr(obj, "id", None) == admin.id:
            request.session.clear()
        db.delete(obj)
        db.commit()
    return RedirectResponse(f"/admin/db/{table}", status_code=303)
