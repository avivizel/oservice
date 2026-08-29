from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COS_API_KEY = os.environ.get("COS_API_KEY", "").strip()
COS_BUCKET = os.environ.get("COS_BUCKET", "").strip()
COS_ENDPOINT = os.environ.get(
    "COS_ENDPOINT", "https://s3.eu-de.cloud-object-storage.appdomain.cloud"
).strip()
COS_INSTANCE_CRN = os.environ.get("COS_INSTANCE_CRN", "").strip()
COS_OBJECT_KEY = os.environ.get("COS_OBJECT_KEY", "maaneim.db").strip() or "maaneim.db"
COS_ENABLED = bool(COS_API_KEY and COS_BUCKET)

if COS_ENABLED:
    DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/maaneim-data"))
else:
    DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "maaneim.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

USER_AGENT = "Maaneim/1.0 (local social-work services portal)"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CKAN_BASE = "https://data.gov.il/api/3/action"
HTTP_TIMEOUT = 25.0
MUNICIPAL_TIMEOUT = 12.0
MUNICIPAL_MAX_PAGES = 35
MUNICIPAL_TIME_BUDGET = 90.0
MUNICIPAL_AUTHORITIES_RESOURCE = "c4916937-f5d3-4295-a22e-88a1af5cde6a"
