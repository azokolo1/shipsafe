"""Asynchronous worker: polls the job queue, runs each job, records the outcome.

Delivery is at-least-once. A message is deleted only after the outcome is safely
in the database, and a job already marked done is never run again, so a
redelivered message is harmless. A message that keeps failing is not deleted:
SQS redelivers it, and after maxReceiveCount attempts moves it to the DLQ.
"""

import logging
import signal
from typing import Any

from shipsafe.config import Settings
from shipsafe.jobs import run_job
from shipsafe.logging_setup import configure_logging
from shipsafe.queue import JobQueue, build_queue
from shipsafe.store import JobStore, build_store

logger = logging.getLogger("shipsafe.worker")


class Worker:
    def __init__(self, queue: JobQueue, store: JobStore) -> None:
        self.queue = queue
        self.store = store
        self._running = True

    def stop(self, *_: Any) -> None:
        # ECS sends SIGTERM before stopping a task: finish the current job, then exit.
        logger.info("shutdown requested", extra={"event": "worker_stopping"})
        self._running = False

    def process(self, body: dict[str, Any]) -> None:
        job_id = body.get("job_id")
        if not job_id:
            raise ValueError("message has no job_id")

        job = self.store.start(job_id)
        if job is None:
            raise LookupError(f"job {job_id} not found")
        if job.status == "done":
            logger.info(
                "duplicate delivery ignored", extra={"job_id": job_id, "event": "job_duplicate"}
            )
            return

        op = job.payload.get("op", "digest")
        logger.info(
            "job started",
            extra={"job_id": job_id, "event": "job_started", "attempts": job.attempts, "op": op},
        )
        try:
            result = run_job(job.payload)
        except Exception as exc:
            self.store.fail(job_id, f"{type(exc).__name__}: {exc}")
            raise
        self.store.complete(job_id, result)
        logger.info(
            "job done", extra={"job_id": job_id, "event": "job_done", "attempts": job.attempts}
        )

    def run_once(self, wait_seconds: int = 20) -> int:
        """Process one batch. Returns the number of messages handled successfully."""
        handled = 0
        for message in self.queue.receive(max_messages=1, wait_seconds=wait_seconds):
            try:
                self.process(message.body)
            except Exception as exc:
                # Not deleted, so SQS redelivers it; repeated failures go to the DLQ.
                logger.warning(
                    "job attempt failed",
                    extra={
                        "event": "job_failed",
                        "job_id": message.body.get("job_id"),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
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
    worker = Worker(
        build_queue(settings.queue_backend, settings.queue_url),
        build_store(settings),
    )
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run_forever()


if __name__ == "__main__":
    main()
