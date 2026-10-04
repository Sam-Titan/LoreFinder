# syntax=docker/dockerfile:1
# One image, two possible Render services: start-web.sh (API only) and
# start-worker.sh (Celery worker/beat only), run as separate services so
# ingestion's memory use never competes with API serving on a small plan —
# see README's "Deploying" section. start.sh (both in one container) is kept
# for local dev convenience only; Render should not use it.
FROM python:3.14-slim

WORKDIR /app

# build-essential is a safety net, not a known requirement: this stack's
# heavier deps (torch, chromadb, onnxruntime, pymupdf) usually ship prebuilt
# wheels, but Python 3.14 is very new and a matching wheel isn't guaranteed
# for every package yet. If pip ends up building one from source during
# `docker build`, this is what makes that possible instead of failing outright.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copied and installed before the rest of the source so this layer stays
# cached across builds that don't touch dependencies.
COPY requirements.txt .
# This dependency set is large (torch alone is ~500MB) and slow to
# re-download on every retry — cache pip's downloads across builds instead
# of discarding them, since a killed/failed build was already wasting a
# genuinely long download the first time this was tried.
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY . .
RUN chmod +x start.sh start-web.sh start-worker.sh

# Documents the default for local `docker run`; Render overrides this with
# its own dynamically-assigned $PORT at runtime regardless (see start.sh).
EXPOSE 8000

CMD ["./start.sh"]
