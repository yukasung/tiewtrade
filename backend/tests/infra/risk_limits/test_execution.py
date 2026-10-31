"""F18 risk composition through real F15 matching, cash and cancellation transactions."""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Any, NoReturn
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _failed_upgrade_or_downgrade
from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import ready_public_sources
from tests.infra.risk_limits.test_requests import submission
from tests.infra.risk_limits.test_worker import claim
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookState
from tiewtrade.core.orders import BaseSize, QuoteBudget
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    BookLease,
    ExecutionMetadata,
    publish_input,
    renew_book_writer,
)
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, renew_writer, write_price
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order, submit_order
from tiewtrade.infra.paper_orders.matching_storage import load_order_state
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.infra.risk_limits.stops import consume_stop
from tiewtrade.infra.risk_limits.storage import process_request


@dataclass
class Runtime:
    market: AsyncEngine
    lease: BookLease
    book: BookState
    metadata: ExecutionMetadata

    async def next_book(self) -> None:
        async with market_data_session(self.market) as session:
            self.lease = await renew_book_writer(session, self.lease)
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            self.book = replace(
                self.book,
                input_id=self.book.input_id + 1,
                received_at=now,
                verified_at=now,
                rebase=False,
            )
            self.lease = await publish_input(session, self.lease, self.book, self.metadata)

    async def price(self, amount: str) -> None:
        async with market_data_session(self.market) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.feed is not None
            lease = await renew_writer(session, snapshot.feed)
            row = next(price for price in snapshot.rows if price.base == "BTC")
            assert row.observation is not None
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            observation = QuoteObservation(
                "primary_spot",
                "BTC",
                "USDT",
                Money.of(amount, "USDT"),
                row.observation.trade_id + 1,
                now,
                now,
                ObservationKind.STREAM,
            )
            await write_price(
                session,
                lease,
                replace(
                    row,
                    observation=observation,
                    reconciled_generation=lease.generation,
                    effective_readiness="READY",
                    reason=None,
                ),
            )


@asynccontextmanager
async def runtime(
    api: AsyncEngine,
    engine: AsyncEngine,
    migrator: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    *,
    limit: str | None = "0.01",
    account_use: str = "MANUAL",
) -> AsyncIterator[Runtime]:
    market, lease, book, metadata = await ready_public_sources()
    try:
        async with user_session(api, owner) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,:use)",
                {"owner": owner, "use": account_use},
            )
        async with migrator.begin() as connection:
            await connection.execute(
                text("""UPDATE risk_protocol_control SET publication_enabled=true,
              financial_enabled=true,admission_enabled=true""")
            )
        async with market_data_session(market) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.feed is not None
            await renew_writer(session, snapshot.feed)
        if limit is not None:
            async with user_session(api, owner) as session:
                receipt = await submit_request(
                    session, replace(submission(owner, wallet), amount=Money.of(limit, "USDT"))
                )
            token = await claim(engine, owner, receipt)
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, token)
        yield Runtime(market, lease, book, metadata)
    finally:
        async with migrator.begin() as connection:
            await connection.execute(
                text("""UPDATE risk_protocol_control SET admission_enabled=false,
              financial_enabled=false,publication_enabled=false""")
            )
        await market.dispose()


async def test_matching_reloads_a_limit_created_after_an_unset_intake(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    policy = TransactionalRiskPolicy()
    value = intent(owner, wallet.episode_id)
    async with runtime(api_engine, engine_engine, migrator_engine, owner, wallet, limit=None):
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            unset = await policy.execution_context(session, value)
        assert unset.setting.limit is None and unset.source_ready

        async with user_session(api_engine, owner) as session:
            receipt = await submit_request(
                session,
                replace(submission(owner, wallet), amount=Money.of("100", "USDT")),
            )
        token = await claim(engine_engine, owner, receipt)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, token)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            configured = await policy.execution_context(session, value)
        assert configured.setting.limit == Money.of("100", "USDT")
        assert configured.source_ready


