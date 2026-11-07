"""Final-tail recovery keeps one deadline and the final publisher identity/head."""

from __future__ import annotations

import argparse
import asyncio
import json
import runpy
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from types import CoroutineType, SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tiewtrade.core.orders import SourceUnavailableError


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "publisher",
        "read_failure",
        "head",
        "owner",
        "generation",
        "not_ready",
        "future_cursor",
        "timeout",
        "cancel",
        "slow_tail",
        "worker",
        "stale",
        "snapshot_failure",
        "snapshot_timeout",
    ],
)
async def test_tail_uses_actual_stopped_head_and_preserves_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    engine = cast(AsyncEngine, object())
    owner_id, producer = uuid4(), uuid4()
    owner = cast(
        f15.OwnerState,
        SimpleNamespace(user_id=owner_id, wallet=SimpleNamespace(episode_id=uuid4())),
    )
    stop = asyncio.Event()
    stats = {"last_input_id": 100, "book_owner": str(producer), "book_generation": 2}
    original_error = (SourceUnavailableError if failure == "stale" else RuntimeError)(
        "PRIVATE_FAILURE_MUST_NOT_BE_SERIALIZED"
    )
    calls = []
    readers = set()
    closed = set()
    both_reading = asyncio.Event()

    async def publisher() -> None:
        await stop.wait()
        if failure == "publisher":
            raise original_error
        # Include an input committed after the stop request but before normal exit.
        stats["last_input_id"] = 125

    async def recovery(*args: Any) -> None:
        calls.append(args[2])
        if failure in {"timeout", "cancel"}:
            await asyncio.Event().wait()
        if failure in {"slow_tail", "worker"} and len(calls) == 2:
            await asyncio.Event().wait()
        if failure in {"read_failure", "stale"} and len(calls) == 2:
            raise original_error

    async def source_query(statement: str, parameters: Any) -> Any:
        assert publisher_task.done() and stop.is_set()
        assert statement.lstrip().startswith("SELECT")
        return SimpleNamespace(
            one_or_none=lambda: SimpleNamespace(
                last_input_id=126 if failure == "head" else 125,
                owner=uuid4() if failure == "owner" else producer,
                generation=3 if failure == "generation" else 2,
            )
        )

    async def cursor_query(reader: Any, statement: str, parameters: Any) -> Any:
        assert statement.lstrip().startswith("SELECT")
        readers.add(reader)
        if len(readers) == 2:
            both_reading.set()
        if failure == "snapshot_failure":
            if reader == owner_id:
                await both_reading.wait()
                raise original_error
            await asyncio.Event().wait()
        if failure == "snapshot_timeout":
            await asyncio.Event().wait()
        return SimpleNamespace(
            one=lambda: SimpleNamespace(
                availability="UNKNOWN" if failure == "not_ready" else "READY",
                input_id=126 if failure == "future_cursor" else 105,
            )
        )

    @asynccontextmanager
    async def source_session(*args: Any, **kwargs: Any) -> Any:
        yield SimpleNamespace(execute=source_query)

    @asynccontextmanager
    async def user_session(*args: Any, **kwargs: Any) -> Any:
        reader = args[1]

        async def execute(statement: str, parameters: Any) -> Any:
            return await cursor_query(reader, statement, parameters)

        try:
            yield SimpleNamespace(execute=execute)
        finally:
            closed.add(reader)

    monkeypatch.setattr(f15, "wait_for_input_recovery", recovery)
    monkeypatch.setattr(f15, "market_data_session", source_session)
    monkeypatch.setattr(f15, "user_session", user_session)
    requested = []
    timeout_at = asyncio.timeout_at

    def budget(deadline: float) -> asyncio.Timeout:
        requested.append(deadline - monotonic())
        return timeout_at(
            asyncio.get_running_loop().time()
            + (0.03 if failure in {"timeout", "slow_tail", "worker", "snapshot_timeout"} else 2)
        )

    monkeypatch.setattr(asyncio, "timeout_at", budget)
    publisher_task = asyncio.create_task(publisher())
    evidence = tmp_path / "tail.json"
    owners = [owner]
    if failure in {"snapshot_failure", "snapshot_timeout"}:
        owners.append(cast(f15.OwnerState, SimpleNamespace(user_id=uuid4(), wallet=owner.wallet)))
    task = asyncio.create_task(
        f15.drain_final_tail(engine, engine, owners, publisher_task, stop, stats, evidence)
    )
    try:
        if failure == "cancel":
            while not calls:
                await asyncio.sleep(0)
            task.cancel()
        if failure is None:
            assert await task >= 0
            record = json.loads(evidence.read_text())
            assert calls == [100, 105]
            assert record["initial_watermark"] == 100 and record["final_head"] == 125
            assert record["minimum_cursor"] == 105 and record["owners"][0]["lag"] == 20
            assert record["recovered"] is True
            assert [value["stage"] for value in record["stages"]] == [
                "live_recovery",
                "stop_publisher",
                "final_tail",
                "complete",
            ]
        else:
            errors: dict[str, type[BaseException]] = {
                "cancel": asyncio.CancelledError,
                "timeout": TimeoutError,
                "slow_tail": TimeoutError,
                "worker": TimeoutError,
                "stale": SourceUnavailableError,
                "snapshot_timeout": TimeoutError,
            }
            expected = errors.get(failure, RuntimeError)
            with pytest.raises(expected) as caught:
                await task
            if failure in {"publisher", "read_failure", "stale", "snapshot_failure"}:
                assert caught.value is original_error
            record = json.loads(evidence.read_text())
            assert "recovered" not in record
            assert record["error_type"] == expected.__name__
            assert "PRIVATE_FAILURE" not in evidence.read_text()
            if failure in {"snapshot_failure", "snapshot_timeout"}:
                assert len(readers) == 2 and closed == readers
        assert len(requested) == 1 and 59.9 < requested[0] <= 60
    finally:
        for pending in [task, publisher_task]:
            if not pending.done():
                pending.cancel()
        await asyncio.gather(task, publisher_task, return_exceptions=True)
        assert task.done() and publisher_task.done()


