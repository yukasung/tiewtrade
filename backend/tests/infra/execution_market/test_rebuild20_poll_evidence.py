"""Long fixture poll evidence stays complete without unbounded process memory."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_rebuild20 as rebuild
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_parent_poll import ParentPollGate


async def test_streamed_poll_trace_exceeds_old_memory_limit(tmp_path: Path) -> None:
    trace = tmp_path / "attempts.jsonl"
    gate = ParentPollGate(stream_path=trace)
    owner = uuid4()
    for _ in range(100001):
        async with gate.permit(owner, "wait_command"):
            pass
    assert gate.rows == [] and not gate.truncated
    assert gate.attempts == gate.finished == 100001
    assert gate.active == 0 and gate.peak == 1
    summary = tmp_path / "summary.json"
    gate.save(summary)
    assert json.loads(summary.read_text())["attempt_count"] == 100001
    with trace.open() as stream:
        assert sum(1 for _ in stream) == 100001


async def test_default_poll_trace_retains_original_memory_guard() -> None:
    gate = ParentPollGate()
    gate.rows = [{}] * 100000
    with pytest.raises(RuntimeError, match="NC09_POLL_GATE_TRACE_TRUNCATED"):
        async with gate.permit(uuid4(), "wait_command"):
            pytest.fail("admitted beyond the default trace limit")
    assert gate.truncated and gate.attempts == gate.finished == 0
    assert gate.active == 0


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "operation",
        "cancel",
        "summary",
        "both",
        "stream",
        "both-stream",
        "cancel-stream",
        "progress",
        "summary-progress",
    ],
)
@pytest.mark.parametrize("ambient", [False, True])
async def test_fixture_poll_finalization_joins_before_summary_and_keeps_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None, ambient: bool
) -> None:
    operation_failed = fault in ("operation", "cancel", "both", "both-stream", "cancel-stream")
    trace_failed = fault in ("stream", "both-stream", "cancel-stream")
    summary_failed = fault in ("summary", "both", "summary-progress")
    progress_failed = fault in ("progress", "summary-progress")
    engine = cast(AsyncEngine, object())
    owner = SimpleNamespace(user_id=uuid4())
    joined = asyncio.Event()
    operation_error = (
        asyncio.CancelledError()
        if fault in ("cancel", "cancel-stream")
        else ValueError("seed failed")
    )
    summary_error = OSError("summary write failed")
    unrelated = ValueError("unrelated caller error")
    gates: list[ParentPollGate] = []
    original_save, original_open = ParentPollGate.save, Path.open

    async def paced(self: Any, stop: asyncio.Event, *, hz: int) -> None:
        self.journal.count = 1
        await stop.wait()

    async def workers(*args: Any, ready: asyncio.Event, **kwargs: Any) -> None:
        ready.set()
        await args[1].wait()
        joined.set()

    async def baseline(*args: Any, poll_gate: ParentPollGate) -> None:
        gates.append(poll_gate)
        async with poll_gate.permit(owner.user_id, "baseline"):
            if operation_failed:
                raise operation_error

    def save(gate: ParentPollGate, path: Path) -> None:
        assert joined.is_set()
        assert gate.active == 0
        if summary_failed:
            raise summary_error
        original_save(gate, path)

    def open_path(path: Path, *args: Any, **kwargs: Any) -> Any:
        if trace_failed and path.name == "parent-poll-attempts.jsonl":
            raise OSError("trace write failed")
        if progress_failed and path.name == "fixture-progress.json":
            raise OSError("progress write failed")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(rebuild, "guard_engines", lambda *args: None)
    monkeypatch.setattr(workload, "seed_owners", AsyncMock(return_value=[owner]))
    monkeypatch.setattr(workload, "seed_baseline", baseline)
    monkeypatch.setattr(rebuild.FixturePublisher, "paced", paced)
    monkeypatch.setattr(rebuild, "parallel_workers", workers)
    monkeypatch.setattr(ParentPollGate, "save", save)
    monkeypatch.setattr(Path, "open", open_path)

    async def operation() -> None:
        await rebuild.prepare_economics(
            engine,
            engine,
            engine,
            engine,
            tmp_path,
            cycles=0,
            parallel_runtime=True,
        )

    async def prepare() -> None:
        if ambient:
            try:
                raise unrelated
            except ValueError:
                await operation()
        else:
            await operation()

    if operation_failed:
        with pytest.raises(type(operation_error)) as caught:
            await prepare()
        assert caught.value is operation_error
        if fault == "both":
            assert "fixture poll evidence failed: OSError" in operation_error.__notes__
        if fault in ("both-stream", "cancel-stream"):
            assert "poll gate trace write failed: OSError" in operation_error.__notes__
            assert "fixture poll evidence failed: RuntimeError" in operation_error.__notes__
    elif fault in ("summary", "stream", "progress", "summary-progress"):
        with pytest.raises(OSError) as caught:
            await prepare()
        if fault in ("summary", "summary-progress"):
            assert caught.value is summary_error
    else:
        await prepare()
    assert joined.is_set() and gates[0].active == 0
    assert not getattr(unrelated, "__notes__", [])
    assert (tmp_path / "fixture-progress.json").exists() is (not progress_failed)
    if not summary_failed:
        result = json.loads((tmp_path / "parent-poll-gate.json").read_text())
        assert result["attempt_count"] == 1
        if not trace_failed:
            assert result["finished_count"] == 1 and not result["truncated"]
            rows = (tmp_path / "parent-poll-attempts.jsonl").read_text().splitlines()
            assert len(rows) == 1


async def test_existing_fixture_poll_trace_rejected_before_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = cast(AsyncEngine, object())
    trace = tmp_path / "parent-poll-attempts.jsonl"
    trace.write_text("previous receipt\n")
    monkeypatch.setattr(rebuild, "guard_engines", lambda *args: None)
    monkeypatch.setattr(workload, "seed_owners", AsyncMock(return_value=[]))
    spawn = AsyncMock()
    monkeypatch.setattr(rebuild.FixturePublisher, "paced", spawn)
    with pytest.raises(FileExistsError):
        await rebuild.prepare_economics(
            engine,
            engine,
            engine,
            engine,
            tmp_path,
            parallel_runtime=True,
        )
    spawn.assert_not_called()
    assert trace.read_text() == "previous receipt\n"


async def test_streaming_gate_keeps_concurrency_and_waiting_cancellation(tmp_path: Path) -> None:
    trace = tmp_path / "attempts.jsonl"
    gate = ParentPollGate(stream_path=trace)
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold() -> None:
        async with gate.permit(uuid4(), "hold"):
            if gate.active == 4:
                entered.set()
            await release.wait()

    holders = [asyncio.create_task(hold()) for _ in range(4)]
    waiting: asyncio.Task[None] | None = None
    try:
        await entered.wait()
        waiting = asyncio.create_task(hold())
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
    finally:
        release.set()
        await asyncio.gather(*holders)
        if waiting is not None and not waiting.done():
            waiting.cancel()
            await asyncio.gather(waiting, return_exceptions=True)
    gate.save(tmp_path / "summary.json")
    assert gate.rows == [] and gate.peak == 4 and gate.active == 0
    assert gate.attempts == gate.finished == 5
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    assert len(rows) == 5
    assert sum(row["outcome"] == "CancelledError" for row in rows) == 1
    assert sum(row["outcome"] == "RETURNED" for row in rows) == 4


@pytest.mark.parametrize("body_failure", [None, "error", "cancel"])
async def test_poll_trace_error_does_not_use_callers_handled_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body_failure: str | None
) -> None:
    gate = ParentPollGate(stream_path=tmp_path / "trace.jsonl")
    unrelated = ValueError("unrelated caller error")
    body_error = (
        asyncio.CancelledError() if body_failure == "cancel" else RuntimeError("read failed")
    )
    io_error = OSError("trace write failed")

    def fail_open(*args: Any, **kwargs: Any) -> Any:
        raise io_error

    monkeypatch.setattr(Path, "open", fail_open)
    try:
        raise unrelated
    except ValueError:
        expected = body_error if body_failure else io_error
        with pytest.raises(type(expected)) as caught:
            async with gate.permit(uuid4(), "wait_command"):
                if body_failure:
                    raise body_error from None
        assert caught.value is expected
    assert not getattr(unrelated, "__notes__", [])
    if body_failure:
        assert "poll gate trace write failed: OSError" in body_error.__notes__
    assert gate.active == 0 and gate.attempts == 1 and gate.finished == 0


async def test_mutator_cleanup_error_does_not_use_callers_handled_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = rebuild.SourceJournal(tmp_path / "journal")
    unrelated = ValueError("unrelated caller error")
    io_error = OSError("journal flush failed")
    monkeypatch.setattr(journal, "flush", Mock(side_effect=io_error))
    try:
        raise unrelated
    except ValueError:
        with pytest.raises(OSError) as caught:
            await rebuild.finish_mutators((), asyncio.Event(), journal)
        assert caught.value is io_error
    assert not getattr(unrelated, "__notes__", [])