async def test_unset_manual_request_reaches_one_fill_without_synthetic_risk_rows(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
    from tiewtrade.infra.paper_orders.request_worker import process_request as transfer
    from tiewtrade.infra.paper_orders.requests import admit_new_request

    value = intent(owner, wallet.episode_id)
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit=None
    ) as src:
        async with user_session(api_engine, owner) as session:
            receipt = await admit_new_request(
                session,
                wallet_id=wallet.wallet_id,
                intent=value,
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_request_dispatch WHERE request_id=:id",
                    {"id": receipt.request_id},
                )
            ).scalar_one()
            request_claim = await claim_request(
                session,
                DueRequest(receipt.request_id, owner, due),
                worker="optional-limit-intake",
            )
        assert request_claim is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await transfer(session, request_claim, policy=TransactionalRiskPolicy())
            command_id = UUID(
                str(
                    (
                        await session.execute(
                            "SELECT command_id FROM paper_order_request_results "
                            "WHERE request_id=:id",
                            {"id": receipt.request_id},
                        )
                    ).scalar_one()
                )
            )

        await drive(engine_engine, owner, command_id)
        await asyncio.sleep(0.12)
        await src.next_book()
        await drive(engine_engine, owner, command_id)

        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": value.order_id},
                )
            ).scalar_one() == "FILLED"
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM risk_limit_settings")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM risk_limit_evaluations")
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM risk_limit_baselines")
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of("9900", "USDT")

    # The old schema cannot represent an opening that was valid while the limit
    # was unset. Downgrade must preserve that history and leave 0060 installed.
    await api_engine.dispose()
    await engine_engine.dispose()
    await migrator_engine.dispose()
    failed = _failed_upgrade_or_downgrade("downgrade", "0059")
    assert "unconfigured Paper economic history prevents downgrade" in failed.stderr
    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0060"


async def drive(engine: AsyncEngine, owner: UUID, command_id: UUID) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        due = (
            await session.execute(
                """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
          WHERE command_id=:id RETURNING next_attempt_at""",
                {"id": command_id},
            )
        ).scalar_one()
        token = await claim_order(
            session, DueOrder(command_id, owner, due), worker="risk-composition"
        )
    assert token is not None
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_claimed_order(session, token, policy=TransactionalRiskPolicy())


async def test_first_fill_breach_blocks_later_depth_and_cancel_does_not_wait_for_price_fence(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(api_engine, engine_engine, migrator_engine, owner, wallet) as sources:
        value = replace(intent(owner, wallet.episode_id), size=QuoteBudget(Money.of(1100, "USDT")))
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, command.command_id)
        # F15's approved 100ms eligibility boundary is part of this correctness test.
        await asyncio.sleep(0.12)
        await sources.next_book()
        # Two fresh inputs are consumed in one worker transaction. The first
        # fill's fee breaches the limit; neither later depth nor the next input
        # may fill the remainder using the pre-fill risk book.
        await sources.next_book()
        await drive(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            order = (
                await session.execute(
                    "SELECT status,filled_quantity,spent FROM paper_order_projections"
                )
            ).one()
            assert (
                order.status == "PARTIALLY_FILLED"
                and order.filled_quantity == 10
                and order.spent == 1000
            )
            assert (await session.execute("SELECT latched FROM risk_limit_settings")).scalar_one()
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_execution_links")
            ).scalar_one() == 1
            actual = await get_wallet(session)
            assert actual is not None and actual.balance == Money.of(9000, "USDT")
            stop = UUID(
                str((await session.execute("SELECT id FROM risk_stop_requests")).scalar_one())
            )
            await consume_stop(session, stop)
            cancel = UUID(
                str(
                    (
                        await session.execute(
                            "SELECT id FROM paper_order_commands WHERE action='CANCEL'"
                        )
                    ).scalar_one()
                )
            )
        async with market_data_session(sources.market) as publisher:
            await publisher.execute("SELECT risk_publication_fence()")
            await asyncio.wait_for(drive(engine_engine, owner, cancel), timeout=2)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await consume_stop(session, stop)
            progress = (await session.execute("SELECT * FROM risk_stop_progress")).one()
            assert progress.target_set_complete and progress.pending_count == 0
            assert (
                await session.execute("SELECT status FROM paper_order_projections")
            ).scalar_one() == "CANCELED"
            assert (
                await session.execute("SELECT quote_reserved FROM paper_reservations")
            ).scalar_one() == 0
            held = (
                await session.execute("SELECT held_quantity FROM paper_position_projections")
            ).scalar_one()
            assert Quantity.of(held, "BTC") == Quantity.of("9.99", "BTC")
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(9000, "USDT")


