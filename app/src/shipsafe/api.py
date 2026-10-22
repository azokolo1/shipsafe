"""HTTP API: health endpoints plus job submission."""

import logging
import time
import uuid
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from shipsafe.config import Settings
from shipsafe.logging_setup import configure_logging
from shipsafe.queue import JobQueue, build_queue
from shipsafe.store import JobStore, build_store

logger = logging.getLogger("shipsafe.api")


class JobRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class JobAccepted(BaseModel):
    job_id: str
    status: str = "queued"


def create_app(
    settings: Settings | None = None,
    queue: JobQueue | None = None,
    store: JobStore | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.service_name, settings.version, settings.log_level)
    # "is None", not "or": an empty InMemoryQueue has len() == 0, so it is falsy.
    job_queue = (
        queue if queue is not None else build_queue(settings.queue_backend, settings.queue_url)
    )
    job_store = store if store is not None else build_store(settings)

    app = FastAPI(title="ShipSafe API", version=settings.version)

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        # Health checks run every few seconds; logging them at INFO would drown real traffic.
        level = logging.DEBUG if request.url.path in ("/healthz", "/readyz") else logging.INFO
        logger.log(
            level,
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    @app.get("/")
    def index() -> dict[str, Any]:
        """Landing response for anyone who opens the URL in a browser."""
        return {
            "service": settings.service_name,
            "version": settings.version,
            "description": "ShipSafe: portfolio ECS delivery platform, not a commercial service",
            "endpoints": ["/healthz", "/readyz", "/version", "POST /jobs", "GET /jobs/{job_id}"],
            "source": "https://github.com/azokolo1/shipsafe",
        }

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Liveness: the process is up. Deliberately checks no dependencies."""
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        """Readiness: safe to receive traffic. Dependency checks are added in M4."""
        return {"status": "ready", "version": settings.version}

    @app.get("/version")
    def version() -> dict[str, str]:
        return {"service": settings.service_name, "version": settings.version}

    @app.post("/jobs", status_code=202, response_model=JobAccepted)
    def submit_job(job: JobRequest) -> JobAccepted:
        job_id = str(uuid.uuid4())
        # Record first, then enqueue: the database is the source of truth and the
        # message carries only the ID. If enqueueing fails, the record says so.
        job_store.create(job_id, job.payload)
        try:
            job_queue.send({"job_id": job_id})
        except Exception as exc:
            job_store.fail(job_id, f"enqueue failed: {type(exc).__name__}")
            logger.exception("enqueue failed", extra={"job_id": job_id, "event": "enqueue_failed"})
            raise HTTPException(status_code=503, detail="job could not be queued") from exc
        logger.info("job queued", extra={"job_id": job_id, "event": "job_queued"})
        return JobAccepted(job_id=job_id)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: UUID) -> dict[str, Any]:
        found = job_store.get(str(job_id))
        if found is None:
            raise HTTPException(status_code=404, detail="job not found")
        return found.to_dict()

    return app