@pytest.mark.parametrize(
    "options",
    [
        [],
        ["--publisher-heartbeat-per-book"],
        ["--publisher-heartbeat-per-book", "--r8-claim-budget", "--phase", "W1"],
        [
            "--publisher-heartbeat-per-book",
            "--r8-claim-budget",
            "--phase",
            "SMOKE",
            "--worker-only",
        ],
    ],
)
def test_tail_cli_rejects_unapproved_runtime_combinations(
    monkeypatch: pytest.MonkeyPatch, options: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["profile", "--final-tail-drain", *options])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(Path(f15.__file__)), run_name="__main__")
    assert caught.value.code == 2


def test_tail_cli_accepts_only_explicit_smoke_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen = []

    def run(coroutine: CoroutineType[Any, Any, Any]) -> int:
        assert coroutine.cr_frame is not None
        args = coroutine.cr_frame.f_locals["args"]
        seen.append(
            (args.final_tail_drain, args.r8_claim_budget, args.publisher_heartbeat_per_book)
        )
        coroutine.close()
        return 0

    monkeypatch.setattr(asyncio, "run", run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile",
            "--phase",
            "SMOKE",
            "--final-tail-drain",
            "--publisher-heartbeat-per-book",
            "--r8-claim-budget",
            "--owners",
            "100",
            "--cycles-per-owner",
            "6",
            "--rate",
            "10",
            "--output",
            str(tmp_path / "run"),
        ],
    )
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(Path(f15.__file__)), run_name="__main__")
    assert caught.value.code == 0 and seen == [(True, True, True)]


async def test_tail_manifest_names_actual_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(f15, "create_engine_for", lambda role: engine)
    monkeypatch.setattr(f15, "database_manifest", AsyncMock(return_value={}))
    monkeypatch.setattr(
        f15, "seed_owners", AsyncMock(side_effect=RuntimeError("controlled setup stop"))
    )
    args = argparse.Namespace(
        output=tmp_path / "run",
        phase="SMOKE",
        owners=100,
        baseline_orders=20,
        cycles_per_owner=6,
        rate=10,
        workers=20,
        baseline_manifest=None,
        publisher_heartbeat_per_book=True,
        r8_claim_budget=True,
        final_tail_drain=True,
    )
    with pytest.raises(RuntimeError, match="controlled setup stop"):
        await f15._run(args)
    manifest = json.loads((args.output / "manifest.json").read_text())
    assert manifest["worker_runtime"] == "F15_STANDALONE_R8_HEARTBEAT_TAIL_V1"
    assert manifest["checkpoint_storage"] == "PG_BATCH_V1" and manifest["final_tail_drain"]


