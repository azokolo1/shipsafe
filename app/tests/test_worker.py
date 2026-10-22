import pytest

from shipsafe.jobs import MAX_SLEEP_SECONDS, JobFailed, run_job
from shipsafe.queue import InMemoryQueue
from shipsafe.store import InMemoryStore
from shipsafe.worker import Worker


class SpyQueue(InMemoryQueue):
    def __init__(self) -> None:
        super().__init__()
        self.deleted: list[str] = []

    def delete(self, receipt: str) -> None:
        self.deleted.append(receipt)


def make_job(store: InMemoryStore, queue: InMemoryQueue, job_id: str, payload: dict) -> None:
    store.create(job_id, payload)
    queue.send({"job_id": job_id})


def test_successful_job_is_recorded_then_acknowledged():
    store, queue = InMemoryStore(), SpyQueue()
    make_job(store, queue, "j1", {"op": "echo", "message": "hello"})
    assert Worker(queue, store).run_once(wait_seconds=0) == 1
    job = store.get("j1")
    assert job.status == "done"
    assert job.result == {"op": "echo", "echo": "hello"}
    assert job.attempts == 1
    assert queue.deleted == ["1"]


def test_failing_job_is_recorded_and_not_acknowledged():
    store, queue = InMemoryStore(), SpyQueue()
    make_job(store, queue, "j1", {"op": "fail"})
    assert Worker(queue, store).run_once(wait_seconds=0) == 0
    job = store.get("j1")
    assert job.status == "failed"
    assert "op=fail" in job.error
    assert queue.deleted == []  # SQS will redeliver, then dead-letter it


def test_unknown_job_is_not_acknowledged():
    store, queue = InMemoryStore(), SpyQueue()
    queue.send({"job_id": "missing"})
    assert Worker(queue, store).run_once(wait_seconds=0) == 0
    assert queue.deleted == []


def test_message_without_job_id_is_not_acknowledged():
    store, queue = InMemoryStore(), SpyQueue()
    queue.send({"payload": {}})
    assert Worker(queue, store).run_once(wait_seconds=0) == 0
    assert queue.deleted == []


def test_redelivered_done_job_is_acknowledged_without_rerunning():
    store, queue = InMemoryStore(), SpyQueue()
    make_job(store, queue, "j1", {"op": "echo", "message": "once"})
    worker = Worker(queue, store)
    worker.run_once(wait_seconds=0)
    queue.send({"job_id": "j1"})  # SQS delivers the same job again
    assert worker.run_once(wait_seconds=0) == 1
    assert store.get("j1").attempts == 1  # not run a second time
    assert queue.deleted == ["1", "2"]


def test_retry_after_failure_counts_attempts():
    store, queue = InMemoryStore(), SpyQueue()
    make_job(store, queue, "j1", {"op": "fail"})
    worker = Worker(queue, store)
    worker.run_once(wait_seconds=0)
    queue.send({"job_id": "j1"})
    worker.run_once(wait_seconds=0)
    assert store.get("j1").attempts == 2


def test_stop_ends_loop():
    worker = Worker(InMemoryQueue(), InMemoryStore())
    worker.stop()
    worker.run_forever()  # returns immediately instead of polling forever


def test_digest_is_deterministic():
    assert run_job({"b": 2, "a": 1}) == run_job({"a": 1, "b": 2})


@pytest.mark.parametrize("seconds", [-1, MAX_SLEEP_SECONDS + 1, "10"])
def test_sleep_rejects_out_of_range(seconds):
    with pytest.raises(JobFailed):
        run_job({"op": "sleep", "seconds": seconds})


def test_unknown_op_fails():
    with pytest.raises(JobFailed):
        run_job({"op": "rm -rf"})
