from fastapi import FastAPI
from app.api import query, ingest

app = FastAPI(title="Dawn")

app.include_router(ingest.router, prefix="/ingest", tags=["Ingestion"])
app.include_router(query.router, prefix="/query", tags=["Query"])

@app.get("/health")
def health_check():
    status = {"api": "ok", "redis": "unavailable", "celery": "unavailable"}

    # Check Redis
    try:
        import redis
        from app.core.config import settings
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"unavailable: {str(e)}"

    # Check Celery
    try:
        from app.tasks.ingestion import celery_app
        inspect = celery_app.control.inspect(timeout=2)
        workers = inspect.ping()
        status["celery"] = "ok" if workers else "no workers found"
    except Exception as e:
        status["celery"] = f"unavailable: {str(e)}"

    return status