"""What a job actually does. Deliberately small: the point of ShipSafe is how jobs
move through the platform, not the work itself. The "fail" and "sleep" operations
exist so retries, the dead-letter queue and task loss can be tested on purpose."""

import hashlib
import json
import time
from typing import Any

MAX_SLEEP_SECONDS = 60  # must stay below the SQS visibility timeout


class JobFailed(Exception):
    """The job cannot succeed as requested; retrying will not help."""


def run_job(payload: dict[str, Any]) -> dict[str, Any]:
    op = payload.get("op", "digest")
    if op == "digest":
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return {"op": op, "sha256": hashlib.sha256(canonical).hexdigest()}
    if op == "echo":
        return {"op": op, "echo": payload.get("message")}
    if op == "sleep":
        seconds = payload.get("seconds", 1)
        if not isinstance(seconds, int | float) or not 0 <= seconds <= MAX_SLEEP_SECONDS:
            raise JobFailed(f"seconds must be between 0 and {MAX_SLEEP_SECONDS}")
        time.sleep(seconds)
        return {"op": op, "slept_seconds": seconds}
    if op == "fail":
        raise JobFailed("failure requested by payload (op=fail)")
    raise JobFailed(f"unknown op: {op!r}")
