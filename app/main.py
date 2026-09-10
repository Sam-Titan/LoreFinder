from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import query, ingest

app = FastAPI(title="Dawn")

# Explicit OPTIONS handler — catches preflight before routing
@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # wildcard for dev
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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