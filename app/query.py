from __future__ import annotations

import json
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.localities import city_filter_values, official_city_names
from app.models import Favorite, Service


def as_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in value.split(",") if part.strip()]


def apply_filters(query, params: dict[str, Any]):
    q = (params.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Service.name.ilike(like),
                Service.city.ilike(like),
                Service.address.ilike(like),
                Service.phone.ilike(like),
                Service.notes.ilike(like),
                Service.target_audience.ilike(like),
                Service.eligibility.ilike(like),
                Service.operator_name.ilike(like),
                Service.supervision_text.ilike(like),
            )
        )
    for field in ("org_type", "kind", "district", "city", "cost_type", "age_group", "gender", "sector", "confidence", "rating"):
        value = (params.get(field) or "").strip()
        if value:
            if field == "city":
                query = query.filter(Service.city.in_(city_filter_values(query.session, value)))
            else:
                query = query.filter(getattr(Service, field) == value)
    addiction = (params.get("addiction") or "").strip()
    if addiction:
        query = query.filter(Service.addiction_types.like(f"%{addiction}%"))
    treatment = (params.get("service_type") or "").strip()
    if treatment:
        query = query.filter(Service.service_types.like(f"%{treatment}%"))
    if params.get("favorites") in {"1", "true", "on"}:
        query = query.join(Favorite, Favorite.service_id == Service.id)
    query = query.filter(Service.status == (params.get("status") or "approved"))
    if not (params.get("org_type") or "").strip() and params.get("include_unsupervised") not in {"1", "true", "on"}:
        query = query.filter(
            or_(Service.org_type != "private", Service.kind.in_(["hotline", "twelve_step"]))
        )
    sort = params.get("sort") or "name"
    mapping = {
        "name": Service.name.asc(),
        "city": Service.city.asc(),
        "updated": Service.last_updated.desc(),
        "confidence": Service.confidence.desc(),
        "rating": Service.rating.desc(),
        "kind": Service.kind.asc(),
    }
    if sort == "rating":
        query = query.order_by(Service.rating.desc(), Service.name.asc())
    else:
        query = query.order_by(mapping.get(sort, Service.name.asc()))
    return query


def unique_cities(db: Session) -> list[str]:
    return official_city_names(db)
