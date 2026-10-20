import json

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.stub import Stubber

from shipsafe.queue import SqsQueue, build_queue

URL = "https://sqs.eu-west-2.amazonaws.com/123456789012/shipsafe-jobs"


def make_queue():
    # Unsigned client: no credentials needed, and the Stubber intercepts every call.
    client = boto3.client("sqs", region_name="eu-west-2", config=Config(signature_version=UNSIGNED))
    return SqsQueue(URL, client=client), Stubber(client)


def test_send_serialises_body():
    queue, stub = make_queue()
    body = {"job_id": "1"}
    stub.add_response(
        "send_message",
        {"MessageId": "m1"},
        {"QueueUrl": URL, "MessageBody": json.dumps(body)},
    )
    with stub:
        queue.send(body)
    stub.assert_no_pending_responses()


def test_receive_uses_long_polling_and_parses_messages():
    queue, stub = make_queue()
    stub.add_response(
        "receive_message",
        {"Messages": [{"Body": json.dumps({"job_id": "1"}), "ReceiptHandle": "r1"}]},
        {"QueueUrl": URL, "MaxNumberOfMessages": 10, "WaitTimeSeconds": 20},
    )
    with stub:
        messages = queue.receive()
    assert messages[0].body == {"job_id": "1"}
    assert messages[0].receipt == "r1"


def test_build_queue_requires_url_for_sqs():
    with pytest.raises(ValueError):
        build_queue("sqs", None)
