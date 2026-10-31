"""R9 real-role routing, canonical claim proof and one-preference recovery."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.migration_support import (
    prepare_migration_roundtrip,
    restore_migration_roundtrip,
)
from tests.infra.risk_limits.test_execution import Runtime, drive, runtime
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import BaseSize, OrderIntent, OrderType, TimeInForce
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    OrderClaimLostError,
    OrderCommand,
    claim_order,
    defer_claim,
    due_orders,
    get_order_command,
    require_claim,
    submit_cancel,
    submit_order,
)
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy


def resting(owner: UUID, episode: UUID, *, base: str = "BTC") -> OrderIntent:
    return replace(
        intent(owner, episode),
        pair=PositionPair(base, "USDT"),
        kind=OrderType.LIMIT,
        size=BaseSize(Quantity.of(1, base)),
        limit_price=Money.of(90, "USDT"),
        time_in_force=TimeInForce.GTC,
    )


@dataclass(frozen=True)
class Queue:
    owner: UUID
    wallet: PaperWalletSnapshot
    sources: Runtime
    head: OrderCommand
    head_order: UUID
    new: OrderCommand
    due: datetime
    admission_first: bool = False


@pytest.fixture(params=[False, True], ids=["r9", "r10"])
async def queue(
    request: pytest.FixtureRequest,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> AsyncIterator[Queue]:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        value = resting(owner, wallet.episode_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            head = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, head.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await get_order_command(session, head.command_id)
            assert result is not None and result.state == "SUCCEEDED", result
            new = await submit_order(
                session, wallet_id=wallet.wallet_id, intent=resting(owner, wallet.episode_id)
            )
            due = (
                await session.execute(
                    """UPDATE paper_order_dispatch SET next_attempt_at=
                      clock_timestamp()-interval '1 day'
                    WHERE command_id=:id RETURNING next_attempt_at""",
                    {"id": head.command_id},
                )
            ).scalar_one()
        try:
            yield Queue(owner, wallet, sources, head, value.order_id, new, due, bool(request.param))
        finally:
            # Mutable scheduling cleanup for this fixture's owner only. Immutable
            # financial/order/audit facts and reservations remain intact.
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute("""UPDATE paper_order_dispatch SET state='TERMINAL',
                  worker=NULL,claim_id=NULL,lease_until=NULL""")


async def hint(scan: AsyncEngine, queue: Queue, *, preferred: bool = True) -> DueOrder:
    async with scan_session_bypassing_rls(scan) as session:
        values = await due_orders(
            session,
            prefer_same_pair=preferred,
            admission_first=queue.admission_first if preferred else False,
        )
    return next(value for value in values if value.user_id == queue.owner)


async def test_preferred_admission_covers_original_pair_with_exact_reservations(
    queue: Queue, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    legacy = await hint(scan_engine, queue, preferred=False)
    chosen = await hint(scan_engine, queue)
    assert legacy.command_id == queue.head.command_id
    assert chosen.command_id == queue.new.command_id
    assert chosen.anchor_command_id == queue.head.command_id and chosen.anchor_due_at == queue.due
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        claim = await claim_order(session, chosen, worker="same-pair")
        head = (
            await session.execute(
                """SELECT next_attempt_at,preferred_for_due FROM paper_order_dispatch
                WHERE command_id=:id""",
                {"id": queue.head.command_id},
            )
        ).one()
        assert head.next_attempt_at == head.preferred_for_due == queue.due
    assert claim is not None
    await queue.sources.next_book()
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        await process_claimed_order(session, claim, policy=TransactionalRiskPolicy())
        rows = (
            await session.execute(
                "SELECT command_id,routing_stage,next_attempt_at FROM paper_order_dispatch"
            )
        ).all()
        assert all(row.routing_stage == "ACTIVE" for row in rows)
        assert (
            next(row for row in rows if row.command_id == queue.head.command_id).next_attempt_at
            > queue.due
        )
        assert Money.of(
            (
                await session.execute("SELECT sum(quote_reserved) FROM paper_reservations")
            ).scalar_one(),
            "USDT",
        ) == Money.of(180, "USDT")
        assert (
            await session.execute("SELECT count(*) FROM paper_position_events")
        ).scalar_one() == 0
        assert Money.of(
            (await session.execute("SELECT sum(amount) FROM paper_wallet_ledger")).scalar_one(),
            "USDT",
        ) == Money.of(10000, "USDT")


@pytest.mark.parametrize(
    "block", ["cancel", "unknown", "pending", "latched", "guard", "other_pair"]
)
async def test_fallback_never_skips_cancel_unknown_risk_or_earlier_other_pair(
    queue: Queue, engine_engine: AsyncEngine, scan_engine: AsyncEngine, block: str
) -> None:
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        if block == "cancel":
            await submit_cancel(
                session,
                wallet_id=queue.wallet.wallet_id,
                episode_id=queue.wallet.episode_id,
                order_id=queue.head_order,
                idempotency_key=queue.head_order,
            )
        elif block == "unknown":
            await session.execute("UPDATE paper_order_dispatch SET routing_stage=NULL")
        elif block == "pending":
            await session.execute("UPDATE risk_owner_state SET replay_pending=true")
        elif block == "latched":
            await session.execute("UPDATE risk_limit_settings SET latched=true")
        elif block == "guard":
            await session.execute(
                """UPDATE paper_order_dispatch SET preferred_for_due=next_attempt_at
                WHERE command_id=:id""",
                {"id": queue.head.command_id},
            )
        elif block == "other_pair":
            other = await submit_order(
                session,
                wallet_id=queue.wallet.wallet_id,
                intent=resting(queue.owner, queue.wallet.episode_id, base="ETH"),
            )
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=
                  clock_timestamp()-interval '1 hour'
                WHERE command_id=:id""",
                {"id": other.command_id},
            )
    assert (await hint(scan_engine, queue)).command_id == queue.head.command_id


