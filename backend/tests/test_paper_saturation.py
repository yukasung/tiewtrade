"""R28 slots are conserved; only unsubmitted demand may be backpressured."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits import profile_saturation as saturation
from tests.test_paper_cycle_budget import Clock
from tiewtrade.core.money import Money


def test_fixed_demand_has_6000_unique_slots_without_claiming_api_offers() -> None:
    owners = [UUID(int=i + 1) for i in range(100)]
    slots = saturation.demand_slots(owners, 60, 100)
    assert len(slots) == len({(s.owner, s.cycle) for s in slots}) == 6000
    assert slots[0].due == 0 and slots[-1].due == 299.95
    assert all(s.owner == owners[i % 100] for i, s in enumerate(slots))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(saturation, "monotonic", clock)
    return clock


async def test_busy_owners_skip_slots_without_catchup_or_duplicate_work(
    tmp_path: Path, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    owners = [UUID(int=1), UUID(int=2)]
    slots = saturation.demand_slots(owners, 3, 10)
    progress = saturation.Progress(owners, len(slots))
    release = asyncio.Event()
    calls = []

    async def sleep(seconds: float) -> None:
        clock.now += seconds
        if clock.now >= 3:
            release.set()
        await asyncio.sleep(0)

    monkeypatch.setattr(
        saturation,
        "asyncio",
        SimpleNamespace(
            **{
                **vars(asyncio),
                "sleep": sleep,
                "timeout_at": lambda end: clock.timeout(end - clock.now),
            }
        ),
    )

    async def operation(owner: UUID, number: int) -> None:
        calls.append((owner, number))
        await release.wait()

    await saturation.run_saturation(
        slots,
        started=0,
        duration=3,
        drain=1,
        operation=operation,
        progress=progress,
        path=tmp_path / "slots.jsonl",
    )
    assert calls == [(owners[0], 0), (owners[1], 0)]
    assert progress.counts == dict.fromkeys(owners, 1)
    assert progress.peak_active == 2 and progress.backpressured == 4
    assert progress.summary()["conserved"] and progress.summary()["all_started_complete"]
    rows = [json.loads(line) for line in (tmp_path / "slots.jsonl").read_text().splitlines()]
    assert sum(r["state"] == "STARTED" for r in rows) == 2
    assert sum(r["state"] == "NOT_SUBMITTED_BACKPRESSURE" for r in rows) == 4


async def test_global_timeout_cancels_and_joins_inflight_work_not_as_backpressure(
    tmp_path: Path,
) -> None:
    owner = uuid4()
    joined = asyncio.Event()
    progress = saturation.Progress([owner], 1)

    async def never(*args: Any) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    with pytest.raises(TimeoutError):
        await saturation.run_saturation(
            saturation.demand_slots([owner], 1, 100),
            started=monotonic(),
            duration=0.02,
            drain=0.02,
            operation=never,
            progress=progress,
            path=tmp_path / "timeout.jsonl",
        )
    assert joined.is_set() and progress.failed == 1 and progress.backpressured == 0
    assert not progress.summary()["all_started_complete"]


async def test_command_error_is_not_reclassified_or_retried(tmp_path: Path) -> None:
    owner = uuid4()
    progress = saturation.Progress([owner], 2)

    async def fail(*args: Any) -> None:
        raise RuntimeError("UNKNOWN command outcome")

    with pytest.raises(RuntimeError, match="UNKNOWN"):
        await saturation.run_saturation(
            saturation.demand_slots([owner], 2, 100),
            started=monotonic(),
            duration=0.1,
            drain=0.1,
            operation=fail,
            progress=progress,
            path=tmp_path / "failure.jsonl",
        )
    assert progress.failed == 1 and progress.backpressured == 0
    assert len(progress.decisions) == 1


async def test_expired_start_window_cannot_offer_new_work(
    tmp_path: Path, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = uuid4()
    progress = saturation.Progress([owner], 1)
    clock.now = 300

    async def sleep(seconds: float) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr(
        saturation,
        "asyncio",
        SimpleNamespace(
            **{
                **vars(asyncio),
                "sleep": sleep,
                "timeout_at": lambda end: clock.timeout(end - clock.now),
            }
        ),
    )

    async def unexpected(*args: Any) -> None:
        pytest.fail("must not offer after window")

    with pytest.raises(TimeoutError, match="start-window"):
        await saturation.run_saturation(
            saturation.demand_slots([owner], 1, 100),
            started=0,
            duration=300,
            drain=60,
            operation=unexpected,
            progress=progress,
            path=tmp_path / "boundary.jsonl",
        )
    assert not progress.decisions


def test_duplicate_decision_and_owner_concurrency_are_rejected() -> None:
    owner = uuid4()
    progress = saturation.Progress([owner], 2)
    progress.decide(saturation.Slot(owner, 0, 0), True)
    with pytest.raises(ValueError, match="duplicate"):
        progress.decide(saturation.Slot(owner, 0, 0), False)
    with pytest.raises(ValueError, match="already active"):
        progress.decide(saturation.Slot(owner, 1, 5), True)


def test_default_and_per_owner_counts_validate_full_contract() -> None:
    owners: Any = [SimpleNamespace(user_id=UUID(int=1)), SimpleNamespace(user_id=UUID(int=2))]
    assert f15.cycle_counts_for(owners, 2, None) == {UUID(int=1): 2, UUID(int=2): 2}
    assert f15.cycle_counts_for(owners, 9, {UUID(int=1): 0, UUID(int=2): 1}) == {
        UUID(int=1): 0,
        UUID(int=2): 1,
    }
    for counts in [
        {UUID(int=1): 1},
        {UUID(int=1): True, UUID(int=2): 1},
        {UUID(int=1): -1, UUID(int=2): 1},
    ]:
        with pytest.raises(ValueError):
            f15.cycle_counts_for(owners, 9, counts)


def test_noncontiguous_slots_produce_different_exact_ids_not_just_counts() -> None:
    owner: Any = SimpleNamespace(user_id=uuid4(), wallet=SimpleNamespace(episode_id=uuid4()))
    run = uuid4()
    first = saturation.expected_requests(owner, run, [0, 3], 20, 0)
    wrong = saturation.expected_requests(owner, run, [0, 1], 20, 0)
    assert len(first) == len(wrong) == 28 and first != wrong
    assert sum(action == "CANCEL" for action, _, _ in first) == 2


async def test_existing_money_oracle_uses_each_owner_count_and_detects_wrong_balance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owners: Any = [
        SimpleNamespace(user_id=UUID(int=i), wallet=SimpleNamespace(episode_id=UUID(int=i)))
        for i in [1, 2]
    ]
    counts = {UUID(int=1): 0, UUID(int=2): 1}

    class Session:
        def __init__(self, owner: UUID) -> None:
            self.owner = owner

        async def execute(self, sql: str, *args: Any) -> Any:
            row = (
                {"held": 0, "cost": 0}
                if "held_quantity" in sql
                else {
                    "accepted": 20,
                    "filled": 0 if self.owner.int == 1 else 2,
                    "canceled": 0 if self.owner.int == 1 else 1,
                    "quote_reserved": 20,
                    "base_reserved": 0,
                }
            )
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row))

    @asynccontextmanager
    async def session(engine: Any, owner: UUID, **kwargs: Any) -> Any:
        yield Session(owner)

    async def wallet(session: Session) -> Any:
        return SimpleNamespace(
            balance=Money.of("10000" if session.owner.int == 1 else "9998.802099", "USDT")
        )

    monkeypatch.setattr(f15, "user_session", session)
    monkeypatch.setattr(f15, "get_wallet", wallet)
    engine: Any = None
    rows = await f15.verify(
        engine, owners, baseline_orders=20, cycles_per_owner=9, cycle_counts=counts
    )
    assert all(r["passed"] for r in rows)
    rows = await f15.verify(
        engine,
        owners,
        baseline_orders=20,
        cycles_per_owner=9,
        cycle_counts=dict.fromkeys(counts, 0),
    )
    assert not rows[1]["passed"]


@pytest.mark.parametrize(
    "mutation,passed",
    [
        ("clean", True),
        ("wrong_id", False),
        ("duplicate", False),
        ("unknown", False),
        ("missing", False),
    ],
)
async def test_identity_oracle_rejects_wrong_equal_counts_duplicate_or_unfinished_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, passed: bool
) -> None:
    owner: Any = SimpleNamespace(user_id=uuid4(), wallet=SimpleNamespace(episode_id=uuid4()))
    run = uuid4()
    progress = saturation.Progress([owner.user_id], 4)
    progress.completed[owner.user_id] = [0, 3]
    intents = [f15.baseline(owner, run, i) for i in range(2)]
    for number in [0, 3]:
        intents += [
            f15.market_buy(owner, run, number),
            f15.limit_sell(owner, run, number),
            f15.market_sell(owner, run, number),
        ]
    orders = [intent.order_id for intent in intents]
    rows: list[dict[str, Any]] = [
        {
            "request_id": uuid4(),
            "action": "NEW",
            "idempotency_key": intent.idempotency_key,
            "order_id": intent.order_id,
            "command_id": uuid4(),
            "intake_state": "TRANSFERRED",
            "command_state": "SUCCEEDED",
        }
        for intent in intents
    ]
    for number in [0, 3]:
        rows.append(
            {
                "request_id": uuid4(),
                "action": "CANCEL",
                "idempotency_key": f15.identity(run, owner.user_id, number, "cancel-key"),
                "order_id": f15.limit_sell(owner, run, number).order_id,
                "command_id": uuid4(),
                "intake_state": "TRANSFERRED",
                "command_state": "SUCCEEDED",
            }
        )
    if mutation == "wrong_id":
        rows[0]["order_id"] = uuid4()
    elif mutation == "duplicate":
        rows.append(dict(rows[0]))
    elif mutation == "unknown":
        rows[0]["command_state"] = None
    elif mutation == "missing":
        rows.pop()

    class Session:
        async def execute(self, sql: str, *args: Any) -> Any:
            return SimpleNamespace(
                mappings=lambda: SimpleNamespace(all=lambda: rows),
                scalars=lambda: SimpleNamespace(all=lambda: orders),
            )

    @asynccontextmanager
    async def session(*args: Any, **kwargs: Any) -> Any:
        yield Session()

    monkeypatch.setattr(saturation, "user_session", session)
    engine: Any = None
    assert (
        await saturation.verify_identities(
            engine, [owner], run, progress, 2, {}, tmp_path / "identities.json"
        )
        is passed
    )


async def test_global_oracle_keeps_uniform_default_and_accepts_unequal_reference_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owners: Any = [
        SimpleNamespace(user_id=UUID(int=i), wallet=SimpleNamespace(episode_id=UUID(int=i)))
        for i in [1, 2]
    ]

    class Session:
        def __init__(self, owner: UUID) -> None:
            self.owner = owner

        async def execute(self, *args: Any, **kwargs: Any) -> Any:
            row = {
                "orders": 20 if self.owner.int == 1 else 23,
                "fills": 0 if self.owner.int == 1 else 2,
                "cancels": 0 if self.owner.int == 1 else 1,
                "pending_dispatch": 20,
                "unlinked_fills": 0,
                "invalid_reservations": 0,
                "invalid_positions": 0,
                "wrong_mode": 0,
                "input_lag": 0,
                "duplicate_fill_effects": 0,
            }
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row))

    @asynccontextmanager
    async def session(engine: Any, owner: UUID, **kwargs: Any) -> Any:
        yield Session(owner)

    monkeypatch.setattr(f15, "user_session", session)
    engine: Any = None
    result = await f15.verify_global_invariants(
        engine,
        owners,
        baseline_orders=20,
        cycles_per_owner=1,
        cycle_counts={UUID(int=1): 0, UUID(int=2): 1},
    )
    assert result["passed"] and result["expected_orders"] == 43
    assert result["expected_fills"] == 2 and result["expected_cancels"] == 1
    result = await f15.verify_global_invariants(
        engine, owners, baseline_orders=20, cycles_per_owner=1
    )
    assert not result["passed"] and result["expected_orders"] == 46


async def test_external_cancellation_joins_started_cycle(tmp_path: Path) -> None:
    owner = uuid4()
    entered, joined = asyncio.Event(), asyncio.Event()
    progress = saturation.Progress([owner], 1)

    async def work(*args: Any) -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    task = asyncio.create_task(
        saturation.run_saturation(
            saturation.demand_slots([owner], 1, 100),
            started=monotonic(),
            duration=1,
            drain=1,
            operation=work,
            progress=progress,
            path=tmp_path / "cancel.jsonl",
        )
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert joined.is_set() and not progress.active and progress.failed == 1
    assert progress.backpressured == 0


async def test_bad_plan_is_rejected_before_any_cycle(tmp_path: Path) -> None:
    owner = uuid4()
    progress = saturation.Progress([owner], 2)

    async def unexpected(*args: Any) -> None:
        pytest.fail("invalid plan must not submit")

    with pytest.raises(ValueError, match="duplicate demand plan"):
        await saturation.run_saturation(
            [saturation.Slot(owner, 0, 0)] * 2,
            started=monotonic(),
            duration=1,
            drain=1,
            operation=unexpected,
            progress=progress,
            path=tmp_path / "bad.jsonl",
        )
    assert not progress.decisions


async def test_w2_cycle_uses_planned_cancel_key_without_extra_reset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from tests.infra.risk_limits.profile_workload import Fixture

    owner: Any = SimpleNamespace(user_id=uuid4(), wallet=SimpleNamespace(episode_id=uuid4()))
    run = uuid4()
    ready = asyncio.Event()
    ready.set()
    calls = []
    fixture: Any = SimpleNamespace(
        selected=uuid4(), partial_ready=ready, bounded_saturation=True, engine=None, output=tmp_path
    )
    counters = f15.Counters()

    async def new(*args: Any, **kwargs: Any) -> None:
        counters.offered += 1
        counters.admitted += 1
        counters.completed += 1

    async def request(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(state="SUCCEEDED", failure_code=None)

    async def wait(*args: Any, **kwargs: Any) -> None:
        return None

    fixture.new, fixture.request = new, request
    monkeypatch.setattr(f15, "wait_status", wait)
    engine: Any = None
    async with Fixture.cycle_scope(fixture, owner, 3):
        await Fixture.cycle(fixture, engine, owner, run, 3, counters, [])
    assert counters.completed == 5 and len(calls) == 2
    assert calls[1]["cancel_key"] == f15.identity(run, owner.user_id, 3, "cancel-key")