@pytest.mark.parametrize("failure", [None, "recovery_error", "cursor_error", "cancel", "deadline"])
async def test_internal_tail_gates_all_twenty_owners_and_joins_waiting_readers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    from tests.infra.execution_market.profile_parent_poll import ParentPollGate

    engine = cast(AsyncEngine, object())
    owners = [
        cast(
            f15.OwnerState,
            SimpleNamespace(user_id=uuid4(), wallet=SimpleNamespace(episode_id=uuid4())),
        )
        for _ in range(20)
    ]
    producer = uuid4()
    stats = {"last_input_id": 100, "book_owner": str(producer), "book_generation": 1}
    gate, stop, four_reading = ParentPollGate(), asyncio.Event(), asyncio.Event()
    sessions: set[object] = set()
    calls: dict[object, int] = {}
    peak = 0
    original_error = RuntimeError("controlled read failure")

    async def publisher() -> None:
        await stop.wait()
        stats["last_input_id"] = 105

    @asynccontextmanager
    async def session(unused: object, owner: object, **kwargs: Any) -> Any:
        nonlocal peak
        assert gate.active > 0  # Permit is acquired before opening a connection.
        sessions.add(owner)
        peak = max(peak, len(sessions))
        if len(sessions) == 4:
            four_reading.set()
        calls[owner] = calls.get(owner, 0) + 1

        async def execute(statement: str, parameters: Any) -> Any:
            assert statement.lstrip().startswith("SELECT")
            if failure in {"cancel", "deadline"}:
                await asyncio.Event().wait()
            await asyncio.sleep(0.001)
            if owner == owners[0].user_id and (
                (failure == "recovery_error" and calls[owner] == 1)
                or (failure == "cursor_error" and calls[owner] == 3)
            ):
                raise original_error
            return SimpleNamespace(one=lambda: SimpleNamespace(availability="READY", input_id=105))

        try:
            yield SimpleNamespace(execute=execute)
        finally:
            # Connection closes while its permit is still held.
            assert gate.active > 0
            sessions.remove(owner)

    @asynccontextmanager
    async def source_session(*args: Any) -> Any:
        async def execute(statement: str, parameters: Any) -> Any:
            return SimpleNamespace(
                one_or_none=lambda: SimpleNamespace(owner=producer, generation=1, last_input_id=105)
            )

        yield SimpleNamespace(execute=execute)

    requested = []
    timeout_at = asyncio.timeout_at

    def deadline(value: float) -> asyncio.Timeout:
        requested.append(value - monotonic())
        return (
            timeout_at(asyncio.get_running_loop().time() + 0.03)
            if failure == "deadline"
            else timeout_at(value)
        )

    monkeypatch.setattr(f15, "user_session", session)
    monkeypatch.setattr(f15, "market_data_session", source_session)
    monkeypatch.setattr(asyncio, "timeout_at", deadline)
    publishing = asyncio.create_task(publisher())
    evidence = tmp_path / "tail.json"
    task = asyncio.create_task(
        f15.drain_final_tail(
            engine, engine, owners, publishing, stop, stats, evidence, poll_gate=gate
        )
    )
    try:
        if failure == "cancel":
            await four_reading.wait()
            task.cancel()
        if failure is None:
            await task
            record = json.loads(evidence.read_text())
            assert len(record["owners"]) == 20 and record["recovered"]
            assert set(calls.values()) == {3}
            assert gate.attempts == 60
        else:
            expected = (
                asyncio.CancelledError
                if failure == "cancel"
                else TimeoutError
                if failure == "deadline"
                else RuntimeError
            )
            with pytest.raises(expected) as caught:
                await task
            if failure.endswith("error"):
                assert caught.value is original_error
            assert "recovered" not in json.loads(evidence.read_text())
        assert peak == gate.peak == 4
        assert not sessions and gate.active == 0 and gate.finished == gate.attempts
        assert len(requested) == 1 and 59.9 < requested[0] <= 60
        if failure in {"cancel", "deadline"}:
            assert gate.attempts == 20 and sum(row["acquired"] for row in gate.rows) == 4
    finally:
        for pending in (task, publishing):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(task, publishing, return_exceptions=True)


async def test_input_recovery_releases_all_permits_before_retry_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.execution_market.profile_parent_poll import ParentPollGate

    gate, reads, sleeps = ParentPollGate(), 0, 0
    owner = cast(
        f15.OwnerState, SimpleNamespace(user_id=uuid4(), wallet=SimpleNamespace(episode_id=uuid4()))
    )
    original_sleep = asyncio.sleep

    @asynccontextmanager
    async def session(*args: Any, **kwargs: Any) -> Any:
        async def execute(statement: str, parameters: Any) -> Any:
            nonlocal reads
            reads += 1
            return SimpleNamespace(
                one=lambda: SimpleNamespace(
                    availability="READY" if reads == 2 else "UNKNOWN", input_id=100
                )
            )

        yield SimpleNamespace(execute=execute)

    async def sleep(seconds: float) -> None:
        nonlocal sleeps
        assert seconds == 0.05 and gate.active == 0
        sleeps += 1
        await original_sleep(0)

    monkeypatch.setattr(f15, "user_session", session)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    await f15.wait_for_input_recovery(cast(AsyncEngine, object()), [owner], 100, poll_gate=gate)
    assert reads == 2 and sleeps == 1 and gate.finished == 2


async def test_tail_resource_observation_reads_existing_pools_and_database(
    engine_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    async with engine_engine.connect():
        observed = await f15.tail_resource_observation(engine_engine, migrator_engine)
        assert observed["parent_pool"]["checked_out"] == 1
        assert observed["parent_pool"]["pool_size"] == 5
        assert observed["parent_pool"]["max_overflow"] == 10
        assert observed["unknown_nulls"] is True
        assert observed["connections"] == sum(
            row["connections"] for row in observed["by_role_and_state"]
        )
        assert {row["role"] for row in observed["by_role_and_state"]} >= {
            "tiewtrade_engine",
            "tiewtrade_migrator",
        }
    assert f15.parent_pool_state(engine_engine)["checked_out"] == 0
    assert f15.parent_pool_state(migrator_engine)["checked_out"] == 0
