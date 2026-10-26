"""End-to-end Paper command worker transactions against real PostgreSQL roles."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from sqlalchemy import Result, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from tests.infra.execution_market.commit_proxy import drop_commit_reply
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_storage import prepared
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel, BookState, MarketTrade
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    TimeInForce,
    TradingMode,
    standard_execution_fee,
)
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, PositionPair
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    BookLease,
    ExecutionMetadata,
    publish_input,
    renew_book_writer,
)
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    read_snapshot,
    set_connected,
    write_price,
)
from tiewtrade.infra.paper_orders.codec import execution_from_payload
from tiewtrade.infra.paper_orders.corrections import correct_fill
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    claim_order,
    get_order_command,
    submit_cancel,
    submit_order,
)
from tiewtrade.infra.paper_orders.executions import stage_correction_cash, stage_fill_cash
from tiewtrade.infra.paper_orders.initialization import (
    enable_financial_writer,
    initialize_order_source,
)
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import (
    PaperCommandState,
    PaperWalletAction,
    admit_command,
    get_wallet,
)
from tiewtrade.infra.paper_wallet import get_command as get_wallet_command
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import (
    PositionEventKind,
    PositionIntegrityError,
    PositionWriteResult,
    PositionWriteStatus,
    apply_position_event,
    initialize_position_source,
    read_position_snapshot,
)
from tiewtrade.services.engine.paper_order import run_paper_order_round
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


class FillReplayRequest(TypedDict):
    wallet_id: UUID
    episode_id: UUID
    order_event_id: UUID
    position_event_id: UUID
    fact: ExecutionFact


class CorrectionReplayRequest(TypedDict):
    wallet_id: UUID
    episode_id: UUID
    order_event_id: UUID
    correction_event_id: UUID
    supersedes_position_event_id: UUID
    kind: PositionEventKind
    fact: ExecutionFact


class AllowPolicy:
    def check(self, value: OrderIntent) -> None:
        assert value.scope.mode is TradingMode.PAPER


async def ready_public_sources() -> tuple[AsyncEngine, BookLease, BookState, ExecutionMetadata]:
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    lease, book, metadata = await prepared(market)
    async with market_data_session(market) as session:
        await publish_input(session, lease, book, metadata)
        await session.execute(
            "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
        )
        price_lease = await acquire_writer(session, uuid4())
        assert price_lease is not None
        price_lease = await set_connected(session, price_lease, True)
        snapshot = await read_snapshot(session)
        row = next(value for value in snapshot.rows if value.base == "BTC")
        now = snapshot.server_time
        quote = QuoteObservation(
            "primary_spot",
            "BTC",
            "USDT",
            book.asks[0].price,
            100,
            now,
            now,
            ObservationKind.STREAM,
        )
        assert await write_price(
            session,
            price_lease,
            replace(
                row,
                observation=quote,
                reconciled_generation=price_lease.generation,
                effective_readiness="READY",
                reason=None,
                unavailable_since=None,
                order_ambiguous_at=None,
            ),
        )
    return market, lease, book, metadata


async def test_missing_policy_rejects_without_order_or_reservation(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="missing-policy",
            policy=None,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await get_order_command(session, command.command_id)
            orders = (
                await session.execute(
                    "SELECT count(*) FROM paper_orders WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
            reserves = (
                await session.execute(
                    "SELECT count(*) FROM paper_reservations WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
        assert result is not None and result.failure_code == "ORDER_SAFETY_UNAVAILABLE"
        assert orders == reserves == 0
    finally:
        await market.dispose()


async def test_pending_order_command_blocks_wallet_reset(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(api_engine, owner) as session:
        snapshot = await get_wallet(session)
        assert snapshot is not None
        assert not snapshot.reset_available and snapshot.reset_reason == "RESET_UNSAFE"
        reset = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="2000",
            expected_episode_id=wallet.episode_id,
        )
    outcome = await run_paper_wallet_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="pending-order-reset",
    )
    assert outcome.rejected == 1
    async with user_session(api_engine, owner) as session:
        result = await get_wallet_command(session, reset.command_id)
        unchanged = await get_wallet(session)
    assert result is not None and result.state is PaperCommandState.REJECTED
    assert result.failure_code == "RESET_UNSAFE"
    assert unchanged is not None and unchanged.episode_id == wallet.episode_id


async def test_reset_and_admission_linearize_without_moving_stale_intent(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_order_source(
            session,
            wallet_id=wallet.wallet_id,
            episode_id=wallet.episode_id,
            initialization_id=uuid4(),
        )
    async with user_session(api_engine, owner) as session:
        reset = await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="2000",
            expected_episode_id=wallet.episode_id,
        )
    original_execute = UserSession.execute
    reset_holds_lock = asyncio.Event()
    admission_waiting = asyncio.Event()
    release_reset = asyncio.Event()

    async def controlled_execute(
        session: UserSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        task = asyncio.current_task()
        name = "" if task is None else task.get_name()
        if name == "reset-race-admission" and "pg_advisory_xact_lock" in statement:
            admission_waiting.set()
        result = await original_execute(session, statement, parameters)
        if (
            name == "reset-race-worker"
            and "FROM paper_wallets w LEFT JOIN" in statement
            and not reset_holds_lock.is_set()
        ):
            reset_holds_lock.set()
            await release_reset.wait()
        return result

    monkeypatch.setattr(UserSession, "execute", controlled_execute)
    reset_task = asyncio.create_task(
        run_paper_wallet_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="reset-race-worker",
        ),
        name="reset-race-worker",
    )
    await reset_holds_lock.wait()

    async def admit_stale_order() -> None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await submit_order(
                session,
                wallet_id=wallet.wallet_id,
                intent=intent(owner, wallet.episode_id),
            )

    admission_task = asyncio.create_task(admit_stale_order(), name="reset-race-admission")
    await admission_waiting.wait()
    assert not admission_task.done()
    release_reset.set()
    reset_round = await reset_task
    assert reset_round.processed == 1
    with pytest.raises(OrderConflictError):
        await admission_task

    async with user_session(api_engine, owner) as session:
        current = await get_wallet(session)
        reset_result = await get_wallet_command(session, reset.command_id)
    assert current is not None and current.sequence == 2
    assert reset_result is not None and reset_result.state is PaperCommandState.SUCCEEDED


async def test_fill_and_reset_linearize_on_the_financial_lock(
    monkeypatch: pytest.MonkeyPatch,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="fill-reset-accept",
            policy=AllowPolicy(),
        )
        await asyncio.sleep(0.12)
        async with market_data_session(market) as market_session:
            lease = await renew_book_writer(market_session, lease)
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            second = replace(
                book,
                input_id=book.input_id + 1,
                received_at=now,
                verified_at=now,
                rebase=False,
            )
            await publish_input(market_session, lease, second, metadata)
        await asyncio.sleep(0.03)
        async with user_session(api_engine, owner) as session:
            reset = await admit_command(
                session,
                action=PaperWalletAction.RESET,
                idempotency_key=uuid4(),
                capital_text="2000",
                expected_episode_id=wallet.episode_id,
            )

        original_execute = UserSession.execute
        fill_holds_lock = asyncio.Event()
        reset_waiting = asyncio.Event()
        release_fill = asyncio.Event()

        async def controlled_execute(
            session: UserSession,
            statement: str,
            parameters: Mapping[str, object] | None = None,
        ) -> Result[Any]:
            task = asyncio.current_task()
            name = "" if task is None else task.get_name()
            if name == "reset-behind-fill" and "pg_advisory_xact_lock" in statement:
                reset_waiting.set()
            result = await original_execute(session, statement, parameters)
            if name == "fill-holds-lock" and "pg_advisory_xact_lock" in statement:
                fill_holds_lock.set()
                await release_fill.wait()
            return result

        monkeypatch.setattr(UserSession, "execute", controlled_execute)
        fill_task = asyncio.create_task(
            run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="fill-holds-lock",
                policy=AllowPolicy(),
            ),
            name="fill-holds-lock",
        )
        await fill_holds_lock.wait()
        reset_task = asyncio.create_task(
            run_paper_wallet_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="reset-behind-fill",
            ),
            name="reset-behind-fill",
        )
        await reset_waiting.wait()
        assert not reset_task.done()
        release_fill.set()
        fill_round, reset_round = await asyncio.gather(fill_task, reset_task)
        assert fill_round.processed >= 1 and reset_round.rejected >= 1

        async with user_session(api_engine, owner) as session:
            current = await get_wallet(session)
            reset_result = await get_wallet_command(session, reset.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            old_cash = (
                await session.execute(
                    """SELECT sum(amount) FROM paper_wallet_ledger
                    WHERE episode_id=:episode""",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
            links = (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                    {"order": value.order_id},
                )
            ).scalar_one()
            order_result = await get_order_command(session, command.command_id)
        assert current is not None and current.episode_id == wallet.episode_id
        assert current.balance.amount == 9900
        assert reset_result is not None and reset_result.state is PaperCommandState.REJECTED
        assert reset_result.failure_code == "RESET_UNSAFE"
        assert order_result is not None and order_result.state == "SUCCEEDED"
        assert old_cash == 9900 and links == 1
    finally:
        await market.dispose()


async def test_closed_expected_episode_is_rejected_without_retry(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        async with user_session(api_engine, owner) as session:
            reset = await admit_command(
                session,
                action=PaperWalletAction.RESET,
                idempotency_key=uuid4(),
                capital_text="10000",
                expected_episode_id=wallet.episode_id,
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await enable_financial_writer(session)
            await session.execute(
                """INSERT INTO paper_wallet_episode_closures
                (episode_id,wallet_id,user_id,reset_command_id)
                VALUES(:episode,:wallet,:owner,:command)""",
                {
                    "episode": wallet.episode_id,
                    "wallet": wallet.wallet_id,
                    "owner": owner,
                    "command": reset.command_id,
                },
            )
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="closed-episode",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await get_order_command(session, command.command_id)
            dispatch = (
                await session.execute(
                    "SELECT state FROM paper_order_dispatch WHERE command_id=:command",
                    {"command": command.command_id},
                )
            ).scalar_one()
            order_count = (
                await session.execute(
                    "SELECT count(*) FROM paper_orders WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
        assert result is not None and result.failure_code == "EPISODE_CONFLICT"
        assert dispatch == "TERMINAL" and order_count == 0
    finally:
        await market.dispose()


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "second_input",
        "input_key",
        "fill_event",
        "checkpoint_event",
        "projection_revision",
        "projections",
        "reservation_revision",
        "reservations",
        "order_activity",
        "wallet_revision",
        "finish_claim",
        "pair_dispatch",
        "init_fill",
        "lost_commit_reply",
        "commit_disconnect",
    ],
)
async def test_accept_restart_fill_and_cash_are_atomic(
    monkeypatch: pytest.MonkeyPatch,
    fault: str | None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    try:
        async with market_data_session(market) as market_session:
            lease = await renew_book_writer(market_session, lease)
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(
                book,
                input_id=book.input_id + 1,
                received_at=now,
                verified_at=now,
                rebase=False,
            )
            lease = await publish_input(market_session, lease, book, metadata)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="accept",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            accepted = (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:order",
                    {"order": value.order_id},
                )
            ).scalar_one()
            evidence = (
                (
                    await session.execute(
                        """SELECT count(*) AS total,min(decision_kind) AS decision_kind
                    FROM paper_execution_inputs WHERE episode_id=:episode""",
                        {"episode": wallet.episode_id},
                    )
                )
                .mappings()
                .one()
            )
        assert accepted == "ACCEPTED"
        assert evidence["total"] == 1 and evidence["decision_kind"] == "INPUT"
        await asyncio.sleep(0.03)
        idle = await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="idle-poll",
            policy=AllowPolicy(),
        )
        assert idle.processed >= 1
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            idle_without_backoff = (
                await session.execute(
                    """SELECT state='PENDING'
                    AND next_attempt_at<clock_timestamp()+interval '500 milliseconds'
                    FROM paper_order_dispatch WHERE command_id=:command""",
                    {"command": command.command_id},
                )
            ).scalar_one()
        assert idle_without_backoff
        await asyncio.sleep(0.09)
        async with market_data_session(market) as market_session:
            lease = await renew_book_writer(market_session, lease)
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            second = replace(
                book,
                input_id=book.input_id + 1,
                received_at=now,
                verified_at=now,
                rebase=False,
            )
            lease = await publish_input(market_session, lease, second, metadata)
            third = replace(
                second,
                input_id=second.input_id + 1,
                received_at=now,
                verified_at=now,
            )
            await publish_input(market_session, lease, third, metadata)
        await asyncio.sleep(0.03)
        if fault == "commit_disconnect":
            armed, dropped = asyncio.Event(), asyncio.Event()
            original_execute = UserSession.execute

            async def arm_disconnect(
                session: UserSession,
                statement: str,
                parameters: Mapping[str, object] | None = None,
            ) -> Result[Any]:
                result = await original_execute(session, statement, parameters)
                if session.user_id == owner and "INSERT INTO paper_reservations" in statement:
                    armed.set()
                return result

            async with drop_commit_reply(
                engine_engine.url.host or "localhost",
                engine_engine.url.port or 5432,
                armed,
                dropped,
            ) as port:
                proxy_engine = create_async_engine(
                    engine_engine.url.set(host="127.0.0.1", port=port),
                    connect_args={"ssl": False},
                    hide_parameters=True,
                )
                try:
                    with monkeypatch.context() as patch:
                        patch.setattr(UserSession, "execute", arm_disconnect)
                        async with asyncio.timeout(10):
                            outcome = await run_paper_order_round(
                                engine=proxy_engine,
                                scan_engine=scan_engine,
                                worker="commit-disconnect",
                                policy=AllowPolicy(),
                            )
                    assert dropped.is_set() and outcome.deferred >= 1
                finally:
                    await proxy_engine.dispose()
        elif fault == "lost_commit_reply":
            original_begin = AsyncEngine.begin
            original_execute = UserSession.execute
            committed_connection: AsyncConnection | None = None
            reply_lost = False

            async def mark_fill_transaction(
                session: UserSession,
                statement: str,
                parameters: Mapping[str, object] | None = None,
            ) -> Result[Any]:
                nonlocal committed_connection
                result = await original_execute(session, statement, parameters)
                if session.user_id == owner and "INSERT INTO paper_reservations" in statement:
                    committed_connection = session._connection
                return result

            @asynccontextmanager
            async def lose_commit_reply(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
                nonlocal reply_lost
                async with original_begin(engine) as connection:
                    yield connection
                if connection is committed_connection and not reply_lost:
                    reply_lost = True
                    raise ConnectionResetError("injected lost commit acknowledgement")

            with monkeypatch.context() as patch:
                patch.setattr(UserSession, "execute", mark_fill_transaction)
                patch.setattr(AsyncEngine, "begin", lose_commit_reply)
                outcome = await run_paper_order_round(
                    engine=engine_engine,
                    scan_engine=scan_engine,
                    worker="lost-commit-reply",
                    policy=AllowPolicy(),
                )
            assert reply_lost and outcome.deferred >= 1
        elif fault == "init_fill":
            original_execute = UserSession.execute
            fill_written = asyncio.Event()
            init_waiting = asyncio.Event()
            release_fill = asyncio.Event()

            async def synchronize_init(
                session: UserSession,
                statement: str,
                parameters: Mapping[str, object] | None = None,
            ) -> Result[Any]:
                task = asyncio.current_task()
                name = "" if task is None else task.get_name()
                if name == "init-during-fill" and "pg_advisory_xact_lock" in statement:
                    init_waiting.set()
                result = await original_execute(session, statement, parameters)
                if (
                    session.user_id == owner
                    and name == "fill-before-init"
                    and "INSERT INTO paper_reservations" in statement
                ):
                    fill_written.set()
                    await release_fill.wait()
                return result

            async def initialize_during_fill() -> None:
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await initialize_order_source(
                        session,
                        wallet_id=wallet.wallet_id,
                        episode_id=wallet.episode_id,
                        initialization_id=uuid4(),
                    )
                    observed = await get_wallet(session)
                    assert observed is not None and observed.balance.amount == 9900
                    assert not observed.reset_available

            with monkeypatch.context() as patch:
                patch.setattr(UserSession, "execute", synchronize_init)
                tasks: list[asyncio.Task[Any]] = []
                try:
                    async with asyncio.timeout(5):
                        tasks.append(
                            asyncio.create_task(
                                run_paper_order_round(
                                    engine=engine_engine,
                                    scan_engine=scan_engine,
                                    worker="fill-before-init",
                                    policy=AllowPolicy(),
                                ),
                                name="fill-before-init",
                            )
                        )
                        await fill_written.wait()
                        tasks.append(
                            asyncio.create_task(initialize_during_fill(), name="init-during-fill")
                        )
                        await init_waiting.wait()
                        assert not tasks[-1].done()
                        release_fill.set()
                        await asyncio.gather(*tasks)
                finally:
                    release_fill.set()
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        elif fault is not None:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                before_failure = await get_wallet(session)
                assert before_failure is not None
            original_execute = UserSession.execute
            injected = False
            input_writes = 0

            async def fail_batch(
                session: UserSession,
                statement: str,
                parameters: Mapping[str, object] | None = None,
            ) -> Result[Any]:
                nonlocal injected, input_writes
                result = await original_execute(session, statement, parameters)
                if session.user_id != owner:
                    return result
                if "INSERT INTO paper_execution_inputs" in statement:
                    input_writes += 1
                matches = (
                    (
                        fault == "second_input"
                        and "INSERT INTO paper_execution_inputs" in statement
                        and input_writes == 2
                    )
                    or (
                        fault == "projections"
                        and "INSERT INTO paper_order_projections" in statement
                    )
                    or (fault == "reservations" and "INSERT INTO paper_reservations" in statement)
                    or (
                        fault == "input_key"
                        and "INSERT INTO paper_execution_input_keys" in statement
                    )
                    or (
                        fault == "fill_event"
                        and "INSERT INTO paper_order_events" in statement
                        and parameters is not None
                        and "execution" in str(parameters.get("payload", ""))
                        and "matching" not in str(parameters.get("payload", ""))
                    )
                    or (
                        fault == "checkpoint_event"
                        and "INSERT INTO paper_order_events" in statement
                        and parameters is not None
                        and parameters.get("kind") == "INPUT_APPLIED"
                    )
                    or (
                        fault == "projection_revision"
                        and "UPDATE paper_order_projections SET revision" in statement
                    )
                    or (
                        fault == "reservation_revision"
                        and "UPDATE paper_reservations SET revision" in statement
                    )
                    or (
                        fault == "order_activity"
                        and "UPDATE paper_order_activity SET source_sequence" in statement
                    )
                    or (
                        fault == "wallet_revision"
                        and "UPDATE paper_wallet_state SET revision" in statement
                    )
                    or (
                        fault == "pair_dispatch" and "UPDATE paper_order_dispatch AS d" in statement
                    )
                    or (
                        fault == "finish_claim"
                        and "UPDATE paper_order_dispatch" in statement
                        and "retry_delay" in statement
                    )
                )
                if matches and not injected:
                    injected = True
                    raise RuntimeError("injected batch failure after write")
                return result

            with monkeypatch.context() as patch:
                patch.setattr(UserSession, "execute", fail_batch)
                await run_paper_order_round(
                    engine=engine_engine,
                    scan_engine=scan_engine,
                    worker="batch-fault",
                    policy=AllowPolicy(),
                )
            assert injected
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                unchanged = await get_wallet(session)
                projection = (
                    await session.execute(
                        """SELECT p.status,p.filled_quantity,r.quote_reserved
                        FROM paper_order_projections p JOIN paper_reservations r USING(order_id)
                        WHERE p.order_id=:order""",
                        {"order": value.order_id},
                    )
                ).one()
                assert unchanged is not None and unchanged.balance.amount == 10000
                assert unchanged.revision == before_failure.revision
                assert projection.status == "ACCEPTED" and projection.filled_quantity == 0
                assert projection.quote_reserved == 100
                for table, expected in (
                    ("paper_execution_inputs", 1),
                    ("paper_execution_links", 0),
                    ("paper_wallet_ledger", 1),
                    ("paper_order_events", 1),
                ):
                    count = (
                        await session.execute(
                            f"SELECT count(*) FROM {table} WHERE episode_id=:episode",
                            {"episode": wallet.episode_id},
                        )
                    ).scalar_one()
                    assert count == expected, table
                # Advance the retry schedule only; reuse the same command and market inputs.
                await session.execute(
                    """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
                    WHERE command_id=:id""",
                    {"id": command.command_id},
                )
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="restart",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await get_order_command(session, command.command_id)
            projection = (
                await session.execute(
                    """SELECT p.status,r.quote_reserved FROM paper_order_projections p
                    JOIN paper_reservations r USING(order_id) WHERE p.order_id=:order""",
                    {"order": value.order_id},
                )
            ).one()
            current = await get_wallet(session)
            links = (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                    {"order": value.order_id},
                )
            ).scalar_one()
            evidence_count = (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_inputs WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
            input_events = (
                await session.execute(
                    """SELECT count(*) FROM paper_order_events
                    WHERE episode_id=:episode AND event_kind='INPUT_APPLIED'""",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
            mismatched_projections = (
                await session.execute(
                    """SELECT count(*) FROM paper_order_projections p
                    JOIN paper_reservations r USING(order_id)
                    JOIN paper_order_activity a ON a.episode_id=p.episode_id
                    WHERE p.episode_id=:episode AND (
                      p.revision<>r.revision OR p.revision<>a.revision
                      OR p.last_event_id IS DISTINCT FROM (
                        SELECT e.id FROM paper_order_events e WHERE e.order_id=p.order_id
                        ORDER BY e.sequence DESC LIMIT 1))""",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
        assert result is not None and result.state == "SUCCEEDED"
        assert projection.status == "FILLED" and projection.quote_reserved == 0
        assert current is not None and current.balance.amount == 9900
        assert not current.reset_available and current.reset_reason == "RESET_UNSAFE"
        assert links == 1
        assert evidence_count == 3 and input_events == 1
        assert mismatched_projections == 0
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            recovered = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        assert recovered == result

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            late_cancel = await submit_cancel(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_id=value.order_id,
                idempotency_key=uuid4(),
            )
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="cancel-after-fill",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            late_result = await get_order_command(session, late_cancel.command_id)
        assert late_result is not None and late_result.snapshot == {
            "order_id": str(value.order_id),
            "status": "FILLED",
        }

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            linked = (
                (
                    await session.execute(
                        """SELECT l.position_event_id,l.order_event_id,e.payload
                        FROM paper_execution_links l JOIN paper_order_events e
                          ON e.id=l.order_event_id
                        WHERE l.order_id=:order AND l.position_event_kind='RECORD'""",
                        {"order": value.order_id},
                    )
                )
                .mappings()
                .one()
            )
            original = execution_from_payload(linked["payload"]["execution"])
            replacement_quantity = original.gross_quantity.__class__.of("0.5", "BTC")
            replacement_quote = original.quote_amount.__class__.of("50", "USDT")
            replacement = ExecutionFact(
                original.execution_id,
                original.pair,
                original.side,
                replacement_quantity,
                replacement_quote,
                standard_execution_fee(original.side, replacement_quantity, replacement_quote),
                original.source_sequence,
                original.occurred_at,
            )
            correction_id = uuid4()
            corrected = await correct_fill(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_event_id=linked["order_event_id"],
                correction_event_id=correction_id,
                supersedes_position_event_id=linked["position_event_id"],
                kind=PositionEventKind.REPLACE,
                fact=replacement,
            )
        assert corrected is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            replay = await correct_fill(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_event_id=linked["order_event_id"],
                correction_event_id=correction_id,
                supersedes_position_event_id=linked["position_event_id"],
                kind=PositionEventKind.REPLACE,
                fact=replacement,
            )
            corrected_projection = (
                await session.execute(
                    """SELECT status,filled_quantity FROM paper_order_projections
                    WHERE order_id=:order""",
                    {"order": value.order_id},
                )
            ).one()
            corrected_wallet = await get_wallet(session)
            correction_cash = (
                await session.execute(
                    """SELECT count(*) FROM paper_wallet_ledger
                    WHERE episode_id=:episode AND kind='CORRECTION_CASH'""",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
        assert replay is None
        assert corrected_projection.status == "CANCELED"
        assert str(corrected_projection.filled_quantity) == "0.5"
        assert corrected_wallet is not None and corrected_wallet.balance.amount == 9950
        assert correction_cash == 1

        void_id = uuid4()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            voided = await correct_fill(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_event_id=linked["order_event_id"],
                correction_event_id=void_id,
                supersedes_position_event_id=correction_id,
                kind=PositionEventKind.VOID,
                fact=replacement,
            )
        assert voided is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            void_replay = await correct_fill(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_event_id=linked["order_event_id"],
                correction_event_id=void_id,
                supersedes_position_event_id=correction_id,
                kind=PositionEventKind.VOID,
                fact=replacement,
            )
            void_projection = (
                await session.execute(
                    """SELECT status,filled_quantity FROM paper_order_projections
                    WHERE order_id=:order""",
                    {"order": value.order_id},
                )
            ).one()
            void_wallet = await get_wallet(session)
            correction_cash = (
                await session.execute(
                    """SELECT count(*) FROM paper_wallet_ledger
                    WHERE episode_id=:episode AND kind='CORRECTION_CASH'""",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
        assert void_replay is None
        assert void_projection.status == "CANCELED" and void_projection.filled_quantity == 0
        assert void_wallet is not None and void_wallet.balance.amount == 10000
        assert correction_cash == 2

        # A lost acknowledgement may be retried after the now-idle episode is reset.
        async with user_session(api_engine, owner) as session:
            reset = await admit_command(
                session,
                action=PaperWalletAction.RESET,
                idempotency_key=uuid4(),
                capital_text="2500",
                expected_episode_id=wallet.episode_id,
            )
        await run_paper_wallet_round(
            engine=engine_engine, scan_engine=scan_engine, worker="reset-before-position-replay"
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            reset_result = await get_wallet_command(session, reset.command_id)
            current = await get_wallet(session)
            old_position = await read_position_snapshot(session, wallet.episode_id)
            assert reset_result is not None and reset_result.state is PaperCommandState.SUCCEEDED
            assert current is not None and current.episode_id != wallet.episode_id
            assert old_position is not None
            new_position = await read_position_snapshot(session, current.episode_id)
            ledger = (await session.execute("SELECT * FROM paper_wallet_ledger ORDER BY id")).all()
            audits = (await session.execute("SELECT id FROM audit_events ORDER BY id")).all()
            history = {}
            for table in (
                "paper_position_events",
                "paper_position_external_fees",
                "paper_position_conflicts",
                "paper_execution_links",
                "paper_order_events",
                "paper_order_projections",
                "paper_order_activity",
                "paper_reservations",
            ):
                history[table] = (
                    await session.execute(f"SELECT * FROM {table} ORDER BY to_jsonb({table})::text")
                ).all()

        fill_request: FillReplayRequest = {
            "wallet_id": wallet.wallet_id,
            "episode_id": wallet.episode_id,
            "order_event_id": UUID(str(linked["order_event_id"])),
            "position_event_id": UUID(str(linked["position_event_id"])),
            "fact": original,
        }
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            replayed_fill = await stage_fill_cash(session, **fill_request)
            assert replayed_fill.status is PositionWriteStatus.REPLAYED
            assert replayed_fill.effects is None

        for kind, correction, linked_predecessor in (
            (PositionEventKind.REPLACE, correction_id, UUID(str(linked["position_event_id"]))),
            (PositionEventKind.VOID, void_id, correction_id),
        ):
            request: CorrectionReplayRequest = {
                "wallet_id": wallet.wallet_id,
                "episode_id": wallet.episode_id,
                "order_event_id": UUID(str(linked["order_event_id"])),
                "correction_event_id": correction,
                "supersedes_position_event_id": linked_predecessor,
                "kind": kind,
                "fact": replacement,
            }
            for writer in (stage_correction_cash, correct_fill):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    replayed = await writer(session, **request)
                    if writer is correct_fill:
                        assert replayed is None
                    else:
                        assert isinstance(replayed, PositionWriteResult)
                        assert replayed.status is PositionWriteStatus.REPLAYED
                        assert replayed.effects is None
                invalid_corrections: tuple[CorrectionReplayRequest, ...] = (
                    {**request, "wallet_id": uuid4()},
                    {**request, "episode_id": current.episode_id},
                    {**request, "order_event_id": uuid4()},
                    {**request, "correction_event_id": uuid4()},
                    {**request, "supersedes_position_event_id": uuid4()},
                    {**request, "fact": replace(replacement, execution_id=uuid4())},
                )
                for invalid_correction in invalid_corrections:
                    with pytest.raises((OrderConflictError, PositionIntegrityError)):
                        async with user_session(
                            engine_engine, owner, role=DatabaseRole.ENGINE
                        ) as session:
                            await writer(session, **invalid_correction)
                with pytest.raises(OrderConflictError):
                    async with user_session(
                        engine_engine, uuid4(), role=DatabaseRole.ENGINE
                    ) as session:
                        await writer(session, **request)
        invalid_fills: tuple[FillReplayRequest, ...] = (
            {**fill_request, "wallet_id": uuid4()},
            {**fill_request, "episode_id": current.episode_id},
            {**fill_request, "order_event_id": uuid4()},
            {**fill_request, "position_event_id": uuid4()},
            {**fill_request, "fact": replacement},
        )
        for invalid_fill in invalid_fills:
            with pytest.raises(OrderConflictError):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await stage_fill_cash(session, **invalid_fill)
        with pytest.raises(OrderConflictError):
            async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
                await stage_fill_cash(session, **fill_request)

        for kind, event_id, fact, predecessor in (
            (PositionEventKind.RECORD, UUID(str(linked["position_event_id"])), original, None),
            (PositionEventKind.RECORD, uuid4(), original, None),
            (
                PositionEventKind.REPLACE,
                correction_id,
                replacement,
                UUID(str(linked["position_event_id"])),
            ),
            (PositionEventKind.VOID, void_id, replacement, correction_id),
        ):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                retried = await apply_position_event(
                    session, wallet.episode_id, event_id, kind, fact, predecessor
                )
                assert retried.status is PositionWriteStatus.REPLAYED
                assert retried.effects is None
                assert retried.activity == old_position.activity

        for kind, event_id, fact, predecessor in (
            (PositionEventKind.RECORD, uuid4(), replace(original, execution_id=uuid4()), None),
            (PositionEventKind.RECORD, UUID(str(linked["position_event_id"])), replacement, None),
            (PositionEventKind.REPLACE, uuid4(), replacement, void_id),
        ):
            with pytest.raises(PositionIntegrityError):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await apply_position_event(
                        session, wallet.episode_id, event_id, kind, fact, predecessor
                    )
        with pytest.raises(PositionIntegrityError):
            async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
                await apply_position_event(
                    session,
                    wallet.episode_id,
                    UUID(str(linked["position_event_id"])),
                    PositionEventKind.RECORD,
                    original,
                )
        with pytest.raises(PositionIntegrityError):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                assert old_position.activity.source_proof is not None
                await initialize_position_source(
                    session, wallet.episode_id, uuid4(), old_position.activity.source_proof
                )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            after = await get_wallet(session)
            old_after = await read_position_snapshot(session, wallet.episode_id)
            new_after = await read_position_snapshot(session, current.episode_id)
            assert after is not None
            assert (after.episode_id, after.balance, after.revision) == (
                current.episode_id,
                Money.of("2500", "USDT"),
                current.revision,
            )
            assert old_after is not None and old_after.activity == old_position.activity
            assert old_after.positions == old_position.positions
            assert new_after is not None and new_position is not None
            assert new_after.activity == new_position.activity
            assert new_after.positions == new_position.positions
            assert (
                await session.execute("SELECT * FROM paper_wallet_ledger ORDER BY id")
            ).all() == ledger
            assert (
                await session.execute("SELECT id FROM audit_events ORDER BY id")
            ).all() == audits
            for table, rows in history.items():
                assert (
                    await session.execute(f"SELECT * FROM {table} ORDER BY to_jsonb({table})::text")
                ).all() == rows
    finally:
        await market.dispose()


async def test_new_command_is_not_starved_by_an_active_order(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()

    def resting_order() -> OrderIntent:
        return OrderIntent(
            uuid4(),
            uuid4(),
            OrderScope(owner, UUID(str(wallet.episode_id)), TradingMode.PAPER),
            PositionPair("BTC", "USDT"),
            OrderOrigin.MANUAL,
            ExecutionSide.BUY,
            OrderType.LIMIT,
            BaseSize(Quantity.of(1, "BTC")),
            Money.of(90, "USDT"),
            TimeInForce.GTC,
        )

    first = resting_order()
    second = resting_order()
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            first_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=first)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="first-active",
            policy=AllowPolicy(),
        )
        await asyncio.sleep(0.03)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            second_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=second)
        # The overdue active order keeps its turn; the next scan admits the new command.
        for index in range(2):
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=f"new-command-{index}",
                policy=AllowPolicy(),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            first_result = await get_order_command(session, first_command.command_id)
            second_result = await get_order_command(session, second_command.command_id)
            statuses = (
                await session.execute(
                    """SELECT order_id,status FROM paper_order_projections
                    WHERE order_id IN (:first,:second)""",
                    {"first": first.order_id, "second": second.order_id},
                )
            ).all()
        assert first_result is not None and first_result.failure_code is None
        assert second_result is not None and second_result.failure_code is None
        assert {row.order_id: row.status for row in statuses} == {
            first.order_id: "ACCEPTED",
            second.order_id: "ACCEPTED",
        }
    finally:
        await market.dispose()


async def test_catalog_removal_rejects_queued_buy_and_cancels_resting_buy(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()
    resting = OrderIntent(
        uuid4(),
        uuid4(),
        OrderScope(owner, UUID(str(wallet.episode_id)), TradingMode.PAPER),
        PositionPair("BTC", "USDT"),
        OrderOrigin.MANUAL,
        ExecutionSide.BUY,
        OrderType.LIMIT,
        BaseSize(Quantity.of(1, "BTC")),
        Money.of(90, "USDT"),
        TimeInForce.GTC,
    )
    queued = replace(resting, order_id=uuid4(), idempotency_key=uuid4())
    catalog_events: tuple[UUID, UUID] | None = None
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            resting_command = await submit_order(
                session, wallet_id=wallet.wallet_id, intent=resting
            )
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="catalog-resting-admit",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            queued_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=queued)
            revisions = (
                (
                    await session.execute(
                        "SELECT payload->>'catalog_revision' FROM paper_order_commands "
                        "WHERE id IN (:resting,:queued) ORDER BY id",
                        {
                            "resting": resting_command.command_id,
                            "queued": queued_command.command_id,
                        },
                    )
                )
                .scalars()
                .all()
            )
            assert revisions and all(int(value) >= 2 for value in revisions)

        # The pair is active again before the worker resumes. Commands admitted
        # before the intervening removal must still be terminally rejected/canceled.
        catalog_events = await _simulate_btc_remove_and_readd(migrator_engine)
        await asyncio.sleep(0.22)
        for index in range(3):
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=f"catalog-removal-{index}",
                policy=AllowPolicy(),
            )

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            resting_result = await get_order_command(session, resting_command.command_id)
            queued_result = await get_order_command(session, queued_command.command_id)
            projection = (
                await session.execute(
                    "SELECT status,filled_quantity FROM paper_order_projections "
                    "WHERE order_id=:order",
                    {"order": resting.order_id},
                )
            ).one()
            canceled = (
                await session.execute(
                    "SELECT count(*) FROM paper_order_events "
                    "WHERE order_id=:order AND event_kind='CANCELED'",
                    {"order": resting.order_id},
                )
            ).scalar_one()
            current = await get_wallet(session)
        assert resting_result is not None and resting_result.state == "SUCCEEDED"
        assert queued_result is not None
        assert queued_result.failure_code == "CATALOG_PAIR_REMOVED"
        assert projection.status == "CANCELED" and projection.filled_quantity == 0
        assert canceled == 1
        assert current is not None and current.balance == wallet.balance
    finally:
        if catalog_events is not None:
            await _restore_btc_seed_catalog(migrator_engine, catalog_events)
        await market.dispose()


async def test_new_buy_cannot_match_an_old_buy_after_catalog_readd(
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    old = OrderIntent(
        uuid4(),
        uuid4(),
        OrderScope(owner, UUID(str(wallet.episode_id)), TradingMode.PAPER),
        PositionPair("BTC", "USDT"),
        OrderOrigin.MANUAL,
        ExecutionSide.BUY,
        OrderType.LIMIT,
        BaseSize(Quantity.of(1, "BTC")),
        Money.of(90, "USDT"),
        TimeInForce.GTC,
    )
    events: tuple[UUID, UUID] | None = None

    async def process(command_id: UUID) -> None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due_at = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": command_id},
                )
            ).scalar_one()
            claim = await claim_order(
                session, DueOrder(command_id, owner, due_at), worker="catalog-readd-regression"
            )
            assert claim is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, claim, policy=AllowPolicy())

    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            old_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=old)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(book, input_id=book.input_id + 1, received_at=now, verified_at=now)
            lease = await publish_input(market_session, lease, book, metadata)
        await process(old_command.command_id)
        await asyncio.sleep(0.22)
        events = await _simulate_btc_remove_and_readd(migrator_engine)
        new = replace(
            old, order_id=uuid4(), idempotency_key=uuid4(), limit_price=Money.of(110, "USDT")
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=new)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            book = replace(
                book, input_id=book.input_id + 1, received_at=now, verified_at=now, rebase=False
            )
            lease = await publish_input(market_session, lease, book, metadata)
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            lease = await publish_input(
                market_session,
                lease,
                MarketTrade(
                    old.pair,
                    book.input_id + 1,
                    book.generation,
                    now,
                    101,
                    ExecutionSide.BUY,
                    Money.of(90, "USDT"),
                    Quantity.of(1, "BTC"),
                    True,
                ),
                metadata,
            )
        # This trade could fill the old resting BUY. Only the new command gets a turn.
        await process(command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": old.order_id},
                )
            ).scalar_one() == "CANCELED"
            current = await get_wallet(session)
            assert current is not None and current.balance == wallet.balance
        await asyncio.sleep(0.22)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                market_session,
                lease,
                replace(
                    book,
                    input_id=book.input_id + 2,
                    received_at=now,
                    verified_at=now,
                    rebase=False,
                    bids=(BookLevel(Money.of(88, "USDT"), Quantity.of(10, "BTC")),),
                    asks=(BookLevel(Money.of(89, "USDT"), Quantity.of(10, "BTC")),),
                ),
                metadata,
            )
        await process(command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            rows = (
                await session.execute(
                    """SELECT order_id,status,filled_quantity FROM paper_order_projections
                    WHERE episode_id=:episode""",
                    {"episode": wallet.episode_id},
                )
            ).all()
            current = await get_wallet(session)
            positions = await read_position_snapshot(session, UUID(str(wallet.episode_id)))
        assert {row.order_id: (row.status, row.filled_quantity) for row in rows} == {
            old.order_id: ("CANCELED", 0),
            new.order_id: ("FILLED", 1),
        }
        assert positions is not None
        assert next(
            p.held_quantity for p in positions.positions if p.pair == old.pair
        ) == Quantity.of("0.999", "BTC")
        assert current is not None and current.balance == wallet.balance - Money.of(89, "USDT")
    finally:
        if events is not None:
            await _restore_btc_seed_catalog(migrator_engine, events)
        await market.dispose()


async def _simulate_btc_remove_and_readd(engine: AsyncEngine) -> tuple[UUID, UUID]:
    removed_command, active_command = uuid4(), uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """INSERT INTO supported_symbol_events(
                revision,command_id,base,quote,status,reason_code)
                VALUES(3,:removed,'BTC','USDT','REMOVED','F38_INITIAL_CATALOG'),
                  (4,:active,'BTC','USDT','ACTIVE','F38_INITIAL_CATALOG')"""
            ),
            {"removed": removed_command, "active": active_command},
        )
        await connection.execute(
            text(
                "UPDATE supported_symbol_fences SET status='ACTIVE',revision=4,"
                "command_id=:active WHERE base='BTC' AND quote='USDT'"
            ),
            {"active": active_command},
        )
        await connection.execute(
            text("UPDATE supported_symbol_catalog_control SET current_revision=4 WHERE id=1")
        )
    return removed_command, active_command


async def _restore_btc_seed_catalog(engine: AsyncEngine, commands: tuple[UUID, UUID]) -> None:
    async with engine.begin() as connection:
        for table in (
            "supported_symbol_events",
            "supported_symbol_fences",
            "supported_symbol_catalog_control",
        ):
            await connection.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER USER"))
        try:
            await connection.execute(
                text(
                    "UPDATE supported_symbol_fences SET status='ACTIVE',revision=1,"
                    "command_id='00000000-0000-0000-0000-000000000001' "
                    "WHERE base='BTC' AND quote='USDT'"
                )
            )
            await connection.execute(
                text("UPDATE supported_symbol_catalog_control SET current_revision=2 WHERE id=1")
            )
            await connection.execute(
                text("DELETE FROM supported_symbol_events WHERE command_id IN (:removed,:active)"),
                {"removed": commands[0], "active": commands[1]},
            )
        finally:
            for table in reversed(
                (
                    "supported_symbol_events",
                    "supported_symbol_fences",
                    "supported_symbol_catalog_control",
                )
            ):
                await connection.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER USER"))


async def test_downstream_position_conflict_is_durable_without_partial_fill(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="conflict-accept",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            before_conflict = await get_wallet(session)
        assert before_conflict is not None and before_conflict.balance == wallet.balance
        predicted_execution = uuid5(
            NAMESPACE_URL,
            f"tiewtrade:paper:{wallet.episode_id}:fill:BTC:USDT:"
            f"{lease.generation}:{book.input_id + 1}:0",
        )
        injected = ExecutionFact(
            predicted_execution,
            value.pair,
            value.side,
            Quantity.of("0.25", value.pair.base),
            Money.of("25", value.pair.quote),
            standard_execution_fee(
                value.side,
                Quantity.of("0.25", value.pair.base),
                Money.of("25", value.pair.quote),
            ),
            1,
            datetime.now(UTC),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await enable_financial_writer(session)
            await apply_position_event(
                session,
                wallet.episode_id,
                uuid4(),
                PositionEventKind.RECORD,
                injected,
            )
        await asyncio.sleep(0.12)
        async with market_data_session(market) as session:
            lease = await renew_book_writer(session, lease)
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                session,
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
        await asyncio.sleep(0.03)
        result = await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="conflict-fill",
            policy=AllowPolicy(),
        )
        assert result.processed >= 1 and result.deferred == 0
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            order_result = await get_order_command(session, command.command_id)
            snapshot = await get_wallet(session)
            row = (
                await session.execute(
                    """SELECT a.availability,d.state,
                    (SELECT count(*) FROM paper_position_conflicts
                     WHERE episode_id=:episode) AS conflicts,
                    (SELECT count(*) FROM paper_order_events
                     WHERE order_id=:order AND event_kind='FILL') AS fills,
                    (SELECT count(*) FROM paper_wallet_ledger
                     WHERE episode_id=:episode AND kind='TRADE_CASH') AS cash,
                    (SELECT count(*) FROM audit_events
                     WHERE owner_user_id=:owner AND action='PAPER_POSITION_CONFLICTED'
                    ) AS conflict_audits
                    FROM paper_order_activity a JOIN paper_order_dispatch d
                      ON d.command_id=:command WHERE a.episode_id=:episode""",
                    {
                        "episode": wallet.episode_id,
                        "order": value.order_id,
                        "owner": owner,
                        "command": command.command_id,
                    },
                )
            ).one()
        assert order_result is not None and order_result.state == "SUCCEEDED"
        assert snapshot is not None and snapshot.balance == wallet.balance
        assert row.availability == "CONFLICTED" and row.state == "TERMINAL"
        assert row.conflicts == row.conflict_audits == 1
        assert row.fills == row.cash == 0
    finally:
        await market.dispose()


@pytest.mark.parametrize("via_manual_inbox", [False, True])
async def test_market_order_crossing_levels_links_every_fill_once(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    via_manual_inbox: bool,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    value = replace(intent(owner, wallet.episode_id), size=QuoteBudget(Money.of(1100, "USDT")))
    try:
        if via_manual_inbox:
            from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
            from tiewtrade.infra.paper_orders.request_worker import process_request
            from tiewtrade.infra.paper_orders.requests import admit_new_request
            from tiewtrade.infra.paper_orders.views import request_view

            async with user_session(api_engine, owner) as session:
                await session.execute(
                    "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                    {"owner": owner},
                )
                receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                due_at = (
                    await session.execute(
                        "SELECT next_attempt_at FROM paper_order_request_dispatch "
                        "WHERE request_id=:id",
                        {"id": receipt.request_id},
                    )
                ).scalar_one()
                claim = await claim_request(
                    session, DueRequest(receipt.request_id, owner, due_at), worker="parity-bridge"
                )
                assert claim is not None
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, claim, policy=AllowPolicy())
                view = await request_view(session, receipt.request_id)
                assert view is not None and view.command_id is not None
                linked = await get_order_command(session, view.command_id)
                assert linked is not None
                command = linked
        else:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="multi-level-accept",
            policy=AllowPolicy(),
        )
        await asyncio.sleep(0.12)
        async with market_data_session(market) as session:
            lease = await renew_book_writer(session, lease)
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                session,
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
        await asyncio.sleep(0.03)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="multi-level-fill",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await get_order_command(session, command.command_id)
            projection = (
                await session.execute(
                    """SELECT status,filled_quantity,spent FROM paper_order_projections
                    WHERE order_id=:order""",
                    {"order": value.order_id},
                )
            ).one()
            links = (
                await session.execute(
                    "SELECT count(*) FROM paper_execution_links WHERE order_id=:order",
                    {"order": value.order_id},
                )
            ).scalar_one()
            current = await get_wallet(session)
        assert result is not None and result.state == "SUCCEEDED"
        assert projection.status == "FILLED"
        assert Quantity.of(projection.filled_quantity, "BTC") == Quantity.of("10.5", "BTC")
        assert Money.of(projection.spent, "USDT") == Money.of(1100, "USDT")
        assert links == 2
        assert current is not None and current.balance.amount == 8900
    finally:
        await market.dispose()


async def test_cancel_before_next_input_releases_remaining_reservation(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()
    value = intent(owner, wallet.episode_id)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="accept-before-cancel",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            cancellation = await submit_cancel(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_id=value.order_id,
                idempotency_key=uuid4(),
            )
        await asyncio.sleep(0.03)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="old-order-first",
            policy=AllowPolicy(),
        )
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="cancel",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await get_order_command(session, cancellation.command_id)
            projection = (
                await session.execute(
                    """SELECT p.status,r.quote_reserved FROM paper_order_projections p
                    JOIN paper_reservations r USING(order_id) WHERE p.order_id=:order""",
                    {"order": value.order_id},
                )
            ).one()
        assert result is not None and result.state == "SUCCEEDED"
        assert projection.status == "CANCELED" and projection.quote_reserved == 0
    finally:
        await market.dispose()


async def test_duplicate_order_identity_is_terminal_and_does_not_block_cancel(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()
    original = intent(owner, wallet.episode_id)
    try:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await submit_order(session, wallet_id=wallet.wallet_id, intent=original)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="duplicate-original",
            policy=AllowPolicy(),
        )

        duplicate = replace(original, idempotency_key=uuid4())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            duplicate_command = await submit_order(
                session, wallet_id=wallet.wallet_id, intent=duplicate
            )
        for worker in ("duplicate-original-poll", "duplicate-reject"):
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=worker,
                policy=AllowPolicy(),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            duplicate_result = await get_order_command(session, duplicate_command.command_id)
            cancellation = await submit_cancel(
                session,
                wallet_id=wallet.wallet_id,
                episode_id=wallet.episode_id,
                order_id=original.order_id,
                idempotency_key=uuid4(),
            )
        assert duplicate_result is not None
        assert duplicate_result.state == "REJECTED"
        assert duplicate_result.failure_code == "ORDER_CONFLICT"

        await asyncio.sleep(0.03)
        for worker in ("duplicate-original-drain", "duplicate-cancel"):
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=worker,
                policy=AllowPolicy(),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            cancel_result = await get_order_command(session, cancellation.command_id)
            projection = (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:order",
                    {"order": original.order_id},
                )
            ).one()
        assert cancel_result is not None and cancel_result.state == "SUCCEEDED"
        assert projection.status == "CANCELED"

        terminal_duplicate = replace(original, idempotency_key=uuid4())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            terminal_command = await submit_order(
                session, wallet_id=wallet.wallet_id, intent=terminal_duplicate
            )
        for worker in ("canceled-original-drain", "terminal-duplicate-reject"):
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker=worker,
                policy=AllowPolicy(),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            terminal_result = await get_order_command(session, terminal_command.command_id)
        assert terminal_result is not None
        assert terminal_result.state == "REJECTED"
        assert terminal_result.failure_code == "ORDER_CONFLICT"
    finally:
        await market.dispose()


@pytest.mark.parametrize("side", [ExecutionSide.BUY, ExecutionSide.SELL])
async def test_two_orders_cannot_reserve_the_same_available_funds(
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    side: ExecutionSide,
) -> None:
    market, lease, book, metadata = await ready_public_sources()
    selling = side is ExecutionSide.SELL
    first = replace(
        intent(owner, wallet.episode_id),
        side=side,
        kind=OrderType.LIMIT,
        size=BaseSize(Quantity.of("0.6" if selling else "61", "BTC")),
        limit_price=Money.of(110 if selling else 99, "USDT"),
        time_in_force=TimeInForce.GTC,
    )
    second = replace(
        intent(owner, wallet.episode_id),
        side=side,
        kind=OrderType.LIMIT,
        size=BaseSize(Quantity.of("0.6" if selling else "61", "BTC")),
        limit_price=Money.of(110 if selling else 99, "USDT"),
        time_in_force=TimeInForce.GTC,
    )
    try:
        if selling:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await submit_order(
                    session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
                )
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="seed-buy-admit",
                policy=AllowPolicy(),
            )
            await asyncio.sleep(0.12)
            async with market_data_session(market) as session:
                lease = await renew_book_writer(session, lease)
                now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                book = replace(
                    book, input_id=book.input_id + 1, received_at=now, verified_at=now, rebase=False
                )
                lease = await publish_input(session, lease, book, metadata)
            await run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="seed-buy-fill",
                policy=AllowPolicy(),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            first_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=first)
            second_command = await submit_order(session, wallet_id=wallet.wallet_id, intent=second)
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="first-reservation",
            policy=AllowPolicy(),
        )
        await asyncio.sleep(0.12)
        async with market_data_session(market) as session:
            lease = await renew_book_writer(session, lease)
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                session,
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
        await asyncio.gather(
            run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="reserve-race-a",
                policy=AllowPolicy(),
            ),
            run_paper_order_round(
                engine=engine_engine,
                scan_engine=scan_engine,
                worker="reserve-race-b",
                policy=AllowPolicy(),
            ),
        )
        await run_paper_order_round(
            engine=engine_engine,
            scan_engine=scan_engine,
            worker="reserve-race-drain",
            policy=AllowPolicy(),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            outcomes = (
                await get_order_command(session, first_command.command_id),
                await get_order_command(session, second_command.command_id),
            )
            order_count = (
                await session.execute(
                    "SELECT count(*) FROM paper_orders WHERE episode_id=:episode",
                    {"episode": wallet.episode_id},
                )
            ).scalar_one()
            reserved = (
                await session.execute(
                    """SELECT sum(quote_reserved) AS quote,sum(base_reserved) AS base
                    FROM paper_reservations WHERE episode_id=:episode""",
                    {"episode": wallet.episode_id},
                )
            ).one()
        assert all(value is not None for value in outcomes)
        assert {value.failure_code for value in outcomes if value is not None} == {
            None,
            "ORDER_INSUFFICIENT_FUNDS",
        }
        assert order_count == (2 if selling else 1)
        assert reserved.quote == (0 if selling else 6039)
        assert reserved.base == Quantity.of("0.6" if selling else "0", "BTC").amount
    finally:
        await market.dispose()
