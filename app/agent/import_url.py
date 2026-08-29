from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import unquote, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.agent.fetch import extract_emails, extract_phones, format_il_phone, strip_html
from app.agent.match import best_match, field_diffs
from app.agent.normalize import guess_addiction_types, guess_kind, infer_org_type, payload_from_mapping
from app.agent.runner import apply_update, payload_to_service_kwargs
from app.config import HTTP_TIMEOUT
from app.models import Service, ServiceSource

log = logging.getLogger("maaneim.import_url")

_LD_ORG_TYPES = {
    "organization",
    "ngo",
    "localbusiness",
    "medicalorganization",
    "medicalbusiness",
    "hospital",
    "governmentorganization",
    "healthandbeautybusiness",
    "place",
    "professional",
    "clinic",
}

_ADDRESS_RE = re.compile(
    r"כתובת\s*[:\-]?\s*([א-תA-Za-z0-9\"׳'\-,\s]{5,80})"
    r"|(?:רחוב|רח['׳.])\s+[א-ת\"׳'][^\n,]{1,40}\s+\d{1,4}"
    r"|(?:שדרות|שד['׳.])\s+[א-ת\"׳'][^\n,]{1,40}"
)
_HOURS_RE = re.compile(
    r"(?:שעות(?:\s+פעילות)?|ימי\s+פעילות)\s*[:\-]?\s*([^\n]{4,80})"
)
_GENERIC_NAMES = {"דף הבית", "בית", "home", "homepage", "ראשי"}
_CHALLENGE_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "checking your browser",
    "attention required",
    "enable javascript and cookies",
    "performing security verification",
)


class ImportUrlError(ValueError):
    pass


