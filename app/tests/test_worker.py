from shipsafe.queue import InMemoryQueue
from shipsafe.worker import Worker


def test_worker_processes_valid_jobs():
    queue = InMemoryQueue()
    queue.send({"job_id": "1", "payload": {}})
    queue.send({"job_id": "2", "payload": {}})
    assert Worker(queue).run_once(wait_seconds=0) == 2
    assert len(queue) == 0


def test_worker_does_not_acknowledge_bad_message():
    deleted: list[str] = []

    class SpyQueue(InMemoryQueue):
        def delete(self, receipt: str) -> None:
            deleted.append(receipt)

    queue = SpyQueue()
    queue.send({"payload": {}})  # missing job_id -> processing fails
    queue.send({"job_id": "ok", "payload": {}})
    assert Worker(queue).run_once(wait_seconds=0) == 1
    assert deleted == ["2"]  # only the good message is acknowledged


def test_stop_ends_loop():
    worker = Worker(InMemoryQueue())
    worker.stop()
    worker.run_forever()  # returns immediately instead of polling forever
