from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import ROOT
from app.models import Locality, Service

LOCALITIES_FILE = ROOT / "israel_cities_localities_local_councils_2026-08-28.md"
_KIND_RANK = {"city": 0, "local_council": 1, "locality": 2, "special": 3}
_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|")
TLV_CANON = "תל אביב - יפו"
_TLV_FOLDS = {
    "תא",
    "תל אביב",
    "תל אביב יפו",
    "תל אביב-יפו",
    "tlv",
    "tel aviv",
    "tel aviv-yafo",
    "tel aviv yafo",
}


def fold_city(name: str) -> str:
    text = (name or "").strip()
    text = text.replace("״", '"').replace("׳", "'").replace("–", "-").replace("—", "-")
    text = text.replace('"', "").replace("'", "")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = text.replace("קריית", "קרית")
    return text.casefold()


def parse_localities_file(path: Path | None = None) -> list[tuple[str, str, str]]:
    path = path or LOCALITIES_FILE
    text = path.read_text(encoding="utf-8")
    by_code: dict[str, tuple[str, str, str]] = {}
    section_kind = "locality"
    for line in text.splitlines():
        if line.startswith("## א."):
            section_kind = "city"
            continue
        if line.startswith("## ב."):
            section_kind = "local_council"
            continue
        if line.startswith("## ג."):
            section_kind = "locality"
            continue
        if line.startswith("## ד.") or line.startswith("## ה."):
            section_kind = ""
            continue
        if not section_kind:
            continue
        match = _ROW_RE.match(line)
        if not match:
            continue
        code = match.group(1).strip()
        name = match.group(2).strip()
        if not code or not name:
            continue
        existing = by_code.get(code)
        if existing is None:
            by_code[code] = (code, name, section_kind)
            continue
        _, old_name, old_kind = existing
        kind = old_kind
        keep_name = old_name
        if _KIND_RANK[section_kind] < _KIND_RANK[old_kind]:
            kind = section_kind
            keep_name = name
        elif section_kind in {"city", "local_council"}:
            keep_name = name
            if section_kind == "city":
                kind = "city"
        by_code[code] = (code, keep_name, kind)
    rows = list(by_code.values())
    rows.append(("0000", "ארצי", "special"))
    return rows


def seed_localities(db: Session) -> int:
    rows = parse_localities_file()
    db.query(Locality).delete()
    db.bulk_save_objects(
        [Locality(code=code, name=name, kind=kind) for code, name, kind in rows]
    )
    db.commit()
    return len(rows)


def official_city_names(db: Session) -> list[str]:
    rows = db.query(Locality.name).order_by(Locality.name.asc()).all()
    return [row[0] for row in rows if row[0]]


def _official_fold_map(db: Session) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name, in db.query(Locality.name).all():
        mapping[fold_city(name)] = name
    for alias in _TLV_FOLDS:
        mapping[alias] = TLV_CANON
        mapping[fold_city(alias)] = TLV_CANON
    mapping[fold_city(TLV_CANON)] = TLV_CANON
    return mapping


def canonical_city(name: str, official: dict[str, str] | None = None, db: Session | None = None) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    folded = fold_city(raw)
    if folded in _TLV_FOLDS or folded in {fold_city(alias) for alias in _TLV_FOLDS}:
        return TLV_CANON
    mapping = official if official is not None else _official_fold_map(db) if db is not None else {}
    return mapping.get(folded) or mapping.get(folded.replace(" ", "-")) or raw


def city_filter_values(db: Session, selected: str) -> list[str]:
    selected = (selected or "").strip()
    if not selected:
        return []
    official = _official_fold_map(db)
    canon = canonical_city(selected, official)
    values = {selected, canon}
    for folded, name in official.items():
        if name == canon:
            values.add(name)
    for alias in (
        "ת\"א",
        "ת״א",
        "תא",
        "תל אביב",
        "תל אביב-יפו",
        "תל אביב - יפו",
        "תל אביב -  יפו",
        "תל אביב יפו",
    ):
        if canonical_city(alias, official) == canon:
            values.add(alias)
    return [v for v in values if v]


def normalize_service_cities(db: Session) -> int:
    official = _official_fold_map(db)
    changed = 0
    for service in db.query(Service).filter(Service.city != "").all():
        new = canonical_city(service.city, official)
        if new and new != service.city:
            service.city = new
            changed += 1
    db.commit()
    return changed


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    from app.config import COS_ENABLED
    from app.cos import restore_from_cos
    from app.db import SessionLocal, init_db, persist_sqlite

    if not COS_ENABLED:
        raise SystemExit("COS is not configured; refusing to write the localities list locally.")
    restore_from_cos()
    init_db()
    db = SessionLocal()
    try:
        changed = normalize_service_cities(db)
        total = db.query(Locality).count()
        tlv = db.query(Locality).filter(Locality.name == TLV_CANON).count()
        print(f"localities={total} normalized_services={changed} tel_aviv_rows={tlv}")
    finally:
        db.close()
    persist_sqlite()
