# מענים

**Live site:** https://service-provider.2e28fox4gpdr.us-south.codeengine.appdomain.cloud

Hebrew RTL portal for **addiction and mental-health services in Israel**, built for social workers. Search, filter, call, and keep a shared catalog of public services and supervised private / nonprofit frames.

There is **no login**. Anyone with the URL can use it. Treat it as an internal professional tool: the data is a working catalog, not a clinical diagnosis, and a social worker should still confirm a phone number, license, and eligibility before referring someone.

- **Source code:** [github.com/avivizel/oservice](https://github.com/avivizel/oservice)
- **Host:** IBM Code Engine (Dallas / `us-south`), app name `service-provider`
- **Database of record:** IBM Cloud Object Storage (Frankfurt / `eu-de`), object `maaneim.db`

Contact on the site footer: רונית גרינברג ויזל, רכזת התמכרויות, האגף לשירותים חברתיים, עיריית תל אביב-יפו — [grinberg_r@mail.tel-aviv.gov.il](mailto:grinberg_r@mail.tel-aviv.gov.il)

---

## What this app does

A social worker can:

1. **Search** by free text (name, city, address, phone, notes).
2. **Filter** by addiction type, organization type, service kind, district, city, cost, age, gender, sector, social-worker quality rating, and source confidence.
3. **Open a service card** with phones, address, hours, eligibility, sources, and notes.
4. **Rate** a frame (weak / medium / good / excellent) with an optional comment.
5. **Star favorites** (stored in the shared database, not in the browser only).
6. **Add a service by hand**, or paste an organization URL and have the app scrape name, phones, email, and city.
7. **Run a scan** against official government catalogs and municipal welfare / education pages.
8. **Review the agent queue** — HTML and NGO finds wait for a human; official ministry rows can be imported automatically.
9. **Export Excel** of the current search, or print / PDF from the browser.

The UI is Hebrew, right-to-left, and styled after Tel Aviv–Yafo municipal pages. Layout adapts for phone vs desktop.

---

## Product rules (important)

These are not optional implementation details. They are how the catalog is supposed to stay trustworthy.

| Rule | What it means in practice |
| --- | --- |
| **Do not invent phone numbers** | A number appears only if it came from a source page, an official dataset, or a person typing it in. |
| **Official sources win** | Ministry of Health, Ministry of Welfare, government, municipality, and Bituach Leumi beat NGO / HTML scrapes when the same service conflicts. |
| **HTML and NGO need a human** | Scraped municipal pages and nonprofit sites land in **תור סוכן** until someone approves or rejects them. |
| **Open catalog** | No user accounts. Ratings and edits are shared with everyone who uses the site. |
| **The bucket is the database** | Code Engine (and any other host) must read and write **only** the SQLite file in COS. A new image push must not ship or overwrite that file. |
| **One running replica** | SQLite + a single COS object cannot be safely written by two instances at once. Code Engine is set to **min scale 1 / max scale 1**. |

Footer disclaimer (also on every page): this is a local tool; information needs a social worker’s confirmation; if sources disagree, the official state source wins; check that a license is still valid before referring.

---

## How a request flows

```
Browser (Hebrew RTL, HTMX)
        │
        ▼
FastAPI  (app/main.py)
  views.py     search, cards, edit, URL import, ratings
  agent.py     scan, approval queue, Excel export
        │
        ▼
SQLAlchemy 2  →  SQLite  (WAL)
  local file:  DATA_DIR/maaneim.db
        │
        ├── startup:  download maaneim.db from COS (if COS is configured)
        └── after each successful commit:  WAL checkpoint + upload snapshot
```

Startup sequence (`app/main.py`):

1. If `COS_API_KEY` and `COS_BUCKET` are set, **download** `maaneim.db` from the bucket **before** SQLite is used. An empty download is refused.
2. Create missing tables, run light migrations, seed the official localities list.
3. If nothing was restored from COS (first run only), seed a small built-in emergency/hotline set.
4. Upload a consistent SQLite snapshot back to COS.
5. Serve the site with Uvicorn.

If COS is not configured (typical laptop without secrets), the app uses `data/maaneim.db` on disk and never talks to the bucket.

---

## Main screens

| Path | What it is |
| --- | --- |
| `/` | Search + filters. Results load with HTMX. Default list is capped (first 60); narrow the filters to see the rest. |
| `/services/{id}` | Full card: contacts, sources, quality rating. |
| `/services/{id}/edit` | Edit an existing row. |
| `/services/new` | Manual add. Includes **import from URL**: paste a specific org page, scrape, save. |
| `/favorites` | Starred services. |
| `/agent` | Pending scan results. Approve / reject one row, or bulk-approve. Official-authority bulk-approve is separate from NGO. |
| `/agent/scan` | Start a harvest of official CKAN datasets + municipal sites. |
| `/export.xlsx` | Excel of the current filter set. |

City dropdowns are **not** a hard-coded Tel Aviv list. They come from the `localities` table, loaded from `israel_cities_localities_local_councils_2026-08-28.md` (official cities, local councils, and localities). Tel Aviv aliases (`תל אביב`, `ת״א`, …) are folded to **`תל אביב - יפו`**.

---

## Data that feeds the catalog

### Official catalogs (auto-import)

The scan agent reads **data.gov.il** (CKAN) packages such as Ministry of Health rehab wards, prescription-drug clinics, balancing homes, psychiatric hospitals, resilience centers, and related sets. Ministry of Welfare employment frames are imported from a dedicated importer. Tel Aviv municipal addiction units (addresses and phones taken from the city’s published list) have their own importer.

Official rows are upserted (`authority` in `moh`, `molsa`, `gov`, `municipality`, `btl`). They do not wait in the NGO queue.

### Municipal crawl

The agent walks Israeli local-authority sites (social services / education), using the government authorities resource on data.gov.il. Each authority is tracked in `municipality_sites` so a later scan can resume. Weak HTML (no phone, no address, no id) is skipped rather than inventing a service.

### URL import (manual)

On **הוספה ידנית**, a worker pastes a concrete page (not a whole homepage if they can avoid it). The importer:

1. Tries a normal HTTPS fetch with a browser-like client.
2. If Cloudflare blocks the data-center IP (common on Code Engine), tries `curl_cffi` TLS impersonation.
3. If that still returns a challenge page, falls back to the **Wayback Machine**.
4. Prefers `h1` / `og:title` over a breadcrumb that says “דף הבית”.
5. Decodes Cloudflare obfuscated emails.
6. Matches city names against the official locality list (longest match wins).
7. Saves with `external_id` `url:…` so the same page is updated instead of duplicated.

### What stays out of Git

`.env`, `data/`, and `*.db` are gitignored and Docker-ignored. A Code Engine rebuild copies application code only. It must not contain a SQLite file that could be mistaken for production data.

---

## Database (SQLite in COS)

The live catalog is a single SQLite file:

- **Bucket:** `for-bob-bucket`
- **Object key:** `maaneim.db` (override with `COS_OBJECT_KEY`)
- **Endpoint:** `https://s3.eu-de.cloud-object-storage.appdomain.cloud`

Safety in `app/cos.py`:

- Restore happens **before** the app opens the database.
- Upload uses SQLite’s backup API (a consistent snapshot), not a raw copy of a live WAL file.
- The app **will not** overwrite a populated bucket object with an empty or tiny file, or with a file that shrank by more than about 50% (guards against a bad boot wiping the catalog).
- First-time `bootstrap_upload` only writes if the object is missing.

**Never** point two production instances at this object. Keep Code Engine **max-scale = 1**.

Main tables:

| Table | Role |
| --- | --- |
| `services` | The catalog: name, city, phones, filters, sources, rating, status |
| `organizations` | Optional parent org |
| `localities` | Official city / council / locality names for dropdowns |
| `service_sources` | Provenance URLs |
| `ratings` | Social-worker quality scores |
| `favorites` | Shared stars |
| `agent_candidates` | Scan queue |
| `scan_runs` | Scan logs |
| `municipality_sites` | Per-authority crawl progress |
| `field_conflicts` | Official vs other-source disagreements |

---

## Running locally

You need **Python 3.12**.

```powershell
cd "c:\Vibe Projects\FindServices"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:8080

Without COS env vars, the database is created at `data/maaneim.db`. That file is local only. Do not copy it into Docker or Git.

To talk to the **same** catalog as production, set the COS variables in the environment (not in a committed file) and start the app. The process will download `maaneim.db`, use it, and upload after each save.

```powershell
$env:COS_API_KEY = "…"          # IBM IAM key with Writer on the bucket
$env:COS_BUCKET = "for-bob-bucket"
$env:COS_ENDPOINT = "https://s3.eu-de.cloud-object-storage.appdomain.cloud"
$env:COS_INSTANCE_CRN = "crn:v1:bluemix:public:cloud-object-storage:…"
$env:COS_OBJECT_KEY = "maaneim.db"
python run.py
```

Do not commit those values. If a key was ever pasted into chat or a ticket, rotate it in IBM Cloud.

---

## Environment variables

| Variable | Required | Meaning |
| --- | --- | --- |
| `COS_API_KEY` | For production / shared DB | IAM API key for COS |
| `COS_BUCKET` | With the key | Bucket name (`for-bob-bucket`) |
| `COS_ENDPOINT` | Optional | Defaults to the `eu-de` public S3 endpoint |
| `COS_INSTANCE_CRN` | Recommended | COS instance CRN |
| `COS_OBJECT_KEY` | Optional | Defaults to `maaneim.db` |
| `DATA_DIR` | Optional | Where SQLite lives on disk. On Code Engine: `/tmp/maaneim-data` |
| `PORT` | On Code Engine | HTTP port (8080) |

COS is “on” only when **both** `COS_API_KEY` and `COS_BUCKET` are non-empty.

On Code Engine these are injected from secret **`maaneim-cos`**, not from Git.

---

## Production (IBM Code Engine)

| | |
| --- | --- |
| Project / app | `service-provider` |
| Region | Dallas (`us-south`) |
| URL | https://service-provider.2e28fox4gpdr.us-south.codeengine.appdomain.cloud |
| Image | Built from this repo’s `Dockerfile` (`python:3.12-slim` + Uvicorn) |
| Git source | https://github.com/avivizel/oservice (`main`) |
| Secret | `maaneim-cos` (COS credentials) |
| Scale | min 1, max 1, 0.5 CPU, 1 GB RAM, port 8080 |

Deploy from GitHub (does **not** upload the database):

```text
ibmcloud ce project select --name service-provider
ibmcloud ce app update --name service-provider --build-source https://github.com/avivizel/oservice --build-commit main --min-scale 1 --max-scale 1 --wait
```

A new revision replaces the **container**. On boot the new process downloads `maaneim.db` from the bucket. The Docker image does not contain `data/` or `*.db` (see `.dockerignore` / `.ceignore`).

Pushing code to GitHub does **not** by itself redeploy. Someone still runs `ibmcloud ce app update` (or an equivalent CI step) against that commit.

---

## Project layout

```
app/
  main.py              FastAPI app + startup / shutdown persist
  config.py            Paths and COS env
  cos.py               Download / upload SQLite with safety checks
  db.py                Engine, WAL, persist after commit, migrations
  models.py            SQLAlchemy tables
  query.py             Search and filters
  catalogs.py          Hebrew labels for types, districts, ratings
  localities.py       Official locality list → localities table
  seed.py              Small built-in seed (used only if COS is empty)
  client.py            Mobile vs desktop detection
  routers/views.py     Search, cards, edit, URL import, ratings
  routers/agent.py     Scan, queue, Excel
  agent/               Harvest, match, municipal crawl, URL import
  templates/           Jinja2, RTL
  static/              CSS / JS
israel_cities_localities_local_councils_2026-08-28.md
Dockerfile             Production image (no database inside)
Procfile               Uvicorn command
requirements.txt
run.py                 Local: http://127.0.0.1:8080 with reload
```

---

## Stack

- **Python 3.12**, **FastAPI**, **Uvicorn**, **Jinja2**, **HTMX**
- **SQLAlchemy 2** + **SQLite** (WAL)
- **httpx**, **BeautifulSoup**, **lxml**, **rapidfuzz**, **openpyxl**
- **ibm-cos-sdk** for the bucket
- **curl_cffi** to impersonate Chrome when Cloudflare blocks the data-center IP

This is a server-rendered site, not a static GitHub Pages site. It needs a long-running process, outbound HTTPS (scans and URL import), and the COS secrets.

---

## Operational cautions

- **Do not scale above one replica.** Two writers will corrupt or clobber `maaneim.db` in the bucket.
- **Do not bake the database into the image.** A push that includes `data/maaneim.db` is how catalogs get overwritten. The code already refuses to upload a tiny file over a large one, but the bucket should still be treated as irreplaceable.
- **Do not commit `.env` or API keys.** Rotate any key that appeared in chat.
- Scan quality is uneven: some municipal sites are JavaScript-only, some concatenate phone numbers, some pages are news rather than services. The queue exists so a person can throw those out.
- The app is **not** a diagnostic tool and must not be presented as medical advice.

---

## License / data

Service text and phone numbers belong to the publishing ministries, municipalities, and organizations. This repository holds the **software**. Production records live in the COS object, not in Git.
