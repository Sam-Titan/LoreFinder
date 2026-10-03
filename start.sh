#!/bin/sh
set -e

# Celery worker + beat run in the background, in the same container as the
# API below. --pool=solo (single-threaded, no forked worker processes)
# instead of the default prefork pool: unbounded, prefork auto-detected and
# spawned 16 separate worker processes in testing — each a full Python
# process capable of independently loading the heavy ML stack (torch,
# transformers, chromadb) — using ~4GB of RAM at idle. solo cut that to
# ~1GB (prefork capped at --concurrency=2 only got to ~1.2GB) by never
# forking a second process that re-imports everything. This low-traffic app
# doesn't need parallel task execution anyway.
celery -A app.tasks.ingestion.celery_app worker --beat --loglevel=info --pool=solo &

# uvicorn is the container's foreground process (exec replaces this shell),
# so Render tracks its lifecycle/health directly. $PORT is assigned by
# Render at runtime; 8000 is only a local-dev fallback.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
