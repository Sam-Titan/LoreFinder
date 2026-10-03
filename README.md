# LoreFinder ("Dawn")

A RAG-based novel and lore analysis tool. Ask questions about a book and get
cited answers pulled from the actual text — no manual re-reading required.

Two ways in:
- **Find a public-domain novel** by title/author — a LangChain + Groq agent
  locates and downloads it from Project Gutenberg, Standard Ebooks, or
  Archive.org, then indexes it for querying.
- **Upload a PDF** directly for temporary, session-scoped Q&A. Nothing about
  the file persists beyond the session's TTL.

The app is intentionally open with no accounts or sign-up — see
[Design notes](#design-notes) below.

## Stack

- **Backend:** FastAPI, Celery + Redis for background ingestion, ChromaDB
  (vector store) + Firestore (document/chunk/chapter metadata), local
  `sentence-transformers` embeddings, Groq + Gemini LLMs via LangChain.
- **Frontend:** React 19 + Vite, React Router.

## Architecture

1. **Acquisition** (`app/services/acquisition.py`) — LangChain agent finds
   and downloads the novel's source text.
2. **Parsing** (`app/services/parser.py`) — cleans text/PDF content and
   detects chapter boundaries.
3. **Chunking** (`app/services/chunker.py`) — overlapping word-count chunks
   per chapter.
4. **Embedding** (`app/services/embedder.py`) — local `sentence-transformers`
   model.
5. **Storage** — chunks go to both Firestore and ChromaDB, in per-document
   collections. PDF uploads only ever reach a temporary Chroma collection —
   no Firestore document is created for them.
6. **Summarization** (`app/services/summarizer.py`) — per-chapter summaries,
   capped at 100 chapters for free-tier LLM rate limits.
7. **Query** (`app/services/query_service.py`) — classifies each question as
   broad (thematic — two-stage chapter-summary → chunk retrieval) or narrow
   (direct chunk vector search), expands it via LLM multi-query, and requires
   citations in the answer.

Ingestion is resumable: a `phase` field on the Firestore doc lets a retried
Celery task pick up where it left off instead of restarting from scratch.

## Getting started

### Prerequisites

- Python 3.11+ and Node 18+
- Redis running locally (`redis://localhost:6379` by default)
- A Firebase/GCP service-account key for Firestore
- A [Chroma Cloud](https://www.trychroma.com/pricing) account + API key (vector storage — see [Design notes](#design-notes) for why this isn't local disk)

### Environment variables

Create a `.env` at the repo root (no `.env.example` is checked in):

```
GROQ_API_KEY=...
GEMINI_API_KEY=...
FIREBASE_CREDENTIALS_PATH=./firebase_credentials.json
CHROMA_API_KEY=...
```

Other tunables (chunk size/overlap, embedding model, session TTL, etc.) live
in `app/core/config.py` with sane defaults.

### Run it

The app's own code has no OS-specific logic — FastAPI, PyMuPDF,
sentence-transformers, ChromaDB, and the frontend all run natively on either
platform. The only real friction is **Celery and Redis**, neither of which
officially supports native Windows: Celery's default worker pool relies on
`os.fork()` (Unix-only), and Redis ships no official Windows build. Pick
whichever path below matches your setup.

#### Linux / WSL2

This is the environment the project is developed and tested in day to day —
everything works exactly as documented, no workarounds needed.

```bash
# Redis (if not already running)
sudo apt install redis-server && sudo service redis-server start
# or: run it via Docker — docker run -d -p 6379:6379 redis

# Backend deps (requirements-dev.txt = requirements.txt + pytest/ruff for local dev)
./venv/bin/pip install -r requirements-dev.txt

# Terminal 1 — API
uvicorn app.main:app --reload

# Terminal 2 — Celery worker (+ beat, for the session cleanup task)
./venv/bin/celery -A app.tasks.ingestion.celery_app worker --beat --loglevel=info

# Terminal 3 — frontend
cd frontend && npm install && npm run dev
```

#### Windows (native)

Runs fine, with two adjustments: venv scripts live under `venv\Scripts\`
instead of `venv/bin/`, and the Celery worker needs `--pool=solo` (or
`--pool=threads`) since the default prefork pool won't start on Windows.

```powershell
# Redis has no official Windows build. Easiest options, in order of effort:
#   1. Run Redis inside WSL2 (see the Linux commands above) and point
#      REDIS_URL/CELERY_BROKER_URL at it — WSL2 services are reachable from
#      Windows at localhost by default.
#   2. Run it via Docker Desktop: docker run -d -p 6379:6379 redis
#   3. Install a third-party Windows build, e.g. Memurai.

# Backend deps (requirements-dev.txt = requirements.txt + pytest/ruff for local dev)
venv\Scripts\pip.exe install -r requirements-dev.txt

# Terminal 1 — API
venv\Scripts\python.exe -m uvicorn app.main:app --reload

# Terminal 2 — Celery worker (+ beat) — note --pool=solo
venv\Scripts\celery.exe -A app.tasks.ingestion.celery_app worker --pool=solo --beat --loglevel=info

# Terminal 3 — frontend (identical to Linux/WSL2 — Node has no OS split here)
cd frontend
npm install
npm run dev
```

`--pool=solo` processes ingestion tasks one at a time instead of in parallel
worker processes — fine for local dev, but if you outgrow it, WSL2 (running
the exact Linux commands above) is the path of least resistance rather than
fighting Celery's Windows support further.

The frontend's API client (`frontend/src/api/lorefinder.js`) points at
`http://127.0.0.1:8000` by default; set `VITE_API_URL` to override it (e.g.
for a deployed backend).

`GET /health` reports API, Redis, and Celery worker status — useful for
confirming everything above is actually up, on either platform.

### Linting

```bash
# Frontend (same on every platform)
cd frontend && npm run lint      # oxlint

# Backend — not yet clean against existing code
./venv/bin/ruff check .          # Linux/WSL2
venv\Scripts\ruff.exe check .    # Windows
```

## Testing

A pytest regression suite lives under `tests/` and runs against a live
backend (`DAWN_API_BASE_URL`, defaults to `http://127.0.0.1:8000`) — it skips
automatically if the backend isn't reachable. Markers: `smoke` (fast narrow
queries), `full` (broad queries needing chapter summarization), `slow`
(100+ chapter novels). Before a fresh test run, clear out data left over from
previous runs — run `document_deletion.py` for Firestore, and delete any
stale collections from the Chroma Cloud dashboard — so stale vectors don't
make results ambiguous.

