# SAHAYATA — Smart Citizen Support Platform

**Report civic issues. AI routes them. Departments act. Citizens verify.**

SAHAYATA is a full-stack civic-tech platform where citizens report problems (potholes,
water shortage, broken lights…) with text/photo/video/audio + GPS location; an explainable
AI layer classifies and prioritises them; duplicate reports are merged into one *problem
cluster*; departments manage work orders; and citizens **verify resolutions** — closing the
accountability loop.

---

## Quick start

### 0. After a PC restart (one double-click)

```
start.bat     → launches backend + frontend + opens the browser
stop.bat      → stops both
```

Your data lives in `backend/data/sahayata.db` and survives restarts — no
re-install or re-seed needed. The steps below are only for first-time setup.

### 1. Backend (Python 3.13, FastAPI)

```powershell
cd backend
py -V:3.13 -m venv .venv              # regular CPython (NOT free-threaded 3.13t)
.\.venv\Scripts\pip install -r requirements.txt
copy ..\.env.example ..\.env          # then edit SECRET_KEY etc.
.\.venv\Scripts\alembic upgrade head  # or: python -c "from app.db.session import create_all; create_all()"
.\.venv\Scripts\python scripts\seed.py --demo    # adds --reset-demo to wipe demo rows first
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

* API docs: <http://127.0.0.1:8000/docs>
* Default dev DB: SQLite at `backend/data/sahayata.db` (WAL mode).
  Set `DATABASE_URL=postgresql+psycopg://...` for production PostGIS (migration auto-detects dialect).

### 2. Frontend (Node 20+, Vite + React + TS)

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api → :8000)
```

### 3. Demo accounts

| Role | Email | Password |
|---|---|---|
| Citizen | `aarti.demo@sahayata.in` | `demo12345` |
| Authority | `officer.demo@sahayata.in` | `demo12345` |
| Admin | printed once when seed first runs (`admin@sahayata.gov.in`) | — |

Demo rows are always flagged `is_demo=True` and never mix with production records.

### 4. Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests -q   # 31 tests: auth/RBAC, reports+AI pipeline,
                                            # clustering, priority, actions→verification loop
```

---

## What's inside

```
backend/
  app/
    ai/            TF-IDF classifier (bundled dataset), char-ngram dedupe embeddings,
                   rule-based severity/urgency lexicon (EN + romanised Hindi), image analysis
    api/v1/        auth · reports · problems · actions · verifications · map · priorities
                   analytics · simulator · accessibility · notifications · catalog · search
                   admin/users · media · health      (all under /api/v1)
    models/        users/roles/refresh tokens · catalog · clusters/reports/media · work
                   (actions/evidence/verifications) · geo (facilities/gaps) · audit/AI-log
    services/      clustering (geo+text dedupe) · priority engine · pipeline · notify ·
                   storage (local/S3) · uploads · simulator · accessibility · analytics
    core/          config · security (JWT access+refresh rotation) · logging
  migrations/      Alembic (SQLite-safe dev path, PostGIS blocks guarded by dialect)
  scripts/seed.py  base catalog + admin bootstrap + clearly-flagged Ranchi demo dataset
  tests/           pytest suite (31 passing)

frontend/
  src/pages/citizen/    dashboard · new report (map picker, GPS, camera/video/mic,
                        Web-Speech voice input) · my reports
  src/pages/console/    priority queue · problems table · actions board · analytics
  src/pages/admin/      user management · impact simulator
  src/pages/            map (Leaflet layers: clusters/facilities/accessibility gaps)
                        problem detail (priority breakdown, verification UI, work history)
  src/components/       MapCanvas · MediaGallery (authenticated streaming) · badges/layouts
```

## The transparency contract

1. **Priority is a public formula** — severity × scale × vulnerability × neglect time;
   every cluster shows its score breakdown.
2. **Duplicates merge into one problem** so ten neighbours reporting the same broken pipe
   create one work order, not ten tickets.
3. **No resolution closes without evidence** — officers submit notes/photos; reporters get a
   Yes / No / Partial verification vote. A “No” reopens the case automatically.
4. **Privacy by design** — exact citizen coordinates are jittered for public views;
   media streams only to authorised viewers.
5. **AI is assistive & auditable** — every prediction logged (`ai_predictions`), every state
   change recorded (`audit_logs`), graceful degradation if any AI component is unavailable.

## Configuration

Copy `.env.example` → `.env`. Key settings:

| Var | Purpose |
|---|---|
| `SECRET_KEY` | **required** JWT signing key in production |
| `DATABASE_URL` | SQLite (default) or PostgreSQL/PostGIS |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | bootstrap admin (password printed once if unset) |
| `AI_TEXT_ENABLED`, `AI_VISION_PROVIDER`, `OPENAI_API_KEY` | optional upgrades; system runs fully offline without them |
| `STORAGE_DRIVER=s3` + keys | switch uploads from local disk to S3-compatible object storage |

## Notes

* Windows quirk: use regular CPython for the venv — free-threaded 3.13t lacks ML wheels
  (`scikit-learn` pinned `<1.8` accordingly).
* SQLite runs in WAL mode with busy-timeout so background AI tasks don't block requests.
* Production deployments should run Alembic migrations + PostgreSQL with PostGIS enabled.
