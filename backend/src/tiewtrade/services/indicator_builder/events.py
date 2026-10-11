"""Fixed operational records; never pass exception/input/config text here."""

import json
import sys
from uuid import UUID


def record(event: str, owner: UUID | None, status: str | None = None) -> None:
    payload = {"component": "indicator-builder", "event": event}
    if owner is not None:
        payload["owner"] = str(owner)
    if status is not None:
        payload["status"] = status
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()
