"""Healthy matching rounds must not inflate a later failure's backoff."""

from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    OrderClaimLostError,
    claim_order,
    defer_claim,
    finish_claim,
    submit_order,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


async def test_success_resets_failure_streak_without_reusing_claim_revision(
    engine_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    revisions = []
    # Many healthy polling rounds precede the first actual source failure.
    for _ in range(5):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                    "WHERE command_id=:id RETURNING next_attempt_at",
                    {"id": command.command_id},
                )
            ).scalar_one()
            claim = await claim_order(
                session, DueOrder(command.command_id, owner, due), worker="healthy"
            )
            assert claim is not None
            revisions.append(claim.revision)
            await finish_claim(session, claim, terminal=False)
    assert revisions == sorted(set(revisions))
    healthy_claim = claim
    for expected in (1, 5, 30, 300):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                    "WHERE command_id=:id RETURNING next_attempt_at",
                    {"id": command.command_id},
                )
            ).scalar_one()
            claim = await claim_order(
                session, DueOrder(command.command_id, owner, due), worker="failed"
            )
            assert claim is not None and claim.revision > revisions[-1]
            await defer_claim(session, claim)
            delay = (
                await session.execute(
                    "SELECT extract(epoch FROM next_attempt_at-clock_timestamp()) "
                    "FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command.command_id},
                )
            ).scalar_one()
            assert expected - 1 < delay <= expected
    # A stale successful worker must not clear the new worker's failure streak.
    assert healthy_claim is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderClaimLostError):
            await finish_claim(session, healthy_claim, terminal=False)
        attempts = (
            await session.execute(
                "SELECT attempts FROM paper_order_dispatch WHERE command_id=:id",
                {"id": command.command_id},
            )
        ).scalar_one()
        assert attempts == 4
