from fastapi.testclient import TestClient

from shipsafe.api import create_app
from shipsafe.config import Settings
from shipsafe.queue import InMemoryQueue
from shipsafe.store import InMemoryStore


def make_client() -> tuple[TestClient, InMemoryQueue]:
    queue = InMemoryQueue()
    settings = Settings(
        service_name="shipsafe-test",
        version="test-sha",
        queue_backend="memory",
        queue_url=None,
        log_level="INFO",
    )
    return TestClient(create_app(settings=settings, queue=queue)), queue


def test_index_describes_service():
    client, _ = make_client()
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "shipsafe-test"
    assert body["version"] == "test-sha"
    assert "/healthz" in body["endpoints"]
    assert "POST /jobs" in body["endpoints"]


def test_healthz_ok():
    client, _ = make_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_version():
    client, _ = make_client()
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["version"] == "test-sha"


def test_submit_job_enqueues_message():
    client, queue = make_client()
    response = client.post("/jobs", json={"payload": {"report": "monthly"}})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert len(queue) == 1
    message = queue.receive()[0]
    assert message.body == {"job_id": job_id}  # the payload lives in the database only


def test_request_id_is_propagated():
    client, _ = make_client()
    response = client.get("/healthz", headers={"x-request-id": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


def test_invalid_payload_rejected():
    client, queue = make_client()
    response = client.post("/jobs", json={"payload": "not-an-object"})
    assert response.status_code == 422
    assert len(queue) == 0


def test_job_can_be_read_back():
    client, _ = make_client()
    job_id = client.post("/jobs", json={"payload": {"op": "echo", "message": "hi"}}).json()[
        "job_id"
    ]
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["payload"] == {"op": "echo", "message": "hi"}
    assert body["attempts"] == 0


def test_unknown_job_is_404():
    client, _ = make_client()
    response = client.get("/jobs/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404


def test_malformed_job_id_is_422():
    client, _ = make_client()
    assert client.get("/jobs/not-a-uuid").status_code == 422


def test_enqueue_failure_returns_503_and_records_it():
    class BrokenQueue(InMemoryQueue):
        def send(self, body):
            raise ConnectionError("sqs unreachable")

    store = InMemoryStore()
    settings = Settings(
        service_name="shipsafe-test",
        version="test-sha",
        queue_backend="memory",
        queue_url=None,
        log_level="INFO",
    )
    client = TestClient(create_app(settings=settings, queue=BrokenQueue(), store=store))
    response = client.post("/jobs", json={"payload": {}})
    assert response.status_code == 503
    [job] = store._jobs.values()
    assert job.status == "failed"
    assert job.error == "enqueue failed: ConnectionError"
