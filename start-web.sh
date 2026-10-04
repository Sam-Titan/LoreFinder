#!/bin/sh
set -e

# API only — no Celery worker. Meant to run as a separate Render service from
# start-worker.sh, each with its own memory budget. Running both in one
# container (start.sh) let ingestion's real memory use (LangChain agent,
# parsing/chunking, Jina/Chroma/Firestore HTTP clients) compete with API
# serving for the same limit — on a 512MB plan, confirmed live, this let the
# Celery worker process get silently OOM-killed mid-task by the kernel while
# uvicorn stayed up, leaving ingestion stuck on "processing" forever with no
# further error. Splitting the services removes that contention entirely.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
