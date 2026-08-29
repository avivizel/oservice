from __future__ import annotations

from typing import Any

import httpx

from app.agent.fetch import format_il_phone
from app.agent.normalize import payload_from_mapping
from app.agent.runner import upsert_official
from app.config import HTTP_TIMEOUT
from app.db import SessionLocal, init_db

TLV_ADDICTIONS_URL = "https://www.tel-aviv.gov.il/Residents/HealthAndSocial/Pages/Addictions.aspx"
TLV_LIST_URL = (
    "https://www.tel-aviv.gov.il/Residents/HealthAndSocial/_api/web/"
    "lists(guid'd6edefe7-0e62-4b5e-a141-4851f7a1ac6d')/items"
)
VIEW_ID = "8f70c0d4-8023-4c63-9bbf-e08ad6985f62"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json;odata=verbose",
}

PHONE_KEYS = (
    "Phone",
    "Telephone",
    "Tel",
    "phone",
    "Phone1",
    "PhoneNumber",
    "Phone_x0020_Number",
    "ContactPhone",
    "טלפון",
)
ADDR_KEYS = ("Address", "address", "FullAddress", "Street", "כתובת", "Location")
HOURS_KEYS = ("Hours", "OpeningHours", "ReceptionHours", "שעות")
EMAIL_KEYS = ("Email", "EMail", "mail", "דואל")


def _sp_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("Value") or value.get("Label") or value.get("Description") or "").strip()
    return str(value).strip()


