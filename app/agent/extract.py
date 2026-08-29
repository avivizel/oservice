from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from app.agent.fetch import extract_emails, extract_phones, format_il_phone, strip_html
from app.agent.normalize import guess_addiction_types, guess_kind, payload_from_mapping


def html_to_candidates(url: str, html: str, source_name: str, authority: str, fallback_types: list[str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    blocks: list[dict[str, Any]] = []
    blocks.extend(_from_tables(soup, url, source_name, authority, fallback_types))
    blocks.extend(_from_tel_links(soup, url, source_name, authority, fallback_types))
    if len(blocks) < 3:
        blocks.extend(_from_headings(soup, url, source_name, authority, fallback_types))
    return _dedupe(blocks)[:80]


def _from_tables(soup, url: str, source_name: str, authority: str, fallback_types: list[str]) -> list[dict[str, Any]]:
    out = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [strip_html(c.get_text()) for c in rows[0].find_all(["th", "td"])]
        for tr in rows[1:]:
            cells = [strip_html(td.get_text()) for td in tr.find_all(["td", "th"])]
            if not cells:
                continue
            mapped = {}
            for i, cell in enumerate(cells):
                key = headers[i] if i < len(headers) else f"col{i}"
                mapped[key] = cell
            blob = " ".join(cells)
            name = _first(mapped, ["שם", "מוסד", "מסגרת", "יחידה", "מרכז"]) or (cells[0] if len(cells[0]) > 3 else "")
            if not name or len(name) < 3:
                continue
            phones = extract_phones(blob) or [format_il_phone(v) for v in mapped.values() if format_il_phone(v)]
            phones = [p for p in phones if p]
            emails = extract_emails(blob)
            city = _first(mapped, ["עיר", "יישוב", "ישוב", "רשות"])
            address = _first(mapped, ["כתובת", "כתובת מלאה"])
            if not address:
                for cell in cells[1:]:
                    if any(ch.isdigit() for ch in cell) and any("א" <= ch <= "ת" for ch in cell) and len(cell) < 80:
                        address = cell
                        break
            if address and address not in name and ("יחידה" in name or "מרכז" in name or "מוקד" in name):
                name = f"{name} · {address}"
            out.append(
                payload_from_mapping(
                    {
                        "name": name,
                        "phone": ", ".join(phones[:2]),
                        "email": emails[0] if emails else "",
                        "city": city,
                        "address": address,
                        "notes": blob[:600],
                        "source_name": source_name,
                        "source_url": url,
                        "authority": authority,
                        "confidence": "medium" if phones else "low",
                        "fallback_types": fallback_types,
                        "kind": guess_kind(name + " " + blob),
                        "addiction_types": guess_addiction_types(name + " " + blob, fallback_types),
                        "website": url,
                    }
                )
            )
    return out


def _from_tel_links(soup, url: str, source_name: str, authority: str, fallback_types: list[str]) -> list[dict[str, Any]]:
    out = []
    for a in soup.select("a[href^=tel]"):
        phone = format_il_phone(a.get("href", "").replace("tel:", ""))
        parent = strip_html(a.parent.get_text() if a.parent else a.get_text())
        name = strip_html(a.get_text()) or parent[:80]
        if not phone:
            continue
        out.append(
            payload_from_mapping(
                {
                    "name": name[:200] or source_name,
                    "phone": phone,
                    "notes": parent[:400],
                    "source_name": source_name,
                    "source_url": url,
                    "authority": authority,
                    "confidence": "medium",
                    "fallback_types": fallback_types,
                    "website": url,
                }
            )
        )
    return out


def _from_headings(soup, url: str, source_name: str, authority: str, fallback_types: list[str]) -> list[dict[str, Any]]:
    title = strip_html(soup.title.get_text() if soup.title else "") or source_name
    h1 = strip_html(soup.find("h1").get_text() if soup.find("h1") else title)
    text = soup.get_text("\n", strip=True)
    phones = extract_phones(text)
    emails = extract_emails(text)
    blocks = []
    for heading in soup.find_all(["h2", "h3"]):
        name = strip_html(heading.get_text())
        if len(name) < 4:
            continue
        chunk_parts = []
        for sib in heading.find_all_next(["p", "li", "h2", "h3"], limit=12):
            if sib.name in {"h2", "h3"} and sib is not heading:
                break
            chunk_parts.append(strip_html(sib.get_text()))
        chunk = " ".join(p for p in chunk_parts if p)
        local_phones = extract_phones(name + " " + chunk) or phones[:2]
        emails_local = extract_emails(chunk) or emails
        if name and (local_phones or len(chunk) > 40):
            blocks.append(
                payload_from_mapping(
                    {
                        "name": name,
                        "phone": ", ".join(local_phones[:3]),
                        "email": emails_local[0] if emails_local else "",
                        "notes": chunk[:800],
                        "source_name": source_name,
                        "source_url": url,
                        "authority": authority,
                        "confidence": "low",
                        "fallback_types": fallback_types,
                        "kind": guess_kind(name + " " + chunk),
                        "addiction_types": guess_addiction_types(name + " " + chunk, fallback_types),
                        "website": url,
                    }
                )
            )
    if not blocks:
        blocks.append(
            payload_from_mapping(
                {
                    "name": h1,
                    "phone": ", ".join(phones[:3]),
                    "email": emails[0] if emails else "",
                    "notes": text[:800],
                    "source_name": source_name,
                    "source_url": url,
                    "authority": authority,
                    "confidence": "low",
                    "fallback_types": fallback_types,
                    "website": url,
                }
            )
        )
    return blocks


def _first(mapped: dict[str, str], keys: list[str]) -> str:
    for key, value in mapped.items():
        for needle in keys:
            if needle in key and value:
                return value
    return ""


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        key = (item.get("name") or "", item.get("phone") or "", item.get("city") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
