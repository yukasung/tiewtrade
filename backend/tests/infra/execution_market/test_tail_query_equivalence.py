"""TAIL-02 keeps the old query's complete owner-visible episode semantics."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_tail_reads as tail
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market import remaining_paper_campaign as campaign
from tests.infra.execution_market.test_publisher_clock_recovery import financial_state
from tests.infra.execution_market.test_tail_reads import market as market
from tiewtrade.infra.db import DatabaseRole, user_session


async def equal_cursor(
    engine: AsyncEngine, owner: workload.OwnerState, episode: Any
) -> tuple[Any, ...]:
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        old = (await session.execute(tail.baseline_sql(), {"episode": episode})).one()
        new = await workload.read_input_cursor(session, episode)
        assert tuple(new) == tuple(old)
        return tuple(new)


@pytest.mark.parametrize("availability", ["READY", "UNKNOWN", "CONFLICTED"])
@pytest.mark.parametrize("head", [0, 1, 5])
async def test_state_and_history_equivalence(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
    tmp_path: Path,
    availability: str,
    head: int,
) -> None:
    engine, owners = market
    owner = owners[0]
    await tail.seed_history(engine, owner, head, tmp_path)
    if availability != "READY":
        async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """UPDATE paper_order_activity SET availability=:state,
                source_proof=NULL,initialization_id=NULL,
                observed_at=CASE WHEN :state='UNKNOWN' THEN NULL ELSE clock_timestamp() END,
                failure_code=CASE WHEN :state='UNKNOWN' THEN NULL ELSE 'TAIL_FIXTURE' END
                WHERE episode_id=:episode""",
                {"state": availability, "episode": owner.wallet.episode_id},
            )
    before = await financial_state(engine, owner.user_id)
    assert await equal_cursor(engine, owner, owner.wallet.episode_id) == (availability, head)
    assert await financial_state(engine, owner.user_id) == before


@pytest.mark.parametrize("invisible", [False, True])
async def test_missing_and_other_owner_activity_still_raise_no_result(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
    invisible: bool,
) -> None:
    engine, owners = market
    target = owners[1].wallet.episode_id if invisible else uuid4()
    async with user_session(engine, owners[0].user_id, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(NoResultFound):
            (await session.execute(tail.baseline_sql(), {"episode": target})).one()
        with pytest.raises(NoResultFound):
            await workload.read_input_cursor(session, target)


async def test_committed_append_snapshot_and_fresh_read_are_preserved(
    market: tuple[AsyncEngine, list[workload.OwnerState]],
    tmp_path: Path,
) -> None:
    engine, owners = market
    owner = owners[0]
    # A repeatable snapshot lets the two SELECT shapes be compared while a different
    # real transaction commits; this is a test engine view, not a runtime isolation change.
    repeatable = engine.execution_options(isolation_level="REPEATABLE READ")
    async with user_session(repeatable, owner.user_id, role=DatabaseRole.ENGINE) as session:
        old = (
            await session.execute(tail.baseline_sql(), {"episode": owner.wallet.episode_id})
        ).one()
        await tail.seed_history(engine, owner, 5, tmp_path)
        new = await workload.read_input_cursor(session, owner.wallet.episode_id)
        assert tuple(new) == tuple(old) == ("READY", 0)
    assert await equal_cursor(engine, owner, owner.wallet.episode_id) == ("READY", 5)


def test_baseline_matches_retained_digest() -> None:
    assert "LEFT JOIN paper_execution_input_keys" in tail.baseline_sql()
    assert "GROUP BY" not in tail.diagnostic_sql()


@pytest.mark.parametrize(
    "fault", ["missing", "json", "hash", "sql", "revision", "source", "normalization", "sql_type"]
)
def test_packaged_control_rejects_corruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    fixture = json.loads(tail.BASELINE_FIXTURE.read_text())
    if fault == "hash":
        fixture["sql_sha256"] = "0" * 64
    elif fault == "sql":
        fixture["sql"] += " AND false"
    elif fault == "revision":
        fixture["source_revision"] = "incorrect"
    elif fault == "source":
        fixture["source_path"] = "other.py"
    elif fault == "normalization":
        fixture["normalization"] = "other"
    elif fault == "sql_type":
        fixture["sql"] = None
    path = tmp_path / "control.json"
    if fault != "missing":
        path.write_text("{" if fault == "json" else json.dumps(fixture))
    monkeypatch.setattr(tail, "BASELINE_FIXTURE", path)
    with pytest.raises(ValueError, match="control is missing or invalid"):
        tail.baseline_sql()


def test_control_works_without_git_or_ancestor_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = Path(
        "specs/features/2026-11-02-tp-sl/evidence/endurance20-20261115/tail01-diagnostic-summary.json"
    )
    receipt = tmp_path / relative
    receipt.parent.mkdir(parents=True)
    receipt.write_bytes((tail.ROOT / relative).read_bytes())
    capture = Mock(side_effect=AssertionError("Git/process lookup is forbidden"))
    monkeypatch.setattr(campaign, "capture", capture)
    monkeypatch.setattr(tail, "ROOT", tmp_path)  # Contains no .git directory or ancestor objects.
    assert "LEFT JOIN paper_execution_input_keys" in tail.baseline_sql()
    capture.assert_not_called()
