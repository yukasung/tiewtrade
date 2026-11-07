"""Isolation harness guards, measurement boundaries and abort behavior."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_checkpoint_isolation as iso
from tests.infra.execution_market.profile_checkpoint_fixture import prepare
from tests.infra.execution_market.profile_workload import save
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders import matching_storage


def test_schedule_has_independent_clones_and_fixed_denominator() -> None:
    arms = iso.schedule("tiewtrade_set4_iso_test")
    assert len({a.database for a in arms}) == len(arms) == 24
    assert sum(a.btc_orders + 4 for a in arms) == 360
    assert [a.writer for a in arms] == ["direct", "batch", "batch", "direct"] * 6
    with pytest.raises(ValueError):
        iso.summarize([])


@pytest.mark.parametrize(
    "name", ["postgres", "tiewtrade_batch4_batch_diag1_20261106", "tiewtrade_set4_iso_x;DROP"]
)
def test_database_names_cannot_target_previous_history(name: str) -> None:
    with pytest.raises(ValueError):
        iso.database_name(name)


def environment() -> dict[str, str]:
    return {
        role.url_variable: f"postgresql+asyncpg://{role.value}:fixture-secret@127.0.0.1:55432/source"
        for role in DatabaseRole
    }


@pytest.mark.parametrize("fault", ["database", "role", "host"])
def test_role_urls_fail_closed_without_credentials_in_error(fault: str) -> None:
    values = environment()
    key = DatabaseRole.ENGINE.url_variable
    values[key] = values[key].replace(
        {"database": "/source", "role": "tiewtrade_engine:", "host": "127.0.0.1"}[fault],
        {"database": "/other", "role": "postgres:", "host": "remote.invalid"}[fault],
    )
    with pytest.raises(ValueError) as error:
        iso.database_environment(values, "tiewtrade_set4_iso_test")
    assert "fixture-secret" not in str(error.value)


def test_all_role_urls_target_the_new_database() -> None:
    values = iso.database_environment(environment(), "tiewtrade_set4_iso_test")
    for role in DatabaseRole:
        assert make_url(values[role.url_variable]).database == "tiewtrade_set4_iso_test"
        assert make_url(values[role.url_variable]).username == role.value


async def test_clone_only_creates_new_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands = []

    async def capture(command: list[str], *args: Any) -> None:
        commands.append(command)

    monkeypatch.setattr(iso, "child", capture)
    for arm in iso.schedule("tiewtrade_set4_iso_test"):
        await iso.clone_database(
            arm.database, "tiewtrade_set4_iso_template", tmp_path, tmp_path / "log"
        )
    sql = [c[-1] for c in commands]
    assert len(set(sql)) == 24
    assert all(s.startswith("CREATE DATABASE ") and " TEMPLATE " in s for s in sql)
    assert all("DROP" not in s and "IF NOT EXISTS" not in s for s in sql)


@pytest.mark.parametrize("wrong", ["database", "role"])
async def test_actual_database_identity_rejected_and_connection_closed(
    monkeypatch: pytest.MonkeyPatch, wrong: str
) -> None:
    disposed = []

    class Engine:
        @asynccontextmanager
        async def connect(self) -> AsyncIterator[Engine]:
            yield self

        async def execute(self, value: Any) -> Any:
            row = ["tiewtrade_set4_iso_test", DatabaseRole.MIGRATOR.value]
            row[0 if wrong == "database" else 1] = "wrong"
            return SimpleNamespace(one=lambda: tuple(row))

        async def dispose(self) -> None:
            disposed.append(True)

    monkeypatch.setattr(iso, "create_engine_for", lambda role: Engine())
    with pytest.raises(ValueError, match="actual role/database"):
        await iso.verify_databases("tiewtrade_set4_iso_test")
    assert disposed == [True]


def test_writer_import_path_and_digest_are_verified(tmp_path: Path) -> None:
    assert matching_storage.__file__ is not None
    actual = Path(matching_storage.__file__).resolve()
    source = actual.parents[3]
    iso.verify_writer(source, iso.digest(actual))
    with pytest.raises(ValueError):
        iso.verify_writer(tmp_path, iso.digest(actual))
    with pytest.raises(ValueError):
        iso.verify_writer(source, "wrong")


@pytest.fixture
def observed_arm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    state: dict[str, Any] = {
        "clock": 0.0,
        "writes": 0,
        "disposed": 0,
        "error": None,
        "delay": False,
    }
    callbacks: list[Callable[..., None]] = []

    class Engine:
        sync_engine = object()
        pool = SimpleNamespace(checkedout=lambda: 0)

        async def dispose(self) -> None:
            state["disposed"] += 1
            if state.get("cleanup_error"):
                raise RuntimeError("cleanup failure")

    @asynccontextmanager
    async def session(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        state["clock"] += 1

        async def execute(sql: str) -> Any:
            return SimpleNamespace(scalar_one=lambda: 4)

        try:
            yield SimpleNamespace(execute=execute)
        finally:
            state["clock"] += 1

    async def preflight(database: str) -> dict[str, Any]:
        return {}

    async def snapshot(session: Any, *, raw: bool = False) -> dict[str, Any]:
        state["clock"] += 10
        return {"paper_order_events": [], "write_count": state["writes"]}

    async def persist(*args: Any, **kwargs: Any) -> None:
        state["writes"] += 1
        state["clock"] += 2
        callbacks[0]()
        if state["delay"]:
            await asyncio.sleep(1)
        if state["error"] is not None and state["writes"] == 2:
            raise state["error"]

    monkeypatch.setattr(iso, "create_engine_for", lambda role: Engine())
    monkeypatch.setattr(iso, "user_session", session)
    monkeypatch.setattr(iso, "verify_databases", preflight)
    monkeypatch.setattr(iso, "verify_writer", lambda *args: None)
    monkeypatch.setattr(iso, "monotonic", lambda: state["clock"])
    monkeypatch.setattr(iso, "checkpoint_snapshot", snapshot)
    monkeypatch.setattr(iso, "state_from_payload", lambda payload: SimpleNamespace(orders=[1, 2]))
    monkeypatch.setattr(matching_storage, "persist_checkpoint", persist)
    monkeypatch.setattr(event, "listen", lambda target, name, callback: callbacks.append(callback))
    monkeypatch.setattr(event, "remove", lambda target, name, callback: callbacks.remove(callback))
    operation = {
        "state": {},
        "order": str(uuid4()),
        "id": str(uuid4()),
        "kind": "ACCEPTED",
        "decision": "ACCEPT",
        "at": "2026-11-06T00:00:00+00:00",
    }
    fixture = tmp_path / "fixture.json"
    save(fixture, {"owner": uuid4(), "wallet": uuid4(), "operations": [operation] * 6})
    initial = tmp_path / "initial.json"
    save(initial, {"paper_order_events": [], "write_count": 0})
    args = argparse.Namespace(
        output=tmp_path / "direct",
        fixture=fixture,
        database="tiewtrade_set4_iso_test",
        source=tmp_path,
        writer_hash="hash",
        writer="direct",
        initial=initial,
        reference=None,
    )
    return args, state, callbacks


async def test_timing_excludes_verification_and_closes_resources(observed_arm: Any) -> None:
    args, state, callbacks = observed_arm
    await iso.measure_arm(args)
    result = json.loads((args.output / "result.json").read_text())
    assert len(result["measurements"]) == 6
    assert all(
        row["checkpoint_seconds"] == 2 and row["transaction_seconds"] == 4
        for row in result["measurements"]
    )
    assert all(row["client_statements"] == 1 for row in result["measurements"])
    assert state["disposed"] == 1 and callbacks == []
    assert json.loads((args.output / "closed.json").read_text())["checked_out"] == 0


async def test_mismatch_stops_before_later_operations(observed_arm: Any) -> None:
    args, state, callbacks = observed_arm
    await iso.measure_arm(args)
    reference = args.output
    save(reference / "operation-02-normalized.json", {"corrupted": True})
    args.output = reference.parent / "batch"
    args.reference, args.writer = reference, "batch"
    state["writes"] = 0
    with pytest.raises(ValueError, match="snapshot mismatch"):
        await iso.measure_arm(args)
    assert state["writes"] == 2 and state["disposed"] == 2 and callbacks == []
    assert not (args.output / "result.json").exists()


@pytest.mark.parametrize("cancellation", [False, True])
async def test_primary_error_survives_cleanup_failure(
    observed_arm: Any, cancellation: bool
) -> None:
    args, state, callbacks = observed_arm
    original = asyncio.CancelledError() if cancellation else ValueError("original")
    state["error"], state["cleanup_error"] = original, True
    with pytest.raises(type(original)) as error:
        await iso.measure_arm(args)
    assert error.value is original
    assert state["writes"] == 2 and state["disposed"] == 1 and callbacks == []


async def test_operation_deadline_aborts_and_closes(
    observed_arm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    args, state, callbacks = observed_arm
    state["delay"] = True
    original = asyncio.timeout
    monkeypatch.setattr(asyncio, "timeout", lambda seconds: original(0.01))
    with pytest.raises(TimeoutError):
        await iso.measure_arm(args)
    assert state["writes"] == 1 and state["disposed"] == 1 and callbacks == []


async def test_child_cancellation_waits_for_process_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spawn = asyncio.create_subprocess_exec
    processes = []

    async def capture(*args: Any, **kwargs: Any) -> Any:
        process = await spawn(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.2):
            await iso.child(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                tmp_path,
                dict(os.environ),
                tmp_path / "child.log",
            )
    assert processes and processes[0].returncode is not None


@pytest.mark.parametrize("size", [2, 20])
async def test_real_fixture_sizes_preserve_operations(
    tmp_path: Path, engine_engine: AsyncEngine, size: int
) -> None:
    path = tmp_path / "fixture.json"
    if size == 2:
        await prepare(path)
    else:
        await prepare(path, btc_orders=size)
    document = json.loads(path.read_text())
    operations = document["operations"]
    owner = UUID(document["owner"])
    try:
        assert len(operations) == size + 4
        assert [o["state"]["base"] for o in operations[: size + 2]] == ["BTC"] * size + ["ETH"] * 2
        assert operations[-2]["kind"] == "CANCELED"
        assert operations[-2]["order"] == operations[0]["order"]
        assert operations[-1]["kind"] == "INPUT_APPLIED"
        assert operations[-1]["order"] == operations[size]["order"]
        assert [datetime.fromisoformat(o["at"]).second for o in operations] == list(
            range(1, size + 5)
        )
        assert len(operations[size - 1]["state"]["orders"]) == size
    finally:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE paper_order_dispatch SET state='TERMINAL',"
                "worker=NULL,claim_id=NULL,lease_until=NULL"
            )


async def test_real_preflight_verifies_all_roles_and_function() -> None:
    database = make_url(os.environ[DatabaseRole.MIGRATOR.url_variable]).database
    assert database is not None
    result = await iso.verify_databases(database)
    assert all(
        result[role.name] == {"database": database, "role": role.value} for role in DatabaseRole
    )
    assert len(result["function_body_sha256"]) == 64
