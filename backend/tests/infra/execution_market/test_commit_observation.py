"""Confirmed completion must never be inferred from pre-commit row timestamps."""

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_commit_observation as observation
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db import session as db
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order, submit_order
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.services.engine import paper_order


@pytest.mark.usefixtures("internal_database")
@pytest.mark.parametrize("rollback", [False, True])
async def test_real_transaction_receipt_matches_visible_commit_or_rollback(
    tmp_path: Path,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    production_wallet: PaperWalletSnapshot,
    rollback: bool,
) -> None:
    market, _, _, _ = await ready_public_sources()
    path = tmp_path / "worker.commits.json"
    value = intent(owner, production_wallet.episode_id)
    before = (db._begin, vars(paper_order)["process_claimed_order"])
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(
                session, wallet_id=production_wallet.wallet_id, intent=value
            )
            due_at = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command.command_id},
                )
            ).scalar_one()
            claim = await claim_order(
                session, DueOrder(command.command_id, owner, due_at), worker="proof"
            )
            assert claim is not None
        with observation.observe_commits(path):
            try:
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await vars(paper_order)["process_claimed_order"](
                        session, claim, policy=AllowPolicy()
                    )
                    assert not path.exists()  # No confirmation published inside the transaction.
                    if rollback:
                        raise RuntimeError("controlled rollback")
            except RuntimeError:
                assert rollback
        finished = monotonic()
        data = json.loads(path.read_text())
        assert len(data["rows"]) == 1
        row = data["rows"][0]
        assert row["commit_confirmed"] is not rollback
        assert row["command_id"] == str(command.command_id)
        assert row["owner"] == str(owner) and row["order_id"] == str(value.order_id)
        assert row["sampled"] <= row["finished"] <= finished
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            count = (
                await session.execute(
                    "SELECT count(*) FROM paper_order_command_results WHERE command_id=:id",
                    {"id": command.command_id},
                )
            ).scalar_one()
        assert count == (0 if rollback else 1)
        assert not data["acceptance_result"]
        assert (db._begin, vars(paper_order)["process_claimed_order"]) == before
    finally:
        await market.dispose()


async def test_uncertain_commit_is_not_confirmation_and_observers_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private = "PRIVATE_COMMIT_ERROR"
    connection = SimpleNamespace(info={})

    @asynccontextmanager
    async def uncertain(*args: Any, **kwargs: Any) -> Any:
        yield connection
        raise TimeoutError(private)

    monkeypatch.setattr(db, "_begin", uncertain)
    process = vars(paper_order)["process_claimed_order"]
    path = tmp_path / "commits.json"
    with observation.observe_commits(path), pytest.raises(TimeoutError, match=private):
        async with db._begin(None) as current:  # type: ignore[arg-type]
            current.info[observation._KEY] = {"command_id": str(uuid4())}
    assert db._begin is uncertain and vars(paper_order)["process_claimed_order"] is process
    data = json.loads(path.read_text())
    assert data["rows"][0]["commit_confirmed"] is False
    assert data["rows"][0]["error_type"] == "TimeoutError"
    assert private not in path.read_text()


@pytest.mark.parametrize("enabled", [False, True])
async def test_commit_observer_is_explicit_in_child_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    spawn = AsyncMock(return_value=SimpleNamespace(pid=123))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(workload, "wait_runtime_pid", AsyncMock(return_value=456))
    monkeypatch.setattr(workload, "WORKER_RUNTIME_PIDS", {})
    await workload.start_worker_processes(1, tmp_path, failure_timeline=enabled)
    assert spawn.await_args is not None
    assert ("--failure-timeline" in spawn.await_args.args) is enabled


@pytest.mark.parametrize("enabled", [False, True])
async def test_worker_entry_observer_is_removed_after_processing_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    before = db._begin, vars(paper_order)["process_claimed_order"]
    run = AsyncMock(side_effect=RuntimeError("primary"))
    monkeypatch.setattr(workload, "run_worker_process", run)
    with pytest.raises(RuntimeError, match="primary"):
        await workload.worker_entry(
            argparse.Namespace(
                acceptance_profile=None,
                diagnostics=False,
                failure_timeline=enabled,
                worker_metrics=tmp_path / "worker.json",
                worker_name="proof",
                worker_stop=tmp_path / "stop",
                r8_claim_budget=False,
                coordinate_claims=False,
            )
        )
    assert (db._begin, vars(paper_order)["process_claimed_order"]) == before
    assert (tmp_path / "worker.commits.json").exists() is enabled


