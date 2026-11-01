import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tiewtrade.services.engine import risk_limit_main
from tiewtrade.services.engine.kill_switch import StopRound
from tiewtrade.services.engine.risk_limit import RiskRequestRound


def test_stop_poll_delay_is_bounded_and_rejects_invalid_rounds() -> None:
    assert [risk_limit_main.stop_poll_delay(value) for value in range(7)] == [
        0.02,
        0.02,
        0.04,
        0.08,
        0.16,
        0.25,
        0.25,
    ]
    assert risk_limit_main.stop_poll_delay(10**100) == 0.25
    with pytest.raises(ValueError):
        risk_limit_main.stop_poll_delay(-1)
    with pytest.raises(ValueError):
        risk_limit_main.stop_poll_delay(True)


async def _observe_delays(
    monkeypatch: pytest.MonkeyPatch,
    *,
    requests: list[StopRound] | None = None,
    platforms: list[StopRound] | None = None,
    stops: list[RiskRequestRound] | None = None,
    rounds: int,
) -> list[float]:
    request_results = iter(requests or [])
    platform_results = iter(platforms or [])
    stop_results = iter(stops or [])

    async def next_result(values: Any, default: Any) -> Any:
        return next(values, default)

    monkeypatch.setattr(
        risk_limit_main,
        "run_stop_request_round",
        lambda **_: next_result(request_results, StopRound()),
    )
    monkeypatch.setattr(
        risk_limit_main,
        "run_platform_discovery_round",
        lambda **_: next_result(platform_results, StopRound()),
    )
    monkeypatch.setattr(
        risk_limit_main,
        "run_risk_stop_round",
        lambda **_: next_result(stop_results, RiskRequestRound()),
    )
    delays: list[float] = []

    class FinishedError(Exception):
        pass

    async def sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) == rounds:
            raise FinishedError

    monkeypatch.setattr(asyncio, "sleep", sleep)
    with pytest.raises(FinishedError):
        await risk_limit_main._serve_stop_rounds(
            cast(Any, SimpleNamespace()),
            cast(Any, SimpleNamespace()),
        )
    return delays


@pytest.mark.asyncio
async def test_empty_stop_rounds_back_off_to_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    assert await _observe_delays(monkeypatch, rounds=7) == [
        0.02,
        0.04,
        0.08,
        0.16,
        0.25,
        0.25,
        0.25,
    ]


@pytest.mark.asyncio
async def test_stop_activity_and_defer_reset_the_idle_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays = await _observe_delays(
        monkeypatch,
        requests=[StopRound(), StopRound(), StopRound(processed=1), StopRound()],
        platforms=[StopRound(), StopRound(), StopRound(), StopRound(deferred=1)],
        rounds=4,
    )
    assert delays == [0.02, 0.04, 0.02, 0.02]


@pytest.mark.asyncio
async def test_active_platform_and_risk_work_keep_the_active_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays = await _observe_delays(
        monkeypatch,
        platforms=[StopRound(active=True), StopRound()],
        stops=[RiskRequestRound(), RiskRequestRound(processed=1)],
        rounds=2,
    )
    assert delays == [0.02, 0.02]
