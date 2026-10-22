"""Runtime configuration, read once from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str
    version: str
    queue_backend: str  # "memory" (local/tests) or "sqs"
    queue_url: str | None
    log_level: str
    # Job store. "memory" for local runs and unit tests, "postgres" in AWS.
    db_backend: str = "memory"
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "shipsafe"
    db_user: str = "shipsafe_app"
    # "iam": short-lived token from the task role (the app in AWS; no password exists).
    # "password": local runs, CI, and the migration task (master secret from Secrets Manager).
    db_auth: str = "iam"
    db_password: str | None = None
    db_sslmode: str = "verify-full"
    db_sslrootcert: str | None = None
    aws_region: str = "eu-west-2"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            service_name=os.getenv("SERVICE_NAME", "shipsafe"),
            version=os.getenv("APP_VERSION", "dev"),
            queue_backend=os.getenv("QUEUE_BACKEND", "memory"),
            queue_url=os.getenv("QUEUE_URL"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            db_backend=os.getenv("DB_BACKEND", "memory"),
            db_host=os.getenv("DB_HOST"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_name=os.getenv("DB_NAME", "shipsafe"),
            db_user=os.getenv("DB_USER", "shipsafe_app"),
            db_auth=os.getenv("DB_AUTH", "iam"),
            db_password=os.getenv("DB_PASSWORD"),
            db_sslmode=os.getenv("DB_SSLMODE", "verify-full"),
            db_sslrootcert=os.getenv("DB_SSLROOTCERT"),
            aws_region=os.getenv("AWS_REGION", "eu-west-2"),
        )
