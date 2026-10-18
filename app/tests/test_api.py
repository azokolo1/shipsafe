from fastapi.testclient import TestClient

from shipsafe.api import create_app
from shipsafe.config import Settings
from shipsafe.queue import InMemoryQueue


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
    assert message.body == {"job_id": job_id, "payload": {"report": "monthly"}}


def test_request_id_is_propagated():
    client, _ = make_client()
    response = client.get("/healthz", headers={"x-request-id": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"


def test_invalid_payload_rejected():
    client, queue = make_client()
    response = client.post("/jobs", json={"payload": "not-an-object"})
    assert response.status_code == 422
    assert len(queue) == 0