async def fill_buy(
    api: AsyncEngine,
    engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    sources: Runtime,
) -> None:
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        command = await submit_order(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
    await drive(engine, owner, command.command_id)
    await asyncio.sleep(0.12)
    await sources.next_book()
    await drive(engine, owner, command.command_id)


async def test_bridge_refusal_does_not_roll_back_its_new_breach_with_the_transfer_savepoint(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
    from tiewtrade.infra.paper_orders.request_worker import process_request as transfer
    from tiewtrade.infra.paper_orders.requests import admit_new_request

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="10"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        value = intent(owner, wallet.episode_id)
        async with user_session(api_engine, owner) as session:
            receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute("SELECT next_attempt_at FROM paper_order_request_dispatch")
            ).scalar_one()
            token = await claim_request(
                session, DueRequest(receipt.request_id, owner, due), worker="breach-transfer"
            )
        assert token is not None
        await sources.price("90")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await transfer(session, token, policy=TransactionalRiskPolicy())
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (await session.execute("SELECT latched FROM risk_limit_settings")).scalar_one()
            assert (
                await session.execute("SELECT count(*) FROM risk_stop_requests")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT state FROM paper_order_request_results")
            ).scalar_one() == "REJECTED"
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_commands WHERE action='NEW'"
                )
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1


