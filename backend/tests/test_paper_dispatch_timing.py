"""Dispatch diagnostics must retain identities and transaction outcomes without SQL."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.infra.risk_limits import profile_dispatch_timing as timing
from tests.infra.risk_limits import profile_workload as workload
from tiewtrade.infra.db import session as db
from tiewtrade.infra.paper_orders import worker as order_worker
from tiewtrade.services.engine import manual_order, paper_order


def control(tmp_path: Path, owner: str) -> Path:
    (tmp_path / "dispatch-trace-control.json").write_text(
        json.dumps(
            {
                "started": monotonic() - 0.01,
                "owners": [owner],
            }
        )
    )
    return tmp_path / "paper-0-0.json"


def test_detail_bound_is_explicit_and_never_silently_accepted(tmp_path: Path) -> None:
    owner = str(uuid4())
    recorder = timing.Recorder(control(tmp_path, owner))
    try:
        for _ in range(101):
            recorder.record("order_process", monotonic(), owner=owner)
        assert recorder.detail_count == 100 and recorder.truncated
        with pytest.raises(RuntimeError, match="TRUNCATED"):
            recorder.flush(final=True)
    finally:
        recorder.stream.close()


@pytest.mark.parametrize("fail", [False, True])
async def test_transaction_identity_outcome_and_patch_restoration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    owner, request, attempt = uuid4(), uuid4(), uuid4()
    metrics = control(tmp_path, str(owner))
    outcomes: list[str] = []
    calls: list[str] = []

    @asynccontextmanager
    async def begin(*args: Any, **kwargs: Any) -> Any:
        try:
            yield None
        except BaseException:
            outcomes.append("rollback")
            raise
        else:
            outcomes.append("commit")

    async def process(*args: Any, **kwargs: Any) -> None:
        calls.append("original process only")

    monkeypatch.setattr(db, "_begin", begin)
    monkeypatch.setattr(manual_order, "process_request", process)
    original = vars(manual_order)["process_request"]

    engine: Any = None

    async def work() -> None:
        async with db._begin(engine):
            process_call: Any = vars(manual_order)["process_request"]
            await process_call(
                None,
                SimpleNamespace(
                    user_id=owner,
                    request_id=request,
                    claim_id=attempt,
                    secret="must not log",
                ),
            )
            if fail:
                raise RuntimeError("controlled failure")

    if fail:
        with pytest.raises(RuntimeError, match="controlled failure"):
            await timing.traced_worker(work(), metrics)
    else:
        await timing.traced_worker(work(), metrics)
    assert db._begin is begin and vars(manual_order)["process_request"] is original
    assert calls == ["original process only"] and outcomes == ["rollback" if fail else "commit"]
    raw = metrics.with_suffix(".dispatch.jsonl").read_text()
    assert "must not log" not in raw
    rows = [json.loads(line) for line in raw.splitlines()]
    tx = next(r for r in rows if r.get("phase") == "manual_process.transaction")
    assert (tx["owner"], tx["request"], tx["attempt"]) == tuple(map(str, (owner, request, attempt)))
    assert tx["outcome"] == ("ROLLBACK:RuntimeError" if fail else "COMMIT")
    assert tx["finished"] >= tx["started"] and rows[-1]["event"] == "CLOSED"


async def test_collector_failure_cancels_work_and_restores_wrappers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    joined = asyncio.Event()
    original = vars(paper_order)["claim_order"]

    def broken(self: timing.Recorder, **kwargs: Any) -> None:
        raise RuntimeError("collector failed")

    async def work() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    monkeypatch.setattr(timing.Recorder, "flush", broken)
    with pytest.raises(RuntimeError, match="collector failed"):
        await timing.traced_worker(work(), tmp_path / "paper-0-0.json")
    assert joined.is_set() and vars(paper_order)["claim_order"] is original


def test_normal_cli_keeps_tracing_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(workload, "run", run)
    monkeypatch.setattr("sys.argv", ["profile", "--phase", "W2", "--output", "/unused"])
    assert workload.main() == 0
    args = run.call_args.args[0]
    assert args.dispatch_diagnostic_seconds is None and not args.dispatch_trace


@pytest.mark.parametrize("state,expected", [(None, "PENDING"), ("SUCCEEDED", "ACTIVE")])
async def test_work_classification_uses_loaded_row_without_new_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str | None, expected: str
) -> None:
    owner, command, attempt = uuid4(), uuid4(), uuid4()
    metrics = control(tmp_path, str(owner))
    engine: Any = None

    @asynccontextmanager
    async def begin(*args: Any, **kwargs: Any) -> Any:
        yield None

    original_calls = []

    async def process_new(*args: Any, **kwargs: Any) -> None:
        original_calls.append(args[2])

    async def process(session: Any, claim: Any, **kwargs: Any) -> None:
        invoke_new: Any = order_worker._process_new
        await invoke_new(session, claim, {"result_state": state}, None, None, None)

    monkeypatch.setattr(db, "_begin", begin)
    monkeypatch.setattr(order_worker, "_process_new", process_new)
    monkeypatch.setattr(paper_order, "process_claimed_order", process)

    async def work() -> None:
        async with db._begin(engine):
            invoke: Any = vars(paper_order)["process_claimed_order"]
            await invoke(None, SimpleNamespace(user_id=owner, command_id=command, claim_id=attempt))

    await timing.traced_worker(work(), metrics)
    rows = [
        json.loads(line) for line in metrics.with_suffix(".dispatch.jsonl").read_text().splitlines()
    ]
    detail = next(r for r in rows if r.get("phase") == "order_process.transaction")
    assert detail["work"] == expected and detail["command"] == str(command)
    assert original_calls == [{"result_state": state}]
    phases = [r["phases"] for r in rows if r["event"] in {"SECOND", "TAIL"}]
    assert any("order_process.transaction/" + expected in r for r in phases)


@pytest.mark.parametrize("fail", [False, True])
async def test_real_session_and_existing_telemetry_keep_commit_rollback_and_pool_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api_engine: Any, fail: bool
) -> None:
    from tiewtrade.infra.db import user_session

    owner = uuid4()
    metrics = control(tmp_path, str(owner))

    async def process(session: Any, claim: Any) -> None:
        assert (await session.execute("SELECT 1")).scalar_one() == 1

    monkeypatch.setattr(manual_order, "process_request", process)

    async def work() -> None:
        async with user_session(api_engine, owner) as session:
            invoke: Any = vars(manual_order)["process_request"]
            await invoke(
                session, SimpleNamespace(user_id=owner, request_id=uuid4(), claim_id=uuid4())
            )
            if fail:
                raise RuntimeError("rollback real session")

    async with workload.telemetry(metrics.with_suffix(".risk.jsonl")):
        if fail:
            with pytest.raises(RuntimeError, match="rollback real session"):
                await timing.traced_worker(work(), metrics)
        else:
            await timing.traced_worker(work(), metrics)
    rows = [
        json.loads(line) for line in metrics.with_suffix(".dispatch.jsonl").read_text().splitlines()
    ]
    tx = next(r for r in rows if r.get("phase") == "manual_process.transaction")
    assert tx["owner"] == str(owner)
    assert tx["outcome"] == ("ROLLBACK:RuntimeError" if fail else "COMMIT")
    assert api_engine.pool.checkedout() == 0
