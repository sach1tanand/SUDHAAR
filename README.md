# Sudhaar - Report. Resolve. Improve.

Civic grievance platform (pilot: Varanasi). Citizens report with **live** photo/video; Sudhaar investigates, scores, routes
each complaint to the right department dashboard; officers act; citizens track and confirm/reopen.

## Run
```bash
./run.sh              # or: pip install -r requirements.txt && python -m uvicorn backend.main:app --port 8000
# open http://localhost:8000
```
Camera access requires **HTTPS or localhost**. To test on a phone, tunnel it (e.g. `cloudflared tunnel --url http://localhost:8000`).

| Role | Login |
|---|---|
| Citizen | any 10-digit mobile → OTP (shown on screen in dev mode, also printed in the server log) |
| Department officer | `vmc_eng`, `vmc_drn`, `vmc_san`, `vmc_lgt`, `vmc_pub`, `jal`, `vtp`, `uppwd`, `nhai`, `vmc_gen` / `demo1234` |
| Super Admin | `admin` / `admin1234` |
| **Sudhaar AI monitor** | `sudhaar` / `sudhaar1234` - read-only; replays every step the AI took on each complaint |

**Change all seeded passwords and set `SUDHAAR_DEV_OTP=0` before any real deployment.**

## Sudhaar AI monitor (the `sudhaar` login)
After a complaint is submitted, every pipeline stage (spec §6 steps 6-12) is recorded in the `ai_trace` table: intake -> computer vision -> internal duplicate search -> severity -> evidence score -> routing -> forward -> (slow pass) external / weather / Street View -> final score.
Each step stores what it **received**, what it **produced**, warnings (e.g. no vision engine configured), and its duration. Chatbot answers are traced too.
- `#/ai` live feed (auto-refresh, pause) + engine status, `#/ai/runs` one row per complaint, `#/ai/c/<ID>` full pipeline replay, `#/ai/chat` chatbot answers.
- Read-only: cannot act as a department, cannot reach citizen identity. Super Admin can also open these pages. API: `/api/ai/*`.
- Tracing is best-effort: if the trace store fails, complaints are still forwarded.

## Tests
`pip install pytest pillow && pytest -q` - 36 tests (spec §10 + AI monitor + reopen-needs-fresh-proof + multi-model YOLO + scoring).
Browser end-to-end (fake camera + GPS, all four roles, typing regression): start a fresh server, then `npm i playwright && node tests/e2e/run.js` (set `SHOTS=dir` to save screenshots).

(includes: submission, routing to municipal/NHAI/state, scores hidden from
citizens, department isolation, privacy, audit, workflow, idempotent upload retry).

## What is implemented (spec section → where)
- **Citizen app (§4.1-4.3, 4.10, 8):** OTP login; 8 categories; live camera only (no gallery input exists); photo, video or both; lat/lon/date/time
  **burned into the pixels** and stored as per-media metadata; GPS or map-pin fallback, manual pins flagged as `manual`; optional description;
  complaint ID; status timeline; in-app notifications; resolution proof; confirm / reopen; camera-permission guidance.
- **Connectivity (§8.1):** upload progress; on failure the complaint is saved as a draft in IndexedDB (with media), retried on reconnect and every 30 s;
  success is only shown after server confirmation; retries are idempotent (`client_id`) so no duplicates.
- **Live-capture enforcement:** server-issued capture session; media timestamp must fall inside that window; files are magic-byte validated.
- **Investigation (§4.4-4.6):** vision (Claude vision or YOLO, optional), internal duplicate/corroboration search (same citizen counted once),
  external corroboration with repost de-duplication, Open-Meteo weather, Street View metadata, 0-10 validity score, separate severity.
  Fast phase forwards immediately; slow external lookups run afterwards, so critical/high are never delayed.
- **Routing (§4.7):** government level → function → road-ownership corridor / municipal area → department → dashboard, with reasoning recorded.
- **Department dashboard (§4.8-4.9):** severity-grouped worklist, media, AI findings, scores, acknowledge/review/assign/progress/remarks/resolution proof/resolve/reject.
- **Super Admin (§3.3):** overview, add departments (+officer account), complaint monitor, routing-review queue with reassignment, zones, audit log with integrity check.
- **Privacy & audit (§9):** departments never receive mobile/identity; media only via authenticated, department-scoped endpoint; views, downloads,
  status changes and uploads are logged in a hash-chained, DB-enforced append-only audit table.
- **Chatbot (§4.11):** offline rule-based helper (English/Hindi/Hinglish, voice in/out where the browser supports it).

## Not production-ready / needs your input (honest list)
1. **Jurisdiction data is placeholder.** NHAI/state corridors and the Varanasi bounding box in `backend/routing.py` are *illustrative*. Load surveyed data
   (Super Admin → Routing shows the zones). Real routing correctness depends entirely on this.
2. **OTP SMS is not connected** (`/api/auth/otp` has a TODO). Plug in MSG91/Twilio/etc.
3. **Vision needs a model.** Set `SUDHAAR_YOLO_MODELS` (one or more YOLO weights, see below) and/or `ANTHROPIC_API_KEY` (Claude vision, used as the fallback).
   Without either, AI findings say "not analysed" and the score omits the vision component.
4. **Social platforms (X, Instagram, Reddit, Facebook, YouTube) are not integrated** - API access/terms are an open question in the spec.
   Register adapters in `investigation.SOCIAL_ADAPTERS`; de-duplication is ready. News via `NEWSAPI_KEY`; Street View via `GOOGLE_MAPS_KEY`.
