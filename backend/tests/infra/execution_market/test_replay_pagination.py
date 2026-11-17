"""Complete evidence pagination must retain tied INPUT/REBASE/generation records."""

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_tail_reads as tail
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_replay_reads import ReplayReadObserver
from tests.infra.execution_market.profile_restore import replay_owner_domain
from tests.infra.execution_market.test_tail_reads import market as market
from tiewtrade.core.orders import OrderConflictError, SimulationProfile
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders import storage
from tiewtrade.infra.paper_orders.records import SavedExecutionInput
from tiewtrade.infra.paper_orders.storage import read_execution_input, read_execution_inputs


@pytest.mark.parametrize("variant", ["unique", "rebase", "generation"])
async def test_pagination_does_not_skip_evidence_at_tied_input_id(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path, variant: str
) -> None:
    engine, owners = market
    owner = owners[0]
    await tail.seed_history(engine, owner, 1, tmp_path)
    if variant != "unique":
        await tail.seed_history(
            engine,
            owner,
            1,
            tmp_path,
            generation=2 if variant == "generation" else 1,
            rebase=variant == "rebase",
        )
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        await session.execute("SET TRANSACTION READ ONLY")
        episode = owner.wallet.episode_id
        pair = PositionPair("BTC", "USDT")
        complete = await read_execution_inputs(session, episode_id=episode, pair=pair, limit=100)
        assert len(complete) == (1 if variant == "unique" else 2)
        first = await read_execution_inputs(session, episode_id=episode, pair=pair, limit=1)
        second = await read_execution_inputs(
            session,
            episode_id=episode,
            pair=pair,
            after=first[-1],
            limit=1,
        )
        assert {item.evidence_id for item in (*first, *second)} == {
            item.evidence_id for item in complete
        }


@pytest.mark.parametrize("limit", [1, 2, 4096])
async def test_complete_order_and_scalar_compatibility(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path, limit: int
) -> None:
    engine, owners = market
    owner = owners[0]
    # Multiple valid records share an input ID; the large case spans a full page.
    await tail.seed_history(engine, owner, 4096 if limit == 4096 else 3, tmp_path)
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        last = (
            await read_execution_inputs(
                session,
                episode_id=owner.wallet.episode_id,
                pair=PositionPair("BTC", "USDT"),
                after_input_id=4095 if limit == 4096 else 2,
            )
        )[0]
        record = replace(last.record, market=replace(last.record.market, generation=2))
        record = replace(record, digest=storage._source_digest(record))
        await storage.append_execution_input(
            session,
            wallet_id=owner.wallet.wallet_id,
            episode_id=owner.wallet.episode_id,
            evidence_id=uuid4(),
            record=record,
        )
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        await session.execute("SET TRANSACTION READ ONLY")
        episode = owner.wallet.episode_id
        pair = PositionPair("BTC", "USDT")
        baseline = (
            (
                await session.execute(
                    """SELECT e.* FROM paper_execution_input_keys k
                JOIN paper_execution_inputs e
                  ON (e.id,e.recorded_at)=(k.evidence_id,k.recorded_at)
                WHERE k.episode_id=:episode AND k.base='BTC' AND k.quote='USDT'
                ORDER BY k.input_id,k.generation,k.decision_kind""",
                    {"episode": episode},
                )
            )
            .mappings()
            .all()
        )
        expected = tuple(storage._decode(row) for row in baseline)
        found: list[SavedExecutionInput] = []
        cursor = None
        while True:
            page = await read_execution_inputs(
                session, episode_id=episode, pair=pair, after=cursor, limit=limit
            )
            assert len(page) <= limit
            if not page:
                break
            assert page[-1] != cursor
            found.extend(page)
            cursor = page[-1]
        assert tuple(found) == expected
        assert len({row.evidence_id for row in found}) == len(expected)
        scalar = await read_execution_inputs(
            session, episode_id=episode, pair=pair, after_input_id=1, limit=4096
        )
        assert scalar == tuple(row for row in expected if row.record.market.input_id > 1)
    if limit == 4096:
        replay = await replay_owner_domain(
            engine,
            user_id=owner.user_id,
            wallet_id=owner.wallet.wallet_id,
            episode_id=owner.wallet.episode_id,
            active=False,
        )
        assert replay["evidence_records"] == len(expected)


