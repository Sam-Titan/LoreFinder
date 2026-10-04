import time

import requests

# Jina's free tier caps at 100,000 tokens/minute (shared across embeddings +
# reranking) — a real novel's chunk text routinely exceeds that in total, so
# hitting 429s partway through ingesting a long book is expected, not an
# error condition, just backpressure. It's a token-bucket limit, not a
# request-count one, and Jina sends no Retry-After header for it — so the
# only correct wait is close to the full per-minute window, not a short
# exponential backoff (confirmed empirically: response body is
# {"detail": "Token rate limit exceeded: X/100,000 tokens per minute...",
# "code": "RATE_TOKEN_LIMIT_EXCEEDED"}, no Retry-After header).
# Retrying here, close to the HTTP call, means only the one rate-limited
# batch is delayed, instead of letting it bubble up and burn one of Celery's
# whole-task retries (which re-runs far more work for a 30s fixed delay that
# can't possibly clear a per-minute window).
_MAX_RETRIES = 10
_DEFAULT_WAIT_SECONDS = 60

def post_with_retry(url: str, headers: dict, json_body: dict, timeout: int) -> requests.Response:
    response = None
    for attempt in range(_MAX_RETRIES):
        response = requests.post(url, headers=headers, json=json_body, timeout=timeout)
        if response.status_code != 429:
            break
        if attempt < _MAX_RETRIES - 1:
            wait = float(response.headers.get("Retry-After", _DEFAULT_WAIT_SECONDS))
            time.sleep(wait)
    response.raise_for_status()
    return response
