"""Job records. The database is the source of truth for a job; the queue only
carries its ID. In memory for unit tests and local runs, PostgreSQL in AWS."""

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

STATUSES = ("queued", "processing", "done", "failed")


@dataclass(frozen=True)
class Job:
    id: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    attempts: int
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "status": self.status,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class JobStore(Protocol):
    def create(self, job_id: str, payload: dict[str, Any]) -> Job: ...
    def get(self, job_id: str) -> Job | None: ...
    def start(self, job_id: str) -> Job | None: ...
    def complete(self, job_id: str, result: dict[str, Any]) -> None: ...
    def fail(self, job_id: str, error: str) -> None: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, job_id: str, payload: dict[str, Any]) -> Job:
        now = datetime.now(UTC)
        job = Job(job_id, "queued", payload, None, None, 0, now, now)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def start(self, job_id: str) -> Job | None:
        job = self._jobs.get(job_id)
        if job is None or job.status == "done":
            return job
        job = replace(job, status="processing", attempts=job.attempts + 1, updated_at=_now())
        self._jobs[job_id] = job
        return job

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        job = self._jobs[job_id]
        self._jobs[job_id] = replace(
            job, status="done", result=result, error=None, updated_at=_now()
        )

    def fail(self, job_id: str, error: str) -> None:
        job = self._jobs.get(job_id)
        if job is not None:
            self._jobs[job_id] = replace(job, status="failed", error=error, updated_at=_now())


class PostgresStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def create(self, job_id: str, payload: dict[str, Any]) -> Job:
        row = self._one(
            "INSERT INTO jobs (id, status, payload) VALUES (%s, 'queued', %s) "
            "RETURNING id, status, payload, result, error, attempts, created_at, updated_at",
            (uuid.UUID(job_id), Jsonb(payload)),
        )
        if row is None:  # INSERT ... RETURNING always returns the row
            raise RuntimeError("insert returned no row")
        return row

    def get(self, job_id: str) -> Job | None:
        return self._one(
            "SELECT id, status, payload, result, error, attempts, created_at, updated_at "
            "FROM jobs WHERE id = %s",
            (uuid.UUID(job_id),),
        )

    def start(self, job_id: str) -> Job | None:
        # A finished job is never re-run: SQS can deliver a message more than once.
        job = self._one(
            "UPDATE jobs SET status = 'processing', attempts = attempts + 1, updated_at = now() "
            "WHERE id = %s AND status <> 'done' "
            "RETURNING id, status, payload, result, error, attempts, created_at, updated_at",
            (uuid.UUID(job_id),),
        )
        return job if job is not None else self.get(job_id)

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        self._exec(
            "UPDATE jobs SET status = 'done', result = %s, error = NULL, updated_at = now() "
            "WHERE id = %s",
            (Jsonb(result), uuid.UUID(job_id)),
        )

    def fail(self, job_id: str, error: str) -> None:
        self._exec(
            "UPDATE jobs SET status = 'failed', error = %s, updated_at = now() "
            "WHERE id = %s AND status <> 'done'",
            (error[:1000], uuid.UUID(job_id)),
        )

    def _one(self, sql: str, params: tuple[Any, ...]) -> Job | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        if row is None:
            return None
        return Job(
            id=str(row["id"]),
            status=row["status"],
            payload=row["payload"],
            result=row["result"],
            error=row["error"],
            attempts=row["attempts"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _exec(self, sql: str, params: tuple[Any, ...]) -> None:
        with self._pool.connection() as conn:
            conn.execute(sql, params)


def _now() -> datetime:
    return datetime.now(UTC)


def build_store(settings: Any) -> JobStore:
    if settings.db_backend == "memory":
        return InMemoryStore()
    if settings.db_backend == "postgres":
        from shipsafe.db import build_pool

        return PostgresStore(build_pool(settings))
    raise ValueError(f"Unknown DB_BACKEND: {settings.db_backend!r}")