@pytest.mark.parametrize("change", ["cancel", "anchor_due", "new_due", "source", "forged_hint"])
async def test_claim_rechecks_canonical_facts_after_scan(
    queue: Queue, engine_engine: AsyncEngine, scan_engine: AsyncEngine, change: str
) -> None:
    chosen = await hint(scan_engine, queue)
    assert chosen.anchor_command_id is not None
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        if change == "cancel":
            await submit_cancel(
                session,
                wallet_id=queue.wallet.wallet_id,
                episode_id=queue.wallet.episode_id,
                order_id=queue.head_order,
                idempotency_key=queue.head_order,
            )
        elif change == "anchor_due":
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
                WHERE command_id=:id""",
                {"id": queue.head.command_id},
            )
        elif change == "new_due":
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
                WHERE command_id=:id""",
                {"id": queue.new.command_id},
            )
        elif change == "source":
            await session.execute("UPDATE risk_owner_state SET replay_pending=true")
        elif change == "forged_hint":
            # Forge an ACTIVE routing hint for an unadmitted command. The engine
            # must verify the absent canonical admission/header, not trust it.
            chosen = replace(
                chosen, anchor_command_id=queue.new.command_id, anchor_due_at=chosen.next_attempt_at
            )
            await session.execute("UPDATE paper_order_dispatch SET routing_stage='ACTIVE'")
        assert await claim_order(session, chosen, worker="stale-preference") is None
        assert (
            await session.execute("SELECT count(*) FROM paper_order_dispatch WHERE state='CLAIMED'")
        ).scalar_one() == 0
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_order_dispatch WHERE preferred_for_due IS NOT NULL"
            )
        ).scalar_one() == 0


async def test_one_preference_survives_defer_and_blocks_fresh_new_until_head_progress(
    queue: Queue, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    chosen = await hint(scan_engine, queue)
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        claim = await claim_order(session, chosen, worker="deferred-preference")
    assert claim is not None
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        await defer_claim(session, claim)
        await submit_order(
            session,
            wallet_id=queue.wallet.wallet_id,
            intent=resting(queue.owner, queue.wallet.episode_id),
        )
    fallback = await hint(scan_engine, queue)
    assert fallback.command_id == queue.head.command_id and fallback.anchor_command_id is None


async def test_rollback_then_two_workers_have_one_claim_and_one_guard(
    queue: Queue, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    chosen = await hint(scan_engine, queue)
    with pytest.raises(RuntimeError, match="rollback"):
        async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
            assert await claim_order(session, chosen, worker="rolled-back") is not None
            raise RuntimeError("controlled rollback")

    async def take() -> object:
        async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
            return await claim_order(session, chosen, worker="same-pair-race")

    winners = await asyncio.gather(take(), take())
    assert sum(value is not None for value in winners) == 1
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute("SELECT count(*) FROM paper_order_dispatch WHERE state='CLAIMED'")
        ).scalar_one() == 1
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_order_dispatch WHERE preferred_for_due IS NOT NULL"
            )
        ).scalar_one() == 1
        await session.execute(
            """UPDATE paper_order_dispatch SET lease_until=clock_timestamp()-interval '1 second'
            WHERE state='CLAIMED'"""
        )
    assert (await hint(scan_engine, queue)).command_id == queue.head.command_id
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderClaimLostError):
            from tiewtrade.infra.paper_orders.dispatch import ClaimedOrder

            winner = next(value for value in winners if isinstance(value, ClaimedOrder))
            await require_claim(session, winner)


