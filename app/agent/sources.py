from __future__ import annotations

from typing import Any

from app.agent.extract import html_to_candidates
from app.agent.fetch import fetch_json, fetch_text, format_il_phone, record_get
from app.agent.normalize import infer_district, infer_org_type, payload_from_mapping
from app.config import CKAN_BASE

CKAN_DATASETS = [
    {
        "package": "drugs-rehab",
        "title": "אשפוזיות לגמילה מסמים ומאלכוהול — משרד הבריאות",
        "authority": "moh",
        "kind": "inpatient_detox",
        "fallback_types": ["drugs", "alcohol"],
        "service_types": ["medical_detox", "inpatient"],
        "org_type": "supervised",
        "operator_type": "ministry_health",
        "licensing": "משרד הבריאות",
        "confidence": "high",
        "auto_import": True,
        "supervision_text": "מוסד המופיע במאגר אשפוזיות הגמילה של משרד הבריאות.",
        "cost_info": "מסגרות ציבוריות במימון משרד הבריאות (השתתפות עצמית לפי פרסום המשרד). פרטיות — מימון עצמי. יש לברר מול המסגרת.",
        "referral_process": "פנייה ישירה לאשפוזית, הפניית רווחה או מסגרת רפואית. חובה לוודא רישיון בתוקף.",
        "name_keys": ["institute_name", "title", "name", "hospital_name"],
    },
    {
        "package": "prescription-drug-addiction-treatment-clinics",
        "title": "מרפאות לטיפול בהתמכרות לתרופות מרשם — משרד הבריאות",
        "authority": "moh",
        "kind": "community",
        "fallback_types": ["opioids", "drugs"],
        "service_types": ["outpatient", "medication"],
        "org_type": "supervised",
        "operator_type": "ministry_health",
        "licensing": "משרד הבריאות",
        "confidence": "high",
        "auto_import": True,
        "supervision_text": "מרפאה המופיעה במאגר משרד הבריאות לטיפול בהתמכרות לתרופות מרשם.",
        "name_keys": ["institute_name", "title", "name"],
    },
    {
        "package": "ballancing-homes",
        "title": "בתים מאזנים — משרד הבריאות",
        "authority": "moh",
        "kind": "balanced_home",
        "fallback_types": ["mental_health", "dual_diagnosis"],
        "service_types": ["psychiatry", "inpatient"],
        "org_type": "supervised",
        "operator_type": "nonprofit",
        "licensing": "משרד הבריאות",
        "confidence": "high",
        "auto_import": True,
        "supervision_text": "בית מאזן בפיקוח משרד הבריאות, כחלופה לאשפוז פסיכיאטרי.",
        "cost_info": "לפי הסדר עם קופות החולים / משרד הביטחון, כמפורט במאגר.",
        "referral_process": "הפניה דרך קופת חולים / גורם מטפל.",
        "name_keys": ["title", "institute_name", "name"],
    },
    {
        "package": "hospitals_psyc",
        "title": "בתי חולים פסיכיאטריים — משרד הבריאות",
        "authority": "moh",
        "kind": "psychiatry",
        "fallback_types": ["mental_health", "dual_diagnosis"],
        "service_types": ["psychiatry", "inpatient"],
        "org_type": "public",
        "operator_type": "public_hospital",
        "licensing": "משרד הבריאות",
        "confidence": "high",
        "auto_import": True,
        "supervision_text": "שירות ציבורי: בית חולים / מחלקה פסיכיאטרית בפיקוח משרד הבריאות.",
        "name_keys": ["hospital_name", "institute_name", "name"],
    },
    {
        "package": "resilience-centers",
        "title": "מרכזי חוסן — משרד הבריאות",
        "authority": "moh",
        "kind": "resilience",
        "fallback_types": ["mental_health"],
        "service_types": ["outpatient", "individual_group"],
        "org_type": "public",
        "operator_type": "ministry_health",
        "licensing": "משרד הבריאות",
        "confidence": "high",
        "auto_import": True,
        "supervision_text": "מרכז חוסן ציבורי המופיע במאגר משרד הבריאות.",
        "name_keys": ["institute_name", "title", "name"],
    },
    {
        "package": "mental-health-institutions-emergency-health-unit",
        "title": "מסגרות דיור שיקומי בבריאות הנפש — משרד הבריאות",
        "authority": "moh",
        "kind": "hostel",
        "fallback_types": ["mental_health"],
        "service_types": ["community_rehab"],
        "org_type": "supervised",
        "operator_type": "nonprofit",
        "licensing": "משרד הבריאות",
        "confidence": "medium",
        "auto_import": True,
        "supervision_text": "מסגרת דיור שיקומי בבריאות הנפש המופיעה במאגר משרד הבריאות.",
        "name_keys": ["institute_name", "title", "name"],
    },
]

