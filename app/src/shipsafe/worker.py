"""Asynchronous worker: polls the job queue and processes messages."""

import logging
import signal
from typing import Any

from shipsafe.config import Settings
from shipsafe.logging_setup import configure_logging
from shipsafe.queue import JobQueue, build_queue

logger = logging.getLogger("shipsafe.worker")


class Worker:
    def __init__(self, queue: JobQueue) -> None:
        self.queue = queue
        self._running = True

    def stop(self, *_: Any) -> None:
        # ECS sends SIGTERM before stopping a task: finish the current batch, then exit.
        logger.info("shutdown requested", extra={"event": "worker_stopping"})
        self._running = False

    def process(self, body: dict[str, Any]) -> None:
        job_id = body.get("job_id")
        if not job_id:
            raise ValueError("message has no job_id")
        # Real work goes here. Keep it idempotent: SQS delivers at least once.
        logger.info("job processed", extra={"job_id": job_id, "event": "job_processed"})

    def run_once(self, wait_seconds: int = 20) -> int:
        """Process one batch. Returns the number of messages handled successfully."""
        handled = 0
        for message in self.queue.receive(wait_seconds=wait_seconds):
            try:
                self.process(message.body)
            except Exception:
                # Not deleted, so SQS redelivers it; repeated failures go to the DLQ.
                logger.exception("job failed", extra={"event": "job_failed"})
                continue
            self.queue.delete(message.receipt)
            handled += 1
        return handled

    def run_forever(self) -> None:
        logger.info("worker started", extra={"event": "worker_started"})
        while self._running:
            self.run_once()
        logger.info("worker stopped", extra={"event": "worker_stopped"})


def main() -> None:
    settings = Settings.from_env()
    configure_logging(f"{settings.service_name}-worker", settings.version, settings.log_level)
    worker = Worker(build_queue(settings.queue_backend, settings.queue_url))
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run_forever()


if __name__ == "__main__":
    main()
