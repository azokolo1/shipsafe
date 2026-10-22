"""Integration tests against a real PostgreSQL. Skipped unless TEST_DB_HOST is set
(CI runs a Postgres service container; locally, point it at any disposable server).
Each test run creates and drops its own database."""

import os
import uuid

import psycopg
import pytest
from psycopg_pool import ConnectionPool

from shipsafe.migrate import apply_migrations, migration_files
from shipsafe.queue import InMemoryQueue
from shipsafe.store import PostgresStore
from shipsafe.worker import Worker

HOST = os.getenv("TEST_DB_HOST")
if os.getenv("REQUIRE_DB_TESTS") == "1" and not HOST:
    # CI sets this, so a misconfigured pipeline fails instead of silently skipping.
    raise RuntimeError("REQUIRE_DB_TESTS=1 but TEST_DB_HOST is not set")
pytestmark = pytest.mark.skipif(not HOST, reason="TEST_DB_HOST not set")


def _conninfo(dbname: str) -> dict:
    return {
        "host": HOST,
        "port": int(os.getenv("TEST_DB_PORT", "5432")),
        "user": os.getenv("TEST_DB_USER", "postgres"),
        "password": os.getenv("PGPASSWORD"),
        "dbname": dbname,
    }


@pytest.fixture(scope="module")
def dbname():
    name = f"shipsafe_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(**_conninfo("postgres"), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
    with psycopg.connect(**_conninfo(name)) as conn:
        apply_migrations(conn)
    yield name
    with psycopg.connect(**_conninfo("postgres"), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def store(dbname):
    pool = ConnectionPool(kwargs=_conninfo(dbname), min_size=1, max_size=2, open=True)
    yield PostgresStore(pool)
    pool.close()


def test_migrations_are_recorded_and_idempotent(dbname):
    with psycopg.connect(**_conninfo(dbname)) as conn:
        assert apply_migrations(conn) == []  # second run applies nothing
        versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY 1")]
    assert versions == [v for v, _ in migration_files()]


def test_job_lifecycle(store):
    job_id = str(uuid.uuid4())
    created = store.create(job_id, {"op": "echo", "message": "hi"})
    assert created.status == "queued"
    started = store.start(job_id)
    assert (started.status, started.attempts) == ("processing", 1)
    store.complete(job_id, {"echo": "hi"})
    done = store.get(job_id)
    assert (done.status, done.result) == ("done", {"echo": "hi"})
    # A finished job is never restarted (duplicate delivery).
    again = store.start(job_id)
    assert (again.status, again.attempts) == ("done", 1)
    # ...and a late failure report cannot overwrite it.
    store.fail(job_id, "late")
    assert store.get(job_id).status == "done"


def test_unknown_job(store):
    assert store.get(str(uuid.uuid4())) is None
    assert store.start(str(uuid.uuid4())) is None


def test_worker_end_to_end(store):
    queue = InMemoryQueue()
    job_id = str(uuid.uuid4())
    store.create(job_id, {"op": "digest", "n": 1})
    queue.send({"job_id": job_id})
    assert Worker(queue, store).run_once(wait_seconds=0) == 1
    job = store.get(job_id)
    assert job.status == "done"
    assert len(job.result["sha256"]) == 64


def test_app_role_is_least_privilege(dbname):
    with psycopg.connect(**_conninfo(dbname)) as conn:
        conn.execute("SET ROLE shipsafe_app")
        job_id = uuid.uuid4()
        conn.execute(
            "INSERT INTO jobs (id, status, payload) VALUES (%s, 'queued', '{}')", (job_id,)
        )
        conn.execute("UPDATE jobs SET status = 'processing' WHERE id = %s", (job_id,))
        assert conn.execute("SELECT count(*) FROM jobs WHERE id = %s", (job_id,)).fetchone() == (1,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        conn.rollback()
        conn.execute("SET ROLE shipsafe_app")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE sneaky (id int)")


def test_build_pool_connects_with_settings(dbname):
    from shipsafe.config import Settings
    from shipsafe.db import build_pool

    settings = Settings(
        service_name="shipsafe-test",
        version="test-sha",
        queue_backend="memory",
        queue_url=None,
        log_level="INFO",
        db_backend="postgres",
        db_host=HOST,
        db_port=int(os.getenv("TEST_DB_PORT", "5432")),
        db_name=dbname,
        db_user=os.getenv("TEST_DB_USER", "postgres"),
        db_auth="password",
        db_password=os.getenv("PGPASSWORD") or "unused-by-trust-auth",
        db_sslmode=os.getenv("TEST_DB_SSLMODE", "disable"),
    )
    pool = build_pool(settings)
    try:
        with pool.connection() as conn:
            assert conn.execute("SELECT 1").fetchone() == (1,)
    finally:
        pool.close()