5. **Scoring formula, severity rubric, status transitions, uncertain-routing fallback are provisional** (spec lists them as deferred). Tune
   `investigation.WEIGHTS`, `severity()`, `main.TRANSITIONS`. Current fallback: general grievance desk + flagged for Super Admin.
6. **Media authenticity is limited**: capture-window + overlay deter casual reuse but a determined user can spoof a browser. Native-app attestation
   (Play Integrity / App Attest) is the real fix. Media is not yet encrypted at rest; retention/deletion policy undefined.
7. SQLite + local disk suit a pilot; move to Postgres + object storage and add rate limiting / HTTPS termination for scale.
8. Map tiles use public OpenStreetMap servers (fine for a pilot; use a tile provider at scale). Media EXIF is not written; metadata lives in the database.

## YOLO models (any number)
`SUDHAAR_YOLO_MODELS="road=/models/road_best.pt,waste=/models/waste_best.pt"` (a bare path also works; `SUDHAAR_YOLO_WEIGHTS` is the old single-model name and still works).
- Models load once and are cached; every model runs on every photo and on up to 4 frames of each video (needs `ffmpeg`). `pip install ultralytics`.
- One model failing never blocks the others; if all fail, Claude vision is used when `ANTHROPIC_API_KEY` is set, otherwise the complaint is forwarded un-analysed.
- Class names are mapped to Sudhaar categories by keyword (pothole, crack, manhole, garbage, streetlight, ...). `matches_category` is true only when a detection is relevant to the *reported* category. If your class names differ, set `SUDHAAR_YOLO_MAP=/path/map.json`: `{"your_class": {"label": "pothole", "categories": ["roads"]}}`.
- `SUDHAAR_YOLO_CONF` (default `0.25`) is the minimum box confidence. Box size sets `size_hint` (feeds severity).

## Evidence score (0-10), `investigation.validity_score`
Own evidence is worth **8**: live capture (video 2.6 / GPS photo 2.2 / photo 1.6, +0.4 for both, max 3), context (GPS location+time 0.7, manual pin 0.35, description 0.3), AI vision (4 x confidence; x0.25 when what it saw does not match the category).
Independent corroboration adds up to **2**: other citizens (0.6 each, max 2), news/social (0.4 each, max 2), heavy rain for drainage (0.3). Weights sum to exactly 10, so nothing is clipped away. A first report with no corroboration can still score 8. With no vision result the own evidence is scaled to 6. Street View availability earns no credit. Still provisional: tune `investigation.WEIGHTS`.

## Site settings
Fill the `SITE` block at the top of `frontend/app.js` (operator, e-mail, phone, hours, data-retention text). Empty values are not shown.

## Config (env)
`SUDHAAR_DATA`, `SUDHAAR_SECRET`, `SUDHAAR_DEV_OTP`, `ANTHROPIC_API_KEY`, `SUDHAAR_VISION_MODEL`, `SUDHAAR_YOLO_MODELS`, `SUDHAAR_YOLO_CONF`, `SUDHAAR_YOLO_MAP`, `NEWSAPI_KEY`, `GOOGLE_MAPS_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`,
`SUDHAAR_MAX_UPLOAD_MB`, `SUDHAAR_OFFLINE=1` (skip all external calls).

The app loads settings from the project-root `.env` file at startup. Restart the server after changing it. The local `.env` is ignored by Git; never commit API credentials.

### PostgreSQL / Render
SQLite remains the local default. Set `DATABASE_URL` to a PostgreSQL connection string to use PostgreSQL (Render's `postgres://` and `postgresql://` forms are supported). `psycopg[binary]` is installed from `requirements.txt`.

To copy an existing local SQLite database, create a Render PostgreSQL database, then run this **before deploying/starting the web service** from the project root. Use the database's **External Database URL** for this one-time command so your computer can reach it; do not commit or paste the URL into source files:

```powershell
$env:DATABASE_URL = "<Render External Database URL>"
python -m backend.migrate_sqlite_to_postgres
Remove-Item Env:DATABASE_URL
```

The script reads `data/sudhaar.db` in read-only mode by default. To use a different source file, set `SUDHAAR_SQLITE_PATH` to its path. It refuses to merge into any PostgreSQL destination table that already has rows, copies all records in one transaction, and leaves the SQLite file intact. After it succeeds, connect the Render web service to that PostgreSQL database so Render provides `DATABASE_URL` (prefer the **Internal Database URL** for a service in the same region), then deploy. The service start command is `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`; the build command installs `requirements.txt`.

### Enable external sources
- **NewsAPI:** create an API key at [newsapi.org](https://newsapi.org/), then set `NEWSAPI_KEY=...` in `.env`. Sudhaar searches recent English news for Varanasi and the reported issue.
- **Google Street View metadata:** create a Google Maps Platform project, enable the Street View Static API, enable billing, and create a key restricted to that API. Set `GOOGLE_MAPS_KEY=...`. Sudhaar only checks whether imagery exists and its date; this is historical context, not proof of a current issue.
- **Reddit:** request and receive Reddit Data API access, then create app credentials and set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and a descriptive `REDDIT_USER_AGENT` in `.env`. The Reddit adapter searches recent public posts; it remains inactive until credentials are set. Follow Reddit's Data API terms and approval requirements.
- **YOLO:** `SUDHAAR_YOLO_MODELS` is preconfigured for the two weight files in `weight/`. Install `ultralytics` in the Python environment used to launch Sudhaar. YOLO runs first; Claude vision is only a fallback when `ANTHROPIC_API_KEY` is configured.

After adding keys, restart Sudhaar and submit a test complaint. The AI monitor (`#/ai`) shows whether NewsAPI, Street View, and vision engines are configured and records external lookup errors.
