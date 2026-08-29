from __future__ import annotations

import hashlib
import re
import time
from collections import deque
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urldefrag, urlparse

import httpx
from bs4 import BeautifulSoup

from app.agent.extract import html_to_candidates
from app.agent.fetch import format_il_phone
from app.agent.muni_sites import KNOWN_SITES
from app.agent.normalize import infer_district, payload_from_mapping
from app.config import (
    BROWSER_UA,
    CKAN_BASE,
    MUNICIPAL_AUTHORITIES_RESOURCE,
    MUNICIPAL_MAX_PAGES,
    MUNICIPAL_TIMEOUT,
    MUNICIPAL_TIME_BUDGET,
)
from app.db import SessionLocal, init_db
from app.models import MunicipalitySite

DEPT_KEYWORDS = (
    "שירותים חברתיים",
    "שירותי רווחה",
    "אגף הרווחה",
    "מחלקה לשירותים",
    "לשכת רווחה",
    "התמכר",
    "סמים",
    "אלכוהול",
    "הימור",
    "גמילה",
    "מניעה",
    "אכפת",
    "קידום נוער",
    "נוער בסיכון",
    "נפגעי",
    "מטרא",
    'מטר"א',
    "מרכז יום",
    "טיפול בהתמכר",
)
HIGH_KEYWORDS = (
    "התמכר",
    "סמים",
    "אלכוהול",
    "הימור",
    "גמילה",
    "מטרא",
    'מטר"א',
    "נפגעי התמכר",
    "מכור",
    "טיפול בהתמכר",
)
ITEM_KEYWORDS = HIGH_KEYWORDS + (
    "יחידה לטיפול",
    "מרכז יום",
    "מוקד מטר",
    "מניעה",
    "אכפת",
)
SKIP_KEYWORDS = (
    "ארנונה",
    "חניה",
    "רישוי עסק",
    "תכנון ובנייה",
    "מכרזים",
    "דרושים",
    "גבייה",
    "ביוב",
    "אשפה",
    "דוחות תנועה",
)
NOISE_NAMES = (
    "-------------",
    "שירותים נפוצים",
    "אירועים בעיר",
    "עדכונים",
    "עמוד הבית",
    "צור קשר",
    "יצירת קשר",
    "חיפוש",
    "שאלות נפוצות בנושא התמכרויות",
)
SKIP_KEYWORDS = (
    "ארנונה",
    "חניה",
    "רישוי עסק",
    "תכנון ובנייה",
    "מכרזים",
    "דרושים",
    "גבייה",
    "ביוב",
    "אשפה",
    "דוחות תנועה",
)
SKIP_PATH = (
    ".pdf",
    ".jpg",
    ".png",
    ".gif",
    ".zip",
    ".doc",
    "/login",
    "/wp-admin",
    "mailto:",
    "javascript:",
    "tel:",
)
FALLBACK_TYPES = ["drugs", "alcohol", "gambling", "behavioral"]


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=MUNICIPAL_TIMEOUT,
        headers={
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "he-IL,he;q=0.9,en;q=0.6",
        },
        follow_redirects=True,
    )


