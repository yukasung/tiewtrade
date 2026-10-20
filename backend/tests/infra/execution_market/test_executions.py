"""Real PostgreSQL cash linkage, immutable intent bounds, faults and concurrent retry."""

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_storage import prepared
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderConflictError
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, FeeEffect
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.market_data.order_book_storage import publish_input, read_inputs
from tiewtrade.infra.paper_orders.executions import execution_payload, stage_fill_cash
from tiewtrade.infra.paper_orders.initialization import initialize_order_source
from tiewtrade.infra.paper_orders.storage import append_execution_input
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionWriteStatus, read_position_snapshot


async def prepare_fill(
    engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    *,
    sequence: int = 1,
    budget: str = "100",
    fee: str = "0.001",
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: str = "1",
    quote: str = "100",
) -> tuple[UUID, UUID, ExecutionFact]:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )
    public = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        lease, book, metadata = await prepared(public)
        async with market_data_session(public) as session:
            await publish_input(session, lease, book, metadata)
    finally:
        await public.dispose()
    fact = ExecutionFact(
        uuid4(),
        book.pair,
        side,
        Quantity.of(quantity, "BTC"),
        Money.of(quote, "USDT"),
        FeeEffect(Quantity.of(fee, "BTC") if side is ExecutionSide.BUY else Money.of(fee, "USDT")),
        sequence,
        book.received_at,
    )
    event, position = uuid4(), uuid4()
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        record = (await read_inputs(session, book.pair, after=book.input_id - 1, limit=1))[0]
        evidence = await append_execution_input(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            evidence_id=uuid4(),
            record=record,
        )
        params = {
            "user": owner,
            "wallet": wallet.wallet_id,
            "episode": wallet.episode_id,
            "command": uuid4(),
            "order": uuid4(),
            "key": uuid4(),
            "event": event,
            "execution": fact.execution_id,
            "at": fact.occurred_at,
            "accepted": fact.occurred_at - timedelta(seconds=1),
            "evidence": evidence.evidence_id,
            "recorded": evidence.recorded_at,
            "payload": canonical({"execution": execution_payload(fact)}),
            "budget": budget if side is ExecutionSide.BUY else None,
            "quantity": quantity if side is ExecutionSide.SELL else None,
            "side": side.value,
            "sequence": sequence,
        }
        await session.execute(
            """INSERT INTO paper_order_commands
          (id,user_id,wallet_id,episode_id,action,idempotency_key,order_id,request_fingerprint,payload)
          VALUES(:command,:user,:wallet,:episode,'NEW',:key,:order,repeat('0',64),'{}')""",
            params,
        )
        await session.execute(
            """INSERT INTO paper_orders
          (id,user_id,wallet_id,episode_id,command_id,sequence,base,quote,origin,side,kind,
           budget,quantity,accepted_at,constraints)
          VALUES(:order,:user,:wallet,:episode,:command,:sequence,'BTC','USDT','MANUAL',:side,'MARKET',
                 CAST(:budget AS tiewtrade_money_amount),CAST(:quantity AS tiewtrade_money_amount),
                 :accepted,'{}')""",
            params,
        )
        await session.execute(
            """INSERT INTO paper_order_events
          (id,order_id,user_id,episode_id,base,quote,sequence,event_kind,execution_id,
           input_recorded_at,input_evidence_id,payload,occurred_at)
          VALUES(:event,:order,:user,:episode,'BTC','USDT',1,'FILL',:execution,:recorded,
                 :evidence,CAST(:payload AS jsonb),:at)""",
            params,
        )
    return event, position, fact


async def write_fill(
    engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    event: UUID,
    position: UUID,
    fact: ExecutionFact,
) -> PositionWriteStatus:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        result = await stage_fill_cash(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            order_event_id=event,
            position_event_id=position,
            fact=fact,
        )
        return result.status


