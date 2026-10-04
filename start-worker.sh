#!/bin/sh
set -e

# Celery worker + beat only — no uvicorn. See start-web.sh for why this runs
# as its own Render service instead of sharing a container with the API.
# --pool=solo (single-threaded, no forked worker processes) instead of the
# default prefork pool: unbounded, prefork auto-detected and spawned 16
# separate worker processes in testing, each independently loading the full
# app — using ~4GB of RAM at idle. This low-traffic app doesn't need
# parallel task execution anyway.
exec celery -A app.tasks.ingestion.celery_app worker --beat --loglevel=info --pool=solo
