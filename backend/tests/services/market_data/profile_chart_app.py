"""Measurement-only ASGI wrapper for the isolated F-12 V-17 workload."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from resource import RUSAGE_SELF, getrusage
from time import monotonic

from starlette.types import Message, Receive, Scope, Send

from tiewtrade.services.api.app import app as real_app

MEASURED_PATHS = {
    "/market-data/candles/pages",
    "/market-data/chart/history",
    "/market-data/chart/live",
    "/market-data/chart/verify",
}


def peak_memory_bytes() -> int:
    return int(getrusage(RUSAGE_SELF).ru_maxrss) * 1024


PROCESS_BASELINE_RSS = peak_memory_bytes()


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http" or scope["path"] not in MEASURED_PATHS:
        await real_app(scope, receive, send)
        return
    started = previous = monotonic()
    lag = 0.0
    status = 0
    body_bytes = 0
    error_body = bytearray()

    async def watch() -> None:
        nonlocal previous, lag
        while True:
            await asyncio.sleep(0.05)
            now = monotonic()
            lag = max(lag, now - previous - 0.05)
            previous = now

    async def measured_send(message: Message) -> None:
        nonlocal status, body_bytes
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")
            body_bytes += len(body)
            if status >= 400 and len(error_body) < 512:
                error_body.extend(body[: 512 - len(error_body)])
        await send(message)

    watcher = asyncio.create_task(watch())
    try:
        await real_app(scope, receive, measured_send)
    finally:
        lag = max(lag, monotonic() - previous - 0.05)
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        with Path("/evidence/api-metrics.jsonl").open("a", encoding="utf-8") as output:
            try:
                detail = json.loads(error_body).get("detail") if error_body else None
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                detail = "INVALID_ERROR_BODY"
            output.write(
                json.dumps(
                    {
                        "recorded_at": str(datetime.now(UTC)),
                        "path": scope["path"],
                        "status": status,
                        "seconds": monotonic() - started,
                        "max_lag_seconds": lag,
                        "rss_delta_upper_bytes": max(0, peak_memory_bytes() - PROCESS_BASELINE_RSS),
                        "body_bytes": body_bytes,
                        "error_code": detail if isinstance(detail, str) else None,
                    }
                )
                + "\n"
            )
