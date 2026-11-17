"""Original reader/decoder counts, real-PG owner isolation and wrapper restoration."""

import asyncio
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_tail_reads as tail
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_replay_reads import (
    ReplayReadObserver,
    finalize_replay_run,
    save_partial_result,
)
from tests.infra.execution_market.test_publisher_clock_recovery import financial_state
from tests.infra.execution_market.test_tail_reads import market as market
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders import storage


async def test_real_pages_rls_no_write_and_task_isolation(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path
) -> None:
    engine, owners = market
    owner = owners[0]
    await tail.seed_history(engine, owner, 3, tmp_path)
    before = await financial_state(engine, owner.user_id)
    execute, decode = UserSession.execute, storage._decode
    observer = ReplayReadObserver()
    args = {"episode_id": owner.wallet.episode_id, "pair": PositionPair("BTC", "USDT"), "limit": 2}
    with observer.observe():
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            await session.execute("SET TRANSACTION READ ONLY")
            first = await observer.read_page(session, after_input_id=0, **args)
            second = await observer.read_page(session, after_input_id=2, **args)
            empty = await observer.read_page(session, after_input_id=3, **args)
            assert [x.record.market.input_id for x in (*first, *second)] == [1, 2, 3]
            assert empty == ()

            # A child inherits the context variable but cannot contribute to parent counters.
            async def child() -> None:
                await session.execute("SELECT 1")

            await asyncio.create_task(child())
        async with user_session(engine, owners[1].user_id, role=DatabaseRole.ENGINE) as session:
            assert await observer.read_page(session, after_input_id=0, **args) == ()
    assert [row["sql_calls"] for row in observer.pages] == [1, 1, 1, 1]
    assert [row["decode_calls"] for row in observer.pages] == [2, 1, 0, 0]
    assert all(row["seconds"] >= row["sql_driver_seconds"] for row in observer.pages)
    assert UserSession.execute is execute and storage._decode is decode
    assert await financial_state(engine, owner.user_id) == before


async def test_decoder_error_called_once_and_originals_restored(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path
) -> None:
    engine, owners = market
    owner = owners[0]
    await tail.seed_history(engine, owner, 1, tmp_path)
    observer = ReplayReadObserver()
    original = UserSession.execute
    error = ValueError("fixture decoder failure")
    with patch.object(storage, "_decode", side_effect=error) as decode:
        with pytest.raises(ValueError) as caught, observer.observe():
            async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
                await observer.read_page(
                    session,
                    episode_id=owner.wallet.episode_id,
                    pair=PositionPair("BTC", "USDT"),
                    after_input_id=0,
                    limit=2,
                )
        assert caught.value is error
        decode.assert_called_once()
        assert storage._decode is decode
    assert UserSession.execute is original
    assert observer.pages[0]["outcome"] == "ValueError"
    assert observer.pages[0]["decode_calls"] == 1


async def test_cancellation_preserves_partial_page_and_restores_wrappers() -> None:
    observer = ReplayReadObserver()
    original = UserSession.execute
    entered = asyncio.Event()

    async def pending(*args: object, **kwargs: object) -> None:
        entered.set()
        await asyncio.Future()

    async def run() -> None:
        with observer.observe():
            await observer.read_page(None, after_input_id=0, limit=2)  # type: ignore[arg-type]

    with patch.object(storage, "read_execution_inputs", pending):
        task = asyncio.create_task(run())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert observer.pages[0]["outcome"] == "CancelledError"
    assert UserSession.execute is original


async def test_inherited_page_context_excludes_foreign_task() -> None:
    observer = ReplayReadObserver()

    async def execute(*args: object, **kwargs: object) -> None:
        pass

    async def read(*args: object, **kwargs: object) -> tuple[()]:
        async def foreign() -> None:
            await UserSession.execute(None, "SELECT 1")  # type: ignore[arg-type]
            storage._decode({})

        await asyncio.create_task(foreign())
        return ()

    with (
        patch.object(UserSession, "execute", execute),
        patch.object(storage, "_decode", return_value=None) as decode,
        patch.object(storage, "read_execution_inputs", side_effect=read) as reader,
        observer.observe(),
    ):
        assert await observer.read_page(None, after_input_id=0, limit=2) == ()  # type: ignore[arg-type]
        reader.assert_called_once()
        decode.assert_called_once()
    assert observer.pages[0]["sql_calls"] == observer.pages[0]["decode_calls"] == 0