HTML_SOURCES = [
    {
        "url": "https://me.health.gov.il/mental-health/information-and-updates/addictions/rehab/",
        "name": "משרד הבריאות — גמילה מהתמכרויות",
        "authority": "moh",
        "fallback_types": ["drugs", "alcohol", "gambling", "sex"],
    },
    {
        "url": "https://me.health.gov.il/mental-health/therapy-rehabilitation/public-care/addiction-treatment/substitution-centers/",
        "name": "משרד הבריאות — מרכזי טיפול תרופתי ממושך",
        "authority": "moh",
        "fallback_types": ["opioids", "drugs"],
    },
    {
        "url": "https://www.eran.org.il/",
        "name": "ער״ן",
        "authority": "ngo",
        "fallback_types": ["mental_health"],
    },
    {
        "url": "https://www.milagambling.org.il/",
        "name": "מיל״ה — המרכז הישראלי לטיפול בהימורים",
        "authority": "molsa",
        "fallback_types": ["gambling", "gaming", "behavioral"],
    },
    {
        "url": "https://www.elem.org.il/",
        "name": "אלמ",
        "authority": "ngo",
        "fallback_types": ["drugs", "alcohol", "mental_health"],
    },
    {
        "url": "https://www.enosh.org.il/",
        "name": "אנוש",
        "authority": "ngo",
        "fallback_types": ["mental_health"],
    },
]

WELFARE_RESOURCE = "de069ddf-bcbc-4754-bda0-84873a353f7b"
WELFARE_KEYWORDS = ("התמכר", "סמים", "אלכוהול", "הימורים", "גמילה", "מכור")
MOLSA_EMPLOYMENT_URL = (
    "https://www.gov.il/he/Departments/DynamicCollectors/molsa-addictions-treatment-frames"
    "?skip=0&type=%D7%A9%D7%99%D7%9C%D7%95%D7%91%20%D7%91%D7%AA%D7%A2%D7%A1%D7%95%D7%A7%D7%94"
)
WELFARE_KIND = {
    "מרכז טיפולי": "community",
    "טיפול יום": "day_center",
    "קהילה טיפולית": "hostel",
    "הוסטל": "hostel",
    "שילוב בתעסוקה": "community",
    "קורת גג": "hostel",
    "פנימיה": "hostel",
}
WELFARE_SERVICE_TYPES = {
    "מרכז טיפולי": ["outpatient", "individual_group"],
    "טיפול יום": ["day_center"],
    "קהילה טיפולית": ["therapeutic_community"],
    "הוסטל": ["community_rehab"],
    "שילוב בתעסוקה": ["vocational_rehab"],
    "קורת גג": ["harm_reduction"],
    "פנימיה": ["inpatient", "youth"],
}


def _clean_org(value: str) -> str:
    text = (value or "").strip()
    if not text or text in {"0", "ללא ארגון", "0 ללא ארגון"} or text.startswith("0 "):
        return ""
    return text


def _frame_operator(row: dict[str, Any]) -> str:
    return _clean_org(record_get(row, "Organization")) or _clean_org(record_get(row, "Authoritys"))


def _employment_display_name(name: str, city: str) -> str:
    cleaned = name.strip()
    if cleaned.startswith("ש.תעסוקתי"):
        cleaned = "שילוב בתעסוקה — נפגעי התמכרויות"
    if city and city not in cleaned:
        return f"{cleaned} · {city}"
    return cleaned


def _ckan_package(package: str) -> dict[str, Any]:
    return fetch_json(f"{CKAN_BASE}/package_show", {"id": package})["result"]


