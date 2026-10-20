"""Durable Paper command admission, ownership, fairness and lease fencing."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money
from tiewtrade.core.orders import (
    OrderConflictError,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    OrderClaimLostError,
    claim_order,
    due_orders,
    finish_claim,
    require_claim,
    submit_order,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot


def intent(owner: UUID, episode: UUID, *, key: UUID | None = None) -> OrderIntent:
    episode = UUID(str(episode))
    return OrderIntent(
        uuid4(),
        key or uuid4(),
        OrderScope(owner, episode, TradingMode.PAPER),
        PositionPair("BTC", "USDT"),
        OrderOrigin.MANUAL,
        ExecutionSide.BUY,
        OrderType.MARKET,
        QuoteBudget(Money.of(100, "USDT")),
    )


async def test_submit_initializes_replays_and_rejects_payload_conflict(
    engine_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        first = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        replay = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        initialized = (
            await session.execute(
                "SELECT count(*) FROM paper_order_initializations WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one()
    assert replay == first
    assert initialized == 1
    changed = intent(owner, wallet.episode_id, key=value.idempotency_key)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderConflictError):
            await submit_order(session, wallet_id=wallet.wallet_id, intent=changed)


async def test_scanner_is_fair_and_expired_claim_is_fenced(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    async with scan_session_bypassing_rls(scan_engine) as scan:
        due = await due_orders(scan)
    owned = [value for value in due if value.user_id == owner]
    assert len(owned) == 1
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        first = await claim_order(session, owned[0], worker="one")
    assert first is not None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """UPDATE paper_order_dispatch SET lease_until=clock_timestamp()-interval '1 second'
            WHERE command_id=:id""",
            {"id": first.command_id},
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        second = await claim_order(session, owned[0], worker="two")
    assert second is not None and second.claim_id != first.claim_id
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderClaimLostError):
            await require_claim(session, first)
        await require_claim(session, second)


async def test_new_arrivals_do_not_postpone_existing_pending_commands(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        first = await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        original_due = (
            await session.execute(
                "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                {"id": first.command_id},
            )
        ).scalar_one()
    for _ in range(3):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await submit_order(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
            current_due = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": first.command_id},
                )
            ).scalar_one()
        assert current_due == original_due
        async with scan_session_bypassing_rls(scan_engine) as scan:
            due = await due_orders(scan)
        assert [item.command_id for item in due if item.user_id == owner] == [first.command_id]


async def test_competing_claim_skips_locked_command(
    engine_engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        scheduled = (
            await session.execute(
                "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                {"id": command.command_id},
            )
        ).scalar_one()
    due = DueOrder(command.command_id, owner, scheduled)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as first_session:
        first = await claim_order(first_session, due, worker="first")
        assert first is not None
        # Keep the first claim uncommitted while a second real connection sees the stale candidate.
        async with asyncio.timeout(1):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as second:
                assert await claim_order(second, due, worker="second") is None
        await require_claim(first_session, first)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await require_claim(session, first)


async def test_finished_round_cannot_reclaim_from_a_stale_scan(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    async with scan_session_bypassing_rls(scan_engine) as scan:
        stale = next(
            item for item in await due_orders(scan) if item.command_id == command.command_id
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        claim = await claim_order(session, stale, worker="first")
        assert claim is not None
        await finish_claim(session, claim, terminal=False)
        # Make the next round eligible without waiting; the old scan remains stale.
        await session.execute(
            """UPDATE paper_order_dispatch
            SET next_attempt_at=clock_timestamp()-interval '1 millisecond'
            WHERE command_id=:id""",
            {"id": command.command_id},
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await claim_order(session, stale, worker="late-worker") is None
    async with scan_session_bypassing_rls(scan_engine) as scan:
        fresh = next(
            item for item in await due_orders(scan) if item.command_id == command.command_id
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await claim_order(session, fresh, worker="fresh-worker") is not None


async def test_owner_has_one_live_claim_across_commands_and_expiry_recovers(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        commands = [
            await submit_order(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
            for _ in range(2)
        ]
        rows = (
            await session.execute(
                "SELECT command_id,next_attempt_at FROM paper_order_dispatch ORDER BY command_id"
            )
        ).all()
    hints = {row.command_id: DueOrder(row.command_id, owner, row.next_attempt_at) for row in rows}
    first_hint, second_hint = (hints[command.command_id] for command in commands)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as first_session:
        first = await claim_order(first_session, first_hint, worker="first")
        assert first is not None
        async with asyncio.timeout(1):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as other:
                assert await claim_order(other, second_hint, worker="competing") is None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert await claim_order(session, second_hint, worker="after-commit") is None
    async with scan_session_bypassing_rls(scan_engine) as scan:
        assert all(item.user_id != owner for item in await due_orders(scan))
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """UPDATE paper_order_dispatch SET lease_until=clock_timestamp()-interval '1 second'
            WHERE command_id=:id""",
            {"id": first.command_id},
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        recovered = await claim_order(session, second_hint, worker="recovery")
        assert recovered is not None
        with pytest.raises(OrderClaimLostError):
            await require_claim(session, first)
        await finish_claim(session, recovered, terminal=True)


@pytest.mark.parametrize("same_owner", [True, False])
async def test_claim_does_not_wait_for_writer_or_block_another_owner(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    same_owner: bool,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        scheduled = (
            await session.execute(
                "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                {"id": command.command_id},
            )
        ).scalar_one()
    locked_owner = owner if same_owner else uuid4()
    async with user_session(engine_engine, locked_owner, role=DatabaseRole.ENGINE) as writer:
        await writer.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            {"key": f"paper-wallet:{locked_owner}"},
        )
        async with asyncio.timeout(1):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                claim = await claim_order(
                    session, DueOrder(command.command_id, owner, scheduled), worker="claim"
                )
                assert (claim is None) == same_owner
