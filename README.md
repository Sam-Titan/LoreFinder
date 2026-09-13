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

### Environment variables

Create a `.env` at the repo root (no `.env.example` is checked in):

```
GROQ_API_KEY=...
GEMINI_API_KEY=...
FIREBASE_CREDENTIALS_PATH=./firebase_credentials.json
```

Other tunables (chunk size/overlap, embedding model, Chroma persist path,
session TTL, etc.) live in `app/core/config.py` with sane defaults.

### Run it

```bash
# Backend deps
./venv/bin/pip install -r requirements.txt

# Terminal 1 — API
uvicorn app.main:app --reload

# Terminal 2 — Celery worker (+ beat, for the session cleanup task)
./venv/bin/celery -A app.tasks.ingestion.celery_app worker --beat --loglevel=info

# Terminal 3 — frontend
cd frontend && npm install && npm run dev
```

The frontend's API client (`frontend/src/api/dawn.js`) points at
`http://127.0.0.1:8000` by default; set `VITE_API_URL` to override it (e.g.
for a deployed backend).

`GET /health` reports API, Redis, and Celery worker status — useful for
confirming everything above is actually up.

### Linting

```bash
# Frontend
cd frontend && npm run lint      # oxlint

# Backend
./venv/bin/ruff check .          # not yet clean against existing code
```

## Testing

A pytest regression suite lives under `tests/` and runs against a live
backend (`DAWN_API_BASE_URL`, defaults to `http://127.0.0.1:8000`) — it skips
automatically if the backend isn't reachable. Markers: `smoke` (fast narrow
queries), `full` (broad queries needing chapter summarization), `slow`
(100+ chapter novels). Before a fresh test run, clear out data left over from
previous runs (delete `chroma_store/` and run `document_deletion.py`) so
stale vectors don't make results ambiguous.

```bash
./venv/bin/pytest -m smoke
```

## Deploying (Render + Netlify)

- **Frontend → Netlify:** base directory `frontend`, build command
  `npm run build`, publish directory `dist`. Set `VITE_API_URL` to your
  Render backend's URL. `frontend/public/_redirects` already handles SPA
  routing so client-side routes don't 404 on refresh.
- **Backend → Render:** provision a managed Redis instance for
  `CELERY_BROKER_URL`/`REDIS_URL`; upload the Firebase credentials JSON via
  Render's Secret Files and point `FIREBASE_CREDENTIALS_PATH` at the mounted
  path; start command needs `--host 0.0.0.0 --port $PORT` (Render assigns the
  port dynamically).
- **Persistent storage gotcha:** Render disks are ephemeral unless you attach
  a paid Persistent Disk, and a disk attaches to exactly one service. Since
  both the API (queries) and the Celery worker (ingestion) read/write the
  same local `chroma_store/`, run them as **one** Render service (a single
  start script backgrounding the Celery worker + beat, then running uvicorn
  in the foreground) sharing one Persistent Disk — splitting them into
  separate services would give each an unsynced copy of the vector store.

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