def _datastore_all(resource_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        data = fetch_json(
            f"{CKAN_BASE}/datastore_search",
            {"resource_id": resource_id, "limit": 1000, "offset": offset},
        )["result"]
        batch = data.get("records") or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def _row_to_payload(spec: dict[str, Any], row: dict[str, Any], page_url: str) -> dict[str, Any] | None:
    name = ""
    for key in spec["name_keys"]:
        name = record_get(row, key)
        if name:
            break
    if not name:
        return None
    phone = format_il_phone(record_get(row, "phone", "טלפון", "Telephone")) or record_get(row, "phone")
    phone2 = format_il_phone(record_get(row, "phone2")) or record_get(row, "phone2")
    email = record_get(row, "email", "דואל", "mail")
    city = record_get(row, "city", "city_name", "City_Name")
    address = record_get(row, "address", "כתובת", "full_address", "Adrees")
    ownership = record_get(row, "ownershipDesc", "ownership", "operator", "Owner_Code_Descr", "Institute_type")
    code = record_get(row, "institute_code", "Code", "Misgeret_Id", "_id")
    kupa = record_get(row, "kupa")
    comments = record_get(row, "comments", "notes", "type_name", "age_description", "Institute_type")
    website = record_get(row, "website")
    org_type = spec["org_type"]
    if ownership:
        guessed = infer_org_type(ownership)
        if guessed:
            org_type = guessed
        if "פרטי" in ownership and "מלכ" not in ownership:
            org_type = "supervised"
        if any(token in ownership for token in ("ממשלתי", "ציבורי", "רשות")):
            org_type = "public"
    cost_info = spec.get("cost_info") or "עלות: יש לברר מול המסגרת"
    if kupa:
        cost_info = f"הסדר: {kupa}. {cost_info}"
    payload = payload_from_mapping(
        {
            "external_id": f"ckan:{spec['package']}:{code or name}",
            "name": name,
            "org_type": org_type,
            "kind": spec["kind"],
            "address": address,
            "city": city,
            "district_name": record_get(row, "district_name", "district", "Region_Descr"),
            "phone": phone,
            "phone2": phone2,
            "email": email,
            "website": website,
            "manager": record_get(row, "manager", "Maneger_Name", "Manager_first_name", "contact"),
            "notes": comments,
            "parent_org": record_get(row, "operator", "Organization") or ownership,
            "licensing": spec["licensing"],
            "fallback_types": spec["fallback_types"],
            "addiction_types": spec["fallback_types"],
            "cost_type": spec.get("cost_type") or "",
            "cost_info": cost_info,
            "referral_process": spec.get("referral_process") or "",
            "source_name": spec["title"],
            "source_url": page_url,
            "authority": spec["authority"],
            "confidence": spec["confidence"],
            "operator_type": spec.get("operator_type") or "",
            "operator_name": record_get(row, "operator", "Organization") or spec.get("operator_type") or "",
            "supervision_text": spec.get("supervision_text") or "",
            "service_types": spec.get("service_types") or [],
            "age_group": "adults" if "מבוגר" in comments else ("youth" if "נוער" in (name + comments) else "all"),
            "gender": "women" if "נשים" in comments and "גברים" not in comments else "all",
            "_auto_import": spec.get("auto_import", False),
        }
    )
    return payload


def harvest_ckan() -> tuple[list[dict[str, Any]], list[str]]:
    payloads: list[dict[str, Any]] = []
    logs: list[str] = []
    for spec in CKAN_DATASETS:
        try:
            pkg = _ckan_package(spec["package"])
            resources = [r for r in pkg.get("resources") or [] if r.get("datastore_active")]
            if not resources:
                logs.append(f"אין datastore פעיל עבור {spec['package']}")
                continue
            rows = _datastore_all(resources[0]["id"])
            page_url = f"https://data.gov.il/dataset/{spec['package']}"
            count = 0
            for row in rows:
                item = _row_to_payload(spec, row, page_url)
                if not item:
                    continue
                payloads.append(item)
                count += 1
            logs.append(f"{spec['title']}: {count} רשומות")
        except Exception as exc:
            logs.append(f"שגיאה ב-{spec['package']}: {exc}")
    return payloads, logs


def harvest_welfare() -> tuple[list[dict[str, Any]], list[str]]:
    logs: list[str] = []
    payloads: list[dict[str, Any]] = []
    try:
        rows = _datastore_all(WELFARE_RESOURCE)
        logs.append(f"מסגרות רווחה: נמשכו {len(rows)} רשומות גולמיות")
        for row in rows:
            head = (record_get(row, "Head_Department") or "").strip()
            blob = " ".join(
                record_get(row, k)
                for k in ("Name", "Type_Descr", "Head_Department", "Second_Classific", "Target_Population_Descr")
            )
            if "נפגעי התמכרויות" not in head and not any(k in blob for k in WELFARE_KEYWORDS):
                continue
            status = record_get(row, "Status_des")
            if status and "פעיל" not in status:
                continue
            name = record_get(row, "Name")
            if not name:
                continue
            type_descr = record_get(row, "Type_Descr")
            owner = record_get(row, "Owner_Code_Descr")
            city = record_get(row, "City_Name")
            region = record_get(row, "Region_Descr")
            gender_raw = record_get(row, "Gender_Descr")
            gender = "all"
            if "נקב" in gender_raw or "נשים" in gender_raw:
                gender = "women"
            elif "זכר" in gender_raw or "גבר" in gender_raw:
                gender = "men"
            from_age = record_get(row, "From_Age")
            age_group = "all"
            try:
                if from_age and float(from_age) >= 18:
                    age_group = "adults"
                elif from_age and float(from_age) < 18:
                    age_group = "youth"
            except ValueError:
                pass
            if "מתבגר" in blob or "נוער" in blob:
                age_group = "youth"
            org_type = "public" if any(t in owner for t in ("רשות", "ציבורי", "ממשלתי")) else "supervised"
            kind = WELFARE_KIND.get(type_descr, "welfare_unit")
            phone = format_il_phone(record_get(row, "Telephone"))
            operator = _frame_operator(row)
            display_name = name
            if type_descr == "שילוב בתעסוקה":
                display_name = _employment_display_name(name, city)
            payloads.append(
                payload_from_mapping(
                    {
                        "external_id": f"ckan:welfare-frames:{record_get(row, 'Misgeret_Id') or name}",
                        "name": display_name,
                        "org_type": org_type,
                        "kind": kind,
                        "address": record_get(row, "Adrees"),
                        "city": city,
                        "district": infer_district(city, region),
                        "phone": phone,
                        "email": "",
                        "manager": record_get(row, "Maneger_Name"),
                        "parent_org": operator,
                        "licensing": "משרד הרווחה",
                        "fallback_types": ["drugs", "alcohol", "gambling", "gaming", "shopping", "behavioral"],
                        "addiction_types": ["drugs", "alcohol", "gambling", "gaming", "shopping", "behavioral"],
                        "cost_type": "welfare",
                        "cost_info": "טיפול במסגרת משרד הרווחה / רשות מקומית. עלות מדויקת: יש לברר מול המסגרת.",
                        "referral_process": "פנייה למחלקה לשירותים חברתיים ברשות המקומית או ישירות למסגרת.",
                        "source_name": "מסגרות לטיפול בהתמכרויות — משרד הרווחה",
                        "source_url": MOLSA_EMPLOYMENT_URL if type_descr == "שילוב בתעסוקה" else "https://data.gov.il/dataset/welfare-frames",
                        "authority": "molsa",
                        "confidence": "high" if phone else "medium",
                        "operator_type": "municipality" if "רשות" in owner else "ministry_welfare",
                        "operator_name": operator,
                        "supervision_text": "מסגרת בפיקוח משרד הרווחה והביטחון החברתי (מאגר מסגרות הטיפול בהתמכרויות).",
                        "service_types": WELFARE_SERVICE_TYPES.get(type_descr, ["outpatient", "individual_group"]),
                        "target_audience": record_get(row, "Target_Population_Descr") or type_descr,
                        "age_group": age_group,
                        "gender": gender,
                        "notes": f"{type_descr} · {head} · {record_get(row, 'Second_Classific')}".strip(),
                        "_auto_import": True,
                    }
                )
            )
        logs.append(f"מסגרות נפגעי התמכרויות מרווחה: {len(payloads)}")
    except Exception as exc:
        logs.append(f"שגיאה במאגר הרווחה: {exc}")
    return payloads, logs


def harvest_html() -> tuple[list[dict[str, Any]], list[str]]:
    payloads: list[dict[str, Any]] = []
    logs: list[str] = []
    for spec in HTML_SOURCES:
        try:
            url, html = fetch_text(spec["url"])
            found = html_to_candidates(url, html, spec["name"], spec["authority"], spec["fallback_types"])
            payloads.extend(found)
            logs.append(f"{spec['name']}: {len(found)} מקטעים")
        except Exception as exc:
            logs.append(f"לא ניתן היה לקרוא {spec['name']}: {exc}")
    return payloads, logs


def harvest_tlv_municipality() -> tuple[list[dict[str, Any]], list[str]]:
    from app.agent.import_tlv_addictions import harvest_tlv_addictions

    return harvest_tlv_addictions()


def harvest_municipal_sites() -> tuple[list[dict[str, Any]], list[str]]:
    from app.agent.municipal import harvest_municipalities

    return harvest_municipalities()


def harvest_all() -> tuple[list[dict[str, Any]], list[str]]:
    payloads: list[dict[str, Any]] = []
    logs: list[str] = []
    for fn in (harvest_ckan, harvest_welfare, harvest_html, harvest_tlv_municipality, harvest_municipal_sites):
        rows, more = fn()
        payloads.extend(rows)
        logs.extend(more)
    return payloads, logs