async def test_cursor_scope_and_foreign_owner(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path
) -> None:
    engine, owners = market
    owner, other = owners
    await tail.seed_history(engine, owner, 2, tmp_path)
    pair = PositionPair("BTC", "USDT")
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        first = (
            await read_execution_inputs(session, episode_id=owner.wallet.episode_id, pair=pair)
        )[0]
        for episode, requested_pair, scalar in (
            (other.wallet.episode_id, pair, 0),
            (owner.wallet.episode_id, PositionPair("ETH", "USDT"), 0),
            (owner.wallet.episode_id, pair, 1),
        ):
            with pytest.raises(ValueError, match="cursor scope"):
                await read_execution_inputs(
                    session,
                    episode_id=episode,
                    pair=requested_pair,
                    after=first,
                    after_input_id=scalar,
                )
    async with user_session(engine, other.user_id, role=DatabaseRole.ENGINE) as session:
        assert (
            await read_execution_inputs(
                session, episode_id=owner.wallet.episode_id, pair=pair, after=first
            )
            == ()
        )
        assert (
            await read_execution_input(
                session,
                episode_id=owner.wallet.episode_id,
                pair=pair,
                evidence_id=first.evidence_id,
                recorded_at=first.recorded_at,
            )
            is None
        )


async def test_exact_identity_and_cursor_snapshot(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path
) -> None:
    engine, owners = market
    owner = owners[0]
    await tail.seed_history(engine, owner, 1, tmp_path)
    pair = PositionPair("BTC", "USDT")
    episode = owner.wallet.episode_id
    repeatable = engine.execution_options(isolation_level="REPEATABLE READ")
    async with user_session(repeatable, owner.user_id, role=DatabaseRole.ENGINE) as session:
        first = (await read_execution_inputs(session, episode_id=episode, pair=pair))[0]
        await tail.seed_history(engine, owner, 1, tmp_path, generation=2)
        assert (
            await read_execution_inputs(session, episode_id=episode, pair=pair, after=first) == ()
        )
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        rest = await read_execution_inputs(session, episode_id=episode, pair=pair, after=first)
        assert len(rest) == 1 and rest[0].record.market.generation == 2
        for row in (first, rest[0]):
            assert (
                await read_execution_input(
                    session,
                    episode_id=episode,
                    pair=pair,
                    evidence_id=row.evidence_id,
                    recorded_at=row.recorded_at,
                )
                == row
            )
        for requested_episode, requested_pair, identity, at in (
            (uuid4(), pair, first.evidence_id, first.recorded_at),
            (episode, PositionPair("ETH", "USDT"), first.evidence_id, first.recorded_at),
            (episode, pair, uuid4(), first.recorded_at),
            (episode, pair, first.evidence_id, first.recorded_at + timedelta(seconds=1)),
        ):
            assert (
                await read_execution_input(
                    session,
                    episode_id=requested_episode,
                    pair=requested_pair,
                    evidence_id=identity,
                    recorded_at=at,
                )
                is None
            )


@pytest.mark.parametrize("limit,scalar", [(0, 0), (4097, 0), (True, 0), (1, -1), (1, True)])
async def test_invalid_bounds_fail_before_query(
    market: tuple[AsyncEngine, list[workload.OwnerState]], limit: int, scalar: int
) -> None:
    engine, owners = market
    async with user_session(engine, owners[0].user_id, role=DatabaseRole.ENGINE) as session:
        with (
            patch.object(UserSession, "execute", side_effect=AssertionError("must not query")),
            pytest.raises(ValueError, match="bounded evidence cursor"),
        ):
            await read_execution_inputs(
                session,
                episode_id=owners[0].wallet.episode_id,
                pair=PositionPair("BTC", "USDT"),
                limit=limit,
                after_input_id=scalar,
            )