def normalize_page_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ImportUrlError("יש להזין כתובת דף.")
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or "." not in parsed.netloc:
        raise ImportUrlError("כתובת לא תקינה. יש להזין כתובת דף שמתחילה ב-https://")
    if parsed.username or parsed.password:
        raise ImportUrlError("כתובת לא תקינה.")
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def url_external_id(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"url:{parsed.scheme}://{parsed.netloc.lower()}{path}"


def import_org_from_url(raw_url: str) -> dict[str, Any]:
    url = normalize_page_url(raw_url)
    final_url, html = _fetch_html(url)
    payload = extract_org_from_html(final_url, html)
    if not (payload.get("name") or "").strip():
        raise ImportUrlError("לא נמצא שם ארגון בדף. בדקו שהכתובת מובילה לדף עם פרטי הארגון.")
    return payload


def save_imported_org(db: Session, payload: dict[str, Any]) -> tuple[Service, bool]:
    kwargs = payload_to_service_kwargs(payload)
    ext = kwargs.get("external_id") or ""
    service = db.query(Service).filter(Service.external_id == ext).first() if ext else None
    if service is None:
        match, score = best_match(db, payload)
        if match and score >= 92:
            service = match
    created = service is None
    if service is None:
        service = Service(**kwargs)
        db.add(service)
        db.flush()
    else:
        apply_update(service, payload, field_diffs(payload, service))
    source_url = payload.get("source_url") or ""
    already = (
        db.query(ServiceSource)
        .filter(ServiceSource.service_id == service.id, ServiceSource.url == source_url)
        .first()
    )
    if already is None:
        db.add(
            ServiceSource(
                service_id=service.id,
                name=payload.get("source_name") or "שליפה מדף",
                url=source_url,
                authority=payload.get("authority") or "ngo",
                excerpt=(payload.get("notes") or "")[:500],
            )
        )
    db.commit()
    db.refresh(service)
    return service, created


def extract_org_from_html(url: str, html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        if tag.name == "script" and (tag.get("type") or "").lower() == "application/ld+json":
            continue
        if tag.name == "script":
            tag.decompose()
        elif tag.name in {"style", "noscript"}:
            tag.decompose()

    ld = _best_json_ld(soup)
    main = soup.select_one("main, article, .gt-rich-content, .content") or soup
    main_text = main.get_text("\n", strip=True)
    text = soup.get_text("\n", strip=True)
    meta_desc = _meta(soup, "description") or _meta(soup, "og:description", attr="property")
    h1 = strip_html(soup.select_one("h1").get_text() if soup.find("h1") else "")
    title = strip_html(soup.title.get_text() if soup.title else "")
    og_title = _meta(soup, "og:title", attr="property")
    site_name = _meta(soup, "og:site_name", attr="property")
    if not site_name and "עיריית" in title:
        parts = re.split(r"\s*[|\-–—·]\s*", title)
        site_name = next((p.strip() for p in reversed(parts) if "עיריית" in p), "")

    name = _usable_name(h1) or _usable_name(og_title) or _usable_name(title) or _usable_name(_as_text(ld.get("name")))
    if name and site_name and site_name not in name and name not in site_name:
        name = f"{name} · {site_name}"

    phones: list[str] = []
    for card in soup.select(".contact-man, .phonebook-contact, .contact"):
        for found in extract_phones(card.get_text()):
            if found not in phones:
                phones.append(found)
    for a in (main.select("a[href^=tel]") if main is not soup else soup.select("a[href^=tel]")):
        formatted = format_il_phone((a.get("href") or "").replace("tel:", ""))
        if formatted and formatted not in phones:
            phones.append(formatted)
    for found in extract_phones(main_text):
        if found not in phones:
            phones.append(found)
    if not phones:
        for found in extract_phones(text):
            if found not in phones:
                phones.append(found)
    specific = [p for p in phones if not p.startswith("*") and p not in {"106", "100", "101"}]
    if specific:
        phones = specific + [p for p in phones if p not in specific]

    emails: list[str] = []
    for encoded in soup.select("[data-cfemail]"):
        mail = _decode_cf_email(encoded.get("data-cfemail") or "")
        if mail and mail not in emails:
            emails.append(mail)
    for a in soup.select("a[href^=mailto]"):
        mail = (a.get("href") or "").replace("mailto:", "").split("?")[0].strip().lower()
        if mail and "@" in mail and "email-protection" not in mail and mail not in emails:
            emails.append(mail)
    for found in extract_emails(main_text) + extract_emails(text):
        if found not in emails:
            emails.append(found)

    address = _ld_address(ld) or _itemprop(soup, "street-address") or _itemprop(soup, "address")
    if not address:
        match = _ADDRESS_RE.search(main_text or text)
        if match:
            address = strip_html(match.group(0))[:200]

    city_src = " ".join(part for part in (title, h1, site_name, name, main_text[:2000]) if part)
    city = _guess_city(city_src) or _guess_city(text[:4000])

    hours = _as_text(ld.get("openingHours") or ld.get("openingHoursSpecification"))
    if not hours:
        hm = _HOURS_RE.search(main_text or text)
        if hm:
            hours = strip_html(hm.group(0))[:200]

    manager = ""
    contact_name = soup.select_one(".contact-name")
    if contact_name:
        manager = strip_html(contact_name.get_text())

    blob = " ".join(part for part in (name, address, meta_desc, main_text[:2500]) if part)
    notes = (main_text or meta_desc or text)[:1200].strip()
    domain = urlparse(url).netloc
    confidence = "low"
    if phones and (address or city):
        confidence = "high"
    elif phones or emails or address:
        confidence = "medium"

    kind = guess_kind(blob)
    if any(token in blob for token in ("אגף הרווחה", "יחידה להתמכרויות", "עיריית")):
        kind = "welfare_unit"
    org_type = "public" if "עיריית" in blob else infer_org_type(blob)
    authority = "municipality" if "עיריית" in blob else "ngo"

    return payload_from_mapping(
        {
            "external_id": url_external_id(url),
            "name": name[:400],
            "org_type": org_type,
            "kind": kind,
            "address": address[:500],
            "city": city,
            "phone": phones[0] if phones else "",
            "phone2": phones[1] if len(phones) > 1 else "",
            "email": emails[0] if emails else "",
            "website": url,
            "hours": hours,
            "notes": notes[:1200],
            "target_audience": (meta_desc or main_text[:400]).strip(),
            "manager": manager,
            "source_name": site_name or name or domain,
            "source_url": url,
            "authority": authority,
            "confidence": confidence,
            "addiction_types": guess_addiction_types(blob)
            or (["drugs", "alcohol", "gambling", "behavioral"] if "התמכר" in blob else []),
            "fallback_types": [],
        }
    )


def _fetch_html(url: str) -> tuple[str, str]:
    last_status = None
    for fetcher in (_fetch_httpx, _fetch_impersonated, _fetch_wayback):
        try:
            result = fetcher(url)
        except Exception:
            continue
        if not result:
            continue
        final_url, html, status = result
        last_status = status
        if status == 200 and html and not _is_challenge(html) and len(strip_html(html)) >= 40:
            log.info("Fetched %s via %s (%s bytes)", url, fetcher.__name__, len(html))
            return final_url, html
    if last_status:
        raise ImportUrlError(f"לא הצלחנו לקרוא את הדף (קוד {last_status}). האתר חוסם קריאה אוטומטית.")
    raise ImportUrlError("לא הצלחנו לקרוא את הדף. בדקו את הכתובת ואת החיבור.")


def _browser_headers(url: str) -> dict[str, str]:
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        "Upgrade-Insecure-Requests": "1",
        "Referer": origin + "/",
    }


def _is_challenge(html: str) -> bool:
    head = (html or "")[:5000].lower()
    return any(marker in head for marker in _CHALLENGE_MARKERS)


def _fetch_httpx(url: str) -> tuple[str, str, int] | None:
    headers = _browser_headers(url)
    with httpx.Client(timeout=HTTP_TIMEOUT, headers=headers, follow_redirects=True) as client:
        origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
        try:
            client.get(origin)
        except httpx.HTTPError:
            pass
        response = client.get(url)
        return str(response.url), response.text or "", response.status_code


def _fetch_impersonated(url: str) -> tuple[str, str, int] | None:
    try:
        from curl_cffi import requests as cf
    except ImportError:
        log.debug("curl_cffi is not installed")
        return None
    for profile in ("chrome131", "chrome124", "chrome110", "chrome"):
        try:
            response = cf.get(url, impersonate=profile, timeout=HTTP_TIMEOUT, allow_redirects=True)
            if response.status_code:
                return str(response.url), response.text or "", response.status_code
        except Exception as exc:
            log.info("curl_cffi %s failed: %s", profile, exc)
    return None


def _fetch_wayback(url: str) -> tuple[str, str, int] | None:
    headers = _browser_headers(url)
    lookup = unquote(url)
    with httpx.Client(timeout=40.0, headers=headers, follow_redirects=True) as client:
        snap_url = ""
        try:
            avail = client.get("https://archive.org/wayback/available", params={"url": lookup})
            snap = (avail.json().get("archived_snapshots") or {}).get("closest") or {}
            snap_url = snap.get("url") or ""
        except Exception as exc:
            log.info("wayback availability failed: %s", exc)
        if not snap_url:
            snap_url = f"https://web.archive.org/web/{lookup}"
        if snap_url.startswith("http://"):
            snap_url = "https://" + snap_url[len("http://") :]
        response = client.get(snap_url)
        return url, response.text or "", response.status_code


def _usable_name(value: str) -> str:
    cleaned = _clean_title(value)
    if not cleaned or cleaned.casefold() in _GENERIC_NAMES or cleaned in _GENERIC_NAMES:
        return ""
    return cleaned


def _decode_cf_email(encoded: str) -> str:
    try:
        key = int(encoded[:2], 16)
        return "".join(chr(int(encoded[i : i + 2], 16) ^ key) for i in range(2, len(encoded), 2)).lower()
    except (ValueError, TypeError):
        return ""


def _best_json_ld(soup: BeautifulSoup) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if "@graph" in item and isinstance(item["@graph"], list):
                blocks.extend(x for x in item["@graph"] if isinstance(x, dict))
            else:
                blocks.append(item)
    for item in blocks:
        types = {t.lower() for t in _as_list(item.get("@type"))}
        if types & _LD_ORG_TYPES:
            return item
    return next((item for item in blocks if item.get("name") and (item.get("telephone") or item.get("address"))), {})


def _ld_address(ld: dict[str, Any]) -> str:
    addr = ld.get("address")
    if isinstance(addr, str):
        return strip_html(addr)
    if isinstance(addr, dict):
        parts = [addr.get("streetAddress"), addr.get("addressLocality"), addr.get("postalCode")]
        return strip_html(" ".join(str(p) for p in parts if p))
    return ""


def _guess_city(text: str) -> str:
    from app.catalogs import CITY_COORDS
    from app.localities import parse_localities_file

    names = {name for _, name, _ in parse_localities_file()} | set(CITY_COORDS)
    hits = [name for name in names if name and name in (text or "")]
    return max(hits, key=len) if hits else ""


def _clean_title(text: str) -> str:
    value = strip_html(text)
    if not value:
        return ""
    for sep in (" | ", " – ", " — ", " - ", " · "):
        if sep in value:
            parts = [p.strip() for p in value.split(sep) if p.strip()]
            parts.sort(key=lambda p: (sum("א" <= ch <= "ת" for ch in p), len(p)), reverse=True)
            value = parts[0]
            break
    skip = {"דף הבית", "בית", "home", "homepage"}
    return "" if value.casefold() in skip or value in skip else value[:200]


def _meta(soup: BeautifulSoup, key: str, attr: str = "name") -> str:
    tag = soup.find("meta", attrs={attr: key}) or soup.find("meta", attrs={attr: key.lower()})
    return strip_html(tag.get("content") if tag else "")


def _itemprop(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find(attrs={"itemprop": name})
    if not tag:
        return ""
    return strip_html(tag.get("content") or tag.get("href") or tag.get_text())


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(part for v in value if (part := _as_text(v)))
    if isinstance(value, dict):
        return _as_text(value.get("name") or value.get("description") or "")
    text = str(value).strip()
    if "<" in text:
        return strip_html(text)
    return re.sub(r"\s+", " ", text).strip()


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)]
