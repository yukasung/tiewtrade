"""NC18 instrumentation observes actual transactions without altering worker decisions."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits import profile_risk_timing as timing
from tests.infra.risk_limits.profile_workload import telemetry
from tests.infra.risk_limits.test_monitor import start
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_requests import seed_setting, submission
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.monitor import initialize_monitor
from tiewtrade.infra.risk_limits.storage import read_setting
from tiewtrade.services.engine import risk_limit as service


def activate(path: Path) -> None:
    (path / "risk-trace-control.json").write_text(
        json.dumps({"started": monotonic(), "seconds": 300})
    )


def records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize("exit_kind", ["commit", "rollback", "savepoint"])
async def test_real_transaction_proofs_exclude_rollback(
    tmp_path: Path,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    publication: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    exit_kind: str,
) -> None:
    await start(publication)
    await seed_setting(engine_engine, owner)
    activate(tmp_path)
    observer = timing.RiskObserver(tmp_path / "paper.json", full=False)
    async with observer.observe(), telemetry(tmp_path / "acks.jsonl", proof=observer):
        try:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                if exit_kind == "savepoint":
                    await session.execute("SAVEPOINT abandoned")
                setting = await read_setting(session, submission(owner, wallet).scope)
                await initialize_monitor(session, setting)
                if exit_kind == "savepoint":
                    await session.execute("ROLLBACK TO SAVEPOINT abandoned")
                    await session.execute("RELEASE SAVEPOINT abandoned")
                if exit_kind == "rollback":
                    raise RuntimeError("test rollback")
        except RuntimeError:
            assert exit_kind == "rollback"
    proofs = [r for r in records(observer.proofs.path) if r.get("event") == "COMMIT_PROOF"]
    acks = records(tmp_path / "acks.jsonl")
    assert len(proofs) == len(acks) == (1 if exit_kind == "commit" else 0)
    if proofs:
        result = await timing.lookup_commits(migrator_engine, proofs)
        assert result[0]["status"] == "VERIFIED"
        assert result[0]["server_committed_at"] <= acks[0]["committed_observed_at"]
        assert int(proofs[0]["writer_xmin"]) == int(proofs[0]["transaction_xid"]) & 0xFFFFFFFF
        changed = [{**proofs[0], "transaction_xid": str(int(proofs[0]["transaction_xid"]) + 1)}]
        assert (await timing.lookup_commits(migrator_engine, changed))[0]["status"] == "UNKNOWN"


async def test_rolled_back_xid_commit_time_is_unknown(engine_engine: AsyncEngine) -> None:
    xid = None
    with pytest.raises(RuntimeError):
        async with engine_engine.begin() as connection:
            xid = (
                await connection.exec_driver_sql("SELECT pg_current_xact_id()::text")
            ).scalar_one()
            raise RuntimeError("rollback assigned test xid")
    assert xid is not None
    row = {"writer_xmin": str(int(xid) & 0xFFFFFFFF), "transaction_xid": xid}
    assert (await timing.lookup_commits(engine_engine, [row]))[0]["status"] == "UNKNOWN"


@pytest.mark.parametrize("blocked", [False, True])
async def test_real_round_preserves_selection_and_reports_lock_timeout_stage(
    tmp_path: Path,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    publication: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    blocked: bool,
) -> None:
    await start(publication)
    await seed_setting(engine_engine, owner)
    activate(tmp_path)
    observer = timing.RiskObserver(tmp_path / "risk.json", full=True)
    original_asyncio, original_round = vars(service)["asyncio"], service.run_risk_monitor_round
    blocker = user_session(engine_engine, owner, role=DatabaseRole.ENGINE)
    if blocked:
        session = await blocker.__aenter__()
        await lock_risk_owner(session, submission(owner, wallet).scope.mode)
    try:
        async with observer.observe(), telemetry(tmp_path / "acks.jsonl", proof=observer):
            result = await service.run_risk_monitor_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                limit=1,
                concurrency=1,
                after_owner=UUID(int=(owner.int - 1) % (1 << 128)),
            )
            assert (result.processed, result.deferred, result.skipped) == (
                (0, 1, 0) if blocked else (1, 0, 0)
            )
        assert (
            vars(service)["asyncio"] is original_asyncio
            and service.run_risk_monitor_round is original_round
        )
        rows = records(observer.spans.path)
        span = next(r for r in rows if r.get("event") == "OWNER")
        round_row = next(r for r in rows if r.get("event") == "ROUND")
        assert span["owner"] == str(owner)
        assert span["round"] == round_row["round"]
        assert round_row["selected"][0]["owner"] == str(owner)
        assert round_row["concurrency"] == 1
        assert any(r["phase"] == "owner_lock" for r in span["stages"])
        if blocked:
            assert span["failure_phase"] == "owner_lock"
            tx = next(r for r in records(observer.window.path) if "sqlstate" in r)
            assert tx["sqlstate"] == "55P03" and tx["backend_pid"] > 0
        assert observer.window.listeners == []
    finally:
        if blocked:
            await blocker.__aexit__(None, None, None)


async def test_collector_failure_is_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "paper.commit-proofs.jsonl").write_text(
        json.dumps({"event": "COMMIT_PROOF"}) + "\n"
    )
    monkeypatch.setattr(
        timing, "lookup_commits", AsyncMock(side_effect=RuntimeError("test collector"))
    )
    stop = asyncio.Event()
    stop.set()
    with pytest.raises(RuntimeError, match="test collector"):
        await timing.collect_commits(AsyncMock(), tmp_path, stop)


def test_cap_rejects_incomplete_evidence(tmp_path: Path) -> None:
    observer = timing.RiskObserver(tmp_path / "risk.json", full=False)
    observer.proofs.count = 100000
    with pytest.raises(RuntimeError, match="TRUNCATED"):
        observer.proofs.record({"no_secret": True})
    with pytest.raises(RuntimeError, match="TRUNCATED"):
        observer.proofs.flush()


@pytest.mark.parametrize("cancel", [False, True])
async def test_scoped_semaphore_bound_cancellation_and_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    active = maximum = entered = 0
    ready, release = asyncio.Event(), asyncio.Event()
    original_semaphore = asyncio.Semaphore

    @asynccontextmanager
    async def fake_session(*args: object, **kwargs: object) -> AsyncIterator[None]:
        yield None

    async def fake_round(**kwargs: object) -> service.RiskRequestRound:
        semaphore = vars(service)["asyncio"].Semaphore(4)

        async def one() -> None:
            nonlocal active, maximum, entered
            async with semaphore, vars(service)["user_session"](None, uuid4()):
                active += 1
                maximum = max(active, maximum)
                entered += 1
                if entered == 4:
                    ready.set()
                try:
                    await release.wait()
                finally:
                    active -= 1

        await asyncio.gather(*(one() for _ in range(8)))
        return service.RiskRequestRound(processed=8)

    monkeypatch.setattr(service, "run_risk_monitor_round", fake_round)
    monkeypatch.setattr(service, "user_session", fake_session)
    activate(tmp_path)
    observer = timing.RiskObserver(tmp_path / "risk.json", full=True)
    async with observer.observe():
        task = asyncio.create_task(vars(service)["run_risk_monitor_round"]())
        await asyncio.wait_for(ready.wait(), 1)
        assert asyncio.Semaphore is original_semaphore
        assert maximum == 4
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            release.set()
            assert (await task).processed == 8
    assert active == 0 and service.run_risk_monitor_round is fake_round
    assert vars(service)["asyncio"] is asyncio
    assert len([r for r in records(observer.spans.path) if r.get("event") == "OWNER"]) == 8


def test_nested_timeout_keeps_leaf_stage_and_redacts_exception(tmp_path: Path) -> None:
    row: dict[str, Any] = {"stages": []}
    token = timing._SPAN.set(row)
    try:
        with pytest.raises(TimeoutError), timing.phase("replay"), timing.phase("persist"):
            raise TimeoutError("TEST_ONLY_SECRET")
    finally:
        timing._SPAN.reset(token)
    assert row["failure_phase"] == "persist"
    assert "TEST_ONLY_SECRET" not in json.dumps(row)


async def test_real_rolling_selection_links_owner_stages_and_inventory(
    tmp_path: Path,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    publication: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.services.engine import risk_limit_main as runtime

    await start(publication)
    await seed_setting(engine_engine, owner)
    activate(tmp_path)
    observer = timing.RiskObserver(tmp_path / "risk.json", full=True)
    async with observer.observe():
        with timing.rolling_inventory(tmp_path / "risk.json"):
            rows = await vars(runtime)["_scan_monitor_candidates"](
                scan_engine,
                limit=4,
                after_owner=UUID(int=(owner.int - 1) % (1 << 128)),
                excluded=(),
            )
            assert owner in [r.user_id for r in rows]
            await asyncio.gather(
                *(
                    vars(runtime)["_evaluate_monitor_owner"](engine_engine, UUID(str(row.user_id)))
                    for row in rows
                )
            )
    rows = records(observer.spans.path)
    turn = next(row for row in rows if row.get("event") == "ROLLING_TURN")
    spans = [row for row in rows if row.get("event") == "OWNER"]
    assert spans and {row["round"] for row in spans} == {turn["round"]}
    assert {row["owner"] for row in spans} == {row["owner"] for row in turn["selected"]}
    assert all(row["scheduler"] == "rolling" and row["outcome"] for row in spans)
    inventory = json.loads((tmp_path / "risk.scheduler.json").read_text())
    assert inventory["closed"] and inventory["active_at_close"] == 0
    assert 1 <= inventory["max_inflight"] <= 4 and inventory["selected"] == len(spans)
