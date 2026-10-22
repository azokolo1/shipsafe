"""Schema migrations: apply src/shipsafe/migrations/*.sql in order, once each.

Runs as a one-off ECS task with the RDS master credentials (injected from Secrets
Manager), never from the application. An advisory lock makes concurrent runs safe.
"""

import logging
from importlib.resources import files

import psycopg

from shipsafe.config import Settings
from shipsafe.logging_setup import configure_logging

logger = logging.getLogger("shipsafe.migrate")

_LOCK_ID = 727_001  # arbitrary, fixed: any concurrent migrate run waits on it


def migration_files() -> list[tuple[str, str]]:
    folder = files("shipsafe") / "migrations"
    names = sorted(p.name for p in folder.iterdir() if p.name.endswith(".sql"))
    return [(name.removesuffix(".sql"), (folder / name).read_text()) for name in names]


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations; returns the versions applied by this run."""
    applied_now: list[str] = []
    conn.autocommit = True
    conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK_ID,))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for version, sql in migration_files():
            if version in done:
                continue
            with conn.transaction():
                conn.execute(sql.encode())  # bytes: run the file as a script, unparameterised
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            logger.info(
                "migration applied", extra={"event": "migration_applied", "migration": version}
            )
            applied_now.append(version)
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))
    return applied_now


def main() -> None:
    settings = Settings.from_env()
    configure_logging(f"{settings.service_name}-migrate", settings.version, settings.log_level)
    from shipsafe.db import connect

    with connect(settings) as conn:
        applied = apply_migrations(conn)
    logger.info(
        "migrations complete", extra={"event": "migrations_complete", "count": len(applied)}
    )


if __name__ == "__main__":
    main()
