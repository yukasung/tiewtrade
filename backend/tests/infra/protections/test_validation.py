"""F-17 feature acceptance gaps, using the real Paper writer and PostgreSQL."""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market.commit_proxy import drop_commit_reply
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_process_recovery import CHILD, marker
from tests.infra.execution_market.test_worker import (
    AllowPolicy,
    CorrectionReplayRequest,
    ready_public_sources,
)
from tests.infra.manual_orders.test_bridge import select_use
from tests.infra.protections.test_lifecycle import buy, execute, single_fill, transfer
from tests.infra.protections.test_lifecycle import protocol as protocol
from tests.infra.risk_limits.test_concurrency import serialize
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import MarketTrade
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderOrigin,
    OrderType,
    TimeInForce,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair
from tiewtrade.core.protections import ProtectionLeg, ProtectionState, TriggerEvidence
from tiewtrade.core.realtime_prices import MAX_PRICE_AGE, ObservationKind, QuoteObservation
from tiewtrade.core.trading_stops import StopAction
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.order_book_storage import publish_input
from tiewtrade.infra.market_data.realtime_storage import (
    begin_generation,
    read_snapshot,
    set_connected,
    write_price,
)
from tiewtrade.infra.paper_orders.corrections import correct_fill
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    OrderClaimLostError,
    claim_order,
    get_order_command,
)
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import (
    DuePaperCommand,
    PaperCommandState,
    PaperWalletAction,
    admit_command,
    claim_command,
    get_command,
    get_wallet,
    process_claimed,
)
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections.storage import admit_request, allocated, groups, load
from tiewtrade.infra.protections.worker import process_group, process_request

PAIR = PositionPair("BTC", "USDT")


@pytest.mark.parametrize(
    "changed_scope,sqlstate", [("mode", "23514"), ("owner", "42501"), ("episode", "23503")]
)
async def test_projection_cannot_move_to_a_different_owner_mode_or_episode(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    changed_scope: str,
    sqlstate: str,
) -> None:
    from tests.infra.positions.conftest import create_production_wallet
    from tiewtrade.infra.db import InfraError
    from tiewtrade.infra.users import create_user

    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        other_owner = uuid4()
        await create_user(api_engine, other_owner)
        other_wallet = await create_production_wallet(
            api_engine, engine_engine, scan_engine, other_owner
        )
        column, document_key, value = {
            "mode": ("mode", "mode", "LIVE"),
            "owner": ("user_id", "owner", other_owner),
            "episode": ("episode_id", "episode", other_wallet.episode_id),
        }[changed_scope]
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None
        with pytest.raises(InfraError, match="42501"):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    f"UPDATE paper_protections SET {column}=:value WHERE id=:id",
                    {"id": group_id, "value": value},
                )
        # Runtime UPDATE grants deliberately exclude immutable scope columns.
        # INSERT exercises CHECK/RLS/FK independently of those column grants.
        owner_sql = "CAST(:value AS uuid)" if changed_scope == "owner" else "user_id"
        episode_sql = "CAST(:value AS uuid)" if changed_scope == "episode" else "episode_id"
        mode_sql = "CAST(:value AS text)" if changed_scope == "mode" else "mode"
        with pytest.raises(InfraError) as rejected:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    f"""INSERT INTO paper_protections
                    (id,user_id,wallet_id,episode_id,mode,base,quote,state,revision,
                     quantity,acquired,disposed,extra_exit,document)
                    SELECT CAST(:new_id AS uuid),{owner_sql},wallet_id,{episode_sql},{mode_sql},
                    base,quote,state,revision,quantity,acquired,disposed,extra_exit,
                    document || jsonb_build_object('id',CAST(CAST(:new_id AS uuid) AS text),
                      'entry',NULL,CAST(:key AS text),CAST(:document_value AS text))
                    FROM paper_protections WHERE id=:id""",
                    {
                        "id": group_id,
                        "new_id": uuid4(),
                        "value": value,
                        "key": document_key,
                        "document_value": str(value),
                    },
                )
                pytest.fail("scope CHECK/RLS/FK must reject before deferred history validation")
        assert sqlstate in str(rejected.value)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            after = await load(session, group_id)
            assert after is not None and after.value == before.value
        async with user_session(api_engine, other_owner) as session:
            assert await load(session, group_id) is None
    finally:
        await market.dispose()


