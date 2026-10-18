"""Job queue abstraction: in-memory for local development and tests, SQS in AWS."""

import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Message:
    body: dict[str, Any]
    receipt: str  # opaque handle used to delete (acknowledge) the message


class JobQueue(Protocol):
    def send(self, body: dict[str, Any]) -> None: ...
    def receive(self, max_messages: int = 10, wait_seconds: int = 20) -> list[Message]: ...
    def delete(self, receipt: str) -> None: ...


class InMemoryQueue:
    def __init__(self) -> None:
        self._items: deque[Message] = deque()
        self._counter = 0

    def send(self, body: dict[str, Any]) -> None:
        self._counter += 1
        self._items.append(Message(body=body, receipt=str(self._counter)))

    def receive(self, max_messages: int = 10, wait_seconds: int = 0) -> list[Message]:
        if not self._items and wait_seconds > 0:
            # Mimic SQS long polling so an idle local worker does not spin the CPU.
            time.sleep(min(wait_seconds, 1))
        batch: list[Message] = []
        while self._items and len(batch) < max_messages:
            batch.append(self._items.popleft())
        return batch

    def delete(self, receipt: str) -> None:
        # Messages are removed on receive; nothing to acknowledge.
        return None

    def __len__(self) -> int:
        return len(self._items)


class SqsQueue:
    def __init__(self, queue_url: str, client: Any | None = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("sqs")
        self._client = client
        self._url = queue_url

    def send(self, body: dict[str, Any]) -> None:
        self._client.send_message(QueueUrl=self._url, MessageBody=json.dumps(body))

    def receive(self, max_messages: int = 10, wait_seconds: int = 20) -> list[Message]:
        response = self._client.receive_message(
            QueueUrl=self._url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_seconds,  # long polling: fewer empty, billable requests
        )
        return [
            Message(body=json.loads(m["Body"]), receipt=m["ReceiptHandle"])
            for m in response.get("Messages", [])
        ]

    def delete(self, receipt: str) -> None:
        self._client.delete_message(QueueUrl=self._url, ReceiptHandle=receipt)


def build_queue(backend: str, queue_url: str | None) -> JobQueue:
    if backend == "memory":
        return InMemoryQueue()
    if backend == "sqs":
        if not queue_url:
            raise ValueError("QUEUE_URL must be set when QUEUE_BACKEND=sqs")
        return SqsQueue(queue_url)
    raise ValueError(f"Unknown QUEUE_BACKEND: {backend!r}")
