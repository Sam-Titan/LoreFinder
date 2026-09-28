#!/bin/sh
set -e

# Celery worker + beat run in the background, in the same container (and on
# the same mounted disk) as the API below — see README's "Deploying" section
# for why they can't be split into separate Render services here.
celery -A app.tasks.ingestion.celery_app worker --beat --loglevel=info &

# uvicorn is the container's foreground process (exec replaces this shell),
# so Render tracks its lifecycle/health directly. $PORT is assigned by
# Render at runtime; 8000 is only a local-dev fallback.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
