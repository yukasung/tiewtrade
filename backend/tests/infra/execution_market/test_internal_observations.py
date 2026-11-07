"""Missing observations, cancelled reads and restore recovery must not become passes."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_internal import activated_protocols
from tests.infra.execution_market.profile_internal_restore import (
    build_extension,
    extension_coverage,
    readonly_admin,
    recover,
)
from tests.infra.execution_market.profile_parent_poll import ParentPollGate
from tests.infra.execution_market.profile_positions import PositionChecks
from tests.infra.execution_market.profile_protections import processing_verdict
from tiewtrade.infra.db import DatabaseRole, create_engine_for


async def test_streamed_poll_attempts_keep_cancellations_without_retaining_rows(
    tmp_path: Path,
) -> None:
    gate = ParentPollGate(stream_path=tmp_path / "attempts.jsonl")
    owner = uuid4()
    gate.rows = [{}] * 100000  # The old bounded buffer cannot limit the opt-in stream.
    async with gate.permit(owner, "read"):
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.01):
                gate.semaphore = asyncio.Semaphore(0)
                async with gate.permit(owner, "blocked"):
                    pytest.fail("not admitted")
    assert gate.attempts == gate.finished == 2 and gate.active == 0
    assert not gate.truncated
    rows = [json.loads(line) for line in (tmp_path / "attempts.jsonl").read_text().splitlines()]
    assert {row["outcome"] for row in rows} == {"RETURNED", "CancelledError"}
    assert all(row["gate_wait_seconds"] >= 0 for row in rows)


def test_protection_sla_requires_every_owner_and_the_original_ready_time(tmp_path: Path) -> None:
    owners = [cast(f15.OwnerState, SimpleNamespace(user_id=uuid4())) for _ in range(20)]
    ready = datetime.now(UTC)
    path = tmp_path / "starts.jsonl"

    def write(count: int, last: float) -> None:
        path.write_text(
            "\n".join(
                json.dumps(
                    {
                        "owner": str(owner.user_id),
                        "ready": ready.isoformat(),
                        "started": (
                            ready + timedelta(seconds=last if index == 19 else 0.1)
                        ).isoformat(),
                    }
                )
                for index, owner in enumerate(owners[:count])
            )
        )

    write(19, 0.1)
    assert not processing_verdict([path], owners, ready)["passed"]
    write(20, 1.001)
    assert not processing_verdict([path], owners, ready)["passed"]
    write(20, 1)
    assert processing_verdict([path], owners, ready)["passed"]


async def test_snapshot_missing_owner_fails_and_preserves_observation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    owners = await f15.seed_owners(api_engine, engine_engine, scan_engine, 1)
    current = owners[0]
    wrong = f15.OwnerState(uuid4(), current.wallet)
    check = PositionChecks(engine_engine, [wrong], tmp_path)
    with pytest.raises(RuntimeError, match="MISSING_OR_WRONG_OWNER"):
        await check.snapshots(scheduled=0)
    assert check.rows[0]["outcome"] == "RuntimeError"
    assert check.rows[0]["queries"] > 0
    assert (tmp_path / "position-snapshots.jsonl").is_file()


@pytest.mark.usefixtures("internal_database")
async def test_restore_extension_fixture_and_retry_with_real_roles(tmp_path: Path) -> None:
    """Scoped harness safety check on a fresh DB, not the W4 backup/restore campaign."""
    engines = {
        role: create_engine_for(role)
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MIGRATOR,
            DatabaseRole.MARKET_DATA,
        )
    }
    observer = readonly_admin()
    try:
        async with observer.connect() as connection:
            assert (
                await connection.execute(text("SHOW transaction_read_only"))
            ).scalar_one() == "on"
        with pytest.raises(DBAPIError, match="read-only"):
            async with observer.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE risk_protocol_control "
                        "SET admission_enabled=admission_enabled WHERE false"
                    )
                )
        async with activated_protocols(engines[DatabaseRole.MIGRATOR], protections=True):
            fixture = await build_extension(engines, tmp_path)
            assert all((await extension_coverage(observer)).values())
            await recover(engines, fixture, tmp_path, observer=observer)
    finally:
        await observer.dispose()
        for engine in engines.values():
            await engine.dispose()


async def test_rejection_observer_preserves_delegation_and_omits_exception_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    from tests.infra.execution_market.profile_internal_restore import observe_rejections
    from tiewtrade.infra.db.session import UserSession
    from tiewtrade.infra.paper_orders import worker as order_worker
    from tiewtrade.infra.paper_orders.dispatch import ClaimedOrder

    original = AsyncMock()
    monkeypatch.setattr(order_worker, "_reject", original)
    command = {"id": uuid4(), "payload": "PRIVATE_COMMAND"}
    session, claim = cast(UserSession, object()), cast(ClaimedOrder, object())
    path = tmp_path / "rejections.jsonl"
    with observe_rejections(path):
        try:
            raise ValueError("PRIVATE_EXCEPTION")
        except ValueError:
            await order_worker._reject(session, claim, command, "ORDER_INPUT_INVALID")
    original.assert_awaited_once_with(session, claim, command, "ORDER_INPUT_INVALID")
    assert order_worker._reject is original
    content = path.read_text()
    assert "PRIVATE" not in content
    record = json.loads(content)
    assert record["error_type"] == "ValueError"
    assert (
        record["locations"][-1]["function"]
        == "test_rejection_observer_preserves_delegation_and_omits_exception_text"
    )


@pytest.mark.parametrize("state", [None, "TRANSFERRED", "REJECTED"])
async def test_terminal_rejection_check_only_fails_a_durable_rejection(
    tmp_path: Path,
    state: str | None,
) -> None:
    from unittest.mock import AsyncMock

    from tests.infra.execution_market.profile_internal_restore import check_terminal_rejection
    from tiewtrade.infra.db.session import UserSession

    row = None if state is None else {"intake_state": "TRANSFERRED", "command_state": state}
    session = cast(
        UserSession,
        SimpleNamespace(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    mappings=lambda: SimpleNamespace(one_or_none=lambda: row)
                )
            )
        ),
    )
    if state == "REJECTED":
        with pytest.raises(RuntimeError, match="TERMINAL_REJECTION"):
            await check_terminal_rejection(session, uuid4(), tmp_path)
        assert (tmp_path / "terminal-rejection.json").is_file()
    else:
        await check_terminal_rejection(session, uuid4(), tmp_path)
        assert not (tmp_path / "terminal-rejection.json").exists()


@pytest.mark.usefixtures("internal_database")
async def test_position_replay_records_database_work_and_rejects_reusing_occupied_database(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, scan_engine: AsyncEngine, tmp_path: Path
) -> None:
    from tests.infra.execution_market.profile_internal import require_empty_database

    owners = await f15.seed_owners(api_engine, engine_engine, scan_engine, 1)
    checks = PositionChecks(engine_engine, owners, tmp_path)
    result = await checks.final(expected_periodic=0)
    assert result["snapshot_samples"] == result["expected_samples"] == 1
    assert all(row["outcome"] == "RETURNED" for row in [*checks.rows, *result["replays"]])
    for row in [*checks.rows, *result["replays"]]:
        assert row["queries"] > 0 and row["rows_returned"] > 0
        assert row["peak_process_rss_bytes"] > 0
    with pytest.raises(ValueError, match="newly created empty"):
        await require_empty_database()


async def test_controlled_protection_baseline_uses_four_poll_slots_and_preserves_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from tests.infra.execution_market import profile_internal as internal
    from tests.infra.execution_market import profile_protections as controlled

    class BaselineCheckedError(Exception):
        pass

    owners = [
        cast(
            f15.OwnerState,
            SimpleNamespace(
                user_id=uuid4(), wallet=SimpleNamespace(wallet_id=uuid4(), episode_id=uuid4())
            ),
        )
        for _ in range(20)
    ]

    @asynccontextmanager
    async def activated(*args: object, **kwargs: object) -> AsyncIterator[None]:
        yield

    async def publisher(*args: object, **kwargs: object) -> None:
        await asyncio.Event().wait()

    async def baseline(
        engine: AsyncEngine,
        owners: list[f15.OwnerState],
        run_id: object,
        count: int,
        *,
        poll_gate: ParentPollGate,
    ) -> None:
        assert count == 20 and len(owners) == 20
        active = peak = 0

        async def read(owner: f15.OwnerState) -> None:
            nonlocal active, peak
            async with poll_gate.permit(owner.user_id, "baseline_result"):
                active += 1
                peak = max(active, peak)
                await asyncio.sleep(0.005)
                active -= 1

        await asyncio.gather(*(read(owner) for owner in owners))
        assert peak == 4 and poll_gate.finished == 20
        raise BaselineCheckedError

    monkeypatch.setattr(internal, "guard_database", lambda env: "isolated")
    monkeypatch.setattr(internal, "require_empty_database", AsyncMock())
    monkeypatch.setattr(internal, "activated_protocols", activated)
    monkeypatch.setattr(f15, "seed_owners", AsyncMock(return_value=owners))
    monkeypatch.setattr(
        controlled,
        "buy",
        AsyncMock(return_value=(SimpleNamespace(dispose=AsyncMock()), None, None, None, uuid4())),
    )
    monkeypatch.setattr(f15, "market_publisher", publisher)
    monkeypatch.setattr(f15, "wait_publisher_ready", AsyncMock())
    monkeypatch.setattr(f15, "start_worker_processes", AsyncMock(return_value=([], None, [])))
    monkeypatch.setattr(f15, "seed_baseline", baseline)
    output = tmp_path / "run"
    with pytest.raises(BaselineCheckedError):
        await controlled.run(output)
    result = json.loads((output / "parent-poll-gate.json").read_text())
    assert result["peak"] == 4 and result["active"] == 0
