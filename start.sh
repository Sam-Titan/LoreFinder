#!/bin/sh
set -e

# Combined mode — API + Celery worker/beat in one process group. Convenient
# for local dev (one `docker run`), but NOT what Render should use: the two
# workloads sharing one memory budget let the worker get silently OOM-killed
# mid-ingestion on a 512MB plan while uvicorn stayed up (confirmed live).
# Render should run start-web.sh and start-worker.sh as two separate
# services instead — see README's Deploying section.
celery -A app.tasks.ingestion.celery_app worker --beat --loglevel=info --pool=solo &

# uvicorn is the container's foreground process (exec replaces this shell),
# so Render tracks its lifecycle/health directly. $PORT is assigned by
# Render at runtime; 8000 is only a local-dev fallback.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
