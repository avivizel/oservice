from __future__ import annotations

import re
from typing import Any

from app.catalogs import DISTRICT_NAME_TO_KEY, city_coords

_PREFIXES = re.compile(r"^(ע\"ר|עמותת|מרכז|אשפוזית|בית|קהילת)\s+", re.I)
_NOISE = re.compile(r"[\"'`״׳()\[\].,]|בע\"מ|ע\"ר|חל\"צ")


def digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def normalize_name(name: str) -> str:
    text = _NOISE.sub(" ", name or "")
    text = _PREFIXES.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def infer_org_type(ownership: str) -> str:
    value = ownership or ""
    if any(token in value for token in ("ממשלתי", "עירי", "קופה", "רשות מקומית")):
        return "public"
    if "ציבורי" in value and "מלכ" not in value:
        return "public"
    if any(token in value for token in ("פיקוח", "רישיון", "משרד", "מלכ", "עמותה")):
        return "supervised"
    if "פרטי" in value:
        return "supervised"
    return "supervised"


def infer_district(city: str, district_name: str = "") -> str:
    label = (district_name or "").strip()
    if label:
        key = DISTRICT_NAME_TO_KEY.get(label)
        if key:
            return key
        if "ירושלים" in label:
            return "jerusalem"
        if "דרום" in label:
            return "south"
        if "חיפה" in label or "צפון" in label:
            return "north"
        if "תל אביב" in label:
            return "tel_aviv"
        if "מרכז" in label:
            return "center"
    coords = city_coords(city)
    if not coords:
        return ""
    lat, lng = coords
    if city in {"ירושלים", "בית שמש", "מעלה אדומים"}:
        return "jerusalem"
    if "תל אביב" in (city or ""):
        return "tel_aviv"
    if lat >= 32.7:
        return "north"
    if lat >= 32.3:
        return "haifa" if lng < 35.2 else "north"
    if lat <= 31.5:
        return "south"
    return "center"


def guess_addiction_types(text: str, fallback: list[str] | None = None) -> list[str]:
    blob = text or ""
    found: list[str] = []
    mapping = [
        ("סם", "drugs"),
        ("סמים", "drugs"),
        ("אופיא", "opioids"),
        ("מתדון", "opioids"),
        ("תרופות מרשם", "opioids"),
        ("אלכוהול", "alcohol"),
        ("הימורים", "gambling"),
        ("גיימינג", "gaming"),
        ("מסכים", "screens"),
        ("פורנו", "sex"),
        ("קניות", "shopping"),
        ("רשתות", "social_media"),
        ("טבק", "tobacco"),
        ("עישון", "tobacco"),
        ("אכילה", "eating"),
        ("תחלואה כפולה", "dual_diagnosis"),
        ("תחלואה משולשת", "dual_diagnosis"),
        ("נפש", "mental_health"),
        ("פסיכיאטר", "mental_health"),
    ]
    for needle, key in mapping:
        if needle in blob and key not in found:
            found.append(key)
    if fallback:
        for key in fallback:
            if key not in found:
                found.append(key)
    return found or (fallback or [])


def guess_kind(text: str, fallback: str = "other") -> str:
    blob = text or ""
    rules = [
        ("קו חירום", "hotline"),
        ("מוקד", "hotline"),
        ("אשפוזית", "inpatient_detox"),
        ("גמילה", "inpatient_detox"),
        ("מתדון", "substitution"),
        ("תרופתי ממושך", "substitution"),
        ("טיפול יום", "day_center"),
        ("בית מאזן", "balanced_home"),
        ("פסיכיאטר", "psychiatry"),
        ("חוסן", "resilience"),
        ("הוסטל", "hostel"),
        ("קהילה טיפולית", "hostel"),
        ("12", "twelve_step"),
        ("אנונימיים", "twelve_step"),
        ("קופת", "hmo"),
        ("רווחה", "welfare_unit"),
        ("שב", "prison"),
        ("אסיר", "prison"),
    ]
    for needle, kind in rules:
        if needle in blob:
            return kind
    return fallback


def payload_from_mapping(data: dict[str, Any]) -> dict[str, Any]:
    city = data.get("city") or ""
    coords = city_coords(city)
    kinds_text = " ".join(str(v) for v in data.values() if v)
    return {
        "external_id": data.get("external_id") or "",
        "name": (data.get("name") or "").strip(),
        "org_type": data.get("org_type") or infer_org_type(data.get("ownership") or ""),
        "kind": data.get("kind") or guess_kind(kinds_text),
        "address": data.get("address") or "",
        "city": city,
        "district": data.get("district") or infer_district(city, data.get("district_name") or ""),
        "lat": data.get("lat") or (coords[0] if coords else None),
        "lng": data.get("lng") or (coords[1] if coords else None),
        "phone": data.get("phone") or "",
        "phone2": data.get("phone2") or "",
        "email": data.get("email") or "",
        "website": data.get("website") or "",
        "hours": data.get("hours") or "",
        "cost_type": data.get("cost_type") or "",
        "cost_info": data.get("cost_info") or "",
        "eligibility": data.get("eligibility") or "",
        "waitlist_info": data.get("waitlist_info") or "",
        "languages": data.get("languages") or ["עברית"],
        "referral_process": data.get("referral_process") or "",
        "target_audience": data.get("target_audience") or data.get("comments") or "",
        "licensing": data.get("licensing") or "",
        "addiction_types": data.get("addiction_types")
        or guess_addiction_types(kinds_text, data.get("fallback_types")),
        "age_group": data.get("age_group") or "all",
        "gender": data.get("gender") or "all",
        "sector": data.get("sector") or "general",
        "manager": data.get("manager") or "",
        "notes": data.get("notes") or "",
        "source_name": data.get("source_name") or "",
        "source_url": data.get("source_url") or "",
        "authority": data.get("authority") or "ngo",
        "confidence": data.get("confidence") or "medium",
        "parent_org": data.get("parent_org") or "",
        "operator_type": data.get("operator_type") or "",
        "operator_name": data.get("operator_name") or data.get("parent_org") or "",
        "supervision_text": data.get("supervision_text") or "",
        "service_types": data.get("service_types") or [],
        "population": data.get("population") or [],
        "_auto_import": bool(data.get("_auto_import")),
    }
