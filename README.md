# מענים

**Live site:** https://maaneim.onrender.com

**Short link:** https://ibm.biz/oservice

Hebrew RTL portal for **addiction and mental-health services in Israel**, built for social workers. Search, filter, call, and keep a shared catalog of public services and supervised private / nonprofit frames.

The **public catalog has no login**. Anyone with the URL can use it. Treat it as an internal professional tool: the data is a working catalog, not a clinical diagnosis, and a social worker should still confirm a phone number, license, and eligibility before referring someone.

- **Source code:** [github.com/avivizel/oservice](https://github.com/avivizel/oservice)
- **Host:** Render (Frankfurt), service `maaneim` — free instance, one replica
- **Database of record:** IBM Cloud Object Storage (Frankfurt / `eu-de`), object `maaneim.db`

Contact on the site footer: רונית גרינברג ויזל — [ronitgrinbergv@gmail.com](mailto:ronitgrinbergv@gmail.com)

**הסבר מלא בעברית:** [למטה](#הסבר-מלא-בעברית)

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

A **locked maintainer area** (not linked from the public header or footer) lets the operator edit every provider in one spreadsheet-style table, export the full catalog to Excel, and see how many **people** used the site (not page hits). See [Maintainer tools](#maintainer-tools).

---

## Product rules (important)

These are not optional implementation details. They are how the catalog is supposed to stay trustworthy.

| Rule | What it means in practice |
| --- | --- |
| **Do not invent phone numbers** | A number appears only if it came from a source page, an official dataset, or a person typing it in. |
| **Official sources win** | Ministry of Health, Ministry of Welfare, government, municipality, and Bituach Leumi beat NGO / HTML scrapes when the same service conflicts. |
| **HTML and NGO need a human** | Scraped municipal pages and nonprofit sites land in **תור סוכן** until someone approves or rejects them. |
| **Open catalog** | No user accounts on the public site. Ratings and edits are shared with everyone who uses it. |
| **The bucket is the database** | The live host must read and write **only** the SQLite file in COS. A new image push must not ship or overwrite that file. |
| **One running replica** | SQLite + a single COS object cannot be safely written by two instances at once. Render is pinned to **one instance**. Do not also run Code Engine (or a second Render service) against the same object. |
| **Review bots do not write** | A monthly catalog review (Grok or similar) may **read** a snapshot and send the operator a list. It must never `UPDATE` SQLite or `upload` to COS. The operator applies accepted changes in the maintainer table. |

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
  admin.py     locked maintainer table, usage report (not in public nav)
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
2. Create missing tables, run light migrations, seed the official localities list, seed a maintainer login only if `admin_users` is empty.
3. If nothing was restored from COS (first run only), seed a small built-in emergency/hotline set.
4. Upload a consistent SQLite snapshot back to COS.
5. Serve the site with Uvicorn (**one worker**).

If COS is not configured (typical laptop without secrets), the app uses `data/maaneim.db` on disk and never talks to the bucket.

Non-static requests from real public IPs are buffered in memory and flushed about once a minute into `access_events` (for the usage report). Render health checks, private IPs, `/static`, and the maintainer area are not counted as people.

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

## Maintainer tools

Not linked from the public header or footer. Login required. Same FastAPI process and the same COS database.

- **מענים** — every provider in one table, with the same fields as the public card (contact, eligibility/cost/audience, service types, source/confidence, social-worker rating). Edit any cell and save that row; delete removes the whole record. First yellow row adds a provider. Search filters by name, city, or phone.
- **ייצוא Excel** — full catalog, Hebrew column groups, all rows (not only the current public search).
- **גישה לאתר** — how many **people** used the portal. Same IP is one visit until **30 minutes** without activity; a return after that is a new visit. This is not HTTP hits and not a per-page report. Server probes and the maintainer area are excluded. Excel export of the daily people/visit table is on that screen.

Change the maintainer password on the account page after first use. Do not put that password, or COS keys, in this README or in Git.

Before bulk edits, keep a dated copy of `maaneim.db` **outside** the live object (local `backups/` is gitignored). The live app only writes the object `maaneim.db`.

---

## Monthly catalog review (read only)

Once a month, a review bot (Grok or a person) should:

1. **Download** a COS snapshot of `maaneim.db` for reading (`mode=ro`). Never run the live app with those keys just to “look”, and never `upload_file` / `put_object`.
2. Learn the current `services` + `service_sources` rows.
3. Scan official sources (data.gov.il CKAN packages, welfare frames, selected ministry/NGO pages).
4. Match with `external_id`, then name + phone + city. Do not invent phones.
5. Send the operator **four lists only**: new institutions, proposed field updates (with existing `id`), “not found in official source this month” (do not auto-delete), and conflicts. Official sources win.

The operator applies accepted rows in the maintainer table. Playbook with connection details lives in a **local** file (`GROK_BOT.md`) that is gitignored and must not be pushed to GitHub.

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
2. If Cloudflare blocks the data-center IP, tries `curl_cffi` TLS impersonation.
3. If that still returns a challenge page, falls back to the **Wayback Machine**.
4. Prefers `h1` / `og:title` over a breadcrumb that says “דף הבית”.
5. Decodes Cloudflare obfuscated emails.
6. Matches city names against the official locality list (longest match wins).
7. Saves with `external_id` `url:…` so the same page is updated instead of duplicated.

### What stays out of Git

`.env`, `data/`, `backups/`, `*.db`, and `GROK_BOT.md` are gitignored (and Docker-ignored where relevant). A rebuild copies application code only. It must not contain a SQLite file that could be mistaken for production data.

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

**Never** point two production instances at this object. Keep Render at **one instance**. Do not start Code Engine again while Render is live.

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
| `admin_users` | Maintainer login (password hashed) |
| `admin_settings` | Including the session secret |
| `access_events` | Public-site activity used to count people / visits |

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
| `DATA_DIR` | Optional | Where SQLite lives on disk. On Render / Docker: `/tmp/maaneim-data` |
| `PORT` | On Render | Set by the platform; the container listens on `$PORT` |

COS is “on” only when **both** `COS_API_KEY` and `COS_BUCKET` are non-empty.

On Render these are service environment variables (not committed to Git).

---

## Production (Render)

| | |
| --- | --- |
| Live site | https://maaneim.onrender.com |
| Short link | https://ibm.biz/oservice |
| Service | `maaneim` (`srv-da9a4m9f2nfc73ergf7g`) |
| Dashboard | https://dashboard.render.com/web/srv-da9a4m9f2nfc73ergf7g |
| Region | Frankfurt |
| Plan | Free, **1 instance** |
| Image | Built from this repo’s `Dockerfile` (`python:3.12-slim` + Uvicorn) |
| Git source | https://github.com/avivizel/oservice (`main`) |
| Database | Same IBM COS object `maaneim.db` |

A push to `main` on GitHub auto-deploys on Render. If the GitHub auto-clone is stale, a manual `render deploys create --clear-cache --wait` is the reliable path. The new container downloads `maaneim.db` from the bucket on boot. The Docker image does not contain `data/` or `*.db`.

The free instance **sleeps after about 15 minutes** idle. The first visit after that is slower while the process starts and restores the database from COS.

### IBM Code Engine (not the live host)

The previous URL https://service-provider.2e28fox4gpdr.us-south.codeengine.appdomain.cloud is **scaled to zero** and no longer has COS credentials, so it cannot write to the bucket. Do not scale it back up while Render is running.

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
  localities.py        Official locality list → localities table
  seed.py              Small built-in seed (used only if COS is empty)
  client.py            Mobile vs desktop detection
  admin_auth.py        Maintainer login (PBKDF2), lockout, session secret
  access_log.py        Buffer public visits; 30-minute IP sessions
  routers/views.py     Search, cards, edit, URL import, ratings
  routers/agent.py     Scan, queue, Excel of the current search
  routers/admin.py     Maintainer table, catalog Excel, usage report
  agent/               Harvest, match, municipal crawl, URL import
  templates/           Public Jinja2, RTL
  templates/admin/     Maintainer UI (not linked from public nav)
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
- **Starlette sessions** (`itsdangerous`) for the maintainer login
- **httpx**, **BeautifulSoup**, **lxml**, **rapidfuzz**, **openpyxl**
- **ibm-cos-sdk** for the bucket
- **curl_cffi** to impersonate Chrome when Cloudflare blocks the data-center IP

This is a server-rendered site, not a static GitHub Pages site. It needs a long-running process, outbound HTTPS (scans and URL import), and the COS secrets.

---

## Operational cautions

- **Do not scale above one replica.** Two writers will corrupt or clobber `maaneim.db` in the bucket.
- **Do not bake the database into the image.** A push that includes `data/maaneim.db` is how catalogs get overwritten. The code already refuses to upload a tiny file over a large one, but the bucket should still be treated as irreplaceable.
- **Do not commit `.env`, API keys, or `GROK_BOT.md`.** Rotate any key that appeared in chat.
- Scan quality is uneven: some municipal sites are JavaScript-only, some concatenate phone numbers, some pages are news rather than services. The queue exists so a person can throw those out.
- A monthly review bot that writes to COS will damage the catalog. Snapshot download only; the operator edits.
- The app is **not** a diagnostic tool and must not be presented as medical advice.

---

## License / data

Service text and phone numbers belong to the publishing ministries, municipalities, and organizations. This repository holds the **software**. Production records live in the COS object, not in Git.

---

# הסבר מלא בעברית

## מה זה מענים

**מענים** הוא פורטל בעברית (מימין לשמאל) לאיתור **שירותים ומסגרות בתחום התמכרויות ובריאות הנפש בישראל**. הוא נבנה לעובדות ולעובדים סוציאליים: חיפוש, סינון, חיוג, ושמירה של קטלוג משותף של מענים ציבוריים ושל מסגרות פרטיות / מלכ״ר מפוקחות.

- **אתר חי:** https://maaneim.onrender.com
- **קישור קצר:** https://ibm.biz/oservice
- **קוד מקור:** https://github.com/avivizel/oservice
- **אירוח:** Render בפרנקפורט, שירות אחד, עותק רץ אחד בלבד
- **מסד הנתונים:** קובץ SQLite יחיד (`maaneim.db`) ב־IBM Cloud Object Storage (פרנקפורט)

**באתר הציבורי אין התחברות.** כל מי שיש לו את הכתובת יכול להשתמש. זה כלי עבודה מקצועי פנימי, לא אבחון קליני. לפני הפניה בפועל חובה לאמת טלפון, רישיון ותנאי זכאות מול המסגרת.

יצירת קשר בתחתית האתר: **רונית גרינברג ויזל** — [ronitgrinbergv@gmail.com](mailto:ronitgrinbergv@gmail.com)

---

## מה אפשר לעשות באתר

1. **חיפוש** לפי טקסט חופשי (שם, יישוב, כתובת, טלפון, הערות).
2. **סינון** לפי סוג התמכרות, סוג גוף, סוג מסגרת, מחוז, יישוב, עלות, גיל, מגדר, מגזר, ציון איכות של עו״ס, ורמת ודאות של המקור.
3. **פתיחת כרטיס מענה** עם טלפונים, כתובת, שעות, זכאות, מקורות והערות.
4. **ציון איכות** (מענה חלש / בינוני / טוב / מעולה) עם הערה אופציונלית.
5. **סימון מועדפים** — נשמר במאגר המשותף, לא רק בדפדפן.
6. **הוספת מענה ידנית**, או הדבקת כתובת דף של ארגון כדי שהמערכת תשלוף שם, טלפונים, דוא״ל ויישוב.
7. **הרצת סריקה** מול מאגרים ממשלתיים ודפי רווחה / חינוך של רשויות מקומיות.
8. **תור סוכן** — ממצאים מאתרי HTML ועמותות ממתינים לאישור אדם; שורות ממשרדים רשמיים יכולות להיכנס אוטומטית.
9. **ייצוא Excel** של תוצאות החיפוש הנוכחי, או הדפסה / PDF מהדפדפן.

הממשק בעברית, מיושר לימין, בסגנון דפי עיריית תל אביב-יפו, ומותאם לנייד ולמחשב.

יש גם **אזור ניהול נעול** (בלי קישור בתפריט הציבורי) שבו מנהלת המערכת עורכת את כל הספקים בטבלה אחת, מייצאת את כל הקטלוג לאקסל, ורואה כמה **אנשים** השתמשו באתר (לא כמה לחיצות על דפים). פירוט בסעיף [כלי ניהול](#כלי-ניהול).

---

## כללי אמון של הקטלוג

אלה לא פרטי מימוש. כך הקטלוג אמור להישאר אמין.

| כלל | מה זה אומר בפועל |
| --- | --- |
| **אין להמציא מספרי טלפון** | מספר מופיע רק אם הגיע מדף מקור, ממאגר רשמי, או מהקלדה של אדם. |
| **מקור רשמי מנצח** | משרד הבריאות, משרד הרווחה, gov.il, רשות מקומית וביטוח לאומי גוברים על גריפה מאתר עמותה / HTML כשיש סתירה. |
| **HTML ועמותה דורשים אדם** | דפים עירוניים ואתרי מלכ״ר נכנסים ל**תור סוכן** עד שמישהו מאשר או דוחה. |
| **קטלוג פתוח** | אין חשבונות משתמש באתר הציבורי. ציונים ועריכות משותפים לכל מי שנכנס. |
| **הדלי הוא המסד** | השרת החי קורא וכותב **רק** את קובץ SQLite שב־COS. דחיפת קוד חדשה אסור שתכיל או תדרוס את הקובץ הזה. |
| **עותק רץ אחד** | SQLite + אובייקט COS אחד לא יכולים להיכתב בבטחה על ידי שני שרתים במקביל. Render מכוון ל־**instance אחד**. אסור להפעיל גם Code Engine (או שירות Render שני) על אותו אובייקט. |
| **בוט סקירה לא כותב** | סריקה חודשית (Grok או אדם) רשאית **לקרוא** צילום של המאגר ולשלוח רשימה למנהלת. אסור `UPDATE` ל־SQLite ואסור `upload` ל־COS. המנהלת מחילה שינויים מאושרים בטבלת הניהול. |

הצהרה בתחתית כל עמוד: זה כלי מקומי; המידע דורש אימות של עו״ס; אם מקורות חולקים — המקור הממלכתי מנצח; לפני הפניה יש לבדוק שרישיון עדיין בתוקף.

---

## איך בקשה עוברת במערכת

הדפדפן (עברית, HTMX) פונה ל־FastAPI:

- `views.py` — חיפוש, כרטיסים, עריכה, ייבוא מכתובת, ציונים
- `agent.py` — סריקה, תור אישור, ייצוא Excel של החיפוש
- `admin.py` — טבלת ניהול ודוח שימוש (לא בתפריט הציבורי)

הנתונים נשמרים ב־SQLAlchemy 2 על SQLite (מצב WAL) בקובץ `DATA_DIR/maaneim.db`.

**בהפעלה:**

1. אם מוגדרים `COS_API_KEY` ו־`COS_BUCKET`, המערכת **מורידה** את `maaneim.db` מהדלי **לפני** שפותחים את SQLite. קובץ ריק נדחה.
2. נוצרים טבלאות חסרות, רצות מיגרציות קלות, נטענת רשימת היישובים הרשמית, ומשתמש ניהול נוצר רק אם טבלת `admin_users` ריקה.
3. אם לא שוחזר כלום מ־COS (הפעלה ראשונה בלבד), נזרעים כמה קווי חירום בסיסיים.
4. מועלה צילום SQLite עקבי בחזרה ל־COS.
5. האתר רץ ב־Uvicorn עם **תהליך עבודה אחד**.

במחשב בלי מפתחות COS הקובץ נוצר ב־`data/maaneim.db` ולא נוגעים בדלי.

פניות אמיתיות מכתובות ציבוריות (בלי קבצים סטטיים) נשמרות בזיכרון ונכתבות ל־`access_events` בערך כל דקה, לצורך דוח השימוש. בדיקות של Render, כתובות פנימיות, `/static` ואזור הניהול **לא נספרים כאנשים**.

---

## מסכים עיקריים

| נתיב | מה זה |
| --- | --- |
| `/` | חיפוש וסינון. התוצאות נטענות ב־HTMX. הרשימה הראשונית מוגבלת (כ־60); מצמצמים סינון כדי לראות את השאר. |
| `/services/{id}` | כרטיס מלא: קשר, מקורות, ציון איכות. |
| `/services/{id}/edit` | עריכת רשומה קיימת. |
| `/services/new` | הוספה ידנית, כולל **שליפה מכתובת דף**. |
| `/favorites` | מענים שמסומנים בכוכב. |
| `/agent` | תוצאות סריקה ממתינות. אישור / דחייה לשורה, או אישור מרובה. אישור מרובה למקורות רשמיים נפרד מעמותות. |
| `/agent/scan` | התחלת קציר ממאגרי CKAN ומאתרי רשויות. |
| `/export.xlsx` | אקסל של הסינון הנוכחי באתר הציבורי. |

רשימת היישובים **אינה** רשימה קשיחה של תל אביב. היא מגיעה מטבלת `localities`, שנטענת מהקובץ הרשמי `israel_cities_localities_local_councils_2026-08-28.md` (ערים, מועצות מקומיות ויישובים). כינויים של תל אביב (`תל אביב`, `ת״א` וכו') מאוחדים ל־**`תל אביב - יפו`**.

---

## כלי ניהול

אין קישור מכותרת או כותרת תחתונה ציבורית. נדרשת התחברות. אותו תהליך שרת ואותו מסד COS.

- **מענים** — כל ספק שירות בשורה אחת, עם אותם שדות כמו בכרטיס הציבורי (קשר, זכאות/עלות/קהל יעד, סוגי מענה, מקור וודאות, ציון עו״ס). מתקנים תא ולוחצים שמירה באותה שורה; מחיקה מוחקת את הרשומה כולה. השורה הצהובה למעלה מוסיפה מענה. חיפוש לפי שם, יישוב או טלפון.
- **ייצוא Excel** — כל הקטלוג, עמודות בעברית לפי קבוצות, כל השורות (לא רק החיפוש הציבורי).
- **גישה לאתר** — כמה **אנשים** השתמשו בפורטל. אותה כתובת רשת נספרת ככניסה אחת עד שעוברות **30 דקות בלי פעילות**; חזרה אחרי זה היא כניסה חדשה. זה לא היטים וזה לא דוח לפי דף. בדיקות שרת ואזור הניהול לא נספרים. אפשר לייצא לאקסל את הטבלה היומית.

אחרי הכניסה הראשונה משנים סיסמה במסך החשבון. **אין** לכתוב את הסיסמה או מפתחות COS ב־README או ב־Git.

לפני עריכה מרובה שומרים עותק מתוארך של `maaneim.db` **מחוץ** לאובייקט החי (תיקיית `backups/` המקומית לא נכנסת ל־Git). האפליקציה החיה כותבת רק לאובייקט `maaneim.db`.

---

## סקירה חודשית של הקטלוג (קריאה בלבד)

פעם בחודש בוט סקירה (Grok או אדם) אמור:

1. **להוריד** צילום של `maaneim.db` מ־COS לקריאה בלבד (`mode=ro`). אסור להריץ את האפליקציה החיה עם המפתחות האלה «רק כדי להסתכל», ואסור `upload_file` / `put_object`.
2. ללמוד את השורות הנוכחיות ב־`services` ו־`service_sources`.
3. לסרוק מקורות רשמיים (חבילות CKAN ב־data.gov.il, מסגרות רווחה, דפי משרד / עמותה נבחרים).
4. להתאים לפי `external_id`, ואחר כך שם + טלפון + יישוב. אין להמציא טלפונים.
5. לשלוח למנהלת **ארבע רשימות בלבד:** מוסדות חדשים, עדכוני שדות מוצעים (עם `id` קיים), «לא נמצא במקור הרשמי החודש» (בלי מחיקה אוטומטית), וסתירות. מקור רשמי מנצח.

המנהלת מחילה שורות שאושרו בטבלת הניהול. חוברת העבודה עם פרטי החיבור נמצאת בקובץ **מקומי** (`GROK_BOT.md`) שלא נכנס ל־Git ולא עולה ל־GitHub.

---

## מאיפה מגיע המידע לקטלוג

### מאגרים רשמיים (ייבוא אוטומטי)

סוכן הסריקה קורא חבילות **data.gov.il** (CKAN) כגון אשפוזיות גמילה של משרד הבריאות, מרפאות להתמכרות לתרופות מרשם, בתים מאזנים, בתי חולים פסיכיאטריים, מרכזי חוסן ומסגרות קשורות. מסגרות תעסוקה של משרד הרווחה מיובאות בייבואן ייעודי. ליחידות העירוניות להתמכרויות בתל אביב-יפו יש ייבואן משלהן (כתובות וטלפונים מהרשימה שפרסמה העירייה).

שורות רשמיות נשמרות עם `authority` מסוג `moh`, `molsa`, `gov`, `municipality`, `btl`. הן לא ממתינות בתור העמותות.

### סריקת אתרי רשויות

הסוכן עובר על אתרי רשויות מקומיות (שירותים חברתיים / חינוך) לפי מאגר הרשויות ב־data.gov.il. כל רשות נרשמת ב־`municipality_sites` כדי שאפשר יהיה להמשיך בסריקה הבאה. HTML חלש (בלי טלפון, בלי כתובת, בלי מזהה) נזרק — לא ממציאים מענה.

### ייבוא מכתובת (ידני)

במסך **הוספה ידנית** מדביקים דף ספציפי של ארגון (עדיף לא דף בית שלם). הייבוא:

1. מנסה שליפת HTTPS רגילה עם לקוח דמוי דפדפן.
2. אם Cloudflare חוסם את כתובת מרכז הנתונים — מנסה התחזות TLS עם `curl_cffi`.
3. אם עדיין מתקבל דף אתגר — נופל ל־**Wayback Machine**.
4. מעדיף `h1` / `og:title` על פירור לחם שכתוב בו «דף הבית».
5. מפענח דוא״ל מוצפן של Cloudflare.
6. מתאים שמות יישוב לרשימה הרשמית (ההתאמה הארוכה ביותר מנצחת).
7. שומר עם `external_id` מסוג `url:…` כדי שאותו דף יתעדכן ולא ייכפל.

### מה לא נכנס ל־Git

`.env`, `data/`, `backups/`, `*.db`, ו־`GROK_BOT.md` מוחרגים מ־Git (ומדוקר איפה שרלוונטי). בנייה מחדש מעתיקה קוד בלבד. אסור שיהיה בתוכה קובץ SQLite שאפשר לטעות בו כמאגר הייצור.

---

## מסד הנתונים (SQLite ב־COS)

הקטלוג החי הוא קובץ SQLite אחד:

- **דלי:** `for-bob-bucket`
- **שם האובייקט:** `maaneim.db` (אפשר לשנות ב־`COS_OBJECT_KEY`)
- **כתובת:** `https://s3.eu-de.cloud-object-storage.appdomain.cloud`

הגנות ב־`app/cos.py`:

- השחזור קורה **לפני** פתיחת SQLite.
- ההעלאה משתמשת ב־API של גיבוי SQLite (צילום עקבי), לא בהעתקה גולמית של קובץ WAL חי.
- המערכת **לא תדרוס** אובייקט מלא בקובץ ריק/זעיר, או בקובץ שהצטמק ביותר מכ־50% (מגן מפני אתחול רע שמוחק את הקטלוג).
- העלאת אתחול ראשונה כותבת רק אם האובייקט חסר.

**לעולם** לא מכוונים שני שרתי ייצור לאותו אובייקט. משאירים את Render על **instance אחד**. לא מעלים מחדש את Code Engine כל עוד Render רץ.

טבלאות עיקריות:

| טבלה | תפקיד |
| --- | --- |
| `services` | הקטלוג: שם, יישוב, טלפונים, מסננים, מקורות, ציון, סטטוס |
| `organizations` | ארגון־אב אופציונלי |
| `localities` | שמות יישובים / מועצות רשמיים לרשימות בחירה |
| `service_sources` | כתובות מקור |
| `ratings` | ציוני איכות של עו״ס |
| `favorites` | כוכבים משותפים |
| `agent_candidates` | תור הסריקה |
| `scan_runs` | יומן סריקות |
| `municipality_sites` | התקדמות סריקה לפי רשות |
| `field_conflicts` | מחלוקת בין מקור רשמי למקור אחר |
| `admin_users` | התחברות מנהלת (סיסמה מגובבת) |
| `admin_settings` | כולל סוד הסשן |
| `access_events` | פעילות באתר הציבורי לספירת אנשים / כניסות |

---

## הרצה מקומית

נדרש **Python 3.12**.

```powershell
cd "c:\Vibe Projects\FindServices"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

פתיחה: http://127.0.0.1:8080

בלי משתני COS המסד נוצר ב־`data/maaneim.db`. הקובץ מקומי בלבד. לא מעתיקים אותו לדוקר או ל־Git.

כדי לעבוד על **אותו קטלוג** כמו בייצור, מגדירים את משתני COS בסביבה (לא בקובץ שמחויב ל־Git) ומפעילים את האפליקציה. התהליך יוריד את `maaneim.db`, ישתמש בו, ויעלה אחרי כל שמירה.

```powershell
$env:COS_API_KEY = "…"          # מפתח IAM של IBM עם הרשאת Writer לדלי
$env:COS_BUCKET = "for-bob-bucket"
$env:COS_ENDPOINT = "https://s3.eu-de.cloud-object-storage.appdomain.cloud"
$env:COS_INSTANCE_CRN = "crn:v1:bluemix:public:cloud-object-storage:…"
$env:COS_OBJECT_KEY = "maaneim.db"
python run.py
```

אין לחייב את הערכים האלה ל־Git. אם מפתח הופיע בצ׳אט או בכרטיס — מחליפים אותו ב־IBM Cloud.

---

## משתני סביבה

| משתנה | חובה | משמעות |
| --- | --- | --- |
| `COS_API_KEY` | לייצור / מאגר משותף | מפתח IAM ל־COS |
| `COS_BUCKET` | יחד עם המפתח | שם הדלי (`for-bob-bucket`) |
| `COS_ENDPOINT` | אופציונלי | ברירת מחדל: נקודת הקצה הציבורית של `eu-de` |
| `COS_INSTANCE_CRN` | מומלץ | CRN של מופע COS |
| `COS_OBJECT_KEY` | אופציונלי | ברירת מחדל `maaneim.db` |
| `DATA_DIR` | אופציונלי | איפה SQLite על הדיסק. ב־Render / דוקר: `/tmp/maaneim-data` |
| `PORT` | ב־Render | נקבע על ידי הפלטפורמה; המכולה מאזינה ל־`$PORT` |

COS «דלוק» רק כש**גם** `COS_API_KEY` וגם `COS_BUCKET` אינם ריקים.

ב־Render אלה משתני שירות (לא ב־Git).

---

## ייצור (Render)

| | |
| --- | --- |
| אתר חי | https://maaneim.onrender.com |
| קישור קצר | https://ibm.biz/oservice |
| שירות | `maaneim` (`srv-da9a4m9f2nfc73ergf7g`) |
| לוח Render | https://dashboard.render.com/web/srv-da9a4m9f2nfc73ergf7g |
| אזור | פרנקפורט |
| תוכנית | חינם, **instance אחד** |
| תמונה | נבנית מ־`Dockerfile` בריפו (`python:3.12-slim` + Uvicorn) |
| מקור Git | https://github.com/avivizel/oservice (`main`) |
| מסד | אותו אובייקט COS `maaneim.db` |

דחיפה ל־`main` ב־GitHub מפעילה פריסה אוטומטית ב־Render. אם השכפול מ־GitHub תקוע, הדרך האמינה היא `render deploys create --clear-cache --wait`. המכולה החדשה מורידה את `maaneim.db` מהדלי בהפעלה. תמונת הדוקר **לא** מכילה `data/` או `*.db`.

השירות החינמי **נרדם אחרי כרבע שעה** בלי תנועה. הביקור הראשון אחרי השינה איטי יותר: התהליך עולה ומשחזר את המסד מ־COS.

### IBM Code Engine (לא השרת החי)

הכתובת הקודמת https://service-provider.2e28fox4gpdr.us-south.codeengine.appdomain.cloud **מורידה לאפס עותקים** ואין לה מפתחות COS, ולכן אינה יכולה לכתוב לדלי. אסור להעלות אותה מחדש כל עוד Render רץ.

---

## מבנה הפרויקט

```
app/
  main.py              אפליקציית FastAPI + שמירה בהפעלה / כיבוי
  config.py            נתיבים ומשתני COS
  cos.py               הורדה / העלאה של SQLite עם בדיקות בטיחות
  db.py                מנוע, WAL, שמירה אחרי commit, מיגרציות
  models.py            טבלאות SQLAlchemy
  query.py             חיפוש וסינון
  catalogs.py          תוויות עבריות לסוגים, מחוזות, ציונים
  localities.py        רשימת יישובים רשמית → טבלת localities
  seed.py              זריעה קטנה (רק אם COS ריק)
  client.py            זיהוי נייד מול מחשב
  admin_auth.py        התחברות מנהלת (PBKDF2), נעילה, סוד סשן
  access_log.py        חוצץ כניסות ציבוריות; סשן IP של 30 דקות
  routers/views.py     חיפוש, כרטיסים, עריכה, ייבוא מכתובת, ציונים
  routers/agent.py     סריקה, תור, אקסל של החיפוש הנוכחי
  routers/admin.py     טבלת ניהול, אקסל קטלוג, דוח שימוש
  agent/               קציר, התאמה, סריקת רשויות, ייבוא מכתובת
  templates/           תבניות ציבוריות, RTL
  templates/admin/     ממשק ניהול (בלי קישור מהתפריט הציבורי)
  static/              CSS / JS
```

---

## מחסנית טכנית

- **Python 3.12**, **FastAPI**, **Uvicorn**, **Jinja2**, **HTMX**
- **SQLAlchemy 2** + **SQLite** (WAL)
- **סשנים של Starlette** (`itsdangerous`) להתחברות הניהול
- **httpx**, **BeautifulSoup**, **lxml**, **rapidfuzz**, **openpyxl**
- **ibm-cos-sdk** לדלי
- **curl_cffi** להתחזות לכרום כש־Cloudflare חוסם את מרכז הנתונים

זה אתר שמרונדר בשרת, לא אתר סטטי של GitHub Pages. נדרשים תהליך רץ, HTTPS יוצא (סריקות וייבוא מכתובת), וסודות COS.

---

## אזהרות תפעול

- **לא להגדיל מעל עותק אחד.** שני כותבים ישחיתו או ידרסו את `maaneim.db` בדלי.
- **לא לאפות את המסד לתוך התמונה.** דחיפה שכוללת `data/maaneim.db` היא הדרך שבה קטלוגים נדרסים. הקוד כבר מסרב להעלות קובץ זעיר מעל קובץ גדול, אבל עדיין צריך להתייחס לדלי כבלתי ניתן להחלפה.
- **לא לחייב `.env`, מפתחות API, או `GROK_BOT.md`.** מחליפים כל מפתח שהופיע בצ׳אט.
- איכות הסריקה לא אחידה: חלק מאתרי הרשויות הם JavaScript בלבד, חלק מדביקים מספרי טלפון, חלק הם חדשות ולא שירותים. התור קיים כדי שאדם יוכל לזרוק אותם.
- בוט סקירה חודשי שכותב ל־COS יפגע בקטלוג. הורדת צילום בלבד; המנהלת עורכת.
- האפליקציה **אינה** כלי אבחון ואין להציג אותה כייעוץ רפואי.

---

## רישיון / נתונים

טקסט השירותים ומספרי הטלפון שייכים למשרדים, לרשויות ולארגונים המפרסמים. הריפו הזה מחזיק את **התוכנה**. רשומות הייצור חיות באובייקט COS, לא ב־Git.