def _first(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            text = _sp_text(item[key])
            if text:
                return text
    lower = {k.lower(): k for k in item}
    for key in keys:
        real = lower.get(key.lower())
        if real and item[real] not in (None, ""):
            text = _sp_text(item[real])
            if text:
                return text
    for key, val in item.items():
        lk = key.lower()
        if any(token in lk for token in ("phone", "tel", "טלפון")) and keys is PHONE_KEYS:
            text = _sp_text(val)
            if text:
                return text
    return ""


def fetch_list_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    params: dict[str, str] = {"$top": "200"}
    url = TLV_LIST_URL
    with httpx.Client(timeout=HTTP_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        while url:
            response = client.get(url, params=params if "skiptoken" not in url.lower() else None)
            response.raise_for_status()
            try:
                data = response.json()
            except Exception as exc:
                raise RuntimeError(f"HTTP {response.status_code} {response.text[:180]}") from exc
            payload = data.get("d") or data
            batch = payload.get("results") or payload.get("value") or []
            items.extend(batch)
            next_url = payload.get("__next")
            url = next_url or ""
            params = {}
            if not next_url and len(batch) >= 200:
                break
    return items


def addiction_related(item: dict[str, Any]) -> bool:
    blob = " ".join(_sp_text(v) for v in item.values() if v and not isinstance(v, (dict, list)))
    return any(token in blob for token in ("התמכר", "סמים", "אלכוהול", "הימור", 'מטר"א', "מטרא", "מטר״א"))


def item_to_payload(item: dict[str, Any]) -> dict[str, Any] | None:
    name = _first(item, ("Title", "LinkTitle", "Title0"))
    if not name:
        return None
    phone = format_il_phone(_first(item, PHONE_KEYS))
    address = _first(item, ADDR_KEYS)
    hours = _first(item, HOURS_KEYS)
    email = _first(item, EMAIL_KEYS)
    unique = _sp_text(item.get("UniqueId") or item.get("GUID") or item.get("Id"))
    notes_parts = [name]
    if hours:
        notes_parts.append(f"שעות: {hours}")
    return payload_from_mapping(
        {
            "external_id": f"tlv:addictions:{unique or name}",
            "name": name if "תל אביב" in name else f"{name} — עיריית תל אביב-יפו",
            "org_type": "public",
            "kind": "welfare_unit",
            "address": address,
            "city": "תל אביב-יפו",
            "district": "tel_aviv",
            "phone": phone,
            "email": email,
            "hours": hours,
            "cost_type": "welfare",
            "cost_info": "שירות עירוני בפיקוח משרד הרווחה. עלות: יש לברר מול היחידה.",
            "eligibility": "מגיל 18 ומעלה; לפי אזור מגורים בעיר.",
            "referral_process": "פנייה ישירה ליחידה באזור המגורים, ללא צורך בהפניה מוקדמת.",
            "target_audience": "תושבי תל אביב-יפו מגיל 18 ומעלה, בני משפחה ואחרים משמעותיים.",
            "licensing": "עיריית תל אביב-יפו / משרד הרווחה",
            "fallback_types": ["drugs", "alcohol", "gambling", "behavioral"],
            "addiction_types": ["drugs", "alcohol", "gambling", "behavioral"],
            "age_group": "adults",
            "source_name": "עיריית תל אביב-יפו — התמכרויות",
            "source_url": TLV_ADDICTIONS_URL,
            "authority": "municipality",
            "confidence": "high" if phone else "medium",
            "operator_type": "municipality",
            "operator_name": "עיריית תל אביב-יפו",
            "supervision_text": "יחידה עירונית לטיפול בשימוש בחומרים ובהתמכרויות התנהגותיות, כפי שפורסם באתר עיריית תל אביב-יפו.",
            "service_types": ["outpatient", "individual_group", "family"],
            "notes": " · ".join(notes_parts),
            "_auto_import": True,
        }
    )


TLV_TREATMENT_UNITS: list[dict[str, str]] = [
    {
        "external_id": "ckan:welfare-frames:211708",
        "address": "הברזל 2",
        "phone": "03-7248383",
    },
    {
        "external_id": "tlv:addictions:unit-hatalmi-yehoshua-16",
        "address": "התלמי יהושע 16",
        "phone": "03-7246090",
    },
    {
        "external_id": "tlv:addictions:unit-yefet-74",
        "address": "יפת 74",
        "phone": "03-7246190",
    },
    {
        "external_id": "tlv:addictions:unit-lubetkin-10",
        "address": "לובטקין צביה 10",
        "phone": "03-7246660",
    },
    {
        "external_id": "tlv:addictions:unit-simcha-8",
        "address": "שמחה 8",
        "phone": "03-7246670",
    },
]


def _treatment_unit_entry(unit: dict[str, str]) -> dict[str, Any]:
    address = unit["address"]
    return {
        "external_id": unit["external_id"],
        "name": f"יחידה לטיפול בהתמכרויות · {address}",
        "kind": "welfare_unit",
        "phone": unit["phone"],
        "address": address,
        "age_group": "adults",
        "service_types": ["outpatient", "individual_group", "family", "referral"],
        "eligibility": "מגיל 18 ומעלה; פנייה ליחידה לפי אזור מגורים בעיר.",
        "target_audience": "תושבי תל אביב-יפו מגיל 18+, בני משפחה ואחרים משמעותיים.",
        "notes": "יחידה עירונית לטיפול בשימוש בחומרים ובהתמכרויות התנהגותיות. טיפול פרטני וקבוצתי, איתור והפניה לגמילה פיזית, התערבות משפחתית, ייעוץ תעסוקתי וקבוצות לתמיכה עצמית.",
        "website": TLV_ADDICTIONS_URL,
        "referral_process": "פנייה ישירה ליחידה באזור המגורים.",
    }


STATIC_SERVICES: list[dict[str, Any]] = [
    *[_treatment_unit_entry(unit) for unit in TLV_TREATMENT_UNITS],

    {
        "external_id": "tlv:addictions:day-center-men",
        "name": "מרכז יום לגברים — עיריית תל אביב-יפו",
        "kind": "day_center",
        "phone": "03-7248383",
        "gender": "men",
        "age_group": "adults",
        "hours": "א׳, ג׳, ה׳ 08:30–15:30",
        "eligibility": "גברים מגיל 18 ומעלה, נפגעי התמכרויות לסמים אלכוהול ותרופות, נקיים לפחות שבועיים ובטיפול פרטני באחת מיחידות מחוז מרכז. משך הטיפול כ-10 חודשים.",
        "service_types": ["day_center", "individual_group"],
        "target_audience": "גברים נפגעי התמכרויות במחוז מרכז.",
        "notes": "קבוצות טיפוליות, CBT, יוגה, פסיכודרמה, סדנאות וטיולים. פנייה מקוונת דרך אתר העירייה.",
    },
    {
        "external_id": "tlv:addictions:day-center-women",
        "name": "מרכז יום לנשים — עיריית תל אביב-יפו",
        "kind": "day_center",
        "phone": "03-7246091",
        "manager": "מיטל מיכאלי",
        "gender": "women",
        "age_group": "adults",
        "hours": "א׳, ב׳, ד׳, ה׳ 08:45–14:30",
        "eligibility": "נשים מגיל 18 ומעלה, נפגעות התמכרויות לסמים אלכוהול ותרופות, נקיות לפחות שבועיים ובטיפול פרטני באחת מיחידות מחוז מרכז. משך הטיפול כ-9 חודשים.",
        "service_types": ["day_center", "individual_group"],
        "target_audience": "נשים נפגעות התמכרויות במחוז מרכז.",
        "notes": "טיפול קבוצתי בלבד. פנייה מקוונת דרך אתר העירייה.",
    },
    {
        "external_id": "tlv:addictions:matara-youth",
        "name": "מוקד מטר״א צעירים — עיריית תל אביב-יפו",
        "kind": "day_center",
        "phone": "03-7248386",
        "age_group": "adults",
        "eligibility": "צעירים בגילאי 18–26 על רצף השימוש בסמים ואלכוהול, שנמצאים בטיפול פרטני.",
        "service_types": ["day_center", "individual_group", "youth"],
        "target_audience": "צעירים 18–26 בטיפול פרטני.",
        "notes": "קבוצה טיפולית, ליווי עו״ס ומדריך, פסיכודרמה, יוגה ומיינדפולנס, CBT, תעסוקה, מועדון חברתי. מרבית הפעילות בשעות אחר הצהריים.",
    },
    {
        "external_id": "tlv:addictions:matara-lgbtq",
        "name": "מרכז מטר״א להט״ב — עיריית תל אביב-יפו",
        "kind": "community",
        "phone": "03-7246362",
        "age_group": "adults",
        "sector": "lgbtq",
        "eligibility": "אוכלוסיית הלהט״ב מגיל 18+, תושבי תל אביב והסביבה, על רצף שימוש בחומרים או התנהגויות מתמכרות.",
        "service_types": ["outpatient", "individual_group", "harm_reduction"],
        "target_audience": "להט״ב מגיל 18+ בתל אביב והסביבה.",
        "addiction_types": ["drugs", "alcohol", "sex", "eating", "behavioral"],
        "notes": "שירות עירוני עם משרד הרווחה ובשיתוף האגודה למען הלהט״ב. בצפון הישן של תל אביב. הינזרות מלאה ומזעור נזקים.",
    },
    {
        "external_id": "seed:na",
        "name": "NA ישראל — נרקוטיקס אנונימיים",
        "kind": "twelve_step",
        "org_type": "supervised",
        "phone": "077-2285500",
        "city": "ארצי",
        "district": "national",
        "operator_type": "nonprofit",
        "operator_name": "עמותת N.A.",
        "cost_type": "free",
        "cost_info": "קבוצות עזרה עצמית ללא עלות.",
        "service_types": ["hotline"],
        "target_audience": "נפגעי התמכרות לסמים ובני משפחה לפי הפרסום באתר העירייה.",
        "notes": "פורסם בדף ההתמכרויות של עיריית תל אביב-יפו כקבוצת עזרה עצמית.",
        "supervision_text": "עמותה / קבוצת 12 צעדים כפי שפורסמה באתר העירייה. אינה יחידה עירונית.",
    },
    {
        "external_id": "tlv:addictions:naranon",
        "name": "נר-אנון — קבוצות תמיכה לבני משפחה",
        "kind": "twelve_step",
        "org_type": "supervised",
        "phone": "050-5845886",
        "city": "ארצי",
        "district": "national",
        "operator_type": "nonprofit",
        "operator_name": "עמותת נר-אנון",
        "cost_type": "free",
        "cost_info": "קבוצות תמיכה ללא עלות.",
        "service_types": ["hotline"],
        "target_audience": "בני משפחה ואחרים משמעותיים של נפגעי התמכרויות.",
        "notes": "פורסם בדף ההתמכרויות של עיריית תל אביב-יפו.",
        "supervision_text": "עמותה / קבוצת 12 צעדים כפי שפורסמה באתר העירייה. אינה יחידה עירונית.",
    },
    {
        "external_id": "tlv:addictions:prevention",
        "name": "חינוך ומניעה — מחלקת אכפת, אגף חינוך על-יסודי",
        "kind": "other",
        "phone": "03-5265820",
        "manager": "לזהר מרגלית",
        "age_group": "youth",
        "service_types": ["youth"],
        "target_audience": "בני נוער; פנייה בנושאי חינוך ומניעה.",
        "notes": "מנהלת היחידה לתכניות מניעה במחלקת אכפת.",
        "supervision_text": "יחידת חינוך ומניעה עירונית כפי שפורסמה בדף ההתמכרויות.",
    },
]


def static_payloads() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in STATIC_SERVICES:
        data = {
            "org_type": "public",
            "city": "תל אביב-יפו",
            "district": "tel_aviv",
            "cost_type": "welfare",
            "cost_info": "שירות עירוני. עלות: יש לברר מול המסגרת.",
            "referral_process": "פנייה טלפונית או פנייה מקוונת דרך אתר עיריית תל אביב-יפו.",
            "licensing": "עיריית תל אביב-יפו",
            "fallback_types": ["drugs", "alcohol", "gambling", "behavioral"],
            "addiction_types": ["drugs", "alcohol", "gambling", "behavioral"],
            "source_name": "עיריית תל אביב-יפו — התמכרויות",
            "source_url": TLV_ADDICTIONS_URL,
            "website": TLV_ADDICTIONS_URL,
            "authority": "municipality",
            "confidence": "high",
            "operator_type": "municipality",
            "operator_name": "עיריית תל אביב-יפו",
            "supervision_text": "כפי שפורסם באתר עיריית תל אביב-יפו, דף התמכרויות.",
            "_auto_import": True,
        }
        data.update(raw)
        out.append(payload_from_mapping(data))
    return out


def fetch_view_query() -> str:
    url = (
        "https://www.tel-aviv.gov.il/Residents/HealthAndSocial/_api/web/"
        f"lists(guid'd6edefe7-0e62-4b5e-a141-4851f7a1ac6d')/Views(guid'{VIEW_ID}')"
    )
    with httpx.Client(timeout=HTTP_TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        response = client.get(url, params={"$select": "Title,ViewQuery,ListViewXml"})
        response.raise_for_status()
        data = response.json().get("d") or response.json()
        return str(data.get("ViewQuery") or "")


def harvest_tlv_addictions() -> tuple[list[dict[str, Any]], list[str]]:
    logs: list[str] = []
    payloads = static_payloads()
    logs.append(f"דף העירייה (תוכן גלוי): {len(payloads)} מענים עם טלפון מפורסם")
    try:
        view_query = fetch_view_query()
        if view_query:
            logs.append(f"מסנן טבלת היחידות: {view_query[:240]}")
    except Exception as exc:
        logs.append(f"לא נטען מסנן הטבלה: {exc}")
    try:
        items = fetch_list_items()
        related = [item for item in items if addiction_related(item)]
        logs.append(f"טבלת מרכזי שירות: {len(items)} רשומות, מהן {len(related)} בנושא התמכרויות")
        if items:
            sample_keys = sorted(k for k in items[0].keys() if not k.startswith("__"))
            logs.append("שדות ברשימה: " + ", ".join(sample_keys[:40]))
        for item in related:
            payload = item_to_payload(item)
            if payload:
                payloads.append(payload)
    except Exception as exc:
        logs.append(f"לא ניתן היה לטעון את טבלת חמש היחידות מהאתר: {exc}")
    return payloads, logs


ALIASES = (
    ("מרכז יום לנשים", "מרכז יום לנשים"),
    ("מטר״א צעירים", 'מטר"א צעירים'),
    ("מטר״א להט״ב", 'מטר"א להט"ב'),
    ("מרכז יום לגברים", "נפגעי סמים מרכז יום"),
)


def _adopt_existing_id(db, payload: dict[str, Any]) -> None:
    from app.models import Service

    name = payload.get("name") or ""
    for needle, existing_part in ALIASES:
        if needle not in name:
            continue
        hit = (
            db.query(Service)
            .filter(Service.name.contains(existing_part), Service.city.contains("תל אביב"))
            .first()
        )
        if hit and hit.external_id:
            payload["external_id"] = hit.external_id
            if hit.address and not payload.get("address"):
                payload["address"] = hit.address
            return


NGO_IDS = {"seed:na", "tlv:addictions:naranon"}


def main() -> None:
    from app.models import Service

    init_db()
    payloads, logs = harvest_tlv_addictions()
    for line in logs:
        print(line)
    db = SessionLocal()
    added = 0
    try:
        for payload in payloads:
            _adopt_existing_id(db, payload)
            if payload.get("external_id") in NGO_IDS:
                payload["authority"] = "ngo"
            phone = payload.get("phone") or ""
            print(f"  {payload.get('name')} | {phone} | {payload.get('external_id')}")
            if upsert_official(db, payload):
                added += 1
            if payload.get("external_id") in NGO_IDS:
                hit = db.query(Service).filter(Service.external_id == payload["external_id"]).first()
                if hit:
                    hit.authority = "ngo"
                    hit.operator_type = "nonprofit"
        db.commit()
    finally:
        db.close()
    print(f"new={added} updated={len(payloads) - added} total={len(payloads)}")


if __name__ == "__main__":
    main()