@pytest.mark.parametrize("cancelled", [False, True])
def test_partial_io_failure_retains_original_read_error(tmp_path: Path, cancelled: bool) -> None:
    primary = asyncio.CancelledError() if cancelled else TimeoutError()
    report: dict[str, object] = {"status": "DIAGNOSTIC_COMPLETE"}
    with (
        patch.object(Path, "write_text", side_effect=OSError("private IO detail")),
        pytest.raises(type(primary)) as caught,
    ):
        try:
            raise primary
        finally:
            save_partial_result(tmp_path / "partial.json", report)
    assert caught.value is primary
    assert report["status"] == "INCOMPLETE"
    assert report["error_type"] == type(primary).__name__
    assert "private IO detail" not in str(report)
    assert primary.__notes__ == ["replay partial_result failed: OSError"]


def test_partial_io_failure_without_read_error_raises(tmp_path: Path) -> None:
    report: dict[str, object] = {}
    error = OSError()
    with patch.object(Path, "write_text", side_effect=error), pytest.raises(OSError) as caught:
        save_partial_result(tmp_path / "partial.json", report)
    assert caught.value is error
    assert report["status"] == "INCOMPLETE"


@pytest.mark.parametrize("fault", ["source_exception", "source_changed", "cleanup", "save", "none"])
def test_finalization_attempts_cleanup_and_save_after_each_failure(fault: str) -> None:
    calls: list[str] = []
    report: dict[str, object] = {"status": "DIAGNOSTIC_COMPLETE"}
    error = OSError()

    def source_check() -> bool:
        calls.append("source")
        if fault == "source_exception":
            raise error
        return fault != "source_changed"

    def cleanup() -> dict[str, object]:
        calls.append("cleanup")
        if fault == "cleanup":
            raise error
        return {"removed": True}

    def save() -> None:
        calls.append("save")
        if fault == "save":
            raise error

    if fault == "none":
        finalize_replay_run(
            report,
            source_check=source_check,
            cleanup_owned=cleanup,
            save_result=save,
            database="owned_fixture",
        )
        assert report["status"] == "DIAGNOSTIC_COMPLETE"
        assert "evidence_errors" not in report
    else:
        with pytest.raises(ValueError if fault == "source_changed" else OSError) as caught:
            finalize_replay_run(
                report,
                source_check=source_check,
                cleanup_owned=cleanup,
                save_result=save,
                database="owned_fixture",
            )
        assert report["status"] == "INCOMPLETE"
        if fault != "source_changed":
            assert caught.value is error
    assert calls == ["source", "cleanup", "save"]
    if fault == "cleanup":
        assert report["retained_database"] == "owned_fixture"


@pytest.mark.parametrize("cancelled", [False, True])
def test_finalization_retains_primary_across_all_secondary_errors(cancelled: bool) -> None:
    calls: list[str] = []
    primary = asyncio.CancelledError() if cancelled else TimeoutError()
    report: dict[str, object] = {}

    def fail(stage: str) -> NoReturn:
        calls.append(stage)
        raise OSError("private IO detail")

    with pytest.raises(type(primary)) as caught:
        finalize_replay_run(
            report,
            source_check=lambda: fail("source"),
            cleanup_owned=lambda: fail("cleanup"),
            save_result=lambda: fail("save"),
            database="owned_fixture",
            primary=primary,
        )
    assert caught.value is primary
    assert calls == ["source", "cleanup", "save"]
    assert report["retained_database"] == "owned_fixture"
    assert report["error_type"] == type(primary).__name__
    assert len(primary.__notes__) == 3
    assert "private IO detail" not in str(report)