@pytest.mark.parametrize("first_price", ["110", "90"])
async def test_opposite_trigger_prices_serialize_to_one_winning_leg(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    first_price: str,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:

        async def first(session: UserSession) -> None:
            await publish_price(market, first_price)
            await process_group(session, group_id)

        async def second(session: UserSession) -> None:
            await publish_price(market, "90" if first_price == "110" else "110")
            await process_group(session, group_id)

        await serialize(engine_engine, migrator_engine, owner, first, second)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            assert current is not None and current.value.state is ProtectionState.EXITING
            assert current.value.quantity == Quantity.of("0.999", "BTC")
            assert current.value.winning_leg is (
                ProtectionLeg.TAKE_PROFIT if first_price == "110" else ProtectionLeg.STOP_LOSS
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
            held, reserved = await held_and_reserved(session, wallet.episode_id, PAIR)
            assert reserved + await allocated(session, wallet.episode_id, PAIR) == held
    finally:
        await market.dispose()


@pytest.mark.parametrize("correction", [PositionEventKind.REPLACE, PositionEventKind.VOID])
async def test_entry_correction_cannot_repair_or_duplicate_an_unknown_exit(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    correction: PositionEventKind,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        await publish_price(market, "110")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            before = await load(session, group_id)
            assert before is not None and before.value.entry_order_id is not None
            command = (
                await session.execute(
                    "SELECT command_id FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one()
            pending = await get_order_command(session, command)
            assert pending is not None and pending.state == "PENDING"
            position_event_id, order_event_id, fact = await single_fill(
                session, before.value.entry_order_id
            )
            replacement = replace(
                fact,
                gross_quantity=Quantity.of("0.5", "BTC"),
                quote_amount=Money.of("50", "USDT"),
                fee=None,
            )
            arguments: CorrectionReplayRequest = {
                "wallet_id": wallet.wallet_id,
                "episode_id": wallet.episode_id,
                "order_event_id": order_event_id,
                "correction_event_id": uuid4(),
                "supersedes_position_event_id": position_event_id,
                "kind": correction,
                "fact": replacement if correction is PositionEventKind.REPLACE else fact,
            }
            await correct_fill(session, **arguments)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            conflicted = await load(session, group_id)
            assert conflicted is not None and conflicted.value.conflicted
            assert conflicted.value.state is ProtectionState.EXITING
            assert conflicted.value.quantity == Quantity.of("0.999", "BTC")
            await process_group(session, group_id)
            unchanged = await load(session, group_id)
            assert unchanged is not None and unchanged.value == conflicted.value
        async with user_session(api_engine, owner) as session:
            premature = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="CANCEL",
                key=uuid4(),
                protection_id=group_id,
                payload={"expected_revision": conflicted.value.revision},
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, premature)
            assert (
                await session.execute(
                    "SELECT state FROM paper_protection_results WHERE request_id=:id",
                    {"id": premature},
                )
            ).scalar_one() == "REJECTED"
            unchanged = await load(session, group_id)
            assert unchanged is not None and unchanged.value == conflicted.value
        # Only the actual financial writer can establish the command rejection.
        await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            original = await get_order_command(session, command)
            assert original is not None and original.state == "REJECTED"
            assert original.failure_code == "ORDER_CONFLICT"
            await process_group(session, group_id)
            failed = await load(session, group_id)
            assert failed is not None and failed.value.state is ProtectionState.FAILED
            assert failed.value.conflicted
        action = "REPLACE" if correction is PositionEventKind.REPLACE else "CANCEL"
        payload: dict[str, object] = {"expected_revision": failed.value.revision}
        if action == "REPLACE":
            payload.update(quantity="0.5", tp="120", sl="90")
        async with user_session(api_engine, owner) as session:
            repair = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action=action,
                key=uuid4(),
                protection_id=group_id,
                payload=payload,
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, repair)
            repaired = await load(session, group_id)
            assert repaired is not None
            assert repaired.value.quantity == Quantity.of(
                "0.5" if action == "REPLACE" else "0", "BTC"
            )
            assert repaired.value.state is (
                ProtectionState.ARMED if action == "REPLACE" else ProtectionState.CANCELED
            )
            revision = repaired.value.revision
            assert await correct_fill(session, **arguments) is None
            await process_group(session, group_id)
            replayed = await load(session, group_id)
            assert replayed is not None and replayed.value.revision == revision
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
            cash = await get_wallet(session)
            assert cash is not None and cash.balance == Money.of(
                "9950" if action == "REPLACE" else "10000", "USDT"
            )
            assert (
                await session.execute(
                    """SELECT count(*) FROM paper_order_events e
                    JOIN paper_orders o ON o.id=e.order_id
                    WHERE o.side='SELL' AND e.event_kind='FILL'""",
                )
            ).scalar_one() == 0
    finally:
        await market.dispose()


async def lose_commit_reply(
    engine: AsyncEngine,
    owner: UUID,
    operation: Callable[[UserSession], Awaitable[None]],
) -> None:
    from tiewtrade.infra.db import InfraError

    armed, dropped = asyncio.Event(), asyncio.Event()
    async with drop_commit_reply(
        engine.url.host or "localhost", engine.url.port or 5432, armed, dropped
    ) as port:
        proxy = create_async_engine(
            engine.url.set(host="127.0.0.1", port=port),
            connect_args={"ssl": False},
            hide_parameters=True,
        )
        try:
            with pytest.raises(InfraError):
                async with user_session(proxy, owner, role=DatabaseRole.ENGINE) as session:
                    await operation(session)
                    # All effects are staged; drop only the server's COMMIT ACK.
                    armed.set()
            assert dropped.is_set()
        finally:
            await proxy.dispose()


async def test_trigger_commit_ack_loss_preserves_single_unknown_exit_identity(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        await publish_price(market, "110")

        async def trigger(session: UserSession) -> None:
            await process_group(session, group_id)

        await lose_commit_reply(engine_engine, owner, trigger)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before = await load(session, group_id)
            assert before is not None and before.value.state is ProtectionState.EXITING
            await process_group(session, group_id)
            after = await load(session, group_id)
            assert after is not None and after.value == before.value
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
            cash = await get_wallet(session)
            assert cash is not None and cash.balance == Money.of("9900", "USDT")
    finally:
        await market.dispose()


@pytest.mark.parametrize("protocol_enabled", [True, False])
async def test_legacy_financial_marker_cannot_write_while_protection_exists(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    protocol_enabled: bool,
) -> None:
    from tiewtrade.infra.db import NotPermittedError

    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text("UPDATE paper_protection_protocol SET enabled=:enabled"),
                {"enabled": protocol_enabled},
            )
        with pytest.raises(NotPermittedError) as rejected:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                current = await load(session, group_id)
                assert current is not None
                await session.execute(
                    "SELECT set_config('tiewtrade.paper_writer_version','F15_V1',true)"
                )
                # The BEFORE INSERT writer fence must reject even an otherwise
                # valid legacy row, before its duplicated identity is checked.
                await session.execute(
                    "INSERT INTO paper_orders SELECT * FROM paper_orders WHERE id=:id",
                    {"id": current.value.entry_order_id},
                )
        assert "42501" in str(rejected.value)
    finally:
        async with migrator_engine.begin() as connection:
            await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
        await market.dispose()


async def test_progress_fk_rejects_same_owner_but_different_episode(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.infra.db import InfraError

    async with user_session(api_engine, owner) as session:
        request = await admit_request(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            action="CREATE",
            key=uuid4(),
            protection_id=None,
            payload={"base": "BTC", "quantity": "0.1", "tp": "110", "sl": "90"},
        )
    with pytest.raises(InfraError) as rejected:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """INSERT INTO paper_protection_request_progress(request_id,user_id,episode_id)
                VALUES(:id,:owner,:episode)""",
                {"id": request, "owner": owner, "episode": uuid4()},
            )
    assert "23503" in str(rejected.value)


async def test_exit_commit_ack_loss_reconciles_original_claim_without_second_trade(
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
        await publish_price(market, "110")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            command = (
                await session.execute(
                    "SELECT command_id FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one()
        await execute(engine_engine, owner, command)
        await asyncio.sleep(0.23)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
            await publish_input(market_session, lease, book, metadata)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command},
                )
            ).scalar_one()
            claim = await claim_order(
                session, DueOrder(command, owner, due), worker="lost-exit-ack"
            )
            assert claim is not None

        async def fill(session: UserSession) -> None:
            await process_claimed_order(session, claim, policy=AllowPolicy())

        await lose_commit_reply(engine_engine, owner, fill)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            cash = await get_wallet(session)
            assert cash is not None and cash.balance == Money.of("9998.802099", "USDT")
            original = await get_order_command(session, command)
            assert original is not None and original.state == "SUCCEEDED"
            with pytest.raises(OrderClaimLostError):
                await process_claimed_order(session, claim, policy=AllowPolicy())
            await process_group(session, group_id)
            current = await load(session, group_id)
            assert current is not None and current.value.state is ProtectionState.CLOSED
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE episode_id=:id",
                    {"id": wallet.episode_id},
                )
            ).scalar_one() == 2
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
    finally:
        await market.dispose()


@pytest.mark.parametrize("gate", ["USER", "REMOVED"])
async def test_production_exit_survives_user_stop_or_inactive_catalog(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    gate: str,
) -> None:
    from tests.infra.execution_market.test_worker import _restore_btc_seed_catalog
    from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
    from tiewtrade.infra.trading_stops import submit_request
    from tiewtrade.infra.trading_stops.storage import current_opening_blocked
    from tiewtrade.services.engine.kill_switch import run_stop_request_round

    market, lease, book, metadata, group_id = await buy(
        api_engine, engine_engine, scan_engine, owner, wallet
    )
    removed = uuid4()
    changed_catalog = False
    try:
        if gate == "USER":
            async with user_session(api_engine, owner) as session:
                await submit_request(
                    session,
                    mode=TradingMode.PAPER,
                    action=StopAction.STOP,
                    key=uuid4(),
                    reason_code="USER_REQUEST",
                )
            await run_stop_request_round(engine=engine_engine, scan_engine=scan_engine)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert await current_opening_blocked(session, TradingMode.PAPER, OrderOrigin.BOT)
        else:
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text("""INSERT INTO supported_symbol_events
                    (revision,command_id,base,quote,status,reason_code)
                    VALUES(3,:removed,'BTC','USDT','REMOVED','F38_INITIAL_CATALOG')"""),
                    {"removed": removed},
                )
                await connection.execute(
                    text("""UPDATE supported_symbol_fences
                    SET status='REMOVED',revision=3,command_id=:removed
                    WHERE base='BTC' AND quote='USDT'"""),
                    {"removed": removed},
                )
                await connection.execute(
                    text(
                        "UPDATE supported_symbol_catalog_control SET current_revision=3 WHERE id=1"
                    )
                )
            changed_catalog = True
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            assert current is not None and current.value.state is ProtectionState.ARMED
        await publish_price(market, "110")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            command = (
                await session.execute(
                    "SELECT command_id FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one()
        await execute(engine_engine, owner, command, policy=TransactionalRiskPolicy())
        await asyncio.sleep(0.23)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
            await publish_input(market_session, lease, book, metadata)
        await execute(engine_engine, owner, command, policy=TransactionalRiskPolicy())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            current = await load(session, group_id)
            cash = await get_wallet(session)
            assert current is not None and current.value.state is ProtectionState.CLOSED
            assert cash is not None and cash.balance == Money.of("9998.802099", "USDT")
    finally:
        if changed_catalog:
            await _restore_btc_seed_catalog(migrator_engine, (removed, uuid4()))
        await market.dispose()


@pytest.mark.parametrize("first", ["request", "reset"])
async def test_reset_and_pending_protection_serialize_on_the_original_episode(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    first: str,
) -> None:
    async with user_session(api_engine, owner) as session:
        baseline = await get_wallet(session)
        assert baseline is not None and baseline.reset_available
        command = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="2000",
            expected_episode_id=wallet.episode_id,
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        claim = await claim_command(
            session, DuePaperCommand(command.command_id, owner), worker="reset-protection"
        )
        assert claim is not None
    receipts, refused = [], []

    async def reset(session: UserSession) -> None:
        await process_claimed(session, claim)

    async def request(session: UserSession) -> None:
        try:
            receipts.append(
                await admit_request(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    action="CREATE",
                    key=uuid4(),
                    protection_id=None,
                    payload={"base": "BTC", "quantity": "0.1", "tp": "110", "sl": "90"},
                )
            )
        except OrderConflictError as error:
            refused.append(error.code)

    await serialize(
        engine_engine,
        migrator_engine,
        owner,
        request if first == "request" else reset,
        reset if first == "request" else request,
    )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        current = await get_wallet(session)
        result = await get_command(session, command.command_id)
        assert current is not None and result is not None
        if first == "request":
            assert len(receipts) == 1 and not refused
            assert (
                result.state is PaperCommandState.REJECTED and result.failure_code == "RESET_UNSAFE"
            )
            assert current.episode_id == wallet.episode_id and current.balance == wallet.balance
        else:
            assert refused == ["PROTECTION_EPISODE_CLOSED"] and not receipts
            assert result.state is PaperCommandState.SUCCEEDED
            assert current.episode_id != wallet.episode_id and current.balance == Money.of(
                "2000", "USDT"
            )
        assert (await session.execute("SELECT count(*) FROM paper_protections")).scalar_one() == 0


@pytest.mark.parametrize("reverse", [False, True])
async def test_competing_allocations_serialize_without_overlap(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    reverse: bool,
) -> None:
    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    try:
        async with user_session(api_engine, owner) as session:
            original = await load(session, group_id)
            assert original is not None
            cancel = await admit_request(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                action="CANCEL",
                key=uuid4(),
                protection_id=group_id,
                payload={"expected_revision": original.value.revision},
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, cancel)
        requests = []
        for quantity in ("0.6", "0.7"):
            async with user_session(api_engine, owner) as session:
                requests.append(
                    await admit_request(
                        session,
                        wallet_id=wallet.wallet_id,
                        episode_id=wallet.episode_id,
                        action="CREATE",
                        key=uuid4(),
                        protection_id=None,
                        payload={"base": "BTC", "quantity": quantity, "tp": "110", "sl": "90"},
                    )
                )
        if reverse:
            requests.reverse()
        await publish_price(market, "100")

        async def first(session: UserSession) -> None:
            await process_request(session, requests[0])

        async def second(session: UserSession) -> None:
            await process_request(session, requests[1])

        await serialize(engine_engine, migrator_engine, owner, first, second)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            states = (
                (
                    await session.execute(
                        "SELECT state FROM paper_protection_results WHERE request_id IN (:a,:b)",
                        {"a": requests[0], "b": requests[1]},
                    )
                )
                .scalars()
                .all()
            )
            assert sorted(states) == ["APPLIED", "REJECTED"]
            current = await groups(session, wallet.episode_id, PAIR)
            assert len(current) == 1
            assert current[0].value.quantity == Quantity.of("0.7" if reverse else "0.6", "BTC")
            held, reserved = await held_and_reserved(session, wallet.episode_id, PAIR)
            assert not held < reserved + await allocated(session, wallet.episode_id, PAIR)
    finally:
        await market.dispose()


@pytest.mark.parametrize(
    "first,step", [("fill", None), ("cancel", None), ("fill", "0.01"), ("cancel", "0.01")]
)
async def test_late_entry_fill_and_cancel_race_keep_only_proven_extra_exit(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    first: str,
    step: str | None,
) -> None:
    async def due_hint(command: UUID) -> DueOrder:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            timing = (
                await session.execute(
                    """SELECT next_attempt_at,clock_timestamp() AS now
                    FROM paper_order_dispatch WHERE command_id=:id""",
                    {"id": command},
                )
            ).one()
        # Use F-15's persisted deadline, as its existing matching tests do. Do
        # not force work due or sleep while holding the owner's transaction.
        await asyncio.sleep(max(0, (timing.next_attempt_at - timing.now).total_seconds()))
        return DueOrder(command, owner, timing.next_attempt_at)

    async def execute_when_due(command: UUID) -> None:
        await due_hint(command)
        await execute(engine_engine, owner, command)

    await select_use(api_engine, owner)
    market, lease, book, metadata = await ready_public_sources()
    if step is not None:
        metadata = replace(
            metadata, market=replace(metadata.market, quantity_step=Quantity.of(step, "BTC"))
        )
    try:
        value = replace(
            intent(owner, wallet.episode_id),
            kind=OrderType.LIMIT,
            size=BaseSize(Quantity.of("2", "BTC")),
            limit_price=Money.of("90", "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        entry = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            value,
            bracket={"tp": "110", "sl": "80"},
        )
        await execute_when_due(entry)
        await asyncio.sleep(0.23)
        # F-15 must first see a post-eligibility book to establish this LIMIT's
        # resting queue. A trade alone cannot stand in for that book evidence.
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(
                book, input_id=book.input_id + 1, received_at=now, verified_at=now, rebase=False
            )
            lease = await publish_input(market_session, lease, book, metadata)
        await execute_when_due(entry)

        async def trade() -> None:
            nonlocal lease
            async with market_data_session(market) as market_session:
                now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
                tick = MarketTrade(
                    PAIR,
                    max(lease.last_input_id, book.input_id) + 1,
                    lease.generation,
                    now,
                    max(lease.last_input_id, book.input_id) + 1000,
                    ExecutionSide.BUY,
                    Money.of("90", "USDT"),
                    Quantity.of("1", "BTC"),
                    True,
                    source_at=now,
                )
                lease = await publish_input(market_session, lease, tick, metadata)

        await trade()
        await asyncio.sleep(0.035)
        await execute_when_due(entry)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            initial_groups = await groups(session, wallet.episode_id, PAIR)
            assert len(initial_groups) == 1
            assert initial_groups[0].value.quantity == Quantity.of("0.999", "BTC")
            group_id = initial_groups[0].value.protection_id
        await publish_price(market, "110")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            cancel = (
                await session.execute(
                    "SELECT id FROM paper_order_commands WHERE order_id=:id AND action='CANCEL'",
                    {"id": value.order_id},
                )
            ).scalar_one()
        await asyncio.sleep(0.23)
        await trade()
        commands = {"fill": entry, "cancel": cancel}
        second = "cancel" if first == "fill" else "fill"
        first_due = await due_hint(commands[first])
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            first_claim = await claim_order(session, first_due, worker=first)
            assert first_claim is not None
        staged, release = asyncio.Event(), asyncio.Event()

        async def first_worker() -> None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_claimed_order(session, first_claim, policy=AllowPolicy())
                staged.set()
                await release.wait()

        running = asyncio.create_task(first_worker())
        try:
            await asyncio.wait_for(staged.wait(), 5)
            second_due = await due_hint(commands[second])
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                # The actual dispatcher skips a busy owner. It cannot pre-claim
                # both commands and then wait behind the financial writer.
                assert await claim_order(session, second_due, worker=second) is None
        finally:
            release.set()
            await asyncio.wait_for(running, 5)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            second_state = (
                await session.execute(
                    "SELECT state FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": commands[second]},
                )
            ).scalar_one()
        if second_state == "TERMINAL":
            assert first == "cancel" and second == "fill"
        else:
            await execute_when_due(commands[second])
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            assert current is not None
            expected = Quantity.of("1.998" if first == "fill" else "0.999", "BTC")
            assert current.value.quantity == expected
            assert current.extra_exit == Quantity.of("0.999" if first == "fill" else "0", "BTC")
            # The first exit has no known admission outcome yet. Replaying group
            # work must not enqueue the late quantity while that exit is unknown.
            await process_group(session, group_id)
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
        exit_count = 2 if first == "fill" else 1
        for index in range(exit_count):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = (
                    await session.execute(
                        """SELECT x.command_id FROM paper_protection_exits x
                    JOIN paper_protection_exit_progress s ON s.id=x.id
                    WHERE x.protection_id=:id AND NOT s.settled""",
                        {"id": group_id},
                    )
                ).scalar_one()
            await execute_when_due(command)
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
                lease = await publish_input(market_session, lease, book, metadata)
            await execute_when_due(command)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_group(session, group_id)
                assert (
                    await session.execute(
                        "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                        {"id": group_id},
                    )
                ).scalar_one() == min(index + 2, exit_count)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            cash = await get_wallet(session)
            assert current is not None and current.value.state is (
                ProtectionState.CLOSED if step is None else ProtectionState.FAILED
            )
            remaining = "0" if step is None else "0.018" if first == "fill" else "0.009"
            assert current.value.quantity == Quantity.of(remaining, "BTC")
            assert (await held_and_reserved(session, wallet.episode_id, PAIR))[0] == Quantity.of(
                remaining, "BTC"
            )
            expected_cash = (
                ("10015.82398" if first == "fill" else "10007.91199")
                if step is not None
                else ("10017.604198" if first == "fill" else "10008.802099")
            )
            assert cash is not None and cash.balance == Money.of(expected_cash, "USDT")
    finally:
        await market.dispose()


async def publish_price(market: AsyncEngine, amount: str) -> datetime:
    async with market_data_session(market) as market_session:
        snapshot = await read_snapshot(market_session)
        assert snapshot.feed is not None
        row = next(value for value in snapshot.rows if value.base == "BTC")
        assert row.observation is not None
        observation = QuoteObservation(
            "primary_spot",
            "BTC",
            "USDT",
            Money.of(amount, "USDT"),
            row.observation.trade_id + 1,
            snapshot.server_time,
            snapshot.server_time,
            ObservationKind.STREAM,
        )
        assert await write_price(
            market_session,
            snapshot.feed,
            replace(
                row,
                observation=observation,
                reconciled_generation=snapshot.feed.generation,
                effective_readiness="READY",
                reason=None,
                unavailable_since=None,
                order_ambiguous_at=None,
            ),
        )
        return snapshot.server_time


@pytest.mark.parametrize("recovered_price", ["111", "100"])
async def test_feed_gap_requires_fresh_generation_and_real_worker_starts_within_one_second(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
    recovered_price: str,
) -> None:
    from tiewtrade.infra.protections import worker
    from tiewtrade.services.engine.paper_order_main import serve

    market, _, _, _, group_id = await buy(api_engine, engine_engine, scan_engine, owner, wallet)
    serving = None
    try:
        async with market_data_session(market) as market_session:
            snapshot = await read_snapshot(market_session)
            assert snapshot.feed is not None
            row = next(value for value in snapshot.rows if value.base == "BTC")
            assert row.observation is not None
            expired_at = snapshot.server_time - MAX_PRICE_AGE - timedelta(milliseconds=1)
            stale = replace(
                row.observation,
                amount=Money.of("111", "USDT"),
                trade_id=row.observation.trade_id + 1,
                trade_time=expired_at,
                received_at=expired_at,
            )
            assert await write_price(market_session, snapshot.feed, replace(row, observation=stale))
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            current = await load(session, group_id)
            assert current is not None and current.value.state is ProtectionState.ARMED
        async with market_data_session(market) as market_session:
            snapshot = await read_snapshot(market_session)
            assert snapshot.feed is not None
            feed = await set_connected(market_session, snapshot.feed, False)
        await publish_price(market, "111")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            current = await load(session, group_id)
            assert current is not None and current.value.state is ProtectionState.ARMED
        async with market_data_session(market) as market_session:
            feed = await begin_generation(market_session, feed)
            await set_connected(market_session, feed, True)
            snapshot = await read_snapshot(market_session)
            prior = next(value for value in snapshot.rows if value.base == "BTC")
            assert prior.observation is not None
            fresh_sequence = prior.observation.trade_id + 1
        # An old crossing observation does not become trusted after reconnect.
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            current = await load(session, group_id)
            assert current is not None and current.value.state is ProtectionState.ARMED
        started: list[datetime] = []
        first_poll, fresh_processed = asyncio.Event(), asyncio.Event()
        original = worker.market_evidence

        async def observe_start(session: UserSession, pair: PositionPair) -> TriggerEvidence:
            if session.user_id == owner:
                first_poll.set()
            evidence = await original(session, pair)
            if session.user_id == owner and evidence.sequence == fresh_sequence and not started:
                # The post-lock read completing is a conservative upper bound
                # for actual processing start, never an enqueue timestamp.
                started.append((await session.execute("SELECT clock_timestamp()")).scalar_one())
                fresh_processed.set()
            return evidence

        monkeypatch.setattr(worker, "market_evidence", observe_start)
        serving = asyncio.create_task(serve())
        await asyncio.wait_for(first_poll.wait(), 5)
        ready_at = await publish_price(market, recovered_price)
        await asyncio.wait_for(fresh_processed.wait(), 5)
        async with asyncio.timeout(5):
            while True:
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    current = await load(session, group_id)
                    assert current is not None
                    if current.observation is not None and current.observation[2] == fresh_sequence:
                        break
                await asyncio.sleep(0.005)
        assert len(started) == 1
        latency = (started[0] - ready_at).total_seconds()
        assert 0 <= latency <= 1, f"processing start latency: {latency}s"
        record_property("input_ready_to_processing_seconds", str(latency))
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            assert current is not None
            if recovered_price == "111":
                assert current.value.trigger is not None
                assert current.value.trigger.price == Money.of("111", "USDT")
            else:
                assert current.value.state is ProtectionState.ARMED
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == (1 if recovered_price == "111" else 0)
    finally:
        if serving is not None:
            serving.cancel()
            await asyncio.gather(serving, return_exceptions=True)
        await market.dispose()


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
async def test_exit_fill_kill_and_takeover_preserve_exact_cash_position_allocation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    boundary: str,
) -> None:
    market, lease, book, metadata, group_id = await buy(
        api_engine, engine_engine, scan_engine, owner, wallet
    )
    process = None
    try:
        await publish_price(market, "110")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            command = (
                await session.execute(
                    "SELECT command_id FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one()
        await execute(engine_engine, owner, command)
        await asyncio.sleep(0.23)
        # Reuse the existing real process/transaction fault harness. This owner
        # has one entry fill plus one exit fill at the commit barrier.
        child = CHILD.replace("assert links == 1", "assert links == 2")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            child,
            str(owner),
            str(command),
            boundary,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await marker(process, b"CLAIMED")
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
            lease = await publish_input(market_session, lease, book, metadata)
        assert process.stdin is not None
        process.stdin.write(b"go\n")
        await process.stdin.drain()
        await marker(process, boundary.upper().encode())
        process.kill()
        await asyncio.wait_for(process.wait(), 5)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await load(session, group_id)
            cash = await get_wallet(session)
            assert current is not None and cash is not None
            committed = boundary == "after_commit"
            assert current.value.quantity == Quantity.of("0" if committed else "0.999", "BTC")
            assert current.disposed == Quantity.of("0.999" if committed else "0", "BTC")
            assert cash.balance == Money.of("9998.802099" if committed else "9900", "USDT")
            held, reserved = await held_and_reserved(session, wallet.episode_id, PAIR)
            assert held == Quantity.of("0" if committed else "0.999", "BTC")
            assert not held < reserved
            assert (
                await session.execute(
                    """SELECT count(*) FROM audit_events WHERE owner_user_id=:owner
                AND action='PROTECTION_EVENT' AND details->>'kind'='FILL'
                AND details->>'protection_id'=:group""",
                    {"owner": owner, "group": str(group_id)},
                )
            ).scalar_one() == (2 if committed else 1)
            await session.execute(
                """UPDATE paper_order_dispatch
                SET lease_until=clock_timestamp()-interval '1 second',
                next_attempt_at=clock_timestamp() WHERE command_id=:id AND state<>'TERMINAL'""",
                {"id": command},
            )
        if boundary == "before_commit":
            async with market_data_session(market) as market_session:
                now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
                book = replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
                lease = await publish_input(market_session, lease, book, metadata)
            await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_group(session, group_id)
            current = await load(session, group_id)
            cash = await get_wallet(session)
            assert current is not None and current.value.state is ProtectionState.CLOSED
            assert current.value.quantity == Quantity.of(0, "BTC")
            assert current.disposed == Quantity.of("0.999", "BTC")
            assert cash is not None and cash.balance == Money.of("9998.802099", "USDT")
            assert (
                await session.execute(
                    """SELECT count(*) FROM audit_events WHERE owner_user_id=:owner
                AND action='PROTECTION_EVENT' AND details->>'kind'='FILL'
                AND details->>'protection_id'=:group""",
                    {"owner": owner, "group": str(group_id)},
                )
            ).scalar_one() == 2
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one() == 2
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
            revision = current.value.revision
            await process_group(session, group_id)
            replayed = await load(session, group_id)
            assert replayed is not None and replayed.value.revision == revision
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        await market.dispose()


@pytest.mark.parametrize("crossed_price", ["110", "90"])
async def test_bracket_fill_after_crossing_triggers_without_rejecting_its_net_quantity(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    crossed_price: str,
) -> None:
    await select_use(api_engine, owner)
    market, lease, book, metadata = await ready_public_sources()
    try:
        command = await transfer(
            api_engine,
            engine_engine,
            scan_engine,
            owner,
            wallet,
            intent(owner, wallet.episode_id),
            bracket={"tp": "110", "sl": "90"},
        )
        await execute(engine_engine, owner, command)
        await asyncio.sleep(0.23)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                market_session,
                lease,
                replace(
                    book,
                    input_id=book.input_id + 1,
                    received_at=now,
                    verified_at=now,
                    rebase=False,
                ),
                metadata,
            )
        # A recorded last trade crosses while the accepted entry is not yet filled.
        # The later fill must preserve its own net allocation and trigger it;
        # standalone creation-level validation must not reject this bracket.
        await publish_price(market, crossed_price)
        await asyncio.sleep(0.035)
        await execute(engine_engine, owner, command)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            rows = await groups(session, wallet.episode_id, PAIR)
            assert len(rows) == 1
            group_id = rows[0].value.protection_id
            await process_group(session, group_id)
            await process_group(session, group_id)
            after = await load(session, group_id)
            assert after is not None and after.value.state is ProtectionState.EXITING
            assert after.value.quantity == Quantity.of("0.999", "BTC")
            assert after.value.winning_leg is (
                ProtectionLeg.TAKE_PROFIT if crossed_price == "110" else ProtectionLeg.STOP_LOSS
            )
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_protection_exits WHERE protection_id=:id",
                    {"id": group_id},
                )
            ).scalar_one() == 1
            cash = await get_wallet(session)
            assert cash is not None and cash.balance == Money.of("9900", "USDT")
    finally:
        await market.dispose()
