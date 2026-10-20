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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            service_name=os.getenv("SERVICE_NAME", "shipsafe"),
            version=os.getenv("APP_VERSION", "dev"),
            queue_backend=os.getenv("QUEUE_BACKEND", "memory"),
            queue_url=os.getenv("QUEUE_URL"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
