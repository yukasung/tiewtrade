"""V-17 consumer budget/failure matrix; real endpoint lifecycle is tested separately."""

from typing import Any

import httpx
import pytest

from tests.api.indicator_refresh_consumer import refresh_once


@pytest.mark.parametrize(
    "scenario,expected,polls,reads",
    [
        ("pending", "STOPPED", 5, 0),
        ("failed", "STOPPED", 1, 0),
        ("unavailable", "STOPPED", 1, 0),
        ("poll401", "STOPPED", 1, 0),
        ("poll503", "STOPPED", 1, 0),
        ("post401", "STOPPED", 0, 0),
        ("post_timeout", "STOPPED", 0, 0),
        ("poll_timeout", "STOPPED", 1, 0),
        ("complete_blocked", "REFRESH_REQUIRED", 1, 1),
        ("post200", "READY", 0, 1),
        ("restart", "READY", 1, 2),
        ("restart_exhausted", "STOPPED", 1, 2),
        ("indicator401", "STOPPED", 1, 1),
        ("ready", "READY", 1, 1),
    ],
)
async def test_consumer_limits_and_terminal_failures(
    scenario: str,
    expected: str,
    polls: int,
    reads: int,
) -> None:
    calls: list[tuple[str, str]] = []
    seconds: list[float] = []
    now = 0.0
    indicator_reads = 0
    initial: dict[str, Any] = {
        "dataset_revision": "old",
        "refresh": {
            "required": True,
            "target": {"base": "BTC", "quote": "USDT", "timeframe": "4h"},
            "more_required": True,
        },
    }

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal indicator_reads
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            if scenario == "post_timeout":
                raise httpx.ReadTimeout("unknown outcome", request=request)
            return httpx.Response(
                401 if scenario == "post401" else 200 if scenario == "post200" else 202, json={}
            )
        if request.url.path.endswith("/candles"):
            if scenario == "poll_timeout":
                raise httpx.ReadTimeout("unavailable", request=request)
            return httpx.Response(
                401 if scenario == "poll401" else 503 if scenario == "poll503" else 200,
                json={
                    "status": scenario.upper()
                    if scenario in ("failed", "unavailable")
                    else "COMPLETE",
                    "failure_code": None,
                    "refresh_pending": scenario == "pending",
                },
            )
        indicator_reads += 1
        status = (
            409
            if scenario == "restart_exhausted" or (scenario == "restart" and indicator_reads == 1)
            else 401
            if scenario == "indicator401"
            else 200
        )
        return httpx.Response(
            status,
            json={
                "dataset_revision": "new",
                "refresh": {
                    "required": scenario == "complete_blocked",
                    "more_required": True,
                },
            },
        )

    async def advance(duration: float) -> None:
        nonlocal now
        seconds.append(duration)
        now += duration

    with httpx.Client(
        transport=httpx.MockTransport(respond), base_url="http://testserver"
    ) as client:
        result = await refresh_once(
            client, initial, {"page_size": 25}, {}, advance, requested=True, clock=lambda: now
        )
    assert result.status == expected
    assert result.polls == polls
    assert seconds == [10] * (polls + (scenario == "pending"))
    assert indicator_reads == reads
    assert sum(method == "POST" for method, _ in calls) == 1
    if reads:
        assert all(page["dataset_revision"] != "old" for page in result.pages)


async def test_get_never_authorizes_a_refresh_action() -> None:
    def forbidden(request: httpx.Request) -> httpx.Response:
        raise AssertionError("automatic HTTP action")

    async def advance(duration: float) -> None:
        raise AssertionError("automatic polling")

    initial = {"refresh": {"required": True, "target": {"base": "BTC"}}}
    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        result = await refresh_once(client, initial, {}, {}, advance, requested=False)
    assert result.status == "UNCHANGED"


@pytest.mark.parametrize(
    "post_seconds,poll_seconds,read_seconds,expected,polls",
    [
        (60, 0, 0, "STOPPED", 0),
        (61, 0, 0, "STOPPED", 0),
        (49, 0, 0, "READY", 1),
        (49, 1, 0, "STOPPED", 1),
        (0, 51, 0, "STOPPED", 1),
        (0, 0, 50, "STOPPED", 1),
        (0, 0, 49, "READY", 1),
    ],
)
async def test_total_deadline_includes_http_and_rejects_late_success(
    post_seconds: float,
    poll_seconds: float,
    read_seconds: float,
    expected: str,
    polls: int,
) -> None:
    now = 0.0
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal now
        assert now < 60  # Never start another request at/after the deadline.
        assert request.extensions["timeout"]["read"] == 60 - now
        calls.append(request.url.path)
        if request.method == "POST":
            now += post_seconds
            return httpx.Response(202, json={})
        if request.url.path.endswith("/candles"):
            now += poll_seconds
            return httpx.Response(
                200, json={"status": "COMPLETE", "failure_code": None, "refresh_pending": False}
            )
        now += read_seconds
        return httpx.Response(200, json={"refresh": {"required": False}})

    async def advance(seconds: float) -> None:
        nonlocal now
        now += seconds

    initial = {"refresh": {"required": True, "target": {"base": "BTC"}}}
    with httpx.Client(transport=httpx.MockTransport(respond), base_url="http://test") as client:
        result = await refresh_once(
            client, initial, {}, {}, advance, requested=True, clock=lambda: now
        )
    assert result.status == expected and result.polls == polls
    assert calls.count("/market-data/candles/requests") == 1


async def test_slow_pending_polls_stop_at_total_deadline() -> None:
    now = 0.0
    starts: list[float] = []

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal now
        starts.append(now)
        now += 11
        return httpx.Response(
            202 if request.method == "POST" else 200,
            json={"status": "PENDING", "failure_code": None, "refresh_pending": True},
        )

    async def advance(seconds: float) -> None:
        nonlocal now
        now += seconds

    initial = {"refresh": {"required": True, "target": {"base": "BTC"}}}
    with httpx.Client(transport=httpx.MockTransport(respond), base_url="http://test") as client:
        result = await refresh_once(
            client, initial, {}, {}, advance, requested=True, clock=lambda: now
        )
    assert result.status == "STOPPED" and result.polls == 2
    assert starts == [0, 21, 42] and now == 60
