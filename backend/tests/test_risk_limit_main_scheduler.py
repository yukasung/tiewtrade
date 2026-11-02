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


@pytest.mark.asyncio
async def test_rolling_admits_new_owner_while_slow_peer_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID

    owners = [UUID(int=i) for i in range(1, 7)]
    release = asyncio.Event()
    full = asyncio.Event()
    replacement = asyncio.Event()
    seen: list[UUID] = []
    running: set[UUID] = set()
    maximum = 0
    scans: list[tuple[int, tuple[UUID, ...]]] = []
    eligible_owners = owners[:4]

    async def scan(
        _: Any, *, limit: int, after_owner: UUID | None, excluded: tuple[Any, ...]
    ) -> list[Any]:
        scans.append((limit, excluded))
        assert limit == 4 - len(excluded)
        eligible = [
            owner for owner in eligible_owners if owner not in excluded and owner not in seen
        ]
        return [SimpleNamespace(user_id=owner, due_at=None) for owner in eligible[:limit]]

    async def evaluate(_: Any, owner: UUID) -> str:
        nonlocal maximum
        assert owner not in running
        running.add(owner)
        seen.append(owner)
        maximum = max(maximum, len(running))
        try:
            if len(running) == 4:
                eligible_owners.extend(owners[4:])
                full.set()
            if owner == owners[0]:
                await release.wait()
            elif owner in owners[1:4]:
                await full.wait()
            else:
                assert owners[0] in running  # No whole-page completion barrier.
                replacement.set()
                await release.wait()
            return "processed"
        finally:
            running.remove(owner)

    monkeypatch.setattr(risk_limit_main, "_scan_monitor_candidates", scan)
    monkeypatch.setattr(risk_limit_main, "_evaluate_monitor_owner", evaluate)
    task = asyncio.create_task(risk_limit_main._serve_monitor(cast(Any, None), cast(Any, None)))
    try:
        await asyncio.wait_for(replacement.wait(), 2)
        assert maximum == 4 and seen[:4] == owners[:4]
        assert len(seen) == len(set(seen))
        assert scans[1][0] == 3 and scans[1][1] == (owners[0],)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert not running


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["scan", "owner"])
async def test_rolling_propagates_failure_and_joins_active_tasks(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from uuid import UUID

    entered = asyncio.Event()
    cleaned = asyncio.Event()
    calls = 0

    class ExpectedFailureError(Exception):
        pass

    async def scan(_: Any, **kwargs: Any) -> list[Any]:
        nonlocal calls
        calls += 1
        if calls > 1:
            await entered.wait()
            if failure == "scan":
                raise ExpectedFailureError
            return []
        return [SimpleNamespace(user_id=UUID(int=i), due_at=None) for i in (1, 2)]

    async def evaluate(_: Any, owner: Any) -> str:
        if owner.int == 1:
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        await entered.wait()
        if failure == "owner":
            raise ExpectedFailureError
        return "deferred"

    monkeypatch.setattr(risk_limit_main, "_scan_monitor_candidates", scan)
    monkeypatch.setattr(risk_limit_main, "_evaluate_monitor_owner", evaluate)
    with pytest.raises(ExpectedFailureError):
        await asyncio.wait_for(risk_limit_main._serve_monitor(cast(Any, None), cast(Any, None)), 2)
    assert cleaned.is_set()


@pytest.mark.asyncio
async def test_rolling_uuid_cursor_wraps_fairly_over_more_than_one_hundred_hot_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uuid import UUID

    owners = [UUID(int=i) for i in range(1, 106)]
    visited: list[UUID] = []
    completed = asyncio.Event()

    async def scan(
        _: Any, *, limit: int, after_owner: UUID | None, excluded: tuple[Any, ...]
    ) -> list[Any]:
        eligible = [o for o in owners if o not in excluded]
        eligible.sort(key=lambda o: (after_owner is not None and o <= after_owner, o))
        return [SimpleNamespace(user_id=o, due_at=None) for o in eligible[:limit]]

    async def evaluate(_: Any, owner: UUID) -> str:
        visited.append(owner)
        if len(visited) >= 210:
            completed.set()
        # Keep owners continuously eligible even after a failed/deferred attempt.
        return "deferred" if owner.int % 7 == 0 else "processed"

    monkeypatch.setattr(risk_limit_main, "_scan_monitor_candidates", scan)
    monkeypatch.setattr(risk_limit_main, "_evaluate_monitor_owner", evaluate)
    task = asyncio.create_task(risk_limit_main._serve_monitor(cast(Any, None), cast(Any, None)))
    try:
        await asyncio.wait_for(completed.wait(), 2)
        assert visited[:105] == owners
        assert visited[105:210] == owners
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
