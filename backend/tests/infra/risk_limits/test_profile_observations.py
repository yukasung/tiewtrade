"""R30 measurement boundaries fail closed without changing trading decisions."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.profile_observations import (
    PhaseJournal,
    cadence_summary,
    live_progress,
)
from tests.infra.risk_limits.profile_workload import measured_transaction_seconds
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


def test_nominal_cadence_excludes_drain_and_duplicate_receipts(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    path = tmp_path / "sources.jsonl"
    rows = []
    for kind, pair in (("BOOK", "BTC/USDT"), ("PRICE", "BTC/USDT"), ("PRICE", "ETH/USDT")):
        for number in range(6):
            rows.append(
                {
                    "kind": kind,
                    "pair": pair,
                    "identity": number,
                    "phase": "load",
                    "committed_at": (start + timedelta(seconds=number / 5)).isoformat(),
                }
            )
    path.write_text("\n".join(json.dumps(row) for row in [*rows, *rows]))
    result = cadence_summary(
        path, start=start, end=start + timedelta(seconds=1), price_suspensions=[]
    )
    assert result["passed"]
    assert result["target_hz"] == 5 and result["target_period_seconds"] == 0.2
    assert all(row["count"] == row["expected"] == 5 for row in result["channels"].values())
    assert all(row["gap_seconds"]["over_target_period"] == 0 for row in result["channels"].values())
    path.write_text(
        "\n".join(
            json.dumps(row) for row in rows if not (row["kind"] == "PRICE" and row["identity"] == 0)
        )
    )
    assert not cadence_summary(
        path, start=start, end=start + timedelta(seconds=1), price_suspensions=[]
    )["passed"]


def test_only_price_demand_is_exempt_and_overlaps_are_not_double_counted(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    path = tmp_path / "sources.jsonl"
    path.write_text("")
    end = start + timedelta(seconds=1)
    result = cadence_summary(
        path, start=start, end=end, price_suspensions=[(start, end), (start, end)]
    )
    assert result["price_exempt_seconds"] == 1
    assert result["channels"]["PRICE:BTC/USDT"]["passed"]
    assert not result["channels"]["BOOK:BTC/USDT"]["passed"]


@pytest.mark.parametrize(
    "change",
    [{"source_ready": False}, {"input_id": 79}, {"input_id": 101}, {"availability": "UNKNOWN"}],
)
def test_live_baseline_rejects_stale_source_lag_and_bad_cursor(change: dict[str, object]) -> None:
    row = {
        "owner_id": "a",
        "source_ready": True,
        "input_id": 80,
        "watermark": 100,
        "availability": "READY",
    }
    assert live_progress([row], {"a"}, 80)["passed"]
    assert not live_progress([{**row, **change}], {"a"}, 80)["passed"]
    assert not live_progress([row, row], {"a"}, 80)["passed"]
    assert not live_progress([row], {"a", "b"}, 80)["passed"]


def test_phase_journal_retains_setup_and_nominal_cut(tmp_path: Path) -> None:
    journal = PhaseJournal(tmp_path / "phases.jsonl")
    journal.begin_load(1)
    assert journal.load_start is not None and journal.load_end is not None
    assert journal.at(journal.load_start - timedelta(microseconds=1)) == "setup"
    assert journal.at(journal.load_start) == "load"
    assert journal.at(journal.load_end) == "drain"
    journal.mark("failure")
    assert len((tmp_path / "phases.jsonl").read_text().splitlines()) == 3


def test_transaction_start_attribution_keeps_full_cross_fault_duration(tmp_path: Path) -> None:
    path = tmp_path / "paper-0.json"
    path.write_text(
        json.dumps(
            {
                "transaction_samples": [
                    {"started": 9, "seconds": 8},
                    {"started": 10, "seconds": 2},
                    {"started": 12, "seconds": 1},
                ]
            }
        )
    )
    assert measured_transaction_seconds([path], started=0, ended=20, excluded=[(10, 12)]) == [8, 1]


async def test_restoration_resumes_gate_before_recovery_observer() -> None:
    from tests.infra.execution_market import profile_workload as f15

    gate = f15.FaultGate()
    observations: list[dict[str, object]] = []
    transitions: list[str] = []

    async def action() -> None:
        pass

    async def recover(row: dict[str, object]) -> None:
        assert row["status"] == "RESTORED"
        assert gate.open.is_set()
        assert "ended_at" in row

    await f15.run_fault_schedule(
        [f15.FaultEvent(offset_seconds=0, duration_seconds=0, kind="WORKER_RESTART")],
        gate,
        redis_container="unused",
        restart_workers=action,
        churn_connections=action,
        observations=observations,
        on_transition=lambda row: transitions.append(str(row["status"])),
        recover=recover,
    )
    assert transitions == ["STARTED", "RESTORED", "RECOVERED"]
    assert float(str(observations[0]["restored"])) <= float(str(observations[0]["recovered"]))


async def test_security_shape_includes_column_grants_and_policies(
    migrator_engine: AsyncEngine,
) -> None:
    from tests.infra.risk_limits.profile_restore import extra_security

    rows = await extra_security(migrator_engine)
    assert any(
        row.get("column_name") == "cursor" and row.get("grantee") == "tiewtrade_engine_scan"
        for row in rows
    )
    assert any("policyname" in row for row in rows)


async def test_failed_recovery_keeps_restored_fault_boundary() -> None:
    from tests.infra.execution_market import profile_workload as f15

    gate = f15.FaultGate()
    observations: list[dict[str, object]] = []

    async def action() -> None:
        pass

    async def recover(row: dict[str, object]) -> None:
        raise TimeoutError("recovery failed")

    with pytest.raises(TimeoutError, match="recovery failed"):
        await f15.run_fault_schedule(
            [f15.FaultEvent(0, 0, "WORKER_RESTART")],
            gate,
            redis_container="unused",
            restart_workers=action,
            churn_connections=action,
            observations=observations,
            on_transition=lambda row: None,
            recover=recover,
        )
    assert gate.open.is_set()
    assert observations[0]["status"] == "RESTORED"
    assert "ended_at" in observations[0] and "recovered_at" not in observations[0]


def test_fixed_rss_window_cannot_use_setup_or_late_drain() -> None:
    from tests.infra.execution_market import profile_workload as f15
    from tests.infra.risk_limits.test_workload_profile import samples

    rows = samples(1800, 21)
    start = rows[0]["at"]
    assert isinstance(start, datetime)
    extras = [
        {"at": start - timedelta(seconds=10), "total_rss_bytes": 999999},
        {"at": start + timedelta(seconds=2000), "total_rss_bytes": 1},
    ]
    result = f15.endurance_rss(
        [extras[0], *rows, extras[1]], duration_seconds=1800, measured_start=start
    )
    assert not result["passed"]
    assert result["growth_fraction"] == 0.21
    assert not f15.endurance_rss(rows[:40], duration_seconds=1800, measured_start=start)["passed"]


async def test_live_snapshot_missing_owner_times_out_without_mutation(
    tmp_path: Path, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    from time import monotonic

    from tests.infra.execution_market import profile_workload as f15
    from tests.infra.risk_limits.profile_workload import Fixture

    fixture = Fixture(tmp_path)
    fixture.owners = [f15.OwnerState(owner, wallet)]
    try:
        with pytest.raises(TimeoutError):
            await fixture.live_baseline(10**12, monotonic() + 0.1)
    finally:
        await fixture.close()


async def test_live_snapshot_uses_one_database_time_across_owner_reads(
    engine_engine: AsyncEngine,
) -> None:
    """A slow owner inventory must not age its own repeatable-read snapshot."""
    from tiewtrade.infra.db import DatabaseRole
    from tiewtrade.infra.db import session as db_session

    async with db_session._begin(engine_engine) as connection:
        await connection.exec_driver_sql(
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
        )
        await db_session._assert_role(connection, DatabaseRole.ENGINE)
        first = (
            (
                await connection.exec_driver_sql(
                    "SELECT transaction_timestamp() AS snapshot_at, "
                    "statement_timestamp() AS read_at"
                )
            )
            .mappings()
            .one()
        )
        await connection.exec_driver_sql("SELECT pg_sleep(1.05)")
        second = (
            (
                await connection.exec_driver_sql(
                    "SELECT transaction_timestamp() AS snapshot_at, "
                    "statement_timestamp() AS read_at"
                )
            )
            .mappings()
            .one()
        )
    assert first["snapshot_at"] == second["snapshot_at"]
    assert second["read_at"] > first["read_at"]


async def test_live_recovery_uses_committed_sources_and_owner_progress(
    tmp_path: Path,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from dataclasses import replace
    from time import monotonic

    from tests.infra.execution_market import profile_workload as f15
    from tests.infra.execution_market.test_dispatch import intent
    from tests.infra.risk_limits.profile_workload import Fixture
    from tests.infra.risk_limits.test_execution import drive, runtime
    from tiewtrade.core.money import Money
    from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
    from tiewtrade.infra.db import DatabaseRole, user_session
    from tiewtrade.infra.db.session import market_data_session
    from tiewtrade.infra.market_data.realtime_storage import read_snapshot, write_price
    from tiewtrade.infra.paper_orders.dispatch import submit_order

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        # The F15 runtime fixture seeds BTC only; F18 requires both declared pairs.
        async with market_data_session(sources.market) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.feed is not None
            eth = next(row for row in snapshot.rows if row.base == "ETH")
            quote = QuoteObservation(
                eth.source,
                "ETH",
                "USDT",
                Money.of(2000, "USDT"),
                1 if eth.observation is None else eth.observation.trade_id + 1,
                snapshot.server_time,
                snapshot.server_time,
                ObservationKind.STREAM,
            )
            assert await write_price(
                session,
                snapshot.feed,
                replace(
                    eth,
                    observation=quote,
                    reconciled_generation=snapshot.feed.generation,
                    effective_readiness="READY",
                    reason=None,
                    unavailable_since=None,
                    order_ambiguous_at=None,
                ),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
        await drive(engine_engine, owner, command.command_id)
        fixture = Fixture(tmp_path)
        fixture.owners = [f15.OwnerState(owner, wallet)]
        try:
            result = await fixture.live_baseline(sources.lease.last_input_id, monotonic() + 0.5)
            assert result["passed"] and result["inventory_complete"]
            assert result["risk_progress"][0]["pending"] is False
        except TimeoutError:
            raise AssertionError(fixture.last_live_baseline) from None
        finally:
            await fixture.close()


async def test_restore_role_checks_use_real_owner_isolation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
) -> None:
    from tests.infra.risk_limits.profile_restore import verify_role_access
    from tests.infra.risk_limits.test_requests import seed_setting
    from tiewtrade.infra.db import DatabaseRole

    await seed_setting(engine_engine, owner)
    await verify_role_access(
        {
            DatabaseRole.API: api_engine,
            DatabaseRole.ENGINE: engine_engine,
            DatabaseRole.ENGINE_SCAN: scan_engine,
        },
        owner,
    )


def test_delayed_receipt_keeps_commit_phase_after_publisher_restart(tmp_path: Path) -> None:
    journal = PhaseJournal(tmp_path / "phases.jsonl")
    injection = journal.mark("injection")
    journal.mark("recovery")
    assert journal.at(datetime.fromisoformat(injection["at"])) == "injection"


def test_overflow_budget_starts_after_injection_and_before_restart() -> None:
    from tests.infra.risk_limits.profile_observations import overflow_timings

    result = overflow_timings(before=0, injection=1, recovery=76, recovered=83, finished=85)
    assert result == {
        "injection_seconds": 75,
        "recovery_seconds": 7,
        "verification_seconds": 3,
        "total_seconds": 85,
    }
    assert (
        overflow_timings(before=0, injection=1, recovery=76, recovered=137, finished=138)[
            "recovery_seconds"
        ]
        > 60
    )
    with pytest.raises(ValueError, match="out of order"):
        overflow_timings(before=0, injection=1, recovery=76, recovered=75, finished=85)


@pytest.mark.parametrize("grant", ["missing", "excess"])
async def test_restore_security_rejects_changed_scanner_grants(
    migrator_engine: AsyncEngine,
    grant: str,
) -> None:
    from tests.infra.risk_limits.profile_restore import extra_security

    change, restore = (
        (
            "REVOKE SELECT(cursor) ON risk_owner_state FROM tiewtrade_engine_scan",
            "GRANT SELECT(cursor) ON risk_owner_state TO tiewtrade_engine_scan",
        )
        if grant == "missing"
        else (
            "GRANT SELECT(book) ON risk_owner_state TO tiewtrade_engine_scan",
            "REVOKE SELECT(book) ON risk_owner_state FROM tiewtrade_engine_scan",
        )
    )
    before = await extra_security(migrator_engine)
    try:
        async with migrator_engine.begin() as connection:
            await connection.exec_driver_sql(change)
        with pytest.raises(RuntimeError, match="SCANNER_PRIVILEGES_INVALID"):
            await extra_security(migrator_engine)
    finally:
        async with migrator_engine.begin() as connection:
            await connection.exec_driver_sql(restore)
    assert await extra_security(migrator_engine) == before


async def test_restore_security_detects_policy_definition_change(
    migrator_engine: AsyncEngine,
) -> None:
    from tests.infra.risk_limits.profile_restore import extra_security

    before = await extra_security(migrator_engine)
    policy = next(row for row in before if row.get("tablename") == "risk_owner_state")
    try:
        async with migrator_engine.begin() as connection:
            await connection.exec_driver_sql(
                "ALTER POLICY risk_owner_state_owner ON risk_owner_state USING(false)"
            )
        assert await extra_security(migrator_engine) != before
    finally:
        async with migrator_engine.begin() as connection:
            await connection.exec_driver_sql(
                f"ALTER POLICY risk_owner_state_owner ON risk_owner_state USING({policy['qual']})"
            )
    assert await extra_security(migrator_engine) == before


@pytest.mark.parametrize("missing", [0, 1, 2])
def test_r34_allowance_is_one_per_channel_window(tmp_path: Path, missing: int) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    path = tmp_path / "sources.jsonl"
    rows = []
    for kind, pair in (("BOOK", "BTC/USDT"), ("PRICE", "BTC/USDT"), ("PRICE", "ETH/USDT")):
        for number in [*range(10 - missing), 10]:
            rows.append(
                {
                    "kind": kind,
                    "pair": pair,
                    "identity": number,
                    "phase": "load",
                    "committed_at": (start + timedelta(seconds=number / 5)).isoformat(),
                }
            )
    path.write_text("\n".join(json.dumps(row) for row in [*rows, *rows]))
    result = cadence_summary(
        path,
        start=start,
        end=start + timedelta(seconds=2),
        price_suspensions=[],
        missing_commit_allowance=1,
    )
    assert result["passed"] is (missing <= 1)
    assert all(row["count"] == 10 - missing for row in result["channels"].values())
    assert all(
        row["expected"] == 10 and row["minimum_count"] == 9 for row in result["channels"].values()
    )
