"""Real pools prove bounded lazy growth and reject outstanding loans at shutdown."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.pool import QueuePool

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market.profile_owned_pools import (
    CURRENT,
    PARENT_CONFIGURATION,
    WORKER_CONFIGURATION,
    OwnedPools,
    validate_reports,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.api.app import app, lifespan


def document(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))


async def test_lazy_real_pool_growth_is_returned_within_existing_capacity(tmp_path: Path) -> None:
    path = tmp_path / "pools.json"
    with OwnedPools(path, [("ENGINE", 5, 10)]) as tracker:
        engine = create_engine_for(DatabaseRole.ENGINE)
        loans = []
        try:
            for _ in range(4):
                loans.append(await engine.connect())
            tracker.sample()
            assert tracker.entries[0]["checked_out"] == 4
            for loan in loans:
                await loan.close()
            tracker.sample()
            assert cast(QueuePool, engine.pool).checkedin() == 4
        finally:
            await engine.dispose()
    assert document(path)["passed"]
    assert document(path)["pools"][0]["peak_checked_out"] == 4
    assert document(path)["pools"][0]["final_disposal_checked_out"] == 0
    assert CURRENT.get() is None


async def test_loan_at_final_disposal_fails_below_configured_capacity(tmp_path: Path) -> None:
    path = tmp_path / "pools.json"
    loan = None
    try:
        with OwnedPools(path, [("ENGINE", 5, 10)]):
            engine = create_engine_for(DatabaseRole.ENGINE)
            loan = await engine.connect()
            await engine.dispose()
        result = document(path)
        assert not result["passed"]
        assert result["pools"][0]["checked_out"] == 1
        assert result["pools"][0]["final_disposal_checked_out"] == 1
    finally:
        if loan is not None:
            await loan.invalidate()
            await loan.close()


@pytest.mark.parametrize("failure", ["capacity", "inventory", "resource_error"])
async def test_invalid_inventory_capacity_or_connection_failure_is_retained(
    tmp_path: Path, failure: str
) -> None:
    path = tmp_path / "pools.json"
    with OwnedPools(
        path, WORKER_CONFIGURATION if failure == "inventory" else [("ENGINE", 5, 10)]
    ) as tracker:
        engine = create_engine_for(DatabaseRole.ENGINE)
        if failure == "capacity":
            original = cast(QueuePool, engine.pool)._max_overflow
            cast(QueuePool, engine.pool)._max_overflow = 20
            tracker.sample()
            cast(QueuePool, engine.pool)._max_overflow = original
        elif failure == "resource_error":
            engine.sync_engine.dialect.dispatch.handle_error(
                Mock(is_disconnect=True, original_exception=OSError("PRIVATE"))
            )
        await engine.dispose()
    assert not document(path)["passed"]
    assert "PRIVATE" not in path.read_text()


async def test_pool_timeout_cannot_disappear_after_all_loans_are_returned(tmp_path: Path) -> None:
    path = tmp_path / "pools.json"
    with OwnedPools(path, [("ENGINE", 1, 0)]):
        engine = create_engine_for(
            DatabaseRole.ENGINE, pool_size=1, max_overflow=0, pool_timeout=0.01
        )
        async with engine.connect():
            with pytest.raises(PoolTimeoutError):
                async with engine.connect():
                    pass
        await engine.dispose()
    result = document(path)
    assert not result["passed"] and result["errors"]["PoolTimeoutError"] == 1
    assert result["pools"][0]["checked_out"] == 0


async def test_planned_generation_change_retains_original_pool_and_configuration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pools.json"
    with OwnedPools(path, [("ENGINE", 5, 10)]) as tracker:
        engine = create_engine_for(DatabaseRole.ENGINE)
        async with engine.connect():
            pass
        with tracker.intermediate_disposal():
            await engine.dispose()
        async with engine.connect():
            pass
        await engine.dispose()
    result = document(path)
    assert result["passed"]
    assert [p["generation"] for p in result["pools"]] == [0, 1]
    assert result["pools"][0]["intermediate_disposed"]


async def test_actual_asgi_lifespan_records_all_lazy_engines_and_returns_them(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pools.json"
    expected = [
        ("API", 5, 10),
        ("API", 1, 0),
        ("AUTH", 5, 10),
        ("API", 3, 0),
        ("API", 1, 0),
        ("API", 1, 0),
    ]
    with OwnedPools(path, expected) as tracker:
        async with lifespan(app):
            try:
                async with app.state.api_engine.connect(), app.state.api_engine.connect():
                    pass
            finally:
                tracker.begin_quiescence()
    assert document(path)["passed"]
    assert len(document(path)["configuration"]) == 6


@pytest.mark.parametrize("failure", [RuntimeError("PRIVATE"), asyncio.CancelledError()])
async def test_observer_restores_hooks_and_preserves_primary_exception(
    tmp_path: Path, failure: BaseException
) -> None:
    original = (AsyncEngine.__init__, AsyncEngine.dispose, AsyncConnection.start)
    path = tmp_path / "pools.json"
    with pytest.raises(type(failure)) as caught, OwnedPools(path, [("ENGINE", 5, 10)]):
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            raise failure
        finally:
            await engine.dispose()
    assert caught.value is failure and CURRENT.get() is None
    assert (AsyncEngine.__init__, AsyncEngine.dispose, AsyncConnection.start) == original
    assert not document(path)["passed"] and "PRIVATE" not in path.read_text()


async def test_missing_or_nonfinal_worker_report_cannot_be_waived(tmp_path: Path) -> None:
    parent = tmp_path / "parent.json"
    worker = tmp_path / "worker.json"
    # Missing evidence is rejected independently of connection totals.
    parent.write_text(json.dumps({"configuration": PARENT_CONFIGURATION, "passed": True}))
    assert not validate_reports(parent, [worker], 1)["passed"]
    assert not validate_reports(parent, [], 1)["passed"]


@pytest.mark.parametrize("profile_name", [internal.NAME, internal.NAME_V2, internal.NAME_V3])
async def test_internal_worker_entry_samples_real_pools_and_joins_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile_name: str
) -> None:
    import argparse

    from tests.infra.execution_market import profile_workload as workload
    from tiewtrade.services.engine import paper_order

    stop = tmp_path / "stop"
    metrics = tmp_path / "worker.json"
    calls = []

    async def round_trip(**options: Any) -> None:
        calls.append(options.get("worker", "protection"))
        async with options["engine"].connect(), options["scan_engine"].connect():
            pass
        if len(calls) == 3:
            stop.touch()

    monkeypatch.setattr(paper_order, "run_protection_round", round_trip)
    monkeypatch.setattr(workload, "run_manual_order_round", round_trip)
    monkeypatch.setattr(workload, "run_paper_order_round", round_trip)
    await workload.worker_entry(
        argparse.Namespace(
            acceptance_profile=profile_name,
            worker_only=True,
            worker_name="pool-regression",
            worker_stop=stop,
            worker_metrics=metrics,
            r8_claim_budget=True,
            coordinate_claims=True,
            diagnostics=False,
        )
    )
    report = document(metrics.with_suffix(".owned-pools.json"))
    assert report["passed"] and len(report["pools"]) == 2
    assert all(p["peak_checked_out"] == 1 for p in report["pools"])
    assert len(calls) == 3 and CURRENT.get() is None


@pytest.mark.parametrize(
    "corruption",
    [
        None,
        "borrow",
        "inventory",
        "sample_file",
        "configuration",
        "timeout",
        "observer_error",
        "both",
    ],
)
@pytest.mark.usefixtures("internal_database")
async def test_complete_reports_and_restart_are_required(
    tmp_path: Path, corruption: str | None
) -> None:
    parent, worker, restart = (
        tmp_path / name for name in ["parent.json", "worker.json", "restart.json"]
    )
    for path, configuration in [
        (parent, PARENT_CONFIGURATION),
        (worker, WORKER_CONFIGURATION),
        (restart, WORKER_CONFIGURATION),
    ]:
        with OwnedPools(path, configuration):
            engines = [
                internal.readonly_admin()
                if role == "ADMIN_OBSERVER"
                else create_engine_for(DatabaseRole[role], pool_size=size, max_overflow=overflow)
                for role, size, overflow in configuration
            ]
            for engine in engines:
                await engine.dispose()
    if corruption:
        report = document(restart)
        if corruption == "borrow":
            report["pools"][0]["checked_out"] = 1
        elif corruption in {"timeout", "observer_error", "both"}:
            report["passed"] = False
            report["errors"] = (
                {"PoolTimeoutError": 1}
                if corruption == "timeout"
                else {"OSError": 1}
                if corruption == "observer_error"
                else {"PoolTimeoutError": 1, "OSError": 1}
            )
        elif corruption == "inventory":
            del report["pools"]
        elif corruption == "configuration":
            report["pools"][0]["pool_size"] = 100
        else:
            restart.with_suffix(".jsonl").unlink()
        restart.write_text(json.dumps(report))
    result = validate_reports(parent, [worker, restart], 1)
    assert result["passed"] == (corruption is None)
    if corruption in {"borrow", "timeout", "both"}:
        assert result["violations"]
        if corruption == "both":
            assert result["incomplete"]
    elif corruption is not None:
        assert result["incomplete"] and not result["violations"]


async def test_stream_write_failure_preserves_primary_and_removes_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = (AsyncEngine.__init__, AsyncEngine.dispose, AsyncConnection.start)
    failure = RuntimeError("PRIVATE")
    with (
        pytest.raises(RuntimeError) as caught,
        OwnedPools(tmp_path / "pools.json", [("ENGINE", 5, 10)]),
    ):
        monkeypatch.setattr(Path, "write_text", Mock(side_effect=OSError("PRIVATE")))
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            raise failure
        finally:
            await engine.dispose()
    assert caught.value is failure
    assert (AsyncEngine.__init__, AsyncEngine.dispose, AsyncConnection.start) == original
    assert CURRENT.get() is None


@pytest.mark.usefixtures("internal_database")
async def test_empty_database_startup_asgi_and_parent_shutdown_have_complete_inventory(
    tmp_path: Path,
) -> None:
    path = tmp_path / "parent.json"
    with OwnedPools(path, PARENT_CONFIGURATION) as tracker:
        # The exact previously missed production campaign startup function.
        await internal.require_empty_database()
        engines = [
            create_engine_for(role)
            for role in [
                DatabaseRole.MARKET_DATA,
                DatabaseRole.MIGRATOR,
                DatabaseRole.API,
                DatabaseRole.ENGINE,
                DatabaseRole.ENGINE_SCAN,
                DatabaseRole.AUTH,
            ]
        ]
        try:
            async with lifespan(app):
                for engine in engines:
                    async with engine.connect():
                        pass
                tracker.begin_quiescence()
        finally:
            for engine in engines:
                await engine.dispose()
    result = document(path)
    assert result["passed"] and len(result["pools"]) == 13
    admin = next(p for p in result["pools"] if p["role"] == "ADMIN_OBSERVER")
    assert admin["peak_checked_out"] == 1
    assert admin["final_disposal_checked_out"] == 0
    assert "postgresql+asyncpg" not in path.read_text()


@pytest.mark.parametrize("invalid", ["identity", "options"])
async def test_unknown_admin_identity_or_read_write_engine_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    path = tmp_path / "parent.json"
    admin_url = os.environ["TIEWTRADE_TEST_ADMIN_URL"]
    if invalid == "identity":
        monkeypatch.setenv("TIEWTRADE_TEST_ADMIN_URL", admin_url + "_different")
    with OwnedPools(path, [("ADMIN_OBSERVER", 5, 10)]):
        engine = create_async_engine(
            admin_url,
            execution_options={
                "isolation_level": "REPEATABLE READ",
                "postgresql_readonly": invalid != "options",
            },
        )
        await engine.dispose()
    result = document(path)
    assert not result["passed"] and result["errors"] == {"ValueError": 1}
    assert admin_url not in path.read_text()


@pytest.mark.usefixtures("internal_database")
async def test_admin_observer_borrow_cannot_be_waived(tmp_path: Path) -> None:
    path = tmp_path / "parent.json"
    loan = None
    try:
        with OwnedPools(path, [("ADMIN_OBSERVER", 5, 10)]):
            engine = internal.readonly_admin()
            loan = await engine.connect()
            await engine.dispose()
        result = document(path)
        assert not result["passed"]
        assert result["pools"][0]["final_disposal_checked_out"] == 1
    finally:
        if loan is not None:
            await loan.invalidate()
            await loan.close()


@pytest.mark.parametrize("readonly", [True, False])
@pytest.mark.usefixtures("internal_database")
async def test_real_query_cancellation_records_origin_and_preserves_deadline_or_cancel(
    tmp_path: Path, readonly: bool
) -> None:
    from sqlalchemy import text

    path = tmp_path / "pools.json"
    role = "ADMIN_OBSERVER" if readonly else "ENGINE"
    original = (AsyncEngine.__init__, AsyncEngine.dispose, AsyncConnection.start)
    started = asyncio.Event()
    with OwnedPools(path, [(role, 5, 10)]):
        engine = internal.readonly_admin() if readonly else create_engine_for(DatabaseRole.ENGINE)
        try:
            async with engine.connect() as connection:

                async def query_with_known_deadline() -> None:
                    # Open the connection first: the deadline must cancel actual SQL I/O.
                    async with asyncio.timeout(0.1) as deadline:
                        await connection.execute(
                            text("SELECT pg_sleep(2), :payload"), {"payload": "PRIVATE"}
                        )
                    assert not deadline.expired()

                async def explicitly_cancelled_engine_query() -> None:
                    started.set()
                    await connection.execute(
                        text("SELECT pg_sleep(2), :payload"), {"payload": "PRIVATE"}
                    )

                if readonly:
                    task = asyncio.create_task(query_with_known_deadline(), name="PRIVATE")
                    with pytest.raises(TimeoutError):
                        await task
                else:
                    task = asyncio.create_task(explicitly_cancelled_engine_query(), name="PRIVATE")
                    await started.wait()
                    await asyncio.sleep(0.1)
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
        finally:
            await engine.dispose()
    result = document(path)
    assert not result["passed"] and result["errors"] == {"ConnectionResourceError": 1}
    detail = result["resource_errors"][0]
    assert detail["error_type"] == "CancelledError"
    assert detail["task_id"] == id(task) and detail["cancellation_requests"] >= 1
    assert detail["role"] == role and detail["configured_readonly"] is readonly
    assert detail["pool_id"] == result["pools"][0]["pool_id"]
    assert detail["generation"] == 0 and detail["pid"] == result["pid"]
    assert detail["monotonic"] > 0 and detail["at"].endswith("+00:00")
    expected = "query_with_known_deadline" if readonly else "explicitly_cancelled_engine_query"
    assert expected in [frame["function"] for frame in detail["await_chain"]]
    assert detail["deadline_context"] == "not_observed"
    assert result["pools"][0]["checked_out"] == 0
    assert result["pools"][0]["final_disposal_checked_out"] == 0
    assert "PRIVATE" not in path.read_text() and "pg_sleep" not in path.read_text()
    assert len(detail["await_chain"]) <= 8
    assert CURRENT.get() is None
    assert (AsyncEngine.__init__, AsyncEngine.dispose, AsyncConnection.start) == original


async def test_provenance_is_bounded_and_missing_task_stays_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "pools.json"
    with OwnedPools(path, [("ENGINE", 5, 10)]):
        engine = create_engine_for(DatabaseRole.ENGINE)
        with monkeypatch.context() as patched:
            patched.setattr(asyncio, "current_task", lambda: None)
            for _ in range(20):
                engine.sync_engine.dialect.dispatch.handle_error(
                    Mock(is_disconnect=True, original_exception=OSError("PRIVATE"))
                )
        await engine.dispose()
    result = document(path)
    assert result["errors"] == {"ConnectionResourceError": 20}
    assert len(result["resource_errors"]) == 16 and result["resource_errors_omitted"] == 4
    assert result["resource_errors"][0]["task_id"] is None
    assert result["resource_errors"][0]["await_chain"] == []
    assert not result["passed"] and "PRIVATE" not in path.read_text()


async def test_provenance_failure_does_not_mask_primary_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.infra.execution_market import profile_owned_pools as owned

    path = tmp_path / "pools.json"
    failure = RuntimeError("PRIVATE")
    with pytest.raises(RuntimeError) as caught, OwnedPools(path, [("ENGINE", 5, 10)]):
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            monkeypatch.setattr(owned, "task_provenance", Mock(side_effect=TypeError("PRIVATE")))
            engine.sync_engine.dialect.dispatch.handle_error(
                Mock(is_disconnect=True, original_exception=OSError("PRIVATE"))
            )
            raise failure
        finally:
            await engine.dispose()
    assert caught.value is failure and CURRENT.get() is None
    result = document(path)
    assert result["errors"] == {"ConnectionResourceError": 1, "Provenance:TypeError": 1}
    assert result["resource_errors"][0]["provenance_error_type"] == "TypeError"
    assert "PRIVATE" not in path.read_text()


async def test_retired_native_negative_counts_do_not_replace_real_loan_accounting(
    tmp_path: Path,
) -> None:
    import gc

    path = tmp_path / "pools.json"
    loans = []
    with OwnedPools(path, [("ENGINE", 5, 10)]) as tracker:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            loans = [await engine.connect(), await engine.connect()]
            old_ref = tracker.bindings[0][1]
            with tracker.intermediate_disposal():
                await engine.dispose()
            async with engine.connect():
                pass
            await loans.pop().close()
            tracker.sample("one_late_return")
            assert old_ref().checkedout() == -1
            assert tracker.entries[0]["checked_out"] == 1
            await loans.pop().close()
            gc.collect()
            tracker.sample("all_retired_returns")
            assert old_ref() is None  # Observer must not keep retired pools alive.
            assert tracker.entries[0]["checked_out"] == 0
        finally:
            for loan in loans:
                await loan.close()
            await engine.dispose()
    report = document(path)
    assert report["passed"] and not report["errors"]
    samples = [json.loads(line) for line in path.with_suffix(".jsonl").read_text().splitlines()]
    rows = [p for row in samples for p in row["pools"] if p.get("checked_out", 0) < 0]
    assert rows and all(
        p["lifecycle"] == "retired" and not p["native_counts_binding"] for p in rows
    )
    assert all(p["checked_out"] == 0 for p in report["pools"])


@pytest.mark.parametrize("returned", [True, False])
async def test_retired_missing_native_view_waits_for_return_but_never_waives_it(
    tmp_path: Path, returned: bool
) -> None:
    import gc

    path = tmp_path / "pools.json"
    loan = None
    try:
        with OwnedPools(path, [("ENGINE", 5, 10)]) as tracker:
            engine = create_engine_for(DatabaseRole.ENGINE)
            loan = await engine.connect()
            with tracker.intermediate_disposal():
                await engine.dispose()
            known, _, entry = tracker.bindings[0]
            # Simulate a collected weakref view; retain the actual DB loan so its
            # genuine checkin event can arrive later. GC must not waive that loan.
            tracker.bindings[0] = (known, lambda: None, entry)
            gc.collect()
            tracker.sample("retired_pending_without_native_view")
            assert entry["checked_out"] == 1 and not tracker.errors
            assert not document(path)["passed"]
            if returned:
                await loan.close()
            await engine.dispose()
        report = document(path)
        assert report["passed"] is returned
        assert report["pools"][0]["final_disposal_checked_out"] == (0 if returned else 1)
    finally:
        if loan is not None and not loan.closed:
            await loan.invalidate()
            await loan.close()
    assert CURRENT.get() is None


async def test_unretired_missing_pool_still_fails(tmp_path: Path) -> None:
    path = tmp_path / "pools.json"
    with OwnedPools(path, [("ENGINE", 5, 10)]) as tracker:
        engine = create_engine_for(DatabaseRole.ENGINE)
        known, _, entry = tracker.bindings[0]
        tracker.bindings[0] = (known, lambda: None, entry)
        tracker.sample()
        await engine.dispose()
    report = document(path)
    assert not report["passed"] and report["errors"]["PoolDisappearedBeforeReturn"] > 0


async def test_retired_pool_capacity_mutation_still_fails(tmp_path: Path) -> None:
    path = tmp_path / "pools.json"
    loan = None
    with OwnedPools(path, [("ENGINE", 5, 10)]) as tracker:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            loan = await engine.connect()
            pool_ref = tracker.bindings[0][1]
            with tracker.intermediate_disposal():
                await engine.dispose()
            pool_ref()._max_overflow = 20
            tracker.sample()
            pool_ref()._max_overflow = 10
        finally:
            if loan is not None:
                await loan.close()
            await engine.dispose()
    report = document(path)
    assert not report["passed"] and report["errors"]["PoolCapacityViolation"] > 0
