from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import HTTP_TIMEOUT, USER_AGENT

PHONE_RE = re.compile(
    r"(?:\*|#)?(?:1-800|1-700|\*?0\d{1,2}|\d{3,4})[\s\-–]?\d{3,7}|\*\d{3,4}|1201|100|101|118"
)
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def format_il_phone(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip()
    if text.startswith("*") or text in {"100", "101", "118", "1201"}:
        return text
    digits = re.sub(r"\D", "", text)
    if not digits or set(digits) <= {"0"}:
        return ""
    if digits.startswith("972"):
        digits = "0" + digits[3:]
    if len(digits) == 8:
        digits = "0" + digits
    if len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits
    if len(digits) == 10 and digits.startswith("05"):
        return f"{digits[:3]}-{digits[3:]}"
    if len(digits) == 10 and digits.startswith("07"):
        return f"{digits[:3]}-{digits[3:]}"
    if len(digits) == 9 and digits.startswith("0"):
        return f"{digits[:2]}-{digits[2:]}"
    return digits


def extract_phones(text: str) -> list[str]:
    found: list[str] = []
    for match in PHONE_RE.findall(text or ""):
        formatted = format_il_phone(match) or match.strip()
        if formatted and formatted not in found:
            found.append(formatted)
    return found


def client() -> httpx.Client:
    return httpx.Client(
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
        follow_redirects=True,
    )


def fetch_json(url: str, params: dict | None = None) -> dict[str, Any]:
    with client() as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.json()


def fetch_text(url: str) -> tuple[str, str]:
    with client() as c:
        r = c.get(url)
        r.raise_for_status()
        return str(r.url), r.text


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(str(value), "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def extract_emails(text: str) -> list[str]:
    return sorted({m.lower() for m in EMAIL_RE.findall(text or "")})


def record_get(record: dict[str, Any], *keys: str) -> str:
    lower = {str(k).lower(): v for k, v in record.items()}
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return strip_html(str(record[key]))
        if key.lower() in lower and lower[key.lower()] not in (None, ""):
            return strip_html(str(lower[key.lower()]))
    return ""