```bash
./venv/bin/pytest -m smoke      # Linux/WSL2
venv\Scripts\pytest.exe -m smoke  # Windows
```

## Deploying (Render + Netlify)

- **Frontend → Netlify:** base directory `frontend`, build command
  `npm run build`, publish directory `dist`. Set `VITE_API_URL` to your
  Render backend's URL. `frontend/public/_redirects` already handles SPA
  routing so client-side routes don't 404 on refresh.
- **Backend → Render:** provision a managed Redis instance for
  `CELERY_BROKER_URL`/`REDIS_URL`; upload the Firebase credentials JSON via
  Render's Secret Files and point `FIREBASE_CREDENTIALS_PATH` at the mounted
  path; set `CHROMA_API_KEY` as a plain env var; start command needs
  `--host 0.0.0.0 --port $PORT` (Render assigns the port dynamically).
- **No Persistent Disk needed.** Vector storage lives in Chroma Cloud, not
  local disk, so Render's free-tier ephemeral filesystem (wiped on every
  redeploy or idle spin-down) is a non-issue for it — see
  [Design notes](#design-notes). `Dockerfile`/`start.sh` still run uvicorn and
  the Celery worker/beat as one container; that's no longer *required* by a
  shared-disk constraint the way it was with local Chroma, but splitting them
  into separate Render services hasn't been built out, so this remains the
  supported setup unless you change it yourself.

## Design notes

- **No auth, by design.** This app is meant to be usable by anyone with no
  sign-up. Per-IP rate limiting (`slowapi`, in `app/main.py` +
  `app/core/limiter.py`) and input/upload validation are what protect it, not
  access control — a `doc_id`/`session_id` effectively acts as a capability
  token, since anyone holding the exact string can query that document.
- **CORS is wildcard-open** (`allow_origins=["*"]` in `app/main.py`) —
  intentional for an app with no session cookies, but flagged as dev-only.
- **`document_deletion.py`** is a standalone, manually-run maintenance script
  that wipes the entire Firestore `documents` collection. It is not wired
  into the API — don't run it outside of deliberate maintenance/test cleanup.
- **Chroma Cloud, not local disk.** Vector storage uses Chroma's hosted
  service (`CHROMA_API_KEY`) rather than `chromadb.PersistentClient`, so it's
  unaffected by Render's ephemeral filesystem. `ingest_service.rebuild_chroma_if_missing`
  (triggered from `query_service.py` when a novel query comes back with
  zero candidates) still exists as a defensive fallback — it re-embeds
  chunk/chapter text already stored in Firestore if Chroma's copy is ever
  found missing for any reason — but it's no longer the normal-case path the
  way it was when storage reset on every container restart.
