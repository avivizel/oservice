from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import DateTime, Float, Integer, Boolean, Text, inspect as sa_inspect, func
from sqlalchemy.orm import Session, selectinload

from app.admin_auth import (
    clear_failures,
    hash_password,
    is_locked,
    record_failure,
    verify_password,
)
from app.db import get_db
from app.models import AccessEvent, AdminUser, Base
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
    nxt = str(form.get("next") or request.query_params.get("next") or "/admin")
    if not nxt.startswith("/admin"):
        nxt = "/admin"
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
