from __future__ import annotations

from app.agent.runner import upsert_official
from app.agent.sources import harvest_welfare
from app.db import SessionLocal, init_db


def main() -> None:
    init_db()
    payloads, logs = harvest_welfare()
    for line in logs:
        print(line)
    employment = [p for p in payloads if "שילוב בתעסוקה" in (p.get("notes") or "")]
    print(f"employment addiction frames: {len(employment)}")
    db = SessionLocal()
    added = 0
    names: list[str] = []
    orgs: set[str] = set()
    try:
        for payload in employment:
            names.append(payload.get("name") or "")
            org = (payload.get("operator_name") or payload.get("parent_org") or "").strip()
            if org:
                orgs.add(org)
            if upsert_official(db, payload):
                added += 1
        db.commit()
    finally:
        db.close()
    print("organizations:")
    for org in sorted(orgs):
        print(f"  {org}")
    print("frames:")
    for name in names:
        print(f"  {name}")
    print(f"new={added} updated={len(employment) - added}")


if __name__ == "__main__":
    main()
