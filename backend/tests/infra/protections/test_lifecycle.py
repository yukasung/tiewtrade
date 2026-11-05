"""Protection financial effects tested through the real F-15 writer and PostgreSQL."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import (
    AllowPolicy,
    CorrectionReplayRequest,
    ready_public_sources,
)
from tests.infra.manual_orders.test_bridge import select_use
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookState, MarketTrade
from tiewtrade.core.orders import AdmissionPolicy, BaseSize, OrderIntent, OrderType, TimeInForce
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, PositionPair
from tiewtrade.core.protections import ProtectionState
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    BookLease,
    ExecutionMetadata,
    publish_input,
)
from tiewtrade.infra.paper_orders.codec import execution_from_payload
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order, submit_cancel
from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
from tiewtrade.infra.paper_orders.request_worker import process_request as transfer_request
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections.storage import admit_request, free_quantity, groups, load
from tiewtrade.infra.protections.worker import process_group, process_request

PAIR = PositionPair("BTC", "USDT")


async def single_fill(session: UserSession, order_id: UUID) -> tuple[UUID, UUID, ExecutionFact]:
    """Read one immutable RECORD fill from these controlled one-fill fixtures."""
    linked = (
        await session.execute(
            """SELECT l.position_event_id,l.order_event_id,e.payload
            FROM paper_execution_links l JOIN paper_order_events e ON e.id=l.order_event_id
            WHERE l.order_id=:order AND l.position_event_kind='RECORD'""",
            {"order": order_id},
        )
    ).one()
    return (
        linked.position_event_id,
        linked.order_event_id,
        execution_from_payload(linked.payload["execution"]),
    )


@pytest.fixture(autouse=True)
async def protocol(migrator_engine: AsyncEngine) -> AsyncIterator[None]:
    async with migrator_engine.begin() as connection:
        await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
    yield
    async with migrator_engine.begin() as connection:
        await connection.execute(text("UPDATE paper_protection_protocol SET enabled=false"))


async def execute(
    engine: AsyncEngine, owner: UUID, command: UUID, *, policy: AdmissionPolicy | None = None
) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        row = (
            await session.execute(
                "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                {"id": command},
            )
        ).one()
        claim = await claim_order(
            session, DueOrder(command, owner, row.next_attempt_at), worker="protection-test"
        )
    assert claim is not None
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_claimed_order(
            session, claim, policy=AllowPolicy() if policy is None else policy
        )


async def transfer(
    api: AsyncEngine,
    engine: AsyncEngine,
    scan: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    value: OrderIntent,
    *,
    bracket: dict[str, Any] | None = None,
    selections: tuple[dict[str, Any], ...] = (),
) -> UUID:
    async with user_session(api, owner) as session:
        request = await admit_new_request(
            session,
            wallet_id=wallet.wallet_id,
            intent=value,
            protection=bracket,
            protection_allocations=selections,
        )
    # Drive the fixture's request directly, like the existing HTTP inbox tests.
    # A global round would also transfer unrelated owners' pending API fixtures.
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        due = (
            await session.execute(
                "SELECT next_attempt_at FROM paper_order_request_dispatch WHERE request_id=:id",
                {"id": request.request_id},
            )
        ).scalar_one()
        claim = await claim_request(
            session, DueRequest(request.request_id, owner, due), worker="protection-intake"
        )
        assert claim is not None
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await transfer_request(session, claim, policy=AllowPolicy())
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        row = (
            await session.execute(
                "SELECT command_id,state FROM paper_order_request_results WHERE request_id=:id",
                {"id": request.request_id},
            )
        ).one()
        assert row.state == "TRANSFERRED"
    return UUID(str(row.command_id))


async def buy(
    api: AsyncEngine,
    engine: AsyncEngine,
    scan: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> tuple[AsyncEngine, BookLease, BookState, ExecutionMetadata, UUID]:
    await select_use(api, owner)
    market, lease, book, metadata = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    command = await transfer(
        api, engine, scan, owner, wallet, value, bracket={"tp": "110", "sl": "90"}
    )
    await execute(engine, owner, command)
    await asyncio.sleep(0.23)
    async with market_data_session(market) as session:
        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        book = replace(
            book, input_id=book.input_id + 1, received_at=now, verified_at=now, rebase=False
        )
        lease = await publish_input(session, lease, book, metadata)
    await asyncio.sleep(0.035)
    await execute(engine, owner, command)
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        rows = await groups(session, wallet.episode_id, PAIR)
        assert len(rows) == 1 and rows[0].value.quantity == Quantity.of("0.999", "BTC")
        group_id = rows[0].value.protection_id
        await process_group(session, group_id)
    return market, lease, book, metadata, group_id


async def test_manual_partial_fill_cancel_releases_only_order_reservation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata, group_id = await buy(
        api_engine, engine_engine, scan_engine, owner, wallet
    )
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None and before.value.state is ProtectionState.ARMED
        sale = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of("0.4", "BTC")),
            limit_price=Money.of("110", "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        command = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            sale,
            selections=(
                {
                    "protection_id": str(group_id),
                    "expected_revision": before.value.revision,
                    "quantity": "0.4",
                },
            ),
        )
        await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            after = await load(session, group_id)
            assert after is not None and after.value.quantity == Quantity.of("0.599", "BTC")
        await asyncio.sleep(0.23)
        async with market_data_session(market) as session:
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
            lease = await publish_input(session, lease, book, metadata)
        await asyncio.sleep(0.035)
        await execute(engine_engine, owner, command)
        await asyncio.sleep(0.23)
        async with market_data_session(market) as session:
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            trade = MarketTrade(
                PAIR,
                book.input_id + 1,
                lease.generation,
                now,
                1001,
                ExecutionSide.SELL,
                Money.of("110", "USDT"),
                Quantity.of("0.1", "BTC"),
                True,
                source_at=now,
            )
            await publish_input(session, lease, trade, metadata)
        await asyncio.sleep(0.035)
        await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            cancel = await submit_cancel(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_id=sale.order_id,
                idempotency_key=uuid4(),
            )
        await execute(engine_engine, owner, cancel.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            after = await load(session, group_id)
            assert after is not None and after.value.quantity == Quantity.of("0.599", "BTC")
            assert await free_quantity(session, wallet.episode_id, PAIR) == Quantity.of(
                "0.3", "BTC"
            )
            status = (
                await session.execute(
                    "SELECT status,filled_quantity FROM paper_order_projections WHERE order_id=:id",
                    {"id": sale.order_id},
                )
            ).one()
            assert status.status == "CANCELED" and Quantity.of(
                status.filled_quantity, "BTC"
            ) == Quantity.of("0.1", "BTC")
    finally:
        await market.dispose()


async def test_rejected_sell_admission_does_not_release_protection(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None
        sale = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of("0.4", "BTC")),
            limit_price=Money.of("0.01", "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        command = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            sale,
            selections=(
                {
                    "protection_id": str(group_id),
                    "expected_revision": before.value.revision,
                    "quantity": "0.4",
                },
            ),
        )
        await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            after = await load(session, group_id)
            assert after is not None and after.value == before.value
            assert (
                await session.execute(
                    "SELECT state FROM paper_order_command_results WHERE command_id=:id",
                    {"id": command},
                )
            ).scalar_one() == "REJECTED"
    finally:
        await market.dispose()


async def test_same_key_concurrent_intake_and_replay_apply_once(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        key = uuid4()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None

        async def intake() -> UUID:
            async with user_session(api_engine, owner) as session:
                return await admit_request(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    action="CANCEL",
                    key=key,
                    protection_id=group_id,
                    payload={"expected_revision": before.value.revision},
                )

        ids = await asyncio.gather(intake(), intake())
        assert ids[0] == ids[1]

        async def apply() -> None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, ids[0])

        await asyncio.gather(apply(), apply())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            after = await load(session, group_id)
            assert after is not None and after.value.state is ProtectionState.CANCELED
            assert after.value.revision == before.value.revision + 1
            assert await free_quantity(session, wallet.episode_id, PAIR) == Quantity.of(
                "0.999", "BTC"
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_results WHERE request_id=:id",
                    {"id": ids[0]},
                )
            ).scalar_one() == 1
    finally:
        await market.dispose()


@pytest.mark.parametrize("liquid", ["10", "0.1"])
async def test_price_trigger_exit_replay_and_exact_financial_effects(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    liquid: str,
) -> None:
    from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
    from tiewtrade.infra.market_data.realtime_storage import read_snapshot, write_price
    from tiewtrade.infra.paper_wallet import get_wallet
    from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

    market, lease, book, metadata, group_id = await buy(
        api_engine, engine_engine, scan_engine, owner, wallet
    )
    try:
        if liquid == "10":
            from tests.infra.risk_limits.test_stops import breach
            from tiewtrade.infra.risk_limits.stops import consume_stop

            stop_id = await breach(engine_engine, owner, wallet)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await consume_stop(session, stop_id)
                preserved = await load(session, group_id)
                assert preserved is not None and preserved.value.state is ProtectionState.ARMED
        async with market_data_session(market) as market_session:
            snapshot = await read_snapshot(market_session)
            assert snapshot.feed is not None
            price = next(r for r in snapshot.rows if r.base == "BTC")
            observation = QuoteObservation(
                "primary_spot",
                "BTC",
                "USDT",
                Money.of("110", "USDT"),
                101,
                snapshot.server_time,
                snapshot.server_time,
                ObservationKind.STREAM,
            )
            await write_price(
                market_session, snapshot.feed, replace(price, observation=observation)
            )

        async def trigger() -> None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_group(session, group_id)

        # The durable scanner must find protection work after its entry is FILLED,
        # without relying on an ordinary active order to wake the financial worker.
        from tiewtrade.services.engine.paper_order import run_protection_round

        if liquid == "10":
            await run_protection_round(engine=engine_engine, scan_engine=scan_engine, limit=160)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                scanned = await load(session, group_id)
                assert scanned is not None and scanned.value.state is ProtectionState.EXITING
        # The partial-liquidity variant has no scanner trigger first: both connections
        # race from ARMED and must converge to a single immutable exit identity.
        await asyncio.gather(trigger(), trigger())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            exits = (
                await session.execute(
                    "SELECT command_id FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).all()
            assert len(exits) == 1
            command = exits[0].command_id
        await execute(engine_engine, owner, command, policy=TransactionalRiskPolicy())
        await asyncio.sleep(0.23)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            from tiewtrade.core.order_book import BookLevel

            book = replace(
                book,
                input_id=book.input_id + 1,
                received_at=now,
                verified_at=now,
                bids=(BookLevel(Money.of("99", "USDT"), Quantity.of(liquid, "BTC")),),
            )
            await publish_input(market_session, lease, book, metadata)
        await asyncio.sleep(0.035)
        await execute(engine_engine, owner, command, policy=TransactionalRiskPolicy())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            after = await load(session, group_id)
            assert after is not None
            assert after.value.state is (
                ProtectionState.CLOSED if liquid == "10" else ProtectionState.FAILED
            )
            assert after.value.quantity == Quantity.of("0" if liquid == "10" else "0.899", "BTC")
            result = await get_wallet(session)
            assert result is not None
            # Buy 1 gross for100, fee0.001 BTC ->0.999 BTC. Sell0.999 at99:
            # quote98.901 less fee0.098901 ->98.802099. No additional PnL credit.
            assert result.balance == Money.of(
                "9998.802099" if liquid == "10" else "9909.8901", "USDT"
            )
            assert await free_quantity(session, wallet.episode_id, PAIR) == Quantity.of(0, "BTC")
            await process_group(session, group_id)
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
        # Read the public exit linkage through an actual API-role snapshot.
        from datetime import UTC, datetime

        from fastapi import FastAPI, Request

        from tiewtrade.services.api.protection_routes import page
        from tiewtrade.services.api.request_identity import Authenticated

        app = FastAPI()
        app.state.api_engine = api_engine
        response = await page(
            Request({"type": "http", "app": app}),
            Authenticated(owner, "test-session", datetime.now(UTC)),
            episode_id=wallet.episode_id,
            cursor=None,
            limit=20,
        )
        public = next(p for p in response.protections if p.protection_id == group_id)
        assert public.exit_order_id is not None
        assert public.exit_order_state in ("FILLED", "EXPIRED")
        assert public.exit_quantity == "0.999"
        assert public.exit_filled_quantity == ("0.999" if liquid == "10" else "0.1")
        # Correct a terminal exit through the real financial writer, then reload
        # and replay it. A CLOSED group must expose returned assets as conflicted
        # residual rather than silently retaining the old full-exit accounting.
        from tiewtrade.infra.paper_orders.corrections import correct_fill
        from tiewtrade.infra.positions import PositionEventKind

        correction_id = uuid4()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            position_event_id, order_event_id, fact = await single_fill(
                session, public.exit_order_id
            )
            corrected = replace(
                fact,
                gross_quantity=Quantity.of("0.5" if liquid == "10" else "0.05", "BTC"),
                quote_amount=Money.of("49.5" if liquid == "10" else "4.95", "USDT"),
                fee=None,
            )
            arguments: CorrectionReplayRequest = {
                "wallet_id": wallet.wallet_id,
                "episode_id": wallet.episode_id,
                "order_event_id": order_event_id,
                "correction_event_id": correction_id,
                "supersedes_position_event_id": position_event_id,
                "kind": PositionEventKind.REPLACE,
                "fact": corrected,
            }
            await correct_fill(session, **arguments)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            after = await load(session, group_id)
            assert after is not None and after.value.state is ProtectionState.FAILED
            assert after.value.conflicted
            assert after.value.quantity == Quantity.of(
                "0.499" if liquid == "10" else "0.949", "BTC"
            )
            assert after.disposed == corrected.gross_quantity
            assert (
                Quantity.of(
                    (
                        await session.execute(
                            "SELECT accounted FROM paper_protection_exit_progress WHERE id=:id",
                            {"id": public.exit_order_id},
                        )
                    ).scalar_one(),
                    "BTC",
                )
                == corrected.gross_quantity
            )
            assert await correct_fill(session, **arguments) is None
            await process_group(session, group_id)
            replayed = await load(session, group_id)
            assert replayed is not None and replayed.value == after.value
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
    finally:
        await market.dispose()


async def test_api_cannot_mutate_projection_and_other_owner_cannot_read(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.infra.db.errors import InfraError

    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(api_engine, uuid4()) as session:
            assert await load(session, group_id) is None
        with pytest.raises(InfraError):
            async with user_session(api_engine, owner) as session:
                await session.execute(
                    "UPDATE paper_protections SET quantity=0 WHERE id=:id", {"id": group_id}
                )
        with pytest.raises(InfraError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "DELETE FROM paper_protection_events WHERE protection_id=:id", {"id": group_id}
                )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            assert current is not None and current.value.quantity == Quantity.of("0.999", "BTC")
    finally:
        await market.dispose()


async def test_setup_retry_deadline_survives_reloaded_owner_sessions(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta
    from unittest.mock import AsyncMock

    from tiewtrade.core.orders import SourceUnavailableError
    from tiewtrade.infra.protections.storage import save

    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None
            await save(
                session,
                before,
                replace(
                    before.value, revision=before.value.revision + 1, state=ProtectionState.ARMING
                ),
                kind="REPLACE",
            )
        missing = AsyncMock(side_effect=SourceUnavailableError("recorded metadata outage"))
        monkeypatch.setattr("tiewtrade.infra.protections.worker.read_latest_book", missing)
        for attempt, delay in ((2, 1), (3, 2), (4, 4)):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                started = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                await process_group(session, group_id)
                current = await load(session, group_id)
                assert current is not None and current.value.setup_attempt == attempt
                assert current.value.setup_due_at is not None
                assert (
                    timedelta(seconds=delay)
                    <= current.value.setup_due_at - started
                    < timedelta(seconds=delay + 1)
                )
                revision = current.value.revision
            # A separate process/session before the durable deadline must not spend an attempt.
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_group(session, group_id)
                current = await load(session, group_id)
                assert current is not None and current.value.revision == revision
                # Advance the controlled clock state, without waiting wall-clock seconds.
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                await save(
                    session,
                    current,
                    replace(
                        current.value,
                        revision=revision + 1,
                        setup_due_at=now - timedelta(seconds=1),
                    ),
                    kind="RETRY",
                )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            current = await load(session, group_id)
            assert current is not None and current.value.state is ProtectionState.FAILED
            assert current.value.quantity == Quantity.of("0.999", "BTC")
            assert current.value.setup_due_at is None
            await process_group(session, group_id)
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 0
        assert missing.await_count == 4
    finally:
        await market.dispose()


async def test_request_failure_rolls_back_group_history_and_result_together(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import AsyncMock

    from tiewtrade.infra.protections import storage

    market, _, _, _, old_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            old = await load(session, old_id)
            assert old is not None
        async with user_session(api_engine, owner) as session:
            cancel = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="CANCEL",
                key=uuid4(),
                protection_id=old_id,
                payload={"expected_revision": old.value.revision},
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, cancel)
        async with user_session(api_engine, owner) as session:
            request = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="CREATE",
                key=uuid4(),
                protection_id=None,
                payload={"base": "BTC", "quantity": "0.2", "tp": "110", "sl": None},
            )
            target = (
                await session.execute(
                    "SELECT protection_id FROM paper_protection_requests WHERE id=:id",
                    {"id": request},
                )
            ).scalar_one()
        original = storage.event
        with monkeypatch.context() as patch:
            patch.setattr(
                storage,
                "event",
                AsyncMock(side_effect=RuntimeError("injected before immutable event")),
            )
            with pytest.raises(RuntimeError, match="injected"):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await process_request(session, request)
        assert storage.event is original
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert await load(session, target) is None
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_results WHERE request_id=:id",
                    {"id": request},
                )
            ).scalar_one() == 0
            await process_request(session, request)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, request)
            current = await load(session, target)
            assert current is not None and current.value.quantity == Quantity.of("0.2", "BTC")
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_events WHERE protection_id=:id",
                    {"id": target},
                )
            ).scalar_one() == 1
    finally:
        await market.dispose()


async def test_standalone_groups_do_not_expand_on_a_new_entry_or_overlap(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata, bracket_id = await buy(
        api_engine, engine_engine, scan_engine, owner, wallet
    )
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            bracket = await load(session, bracket_id)
            assert bracket is not None
            revision = bracket.value.revision
        async with user_session(api_engine, owner) as session:
            cancel = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="CANCEL",
                key=uuid4(),
                protection_id=bracket_id,
                payload={"expected_revision": revision},
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, cancel)

        async def create_standalone(quantity: str) -> UUID:
            async with user_session(api_engine, owner) as session:
                request = await admit_request(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    action="CREATE",
                    key=uuid4(),
                    protection_id=None,
                    payload={"base": "BTC", "quantity": quantity, "tp": "110", "sl": "90"},
                )
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, request)
            return request

        await create_standalone("0.4")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            initial = await groups(session, wallet.episode_id, PAIR)
            assert len(initial) == 1 and initial[0].value.quantity == Quantity.of("0.4", "BTC")
            await process_group(session, initial[0].value.protection_id)
            armed = await load(session, initial[0].value.protection_id)
            assert armed is not None and armed.value.state is ProtectionState.ARMED
            standalone = armed.value
        command = await transfer(
            api_engine, engine_engine, scan_engine, owner, wallet, intent(owner, wallet.episode_id)
        )
        await execute(engine_engine, owner, command)
        await asyncio.sleep(0.23)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(
                book,
                input_id=lease.last_input_id + 1,
                received_at=now,
                verified_at=now,
                rebase=False,
            )
            await publish_input(market_session, lease, book, metadata)
        await asyncio.sleep(0.035)
        await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, standalone.protection_id)
            unchanged = await load(session, standalone.protection_id)
            assert unchanged is not None and unchanged.value == standalone
            held, reserved = await held_and_reserved(session, wallet.episode_id, PAIR)
            assert held == Quantity.of("1.998", "BTC") and reserved == Quantity.of(0, "BTC")
            assert await free_quantity(session, wallet.episode_id, PAIR) == Quantity.of(
                "1.598", "BTC"
            )
        await create_standalone("0.6")
        rejected = await create_standalone("1")  # Only0.998 remains available.
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = (
                await session.execute(
                    "SELECT state,failure_code FROM paper_protection_results WHERE request_id=:id",
                    {"id": rejected},
                )
            ).one()
            assert result.state == "REJECTED"
            active = await groups(session, wallet.episode_id, PAIR)
            assert len(active) == 2
            assert {row.value.quantity for row in active} == {
                Quantity.of("0.4", "BTC"),
                Quantity.of("0.6", "BTC"),
            }
            assert all(row.value.entry_order_id is None for row in active)
            assert await free_quantity(session, wallet.episode_id, PAIR) == Quantity.of(
                "0.998", "BTC"
            )
    finally:
        await market.dispose()


async def test_entry_fixture_does_not_transfer_another_owners_pending_request(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.positions.conftest import create_production_wallet
    from tiewtrade.infra.users import create_user

    other = uuid4()
    await create_user(api_engine, other)
    other_wallet = await create_production_wallet(api_engine, engine_engine, scan_engine, other)
    await select_use(api_engine, other)
    async with user_session(api_engine, other) as session:
        pending = await admit_new_request(
            session, wallet_id=other_wallet.wallet_id, intent=intent(other, other_wallet.episode_id)
        )
    market = None
    try:
        market, _, _, _, _ = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
        async with user_session(engine_engine, other, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_request_results WHERE request_id=:id",
                    {"id": pending.request_id},
                )
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_order_commands")
            ).scalar_one() == 0
    finally:
        if market is not None:
            await market.dispose()
        # This test creates a second owner intentionally; preserve facts while
        # finishing that owner's mutable fixture queues even on a failing proof.
        async with user_session(engine_engine, other, role=DatabaseRole.ENGINE) as session:
            for table in ("paper_order_request_dispatch", "paper_order_dispatch"):
                await session.execute(f"""UPDATE {table} SET state='TERMINAL',
                    worker=NULL,claim_id=NULL,lease_until=NULL""")
