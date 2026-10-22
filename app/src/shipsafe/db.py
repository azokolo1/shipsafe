"""PostgreSQL connections.

In AWS the application has no database password: each new connection is opened
with an IAM authentication token, generated from the ECS task role and valid for
15 minutes (connecting only; an open connection is unaffected when it expires).
Local runs, CI and the migration task use a password instead.
"""

from collections.abc import Callable
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from shipsafe.config import Settings


def password_provider(settings: Settings, rds_client: Any | None = None) -> Callable[[], str]:
    if settings.db_auth == "iam":
        if rds_client is None:
            import boto3

            rds_client = boto3.client("rds", region_name=settings.aws_region)

        def iam_token() -> str:
            # Signed locally with the task role's credentials: no API call, no secret.
            return rds_client.generate_db_auth_token(
                DBHostname=settings.db_host,
                Port=settings.db_port,
                DBUsername=settings.db_user,
                Region=settings.aws_region,
            )

        return iam_token

    if settings.db_auth == "password":
        if not settings.db_password:
            raise ValueError("DB_PASSWORD must be set when DB_AUTH=password")
        password = settings.db_password
        return lambda: password

    raise ValueError(f"Unknown DB_AUTH: {settings.db_auth!r}")


def connect_kwargs(settings: Settings) -> dict[str, Any]:
    if not settings.db_host:
        raise ValueError("DB_HOST must be set when DB_BACKEND=postgres")
    kwargs: dict[str, Any] = {
        "host": settings.db_host,
        "port": settings.db_port,
        "dbname": settings.db_name,
        "user": settings.db_user,
        "sslmode": settings.db_sslmode,
        "connect_timeout": 5,
        "application_name": settings.service_name,
    }
    if settings.db_sslrootcert:
        kwargs["sslrootcert"] = settings.db_sslrootcert
    return kwargs


def connect(settings: Settings, rds_client: Any | None = None) -> psycopg.Connection:
    """One-off connection (migrations)."""
    password = password_provider(settings, rds_client)
    return psycopg.connect(**connect_kwargs(settings), password=password())


def build_pool(settings: Settings, rds_client: Any | None = None) -> ConnectionPool:
    """Small pool for the API and worker. kwargs is a callable, so every new
    connection gets a fresh token; connections are recycled within 10 minutes."""
    password = password_provider(settings, rds_client)
    base = connect_kwargs(settings)
    return ConnectionPool(
        kwargs=lambda: {**base, "password": password()},
        min_size=1,
        max_size=4,
        max_lifetime=600,
        timeout=5,
        open=True,
        name=settings.service_name,
    )