@pytest.mark.parametrize("uncertain", [False, True])
async def test_bounded_recorder_never_masks_uncertain_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uncertain: bool,
) -> None:
    connection = SimpleNamespace(info={})

    @asynccontextmanager
    async def transaction(*args: Any, **kwargs: Any) -> Any:
        yield connection
        if uncertain:
            raise TimeoutError("PRIVATE_UNCERTAIN")

    monkeypatch.setattr(db, "_begin", transaction)
    monkeypatch.setattr(observation, "ROW_LIMIT", 0)
    path = tmp_path / "bounded.json"
    expected = TimeoutError if uncertain else RuntimeError
    with observation.observe_commits(path), pytest.raises(expected):
        async with db._begin(None) as current:  # type: ignore[arg-type]
            current.info[observation._KEY] = {"command_id": str(uuid4())}
    data = json.loads(path.read_text())
    assert data["truncated"] and data["rows"] == []
    assert "PRIVATE" not in path.read_text()


@pytest.mark.parametrize(
    "sampled,finished,expected",
    [(8.0, 9.0, "confirmed_before"), (11.0, 12.0, "commit_after"), (9.0, 11.0, "ambiguous")],
)
def test_correlation_preserves_commit_bounds_and_ignores_rollback(
    tmp_path: Path,
    sampled: float,
    finished: float,
    expected: str,
) -> None:
    owner, command, order = map(str, (uuid4(), uuid4(), uuid4()))
    row = {
        "owner": owner,
        "command_id": command,
        "order_id": order,
        "status": "FILLED",
        "result_state": "SUCCEEDED",
        "sampled": sampled,
        "finished": finished,
        "transaction_started": 7.0,
        "commit_confirmed": True,
    }
    (tmp_path / "worker-0.commits.json").write_text(
        json.dumps(
            {"truncated": False, "rows": [{**row, "finished": 1, "commit_confirmed": False}, row]}
        )
    )
    phase = {
        "phase": "wait_status",
        "owner": owner,
        "order_id": order,
        "expected_status": "FILLED",
        "started_monotonic": 6.0,
        "finished_monotonic": 8.5,
    }
    (tmp_path / "first-observations.json").write_text(json.dumps({"rows": [phase]}))
    (tmp_path / "cycle-timeouts.json").write_text(
        json.dumps(
            {
                "cycles": [
                    {"deadline_monotonic": 10.0, "phases": [{**phase, "outcome": "CancelledError"}]}
                ]
            }
        )
    )
    data = observation.correlate_observations(tmp_path)
    assert data["confirmed_worker_rows"] == 1 and data["matched"] == 2
    assert data["rows"][0]["observation_after_confirmation_seconds"] == 8.5 - finished
    assert data["rows"][1]["confirmation_vs_deadline"] == expected
    assert data["acceptance_result"] is False


@pytest.mark.parametrize("failure", ["body", "cancel", "metadata"])
async def test_unreadable_metadata_preserves_primary_and_restores_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    class InvalidConnection:
        @property
        def info(self) -> dict[str, Any]:
            raise RuntimeError("PRIVATE_METADATA_ERROR")

    @asynccontextmanager
    async def transaction(*args: Any, **kwargs: Any) -> Any:
        yield InvalidConnection()

    monkeypatch.setattr(db, "_begin", transaction)
    process = vars(paper_order)["process_claimed_order"]
    primary = asyncio.CancelledError() if failure == "cancel" else ValueError("body failure")
    path = tmp_path / "commits.json"
    expected = RuntimeError if failure == "metadata" else type(primary)
    with pytest.raises(expected) as caught, observation.observe_commits(path):
        async with db._begin(None):  # type: ignore[arg-type]
            if failure != "metadata":
                raise primary
    if failure != "metadata":
        assert caught.value is primary
        assert primary.__notes__ == ["commit metadata read failed: RuntimeError"]
    assert db._begin is transaction and vars(paper_order)["process_claimed_order"] is process
    assert json.loads(path.read_text())["rows"] == []
    assert "PRIVATE" not in path.read_text()