async def test_risk_journal_gap_allows_bounded_sell_and_replay_does_not_move_money_twice(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.core.risk_limits import RiskUnavailableError
    from tiewtrade.infra.risk_limits import monitor
    from tiewtrade.infra.risk_limits.storage import read_setting

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        await sources.price("90")

        async def unavailable(*args: object, **kwargs: object) -> NoReturn:
            raise RiskUnavailableError("controlled journal reader outage")

        with monkeypatch.context() as patch:
            patch.setattr(monitor, "read_frames", unavailable)
            sell = replace(
                intent(owner, wallet.episode_id),
                side=ExecutionSide.SELL,
                size=BaseSize(Quantity.of("0.5", "BTC")),
            )
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = await submit_order(session, wallet_id=wallet.wallet_id, intent=sell)
            await drive(engine_engine, owner, command.command_id)
            await asyncio.sleep(0.12)
            await sources.next_book()
            await drive(engine_engine, owner, command.command_id)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                current = await get_wallet(session)
                assert current is not None and current.balance == Money.of("9949.4505", "USDT")
                stored_evaluation = (
                    await session.execute(
                        "SELECT reason,loss,replay_pending FROM risk_limit_evaluations"
                    )
                ).one()
                assert stored_evaluation.loss is None and stored_evaluation.replay_pending
                assert (
                    await session.execute(
                        "SELECT status FROM paper_order_projections WHERE order_id=:id",
                        {"id": sell.order_id},
                    )
                ).scalar_one() == "FILLED"
        scope = submission(owner, wallet).scope
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            evaluation = await monitor.replay_monitor(session, await read_setting(session, scope))
            assert evaluation.loss == Money.of("5.6395", "USDT")
            assert not evaluation.latched
            assert (
                await session.execute("SELECT count(*) FROM paper_execution_links")
            ).scalar_one() == 2
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of("9949.4505", "USDT")


async def test_locked_risk_journal_cannot_rollback_sell_and_later_replay_latches_pre_sell_breach(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.infra.risk_limits.monitor import replay_monitor
    from tiewtrade.infra.risk_limits.storage import read_setting

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="10"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        await sources.price("90")
        sell = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            size=BaseSize(Quantity.of("0.5", "BTC")),
        )
        async with migrator_engine.begin() as unavailable:
            await unavailable.execute(
                text("LOCK TABLE market_risk_price_frames IN ACCESS EXCLUSIVE MODE")
            )
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = await submit_order(session, wallet_id=wallet.wallet_id, intent=sell)
            await asyncio.wait_for(drive(engine_engine, owner, command.command_id), timeout=2)
            await asyncio.sleep(0.12)
            await sources.next_book()
            await asyncio.wait_for(drive(engine_engine, owner, command.command_id), timeout=2)
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                current = await get_wallet(session)
                assert current is not None and current.balance == Money.of("9949.4505", "USDT")
                row = (
                    await session.execute("SELECT loss,replay_pending FROM risk_limit_evaluations")
                ).one()
                assert row.loss is None and row.replay_pending
        scope = submission(owner, wallet).scope
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await replay_monitor(session, await read_setting(session, scope))
            # The exposure breached before the SELL, even though the current loss
            # after selling at the verified bid is now below the threshold.
            assert result.latched and result.loss == Money.of("5.6395", "USDT")
            assert (
                await session.execute("SELECT count(*) FROM risk_stop_requests")
            ).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of("9949.4505", "USDT")


async def test_corrupt_derived_position_cache_fails_closed_without_blocking_sell(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.core.risk_limits import RiskReason
    from tiewtrade.infra.risk_limits.monitor import replay_monitor
    from tiewtrade.infra.risk_limits.storage import read_setting
    from tiewtrade.infra.risk_limits.views import current_evaluation

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        scope = submission(owner, wallet).scope
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            original = (await session.execute("SELECT book FROM risk_owner_state")).scalar_one()
            # This mutable projection disagrees internally; F14 facts remain authoritative.
            await session.execute("""UPDATE risk_owner_state
                SET book=jsonb_set(book,'{pairs,0,held}','"0"'::jsonb)""")
        async with user_session(api_engine, owner) as session:
            value = await current_evaluation(session, await read_setting(session, scope))
            assert value.reason is RiskReason.SOURCE_UNAVAILABLE and value.loss is None
        await sources.price("90")
        sell = replace(
            intent(owner, wallet.episode_id),
            side=ExecutionSide.SELL,
            size=BaseSize(Quantity.of("0.5", "BTC")),
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=sell)
        await drive(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        await sources.next_book()
        await drive(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of("9949.4505", "USDT")
            assert (
                await session.execute("SELECT loss FROM risk_limit_evaluations")
            ).scalar_one() is None
            # Restore only the cache, then replay the committed financial boundary.
            await session.execute(
                "UPDATE risk_owner_state SET book=CAST(:book AS jsonb)",
                {"book": json.dumps(original)},
            )
            evaluation = await replay_monitor(session, await read_setting(session, scope))
            assert evaluation.loss == Money.of("5.6395", "USDT")
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 2


async def test_disabling_admission_between_inputs_cannot_use_a_ready_batch_snapshot(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        value = intent(owner, wallet.episode_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            order = await load_order_state(session, value.order_id)
        await asyncio.sleep(0.12)
        async with market_data_session(sources.market) as producer:
            sources.lease = await renew_book_writer(producer, sources.lease)
            now = (await producer.execute("SELECT clock_timestamp()")).scalar_one()
            # Equality to eligible_at is an authoritative no-fill first input.
            # The next fresh input would fill unless the rollout control is read again.
            sources.book = replace(
                sources.book,
                input_id=sources.book.input_id + 1,
                received_at=order.eligible_at,
                verified_at=now,
                rebase=False,
            )
            sources.lease = await publish_input(
                producer, sources.lease, sources.book, sources.metadata
            )
        await sources.next_book()
        original = UserSession.execute
        copied = evaluated = 0

        async def disable_before_second_input(
            session: UserSession,
            statement: str,
            parameters: Mapping[str, object] | None = None,
        ) -> Any:
            nonlocal copied, evaluated
            if statement.lstrip().startswith("INSERT INTO paper_execution_inputs"):
                assert parameters is not None
                copied += len(json.loads(str(parameters["rows"])))
            if copied and statement == "SELECT clock_timestamp()":
                # Evidence is copied in bulk; each matching decision still reads
                # fresh time. Disable after input one, before input two executes.
                evaluated += 1
                if evaluated == 2:
                    async with migrator_engine.begin() as connection:
                        await connection.execute(
                            text("UPDATE risk_protocol_control SET admission_enabled=false")
                        )
            return await original(session, statement, parameters)

        monkeypatch.setattr(UserSession, "execute", disable_before_second_input)
        await drive(engine_engine, owner, command.command_id)
        assert copied == 2 and evaluated >= 2
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(10000, "USDT")
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": value.order_id},
                )
            ).scalar_one() == "ACCEPTED"


async def test_matching_cash_guard_failure_rolls_back_fill_and_money(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tiewtrade.infra.paper_orders import executions
    from tiewtrade.infra.paper_wallet.records import PaperWalletIntegrityError

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        value = intent(owner, wallet.episode_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
        await drive(engine_engine, owner, command.command_id)
        await asyncio.sleep(0.12)
        await sources.next_book()

        async def invalid_cash(*args: object, **kwargs: object) -> NoReturn:
            raise PaperWalletIntegrityError("controlled ledger integrity failure")

        with monkeypatch.context() as patch:
            patch.setattr(executions, "get_wallet", invalid_cash)
            with pytest.raises(PaperWalletIntegrityError):
                await drive(engine_engine, owner, command.command_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(10000, "USDT")
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 0
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_events WHERE event_kind='FILL'"
                )
            ).scalar_one() == 0
            assert (
                await session.execute("SELECT count(*) FROM paper_execution_links")
            ).scalar_one() == 0
            projection = (
                await session.execute(
                    """SELECT status,filled_quantity,spent FROM paper_order_projections
                    WHERE order_id=:id""",
                    {"id": value.order_id},
                )
            ).one()
            assert projection.status == "ACCEPTED"
            assert Quantity.of(projection.filled_quantity, "BTC") == Quantity.of(0, "BTC")
            assert Money.of(projection.spent, "USDT") == Money.of(0, "USDT")
