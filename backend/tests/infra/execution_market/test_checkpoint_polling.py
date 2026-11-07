"""NC07 matrix, read boundaries, cancellation and final-history gates."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_checkpoint_isolation as iso
from tests.infra.execution_market import profile_checkpoint_polling as probe
from tests.infra.execution_market.profile_workload import save
from tiewtrade.infra.db import DatabaseRole, user_session


def test_fixed_matrix_and_balanced_readers() -> None:
    assert probe.conditions() == [
        (1, 0),
        (1, 100),
        (4, 0),
        (4, 100),
        (4, 100),
        (4, 0),
        (1, 100),
        (1, 0),
    ]
    assert sum(w * 24 for w, _ in probe.conditions()) + 96 == 576
    for writers, distribution in ((1, [100]), (4, [26, 26, 24, 24])):
        rows = probe.assignments(writers)
        assert Counter(owner for owner, _, _ in rows) == dict(enumerate(distribution))
        assert Counter(family for _, family, _ in rows) == {"command": 50, "status": 50}
        assert [offset for _, _, offset in rows] == [i * 0.25 / 100 for i in range(100)]
        for owner in range(writers):
            counts = Counter(f for o, f, _ in rows if o == owner)
            assert counts["command"] == counts["status"]
    with pytest.raises(ValueError):
        probe.assignments(2)


def test_fixture_rejects_duplicate_owner_and_incomplete_operations(tmp_path: Path) -> None:
    documents: list[dict[str, Any]] = [
        {"owner": str(uuid4()), "wallet": str(uuid4()), "operations": [{}] * 24} for _ in range(4)
    ]
    for i, document in enumerate(documents):
        save(tmp_path / f"fixture-{i}.json", document)
    assert probe.fixtures(tmp_path) == documents
    save(tmp_path / "fixture-3.json", documents[0])
    with pytest.raises(ValueError, match="distinct"):
        probe.fixtures(tmp_path)
    documents[3]["operations"].pop()
    save(tmp_path / "fixture-3.json", documents[3])
    with pytest.raises(ValueError, match="24 checkpoints"):
        probe.fixtures(tmp_path)


@pytest.mark.parametrize("fault", ["history", "inactive", "missing", "identity"])
def test_all_owner_final_gate_detects_corruption(fault: str) -> None:
    initial: list[dict[str, Any]] = [
        {"owner": str(i), "raw": {"history": []}, "normalized": {"history": []}} for i in range(4)
    ]
    reference: list[dict[str, Any]] = [
        {
            "owner": str(i),
            "raw": {"history": ["raw"]},
            "normalized": {"history": ["business event"]},
        }
        for i in range(4)
    ]
    final = copy.deepcopy([reference[0], *initial[1:]])
    probe.verify_final(final, initial, reference, 1)
    if fault == "history":
        final[0]["normalized"]["history"].append("duplicate")
    elif fault == "inactive":
        final[3]["raw"]["history"].append("unintended write")
    elif fault == "missing":
        final.pop()
    else:
        final[1]["owner"] = "other"
    with pytest.raises(ValueError):
        probe.verify_final(final, initial, reference, 1)


async def test_poll_results_never_drive_writes_and_keep_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop, ready = asyncio.Event(), asyncio.Event()
    sleeps = []
    counts: dict[str, Any] = {
        "started": 0,
        "completed": 0,
        "cancelled": 0,
        "errors": [],
        "absent": 0,
    }

    async def read(*args: Any) -> None:
        if counts["started"] == 3:
            stop.set()

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(probe, "read_target", read)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    await probe.poll(None, {}, "status", 0.125, ready, stop, counts)  # type: ignore[arg-type]
    assert counts["started"] == counts["completed"] == counts["absent"] == 3
    assert ready.is_set() and sleeps == [0.125, 0.25, 0.25, 0.25]


async def test_reader_queries_are_owner_scoped_and_select_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = {key: str(uuid4()) for key in ("owner", "order", "command")}
    calls = []

    @asynccontextmanager
    async def session(engine: Any, owner: UUID, *, role: DatabaseRole) -> AsyncIterator[Any]:
        assert owner == UUID(target["owner"]) and role is DatabaseRole.ENGINE

        async def execute(sql: str, params: Any) -> Any:
            calls.append((sql, params))
            return SimpleNamespace(scalar_one_or_none=lambda: None)

        yield SimpleNamespace(execute=execute)

    async def command(session: Any, identifier: UUID) -> Any:
        assert identifier == UUID(target["command"])
        return SimpleNamespace(state="PENDING")

    monkeypatch.setattr(probe, "user_session", session)
    monkeypatch.setattr(probe, "get_order_command", command)
    assert await probe.read_target(None, target, "command") == "PENDING"  # type: ignore[arg-type]
    assert await probe.read_target(None, target, "status") is None  # type: ignore[arg-type]
    assert calls == [
        (
            "SELECT status FROM paper_order_projections WHERE order_id=:order",
            {"order": UUID(target["order"])},
        )
    ]


@pytest.fixture
def group_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    args = argparse.Namespace(
        output=tmp_path,
        fixtures=tmp_path,
        source=tmp_path,
        writer_hash="hash",
        backend=tmp_path,
        database="tiewtrade_set4_iso_test",
    )
    save(
        tmp_path / "parent-pools.json",
        {"pools": [{"role": "ENGINE", "pool_size": 5, "max_overflow": 10}]},
    )
    state: dict[str, Any] = {"live": set(), "joined": set(), "fault": None, "read": 0}
    targets = [
        {"owner": str(uuid4()), "order": str(uuid4()), "command": str(uuid4())} for _ in range(4)
    ]

    async def child(command: list[str], *args: Any) -> None:
        owner = int(command[-1])
        state["live"].add(owner)
        try:
            path = tmp_path / f"writer-{owner}"
            path.mkdir()
            save(path / "pools.json", json.loads((tmp_path / "parent-pools.json").read_text()))
            if state["fault"] != "readiness":
                save(path / "ready.json", {})
            await probe.wait_files([tmp_path / "start.json"])
            assert state["read"] >= 100
            if state["fault"] == "writer" and owner == 0:
                raise ValueError("original writer failure")
            if state["fault"] == "deadline":
                await asyncio.Event().wait()
            await asyncio.sleep(0.01)
        finally:
            state["live"].remove(owner)
            state["joined"].add(owner)

    async def read(*args: Any) -> None:
        state["read"] += 1
        if state["fault"] == "reader":
            raise ValueError("original reader failure")

    async def sample(db: str, path: Path, stop: asyncio.Event) -> None:
        await stop.wait()

    monkeypatch.setattr(iso, "child", child)
    monkeypatch.setattr(probe, "read_target", read)
    monkeypatch.setattr(probe, "sampler", sample)
    # Keep 100 tasks/mapping but eliminate startup offsets in coordination tests only.
    assignments = probe.assignments
    monkeypatch.setattr(probe, "assignments", lambda w: [(o, f, 0) for o, f, _ in assignments(w)])
    return args, state, targets


async def test_group_barrier_and_join_before_return(group_runtime: Any) -> None:
    args, state, targets = group_runtime
    result = await probe.run_group(args, cast(AsyncEngine, None), targets, [0, 1, 2, 3], 100, {})
    assert not state["live"] and state["joined"] == {0, 1, 2, 3}
    assert len(result["polls"]) == 100
    assert result["writer_seconds"] <= result["seconds"]


@pytest.mark.parametrize("fault", ["writer", "reader", "readiness", "deadline"])
async def test_group_failure_joins_all_and_retains_error(
    group_runtime: Any, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    args, state, targets = group_runtime
    state["fault"] = fault
    original = asyncio.timeout
    monkeypatch.setattr(
        asyncio, "timeout", lambda seconds: original(0.08 if seconds == 10 else 0.02)
    )
    with pytest.raises(ExceptionGroup) as error:
        await probe.run_group(args, cast(AsyncEngine, None), targets, [0, 1, 2, 3], 100, {})
    assert not state["live"] and state["joined"] == {0, 1, 2, 3}
    assert (args.output / "polls.json").exists()
    assert (
        ("original " + fault + " failure") in str(error.value.exceptions)
        if fault in ("reader", "writer")
        else any(isinstance(e, TimeoutError) for e in error.value.exceptions)
    )


async def test_cleanup_preserves_primary_error(tmp_path: Path) -> None:
    async def dispose() -> None:
        raise RuntimeError("cleanup")

    engine = SimpleNamespace(pool=SimpleNamespace(checkedout=lambda: 0), dispose=dispose)
    await probe.close_engine(
        cast(AsyncEngine, engine), tmp_path / "closed.json", ValueError("primary")
    )
    assert json.loads((tmp_path / "closed.json").read_text())["primary"] == "ValueError"


async def test_observer_is_read_only_and_database_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = []

    async def capture(command: list[str]) -> str:
        commands.append(command)
        return "{}" if command[0] == "docker" else "memory sample"

    monkeypatch.setattr(probe, "capture", capture)
    await probe.observe_resources("tiewtrade_set4_iso_test")
    sql = commands[0][-1]
    assert sql.startswith("BEGIN READ ONLY;") and "datname='tiewtrade_set4_iso_test'" in sql
    assert "pg_blocking_pids" in sql and "query" not in sql.lower()
    with pytest.raises(ValueError):
        await probe.observe_resources("postgres")


async def test_real_four_owner_read_only_isolation(
    tmp_path: Path, engine_engine: AsyncEngine
) -> None:
    await probe.setup(argparse.Namespace(fixtures=tmp_path))
    documents = probe.fixtures(tmp_path)
    before = await probe.snapshot_all(engine_engine, documents)
    targets = json.loads((tmp_path / "targets.json").read_text())
    try:
        assert len({t["owner"] for t in targets}) == 4
        for target in targets:
            assert await probe.read_target(engine_engine, target, "command") == "PENDING"
            assert await probe.read_target(engine_engine, target, "status") is None
            foreign = {**target, "owner": targets[(targets.index(target) + 1) % 4]["owner"]}
            assert await probe.read_target(engine_engine, foreign, "command") is None
        assert await probe.snapshot_all(engine_engine, documents) == before
        measurement = await iso.timed_checkpoint(
            engine_engine, documents[0], documents[0]["operations"][0]
        )
        assert measurement["client_statements"] == 6 and measurement["outcome"] == "COMMIT"
        after = await probe.snapshot_all(engine_engine, documents)
        assert after[1:] == before[1:] and after[0] != before[0]
        assert await probe.read_target(engine_engine, targets[0], "status") is not None
    finally:
        for document in documents:
            async with user_session(
                engine_engine, UUID(document["owner"]), role=DatabaseRole.ENGINE
            ) as session:
                await session.execute(
                    "UPDATE paper_order_dispatch SET state='TERMINAL',"
                    "worker=NULL,claim_id=NULL,lease_until=NULL"
                )


def test_incomplete_duplicate_and_wrong_writer_measurements_fail() -> None:
    docs = [{"owner": "one"}]
    rows = [
        {"owner": "one", "operation": i, "outcome": "COMMIT", "client_statements": 6}
        for i in range(1, 25)
    ]
    probe.validate_measurements(rows, docs)
    for changed in (rows[:-1], [rows[0]] * 24, [{**r, "client_statements": 11} for r in rows]):
        with pytest.raises(ValueError):
            probe.validate_measurements(changed, docs)


async def test_real_trace_cap_fails_and_restores(
    tmp_path: Path, engine_engine: AsyncEngine
) -> None:
    from tests.infra.risk_limits.profile_pool_timing import TransactionTrace
    from tiewtrade.infra.db import session as db

    control = tmp_path / "control.json"
    save(control, {"started": monotonic(), "seconds": 900})
    trace = TransactionTrace(tmp_path / "trace.jsonl", control=control)
    trace.rows = 100000
    original = db._begin
    with pytest.raises(RuntimeError, match="TRUNCATED"):
        async with (
            trace.observe(),
            user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session,
        ):
            await session.execute("SELECT 1")
    assert db._begin is original and not trace.listeners
    assert json.loads(trace.path.read_text().splitlines()[-1])["truncated"] is True


@pytest.mark.parametrize("fail_at", [None, 3])
async def test_writer_pacing_error_and_no_snapshot_during_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_at: int | None
) -> None:
    docs = [{"owner": str(uuid4()), "operations": [{"kind": "ACCEPTED"}] * 24} for _ in range(4)]
    calls: list[int] = []
    sleeps: list[float] = []
    closed = []
    args = argparse.Namespace(
        source=tmp_path, writer_hash="hash", fixtures=tmp_path, owner=0, output=tmp_path
    )
    monkeypatch.setenv(
        DatabaseRole.ENGINE.url_variable,
        "postgresql+asyncpg://tiewtrade_engine@127.0.0.1:55432/tiewtrade_set4_iso_test",
    )
    monkeypatch.setattr(iso, "verify_writer", lambda *args: None)

    async def verified(*args: Any) -> dict[str, Any]:
        return {}

    monkeypatch.setattr(iso, "verify_databases", verified)
    monkeypatch.setattr(probe, "fixtures", lambda path: docs)
    monkeypatch.setattr(probe, "create_engine_for", lambda role: object())
    monkeypatch.setattr(
        probe,
        "PoolEvidence",
        lambda path: SimpleNamespace(add=lambda *a: None, finish=lambda: None),
    )

    @asynccontextmanager
    async def observed() -> AsyncIterator[None]:
        yield

    monkeypatch.setattr(
        probe, "TransactionTrace", lambda *a, **kw: SimpleNamespace(observe=observed)
    )

    @asynccontextmanager
    async def session(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        async def execute(sql: str) -> None:
            assert sql == "SELECT 1"

        yield SimpleNamespace(execute=execute)

    monkeypatch.setattr(probe, "user_session", session)

    async def wait(*args: Any) -> None:
        pass

    monkeypatch.setattr(probe, "wait_files", wait)

    async def persist(*args: Any) -> dict[str, Any]:
        calls.append(len(calls) + 1)
        if calls[-1] == fail_at:
            raise ValueError("original checkpoint failure")
        return {"checkpoint_seconds": 2, "transaction_seconds": 4}

    monkeypatch.setattr(iso, "timed_checkpoint", persist)

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    async def close(*args: Any) -> None:
        closed.append(True)

    monkeypatch.setattr(probe, "close_engine", close)

    async def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("snapshot in writer window")

    monkeypatch.setattr(probe, "checkpoint_snapshot", forbidden)
    if fail_at is None:
        await probe.writer(args)
        assert len(calls) == 24 and sleeps == [0.1] * 23
    else:
        with pytest.raises(ValueError, match="original checkpoint"):
            await probe.writer(args)
        assert len(calls) == 3 and sleeps == [0.1] * 2
        assert not (tmp_path / "writer-0/result.json").exists()
    assert closed == [True]
