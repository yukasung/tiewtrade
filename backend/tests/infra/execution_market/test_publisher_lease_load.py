"""LEASE-02 scope, bounded recording and original transaction safety."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_publisher_lease_load as load
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_owned_pools import OwnedPools
from tests.infra.execution_market.profile_publisher_readiness import observe_publisher_readiness
from tests.infra.execution_market.test_publisher_clock_recovery import (
    published_market as published_market,
)
from tiewtrade.infra.market_data import order_book_storage as books
from tiewtrade.infra.market_data.realtime_records import FeedLease, WriterLeaseLost


def options(**values: Any) -> argparse.Namespace:
    return argparse.Namespace(
        **{
            "publisher_lease_observer": True,
            "acceptance_profile": "PAPER_INTERNAL20_V1",
            "phase": "SMOKE",
            **values,
        }
    )


@pytest.mark.parametrize(
    "change",
    [
        {"phase": "W3"},
        {"acceptance_profile": "PAPER_INTERNAL20_V2"},
        {"worker_only": True},
        {"publisher_clock_recovery": True},
        {"diagnostics": True},
        {"failure_timeline": True},
        {"controlled_delay": True},
    ],
)
def test_disallowed_options(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        load.validate_options(options(**change))


def test_opt_in_default_and_approved_scope() -> None:
    load.validate_options(argparse.Namespace())
    load.validate_options(options())


async def test_bounded_retention_and_foreign_task(tmp_path: Path) -> None:
    observer = load.LoadLeaseObserver(tmp_path, {"write_failed": False})
    observer.actor = asyncio.current_task()
    for tick in range(200):
        observer.record({"tick": tick, "outcome": "RETURNED", "elapsed_seconds": float(tick)})
    assert len(observer.recent) == 64 and len(observer.slowest) == 16
    assert observer.slowest[0]["tick"] == 199 and sum(observer.outcomes.values()) == 200

    async def foreign() -> None:
        observer.record({"outcome": "RETURNED", "elapsed_seconds": 1})

    with pytest.raises(ValueError, match="foreign"):
        await asyncio.create_task(foreign())
    observer.record({"tick": 201, "outcome": "WriterLeaseLost", "elapsed_seconds": 0.1})
    assert observer.failed is not None and observer.failed["tick"] == 201
    assert observer.failed not in observer.slowest
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("fence_enabled,fail_fast", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("failure", ["none", "lease", "ambiguous", "cancel"])
async def test_actual_publication_and_failure_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: tuple[AsyncEngine, books.BookLease, FeedLease],
    failure: str,
    fence_enabled: bool,
    fail_fast: bool,
) -> None:
    from contextlib import asynccontextmanager

    from tiewtrade.infra.db.session import market_data_session

    engine, book, price = published_market
    original = workload.publish_market
    error = WriterLeaseLost()
    if failure == "lease":
        monkeypatch.setattr(workload, "renew_writer", AsyncMock(side_effect=error))
    elif failure == "ambiguous":

        @asynccontextmanager
        async def ambiguous(*args: Any, **kwargs: Any) -> Any:
            async with market_data_session(*args, **kwargs) as session:
                yield session
            raise TimeoutError("PRIVATE_COMMIT")

        monkeypatch.setattr(workload, "market_data_session", ambiguous)
    elif failure == "cancel":
        monkeypatch.setattr(
            workload, "renew_writer", AsyncMock(side_effect=asyncio.CancelledError())
        )

    async def publisher(*args: Any, **kwargs: Any) -> Any:
        return await workload.publish_market(
            engine,
            book,
            price,
            rebase=False,
            trade_id=27,
            update_price=False,
            heartbeat_per_book=True,
        )

    monkeypatch.setattr(workload, "market_publisher", publisher)
    status = {"write_failed": False}
    observer = load.LoadLeaseObserver(
        tmp_path, status, fence_observer=fence_enabled, fence_fail_fast=fail_fast
    )
    expected = {
        "lease": WriterLeaseLost,
        "ambiguous": TimeoutError,
        "cancel": asyncio.CancelledError,
    }
    with (
        OwnedPools(
            tmp_path / "witness-pool.json",
            [("MARKET_DATA", 1, 0)] + ([("ADMIN_OBSERVER", 5, 10)] if fence_enabled else []),
        ),
        observer.observe(),
        observe_publisher_readiness(tmp_path / "publisher-readiness.json", evidence_status=status),
    ):
        if failure == "none":
            await workload.market_publisher(engine, asyncio.Event(), {})
        else:
            with pytest.raises(expected[failure]) as caught:
                await workload.market_publisher(engine, asyncio.Event(), {})
            if failure == "lease":
                assert caught.value is error
    assert json.loads((tmp_path / "witness-pool.json").read_text())["passed"]
    report = json.loads((tmp_path / "publisher-lease.json").read_text())
    assert report["total"] == 1 and report["recent"][0]["tick"] == 27
    assert report["recent"][0]["case"] == "WORKLOAD" and report["recent"][0]["injections"] == 0
    assert report["recent"][0]["heartbeat_per_book"] and not report["recent"][0]["update_price"]
    assert sum(s["stage"] == "book_renew" for s in report["recent"][0]["spans"]) == 1
    if failure != "none":
        assert observer.witness is not None
        assert observer.witness["buffer_ids"] == ([1, 2] if failure == "ambiguous" else [1])
        assert not any(
            e["event"] == "session_exited_confirmed" for e in report["recent"][0]["events"]
        )
    assert workload.publish_market is original
    assert "PRIVATE" not in (tmp_path / "publisher-lease.json").read_text()


@pytest.mark.parametrize("primary", [False, True])
async def test_flush_failure_preserves_primary_and_downgrades_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    primary: bool,
) -> None:
    observer = load.LoadLeaseObserver(tmp_path, {"write_failed": False})
    (tmp_path / "result.json").write_text(json.dumps({"status": "PASSED"}))
    monkeypatch.setattr(observer, "flush", lambda: (_ for _ in ()).throw(OSError("PRIVATE_IO")))
    error = RuntimeError("PRIVATE_ORIGINAL")
    with pytest.raises(RuntimeError if primary else OSError) as caught, observer.observe():
        if primary:
            raise error
    if primary:
        assert caught.value is error and error.__notes__
    assert json.loads((tmp_path / "result.json").read_text())["status"] == "INCOMPLETE"


async def test_missing_or_failed_readiness_rejected(tmp_path: Path) -> None:
    observer = load.LoadLeaseObserver(tmp_path, {"write_failed": True})
    observer.outcomes["RETURNED"] = 1
    with pytest.raises(ValueError):
        observer.flush()
    observer.readiness_status["write_failed"] = False
    with pytest.raises(FileNotFoundError):
        observer.flush()


async def test_incomplete_readiness_document_rejected(tmp_path: Path) -> None:
    observer = load.LoadLeaseObserver(tmp_path, {"write_failed": False})
    observer.outcomes["RETURNED"] = 1
    (tmp_path / "publisher-readiness.json").write_text(json.dumps({"total_checks": 1}))
    with pytest.raises(KeyError):
        observer.flush()


async def test_normal_recorder_cannot_inject_controlled_delay(tmp_path: Path) -> None:
    from tests.infra.execution_market.profile_publisher_lease import LeaseTrace, Publication

    rows: list[dict[str, Any]] = []
    trace = LeaseTrace(
        None, tmp_path / "unused", publication=Publication(153, False, True), sink=rows.append
    )
    await trace.delay("after_book")
    await trace.delay("before_renew_update")
    trace.persist()
    assert not trace.injections and rows[0]["tick"] == 153
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "change,allowed",
    [
        ({}, True),
        ({"publisher_clock_recovery": False}, False),
        ({"publisher_fence_observer": False}, False),
        ({"phase": "SMOKE"}, False),
        ({"acceptance_profile": "PAPER_INTERNAL20_V2"}, False),
        ({"worker_only": True}, False),
        ({"publisher_clock_recovery": 1}, False),
    ],
)
def test_observed_w3_requires_exact_approved_combination(
    change: dict[str, Any], allowed: bool
) -> None:
    args = options(phase="W3", publisher_clock_recovery=True, publisher_fence_observer=True)
    vars(args).update(change)
    if allowed:
        load.validate_options(args)
    else:
        with pytest.raises(ValueError):
            load.validate_options(args)


@pytest.mark.parametrize("repeat", [False, True])
@pytest.mark.parametrize("fail_fast", [False, True])
async def test_combined_clock_recovery_counts_actual_guards_and_skips_rollback_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: tuple[AsyncEngine, books.BookLease, FeedLease],
    repeat: bool,
    fail_fast: bool,
) -> None:
    from time import monotonic

    from tests.infra.execution_market import profile_publisher_recovery as recovery
    from tests.infra.execution_market.profile_publisher_lease import (
        financial_counts,
        state_snapshot,
    )
    from tests.infra.execution_market.test_publisher_clock_recovery import inject_clock
    from tiewtrade.core.orders import SourceUnavailableError

    engine, book, price = published_market
    calls = inject_clock(monkeypatch, repeat=repeat)

    async def publisher(*args: Any, **kwargs: Any) -> Any:
        return await workload.publish_market(
            engine, book, price, rebase=False, trade_id=2, heartbeat_per_book=True
        )

    monkeypatch.setattr(workload, "market_publisher", publisher)
    state = recovery.ClockRecovery(tmp_path / "clock.json")
    state.window_start = monotonic() - 1
    readiness = {"write_failed": False}
    observer = load.LoadLeaseObserver(
        tmp_path, readiness, fence_observer=True, fence_fail_fast=fail_fast
    )
    failure = None
    try:
        with (
            state.observe(),
            observer.observe(),
            observe_publisher_readiness(
                tmp_path / "publisher-readiness.json", evidence_status=readiness
            ),
        ):
            await workload.market_publisher(engine, asyncio.Event(), {})
            state.window_end = monotonic()
            state.validate_success()
    except SourceUnavailableError as error:
        failure = error
    assert (failure is not None) == repeat
    report = json.loads((tmp_path / "publisher-lease.json").read_text())
    assert len(calls) == 2 and report["total"] == 1 and report["guard_calls"] == 2
    assert report["recent"][0]["guard_calls"] == 2
    events = report["recent"][0]["events"]
    assert sum(row["event"] == "session_exited_rollback_confirmed" for row in events) == 1
    assert sum(row["event"] == "precommit_db_clock" for row in events) == int(not repeat)
    assert sum(row["event"] == "session_exited_confirmed" for row in events) == int(not repeat)
    snapshot = await state_snapshot(engine)
    assert snapshot["buffer_ids"] == ([1] if repeat else [1, 2])
    assert not any((await financial_counts()).values())
    assert not report["fence_observation"]["errors"] and report["fence_observation"]["task_joined"]
    assert recovery.current() is None


async def test_foreign_guard_cannot_add_parent_trace_counts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_market: tuple[AsyncEngine, books.BookLease, FeedLease],
) -> None:
    from datetime import UTC, datetime
    from unittest.mock import Mock

    from tests.infra.execution_market.profile_publisher_lease import CASES, LeaseTrace
    from tests.infra.risk_limits.test_book_clock import ready_book
    from tiewtrade.core.order_book import BookState

    now = datetime.now(UTC)
    book = ready_book(now)
    original = Mock(wraps=BookState.require_ready)
    monkeypatch.setattr(BookState, "require_ready", original)
    trace = LeaseTrace(CASES[0], tmp_path / "trace.json")

    async def child() -> None:
        book.require_ready(now)

    with trace.observe(published_market[0]):
        await asyncio.create_task(child())
        assert trace.guard_calls == 0
        book.require_ready(now)
        assert trace.guard_calls == 1
    assert original.call_count == 2
