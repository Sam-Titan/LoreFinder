import os
import time

import pytest
import requests

BASE_URL = os.environ.get("DAWN_API_BASE_URL", "http://127.0.0.1:8000")

# Cached across the whole test session so multiple query tests against the same
# novel don't each pay for a fresh ingestion — the /ingest/novel endpoint itself
# already returns the existing doc_id for a known title/author, so this cache is
# just an in-process shortcut on top of that.
_doc_id_cache: dict[str, str] = {}


@pytest.fixture(scope="session", autouse=True)
def backend_available():
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        resp.raise_for_status()
    except Exception as e:
        pytest.skip(
            f"Backend not reachable at {BASE_URL} ({e}). "
            "Start uvicorn + a Celery worker + Redis before running these tests."
        )


def ensure_ingested(novel: dict, timeout: int = 900) -> str:
    """POST /ingest/novel and poll /ingest/status until fully indexed.

    novel: {"title": str, "author": str}. Returns the doc_id.
    """
    key = f"{novel['title']}|{novel['author']}"
    if key in _doc_id_cache:
        return _doc_id_cache[key]

    resp = requests.post(
        f"{BASE_URL}/ingest/novel",
        json={"novel_name": novel["title"], "author_name": novel["author"]},
        timeout=30,
    )
    resp.raise_for_status()
    doc_id = resp.json()["doc_id"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        status_resp = requests.get(f"{BASE_URL}/ingest/status/{doc_id}", timeout=10)
        status_resp.raise_for_status()
        data = status_resp.json()
        if data["status"] == "failed":
            pytest.fail(f"Ingestion failed for '{novel['title']}': {data}")
        if data.get("progress") == "fully indexed":
            _doc_id_cache[key] = doc_id
            return doc_id
        time.sleep(5)

    pytest.fail(f"Ingestion timed out for '{novel['title']}' after {timeout}s")


def run_query(doc_id: str, query: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/query/",
        json={"doc_id": doc_id, "query": query},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()