async def test_concurrent_retry_applies_exact_cash_and_position_once(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    event, position, fact = await prepare_fill(engine_engine, owner, wallet)
    results = await asyncio.gather(
        write_fill(engine_engine, owner, wallet, event, position, fact),
        write_fill(engine_engine, owner, wallet, event, position, fact),
    )
    assert set(results) == {PositionWriteStatus.APPLIED, PositionWriteStatus.REPLAYED}
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        after = await get_wallet(session)
        assert after is not None and after.balance == wallet.balance - Money.of(100, "USDT")
        snapshot = await read_position_snapshot(session, wallet.episode_id)
        assert snapshot is not None
        assert snapshot.positions[0].held_quantity == Quantity.of("0.999", "BTC")
        assert (
            await session.execute(
                """SELECT count(*) FROM paper_wallet_ledger
          WHERE episode_id=:episode AND kind='TRADE_CASH'""",
                {"episode": wallet.episode_id},
            )
        ).scalar_one() == 1


@pytest.mark.parametrize(
    ("quantity", "quote", "fee", "cash", "entries"),
    [
        ("0.5", "49.5", "0.0495", "49.4505", 2),
        ("0.000000000000000001", "0.000000000000000001", "0.000000000000000001", "0", 1),
    ],
)
async def test_sell_proceeds_and_zero_cash_linkage_replay_after_source_expiry(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    quantity: str,
    quote: str,
    fee: str,
    cash: str,
    entries: int,
) -> None:
    event, position, fact = await prepare_fill(engine_engine, owner, wallet)
    await write_fill(engine_engine, owner, wallet, event, position, fact)
    event, position, fact = await prepare_fill(
        engine_engine,
        owner,
        wallet,
        sequence=2,
        side=ExecutionSide.SELL,
        quantity=quantity,
        quote=quote,
        fee=fee,
    )
    assert await write_fill(engine_engine, owner, wallet, event, position, fact) is (
        PositionWriteStatus.APPLIED
    )
    public = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(public) as session:
            await session.execute("""UPDATE market_execution_state
              SET ready=false,verified_at=clock_timestamp()-interval '2 seconds'
              WHERE base='BTC'""")
    finally:
        await public.dispose()
    assert await write_fill(engine_engine, owner, wallet, event, position, fact) is (
        PositionWriteStatus.REPLAYED
    )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        after = await get_wallet(session)
        assert after is not None
        assert after.balance == wallet.balance - Money.of(100, "USDT") + Money.of(cash, "USDT")
        snapshot = await read_position_snapshot(session, wallet.episode_id)
        assert snapshot is not None
        assert snapshot.positions[0].held_quantity == (
            Quantity.of("0.999", "BTC") - Quantity.of(quantity, "BTC")
        )
        assert (
            await session.execute(
                """SELECT count(*) FROM paper_wallet_ledger
            WHERE episode_id=:episode AND kind='TRADE_CASH'""",
                {"episode": wallet.episode_id},
            )
        ).scalar_one() == entries
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_execution_links WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one() == 2


async def test_cash_failure_rolls_back_position_link_and_audit_then_retry(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event, position, fact = await prepare_fill(engine_engine, owner, wallet)
    original = UserSession.execute

    async def fail(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        if "INSERT INTO paper_wallet_ledger" in statement:
            raise RuntimeError("injected trade cash failure")
        return await original(session, statement, parameters)

    with monkeypatch.context() as patch:
        patch.setattr(UserSession, "execute", fail)
        with pytest.raises(RuntimeError, match="injected trade cash"):
            await write_fill(engine_engine, owner, wallet, event, position, fact)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        snapshot = await read_position_snapshot(session, wallet.episode_id)
        assert snapshot is not None and snapshot.positions == ()
        assert (
            await session.execute(
                "SELECT count(*) FROM paper_execution_links WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).scalar_one() == 0
        assert (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE subject_id=:event",
                {"event": str(position)},
            )
        ).scalar_one() == 0
    assert await write_fill(engine_engine, owner, wallet, event, position, fact) is (
        PositionWriteStatus.APPLIED
    )


@pytest.mark.parametrize(("budget", "fee"), [("99", "0.001"), ("100", "0.002")])
async def test_oversized_order_or_incorrect_fee_cannot_change_money(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    budget: str,
    fee: str,
) -> None:
    event, position, fact = await prepare_fill(engine_engine, owner, wallet, budget=budget, fee=fee)
    with pytest.raises(OrderConflictError):
        await write_fill(engine_engine, owner, wallet, event, position, fact)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        after = await get_wallet(session)
        assert after is not None and after.balance == wallet.balance


async def test_execution_payload_mismatch_and_sequence_conflict_do_not_change_cash(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    event, position, fact = await prepare_fill(engine_engine, owner, wallet, sequence=2)
    with pytest.raises(OrderConflictError):
        await write_fill(
            engine_engine,
            owner,
            wallet,
            event,
            position,
            replace(fact, quote_amount=Money.of(101, "USDT")),
        )
    result = await write_fill(engine_engine, owner, wallet, event, position, fact)
    assert result is PositionWriteStatus.CONFLICTED
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        after = await get_wallet(session)
        assert after is not None and after.balance == wallet.balance
        assert after.revision == wallet.revision + 1
        row = (
            await session.execute(
                "SELECT availability FROM paper_order_activity WHERE episode_id=:episode",
                {"episode": wallet.episode_id},
            )
        ).one()
        assert row.availability == "CONFLICTED"