async def test_fairness_uses_original_anchor_instead_of_new_command_time(
    queue: Queue, api_engine: AsyncEngine, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    from uuid import uuid4

    from tests.infra.risk_limits.test_scheduler import another_wallet, ready

    other_owner = uuid4()
    wallet = await another_wallet(api_engine, engine_engine, scan_engine, other_owner)
    try:
        async with user_session(api_engine, other_owner) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences(user_id,use) VALUES(:id,'MANUAL')",
                {"id": other_owner},
            )
        async with user_session(engine_engine, other_owner, role=DatabaseRole.ENGINE) as session:
            head = await submit_order(
                session, wallet_id=wallet.wallet_id, intent=resting(other_owner, wallet.episode_id)
            )
        await ready(engine_engine, other_owner, wallet)
        await drive(engine_engine, other_owner, head.command_id)
        async with user_session(engine_engine, other_owner, role=DatabaseRole.ENGINE) as session:
            new = await submit_order(
                session, wallet_id=wallet.wallet_id, intent=resting(other_owner, wallet.episode_id)
            )
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=
                  CAST(:due AS timestamptz)-interval '10 seconds'
                WHERE command_id=:id""",
                {"due": queue.due, "id": head.command_id},
            )
        async with scan_session_bypassing_rls(scan_engine) as session:
            hints = await due_orders(
                session, limit=2, prefer_same_pair=True, admission_first=queue.admission_first
            )
        assert [row.user_id for row in hints] == [other_owner, queue.owner]
        assert [row.command_id for row in hints] == [new.command_id, queue.new.command_id]
        assert hints[0].next_attempt_at > hints[1].next_attempt_at
        async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await claim_order(
                    session, replace(hints[0], user_id=queue.owner), worker="cross-owner"
                )
                is None
            )
            assert (
                await session.execute(
                    "SELECT * FROM paper_order_routing(:id)", {"id": head.command_id}
                )
            ).all() == []
    finally:
        async with user_session(engine_engine, other_owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("""UPDATE paper_order_dispatch SET state='TERMINAL',
                worker=NULL,claim_id=NULL,lease_until=NULL""")


async def test_routing_grants_exclude_financial_payloads_and_writes(
    queue: Queue, api_engine: AsyncEngine, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    from uuid import uuid4

    from tiewtrade.infra.db.errors import NotPermittedError

    async with scan_session_bypassing_rls(scan_engine) as session:
        rows = (
            await session.execute(
                "SELECT routing_stage FROM paper_order_dispatch WHERE user_id=:owner",
                {"owner": queue.owner},
            )
        ).all()
        assert {row.routing_stage for row in rows} == {"ACTIVE", "PENDING"}
    for query in (
        "SELECT payload FROM paper_order_commands",
        "SELECT amount FROM risk_limit_settings",
        "SELECT loss FROM risk_limit_evaluations",
        "SELECT book FROM risk_owner_state",
        "UPDATE paper_order_dispatch SET preferred_for_due=next_attempt_at",
    ):
        with pytest.raises(NotPermittedError):
            async with scan_session_bypassing_rls(scan_engine) as session:
                await session.execute(query)
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, queue.owner) as session:
            await session.execute("UPDATE paper_order_dispatch SET routing_stage='ACTIVE'")
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, queue.owner) as session:
            await session.execute(
                "SELECT * FROM paper_order_routing(:id)", {"id": queue.head.command_id}
            )
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT * FROM paper_order_routing(:id)",
                {"id": uuid4()},
            )
        ).all() == []


async def test_real_lost_claim_ack_commits_guard_and_fences_old_worker(
    queue: Queue, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from tests.infra.execution_market.commit_proxy import drop_commit_reply
    from tiewtrade.infra.db import InfraError

    chosen = await hint(scan_engine, queue)
    armed, dropped = asyncio.Event(), asyncio.Event()
    async with drop_commit_reply(
        engine_engine.url.host or "localhost", engine_engine.url.port or 5432, armed, dropped
    ) as port:
        proxy = create_async_engine(
            engine_engine.url.set(host="127.0.0.1", port=port),
            connect_args={"ssl": False},
            hide_parameters=True,
        )
        try:
            with pytest.raises(InfraError):
                async with user_session(proxy, queue.owner, role=DatabaseRole.ENGINE) as session:
                    claim = await claim_order(session, chosen, worker="lost-claim-ack")
                    assert claim is not None
                    armed.set()
            assert dropped.is_set()
        finally:
            await proxy.dispose()
    assert claim is not None
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        row = (
            await session.execute(
                "SELECT preferred_for_due FROM paper_order_dispatch WHERE command_id=:id",
                {"id": queue.head.command_id},
            )
        ).one()
        assert row.preferred_for_due == queue.due
        await session.execute(
            """UPDATE paper_order_dispatch
          SET lease_until=clock_timestamp()-interval '1 second' WHERE command_id=:id""",
            {"id": chosen.command_id},
        )
    assert (await hint(scan_engine, queue)).command_id == queue.head.command_id
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        replacement = await claim_order(
            session,
            DueOrder(chosen.command_id, queue.owner, chosen.next_attempt_at),
            worker="takeover",
        )
        assert replacement is not None and replacement.revision > claim.revision
        with pytest.raises(OrderClaimLostError):
            await require_claim(session, claim)
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        await process_claimed_order(session, replacement, policy=TransactionalRiskPolicy())
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_orders WHERE command_id=:id", {"id": chosen.command_id}
            )
        ).scalar_one() == 1


async def test_projection_only_migration_roundtrip_preserves_facts_and_r8_default(
    queue: Queue,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    from tests.infra.db.test_migrations import _alembic
    from tiewtrade.infra.db import create_engine_for

    async def snapshot(engine: AsyncEngine) -> str:
        async with user_session(engine, queue.owner, role=DatabaseRole.ENGINE) as session:
            return str(
                (
                    await session.execute("""SELECT jsonb_build_object(
              'ledger',(SELECT jsonb_agg(to_jsonb(l) ORDER BY l.id) FROM paper_wallet_ledger l),
              'orders',(SELECT jsonb_agg(to_jsonb(o) ORDER BY o.id) FROM paper_orders o),
              'events',(SELECT jsonb_agg(to_jsonb(e) ORDER BY e.id) FROM paper_order_events e),
              'results',(SELECT jsonb_agg(to_jsonb(r) ORDER BY r.command_id)
                FROM paper_order_command_results r),
              'risk',(SELECT jsonb_agg(to_jsonb(s) ORDER BY s.mode) FROM risk_limit_settings s)
              )::text""")
                ).scalar_one()
            )

    before = await snapshot(engine_engine)
    migration_state = await prepare_migration_roundtrip(migrator_engine)
    try:
        _alembic("downgrade", "0055")
        # A legacy snapshot in flight cannot cause partial FORCE-RLS changes or
        # an unbounded DDL/runtime lock inversion. Release it before retry.
        async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("SELECT order_id FROM paper_order_projections")
            with pytest.raises(AssertionError, match="could not obtain lock"):
                _alembic("upgrade", "head")
            assert (
                await session.execute(
                    "SELECT bool_and(relforcerowsecurity) FROM pg_class WHERE relname IN "
                    "('paper_order_dispatch','paper_orders','paper_order_projections')"
                )
            ).scalar_one()
        assert (await hint(scan_engine, queue, preferred=False)).command_id == queue.head.command_id
    finally:
        _alembic("upgrade", "head")
        await restore_migration_roundtrip(migrator_engine, migration_state)
    fresh = create_engine_for(DatabaseRole.ENGINE)
    fresh_scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    try:
        assert await snapshot(fresh) == before
        chosen = await hint(fresh_scan, queue)
        assert chosen.command_id == queue.new.command_id
    finally:
        await fresh.dispose()
        await fresh_scan.dispose()


async def test_deferred_preference_cannot_starve_a_bounded_sell_during_risk_gap(
    queue: Queue,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    from tests.infra.risk_limits.test_execution import fill_buy
    from tiewtrade.core.positions import ExecutionSide
    from tiewtrade.core.risk_limits import RiskUnavailableError
    from tiewtrade.infra.risk_limits import monitor

    await fill_buy(api_engine, engine_engine, queue.owner, queue.wallet, queue.sources)
    sell = replace(
        resting(queue.owner, queue.wallet.episode_id),
        side=ExecutionSide.SELL,
        size=BaseSize(Quantity.of("0.5", "BTC")),
        limit_price=Money.of(99, "USDT"),
    )
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        head = await submit_order(session, wallet_id=queue.wallet.wallet_id, intent=sell)
    await drive(engine_engine, queue.owner, head.command_id)
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        before = Quantity.of(
            (
                await session.execute(
                    "SELECT held_quantity FROM paper_position_projections WHERE base='BTC'"
                )
            ).scalar_one(),
            "BTC",
        )
        cash = Money.of(
            (await session.execute("SELECT sum(amount) FROM paper_wallet_ledger")).scalar_one(),
            "USDT",
        )
        count = (await session.execute("SELECT count(*) FROM paper_execution_links")).scalar_one()
        await session.execute(
            """UPDATE paper_order_dispatch SET next_attempt_at=
          clock_timestamp()-interval '2 days' WHERE command_id=:id""",
            {"id": head.command_id},
        )
    chosen = await hint(scan_engine, queue)
    assert chosen.command_id == queue.new.command_id and chosen.anchor_command_id == head.command_id
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        failed = await claim_order(session, chosen, worker="preferred-source-failure")
    assert failed is not None
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        await defer_claim(session, failed)
        await session.execute("UPDATE risk_owner_state SET replay_pending=true")
    await asyncio.sleep(0.12)  # F15's real order eligibility delay.
    await queue.sources.next_book()
    await queue.sources.price("100")
    original = await hint(scan_engine, queue)
    assert original.command_id == head.command_id and original.anchor_command_id is None
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        claim = await claim_order(session, original, worker="reduction-with-risk-gap")
    assert claim is not None
    with monkeypatch.context() as patch:
        patch.setattr(
            monitor, "read_frames", AsyncMock(side_effect=RiskUnavailableError("test gap"))
        )
        async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, claim, policy=TransactionalRiskPolicy())
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        held = Quantity.of(
            (
                await session.execute(
                    "SELECT held_quantity FROM paper_position_projections WHERE base='BTC'"
                )
            ).scalar_one(),
            "BTC",
        )
        after = Money.of(
            (await session.execute("SELECT sum(amount) FROM paper_wallet_ledger")).scalar_one(),
            "USDT",
        )
        assert held == before - Quantity.of("0.5", "BTC")
        assert after == cash + Money.of("49.4505", "USDT")
        assert (
            await session.execute("SELECT count(*) FROM paper_execution_links")
        ).scalar_one() == count + 1
        assert (await session.execute("SELECT replay_pending FROM risk_owner_state")).scalar_one()
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_orders WHERE command_id=:id",
                {"id": queue.new.command_id},
            )
        ).scalar_one() == 0


async def test_runtime_round_uses_one_preferred_claim_and_reenables_after_pair_progress(
    queue: Queue, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    from tiewtrade.services.engine.paper_order import run_paper_order_round

    await queue.sources.next_book()
    result = await run_paper_order_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="r9-runtime",
        policy=TransactionalRiskPolicy(),
        limit=20,
        claim_limit=1,
        prefer_same_pair=True,
        admission_first=queue.admission_first,
    )
    assert result.processed == 1 and result.deferred == result.skipped == 0
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        rows = (
            await session.execute(
                "SELECT command_id,claim_revision,preferred_for_due FROM paper_order_dispatch"
            )
        ).all()
        assert all(row.claim_revision == 1 for row in rows)
        assert (
            next(row for row in rows if row.command_id == queue.head.command_id).preferred_for_due
            == queue.due
        )
        applied = await get_order_command(session, queue.new.command_id)
        assert applied is not None and applied.state == "SUCCEEDED"
    await asyncio.sleep(0.21)  # Existing resting-owner reschedule, no production sleep added.
    async with user_session(engine_engine, queue.owner, role=DatabaseRole.ENGINE) as session:
        third = await submit_order(
            session,
            wallet_id=queue.wallet.wallet_id,
            intent=resting(queue.owner, queue.wallet.episode_id),
        )
    following = await hint(scan_engine, queue)
    assert following.command_id == third.command_id and following.anchor_due_at is not None
    assert following.anchor_due_at > queue.due