async def test_partition_boundary_and_exact_digest_rejection(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path
) -> None:
    engine, owners = market
    owner = owners[0]
    await tail.seed_history(engine, owner, 1, tmp_path)
    pair = PositionPair("BTC", "USDT")
    episode = owner.wallet.episode_id
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        first = (await read_execution_inputs(session, episode_id=episode, pair=pair))[0]
        record = replace(first.record, market=replace(first.record.market, generation=2))
        record = replace(record, digest=storage._source_digest(record))
        profile = SimulationProfile()
        row = storage._prepare_execution_input(
            session,
            wallet_id=owner.wallet.wallet_id,
            episode_id=episode,
            evidence_id=uuid4(),
            record=record,
            decision_market=None,
            fee_version=profile.fee_version,
            model_version=profile.liquidity_version,
        )
    # Insert an immutable second-day fixture; never mutate existing evidence or disable RLS.
    at = first.recorded_at + timedelta(days=1)
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("SELECT create_paper_execution_input_partition(:day)"), {"day": at.date()}
            )
    finally:
        await migrator.dispose()
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        # The existing bulk seed SQL stamps database time; override only the fixture timestamp.
        fixture_sql = tail.SEED_SQL.replace(
            "(id,user_id,wallet_id", "(recorded_at,id,user_id,wallet_id", 1
        ).replace("SELECT id,user_id,wallet_id", "SELECT :recorded_at,id,user_id,wallet_id", 1)
        assert fixture_sql != tail.SEED_SQL
        await session.execute(
            fixture_sql, {"rows": json.dumps([row], default=str), "recorded_at": at}
        )
    observer = ReplayReadObserver()
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        with observer.observe():
            second = await observer.read_page(
                session, episode_id=episode, pair=pair, after=first, limit=1
            )
        assert len(second) == 1 and second[0].recorded_at.date() != first.recorded_at.date()
        assert observer.pages[0]["after_input_id"] == first.record.market.input_id
        assert observer.pages[0]["after_generation"] == first.record.market.generation
        assert (
            await read_execution_input(
                session,
                episode_id=episode,
                pair=pair,
                evidence_id=second[0].evidence_id,
                recorded_at=second[0].recorded_at,
            )
            == second[0]
        )
        with (
            patch.object(storage, "canonical", return_value="corrupted payload"),
            pytest.raises(OrderConflictError, match="evidence is invalid"),
        ):
            await read_execution_input(
                session,
                episode_id=episode,
                pair=pair,
                evidence_id=second[0].evidence_id,
                recorded_at=second[0].recorded_at,
            )


async def test_exact_lookup_requires_registry_membership(
    market: tuple[AsyncEngine, list[workload.OwnerState]], tmp_path: Path
) -> None:
    engine, owners = market
    owner = owners[0]
    await tail.seed_history(engine, owner, 1, tmp_path)
    pair = PositionPair("BTC", "USDT")
    episode = owner.wallet.episode_id
    async with user_session(engine, owner.user_id, role=DatabaseRole.ENGINE) as session:
        original = (await read_execution_inputs(session, episode_id=episode, pair=pair))[0]
        identity = uuid4()
        # An orphan is schema-valid; authentication still requires its key registry row.
        at = (
            await session.execute(
                """INSERT INTO paper_execution_inputs
            (id,user_id,wallet_id,episode_id,base,quote,input_id,generation,decision_kind,
             payload,digest,source_digest)
            SELECT :id,user_id,wallet_id,episode_id,base,quote,input_id,generation,decision_kind,
              payload,digest,source_digest FROM paper_execution_inputs
            WHERE id=:original AND recorded_at=:at RETURNING recorded_at""",
                {"id": identity, "original": original.evidence_id, "at": original.recorded_at},
            )
        ).scalar_one()
        assert (
            await read_execution_input(
                session,
                episode_id=episode,
                pair=pair,
                evidence_id=identity,
                recorded_at=at,
            )
            is None
        )