def _normalize_url(base: str, href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith("#") or href.lower().startswith("javascript:"):
        return ""
    joined = urljoin(base, href)
    joined, _ = urldefrag(joined)
    return joined.split("?")[0] if any(joined.lower().endswith(ext) for ext in (".aspx", ".html", ".htm")) else joined


def _same_site(home: str, url: str) -> bool:
    a, b = urlparse(home), urlparse(url)
    if not b.netloc:
        return False
    host_a = a.netloc.lower().removeprefix("www.")
    host_b = b.netloc.lower().removeprefix("www.")
    return host_b == host_a or host_b.endswith("." + host_a) or host_a.endswith("." + host_b)


def _score_link(text: str, url: str) -> int:
    blob = f"{text} {url}".lower()
    if any(k.lower() in blob for k in SKIP_KEYWORDS):
        return -20
    if any(token in url.lower() for token in SKIP_PATH):
        return -50
    score = 0
    for kw in HIGH_KEYWORDS:
        if kw.lower() in blob:
            score += 8
    for kw in DEPT_KEYWORDS:
        if kw.lower() in blob:
            score += 4
    return score


def _is_relevant_page(title: str, text: str, url: str, is_home: bool = False) -> bool:
    blob = f"{title} {text[:5000]} {url}"
    if any(k in blob for k in HIGH_KEYWORDS):
        return True
    if is_home:
        return False
    welfare = any(k in blob for k in ("שירותים חברתיים", "שירותי רווחה", "אגף הרווחה", "מחלקה לשירותים", "לשכת רווחה"))
    prevention = any(k in blob for k in ("מניעה", "אכפת", "קידום נוער", "נוער בסיכון"))
    return welfare or prevention


SEARCH_PATHS = (
    "/Residents/HealthAndSocial/Pages/Addictions.aspx",
    "/Residents/HealthAndSocial/Pages/SocialServices.aspx",
    "/Residents/HealthAndSocial/",
    "/Residents/Education/",
    "/he/residents/health-and-social",
    "/he/residents/welfare",
    "/he/residents/education",
    "/services/welfare",
    "/?s=%D7%94%D7%AA%D7%9E%D7%9B%D7%A8%D7%95%D7%99%D7%95%D7%AA",
    "/search?q=%D7%94%D7%AA%D7%9E%D7%9B%D7%A8%D7%95%D7%99%D7%95%D7%AA",
)


def _seed_urls(home: str) -> list[str]:
    parsed = urlparse(home)
    root = f"{parsed.scheme}://{parsed.netloc}"
    return [urljoin(root, path) for path in SEARCH_PATHS]


def crawl_authority(home: str, name: str, deadline: float | None = None) -> tuple[list[tuple[str, str]], int]:
    pages: list[tuple[str, str]] = []
    seen: set[str] = set()
    queued: set[str] = set()
    with _client() as client:
        queue: deque[tuple[int, str]] = deque()
        queue.append((10, home))
        queued.add(home)
        for extra in _seed_urls(home):
            if extra not in queued:
                queue.append((7, extra))
                queued.add(extra)
        for sm in _sitemap_urls(client, home):
            if sm not in queued:
                queue.append((6, sm))
                queued.add(sm)
        while queue and len(seen) < MUNICIPAL_MAX_PAGES:
            if deadline and time.monotonic() >= deadline:
                break
            _score, url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            got = _fetch(client, url)
            if not got:
                continue
            final_url, html = got
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            title = re.sub(r"\s+", " ", title_match.group(1) if title_match else "")
            text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
            is_home = urlparse(final_url).path in {"", "/"}
            if is_home:
                if any(k in text for k in HIGH_KEYWORDS):
                    pages.append((final_url, html))
            elif _is_relevant_page(title, text, final_url, is_home=False):
                pages.append((final_url, html))
            for link_score, href, _label in sorted(_collect_links(home, final_url, html), reverse=True):
                if href not in queued and link_score >= 4:
                    queue.append((link_score, href))
                    queued.add(href)
    return pages, len(seen)


def _fetch(client: httpx.Client, url: str) -> tuple[str, str] | None:
    try:
        response = client.get(url)
        if response.status_code >= 400:
            return None
        ctype = response.headers.get("content-type", "")
        if "html" not in ctype and "xml" not in ctype and not url.endswith(".aspx"):
            return None
        return str(response.url), response.text
    except Exception:
        return None


def _collect_links(home: str, page_url: str, html: str) -> list[tuple[int, str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: list[tuple[int, str, str]] = []
    for a in soup.find_all("a", href=True):
        href = _normalize_url(page_url, a.get("href", ""))
        if not href or not _same_site(home, href):
            continue
        if any(token in href.lower() for token in SKIP_PATH):
            continue
        text = a.get_text(" ", strip=True)[:160]
        score = _score_link(text, href)
        if score > 0:
            found.append((score, href, text))
    return found


def _sitemap_urls(client: httpx.Client, home: str) -> list[str]:
    urls: list[str] = []
    parsed = urlparse(home)
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path in ("/sitemap.xml", "/sitemap_index.xml"):
        got = _fetch(client, root + path)
        if not got:
            continue
        _, xml = got
        for loc in re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml, re.I):
            loc = loc.strip()
            if _same_site(home, loc) and _score_link("", loc) > 0:
                urls.append(loc)
        if urls:
            break
    return urls[:80]


def _payloads_from_page(url: str, html: str, authority: MunicipalitySite) -> list[dict[str, Any]]:
    source_name = f"{authority.authority_type} {authority.name} — אתר הרשות"
    raw = html_to_candidates(url, html, source_name, "municipality", FALLBACK_TYPES)
    out: list[dict[str, Any]] = []
    page_text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    high_page = any(k in page_text for k in HIGH_KEYWORDS)
    if not _is_relevant_page("", page_text, url) and not high_page:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        name = (item.get("name") or "").strip()
        if len(name) < 6 or name in NOISE_NAMES or "{{" in name or "לחץ כאן" in name:
            continue
        if len(name) > 120:
            continue
        blob = f"{name} {item.get('notes') or ''}"
        if not any(k in blob for k in ITEM_KEYWORDS):
            continue
        phone = format_il_phone(item.get("phone") or "") or (item.get("phone") or "")
        if phone.startswith("*") and not high_page:
            continue
        address = item.get("address") or ""
        if address and address not in name and ("יחידה" in name or "מרכז" in name or "מוקד" in name):
            name = f"{name} · {address}"
        digest = hashlib.sha1(f"{authority.code}:{name}:{phone}".encode("utf-8")).hexdigest()[:12]
        payload = payload_from_mapping(
            {
                "external_id": f"muni:{authority.code}:{digest}",
                "name": name,
                "org_type": "public",
                "kind": item.get("kind") or "welfare_unit",
                "address": address,
                "city": authority.name,
                "district": infer_district(authority.name, authority.district),
                "phone": phone,
                "email": item.get("email") or "",
                "website": url,
                "notes": (item.get("notes") or "")[:800],
                "source_name": source_name,
                "source_url": url,
                "authority": "municipality",
                "confidence": "high" if phone and high_page else ("medium" if phone else "low"),
                "operator_type": "municipality",
                "operator_name": authority.name,
                "licensing": authority.authority_type,
                "fallback_types": FALLBACK_TYPES,
                "addiction_types": item.get("addiction_types") or FALLBACK_TYPES,
                "cost_type": "welfare",
                "cost_info": "שירות ברשות המקומית. עלות: יש לברר מול המחלקה.",
                "referral_process": "פנייה למחלקה לשירותים חברתיים ברשות המקומית.",
                "supervision_text": f"כפי שפורסם באתר {authority.authority_type} {authority.name}.",
                "service_types": ["outpatient", "individual_group"],
                "_auto_import": bool(phone) and (high_page or any(k in blob for k in HIGH_KEYWORDS)),
            }
        )
        out.append(payload)
    return out


def _ensure_catalog(db) -> int:
    from app.agent.fetch import fetch_json

    existing = {row.code for row in db.query(MunicipalitySite).all()}
    data = fetch_json(
        f"{CKAN_BASE}/datastore_search",
        {"resource_id": MUNICIPAL_AUTHORITIES_RESOURCE, "limit": 1000},
    )["result"]
    added = 0
    for row in data.get("records") or []:
        code = str(row.get("LocalAuthorityCode") or "")
        name = (row.get("LocalAuthorityName") or "").strip()
        if not code or not name:
            continue
        website = KNOWN_SITES.get(name) or KNOWN_SITES.get(name.replace(" ", "")) or ""
        if code in existing:
            site = db.query(MunicipalitySite).filter(MunicipalitySite.code == code).first()
            if site and not site.website and website:
                site.website = website
            continue
        db.add(
            MunicipalitySite(
                code=code,
                name=name,
                authority_type=row.get("LocalAuthorityType") or "",
                district=row.get("LocalAuthorityDistrict") or "",
                website=website,
                last_status="pending",
            )
        )
        added += 1
        existing.add(code)
    db.commit()
    return added


def _probe_website(name: str, known: str) -> str:
    candidates = []
    if known:
        candidates.append(known)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower())
    if slug and slug not in {"-", ""}:
        candidates.append(f"https://www.{slug}.muni.il")
    with _client() as client:
        for url in candidates:
            got = _fetch(client, url)
            if not got:
                continue
            final, html = got
            if name[:4] in html or "עירי" in html or "מועצה" in html or "רשות" in html:
                return final
    return known


def harvest_municipalities() -> tuple[list[dict[str, Any]], list[str]]:
    init_db()
    logs: list[str] = []
    payloads: list[dict[str, Any]] = []
    db = SessionLocal()
    started = time.monotonic()
    try:
        added = _ensure_catalog(db)
        total = db.query(MunicipalitySite).count()
        with_site = db.query(MunicipalitySite).filter(MunicipalitySite.website != "").count()
        scanned = db.query(MunicipalitySite).filter(MunicipalitySite.last_status.in_(["done", "empty", "error"])).count()
        logs.append(f"רשויות מקומיות במאגר: {total} (אתר ידוע: {with_site}). נסרקו עד כה {scanned}.")
        if added:
            logs.append(f"נוספו {added} רשויות מרשימת משרד הפנים.")
        pending = (
            db.query(MunicipalitySite)
            .filter(MunicipalitySite.last_status.in_(["pending", "error", "empty", "no_website"]))
            .order_by(MunicipalitySite.last_scanned.is_(None).desc(), MunicipalitySite.last_scanned.asc())
            .all()
        )
        done_now = 0
        for site in pending:
            if time.monotonic() - started >= MUNICIPAL_TIME_BUDGET:
                logs.append("הופסק לפי תקציב זמן; הסריקה תמשיך בלחיצה הבאה על «סרוק עכשיו».")
                break
            known = site.website or KNOWN_SITES.get(site.name, "")
            website = _probe_website(site.name, known) if not site.website else (site.website or known)
            if not website:
                website = known
            if not website:
                site.last_status = "no_website"
                site.last_scanned = datetime.utcnow()
                site.error_text = "לא נמצא אתר רשמי ידוע לרשות"
                db.commit()
                continue
            site.website = website
            try:
                pages, visited = crawl_authority(
                    website, site.name, deadline=started + MUNICIPAL_TIME_BUDGET
                )
                found: list[dict[str, Any]] = []
                for url, html in pages:
                    found.extend(_payloads_from_page(url, html, site))
                payloads.extend(found)
                site.pages_visited = visited
                site.services_found = len(found)
                site.last_scanned = datetime.utcnow()
                site.last_status = "done" if found else "empty"
                site.error_text = ""
                logs.append(f"{authority_label(site)}: {len(pages)} דפי רווחה/חינוך, {len(found)} מענים, {visited} עמודים בסריקה")
                done_now += 1
            except Exception as exc:
                site.last_status = "error"
                site.last_scanned = datetime.utcnow()
                site.error_text = str(exc)[:400]
                logs.append(f"{authority_label(site)}: שגיאה {exc}")
            db.commit()
        remaining = db.query(MunicipalitySite).filter(MunicipalitySite.last_status.in_(["pending", "error"])).count()
        no_web = db.query(MunicipalitySite).filter(MunicipalitySite.last_status == "no_website").count()
        logs.append(f"בסריקה זו טופלו {done_now} רשויות. נותרו {remaining} להמשך. בלי אתר ידוע: {no_web}.")
    finally:
        db.close()
    return payloads, logs


def authority_label(site: MunicipalitySite) -> str:
    return f"{site.authority_type} {site.name}".strip()
