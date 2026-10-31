"""Financial races use actual PostgreSQL lock waits and production transactions."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.positions.test_storage import _fact
from tests.infra.risk_limits.test_monitor import publish, start
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_requests import seed_setting, submission
from tests.infra.risk_limits.test_worker import claim
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind, apply_position_event
from tiewtrade.infra.risk_limits.books import authoritative_book
from tiewtrade.infra.risk_limits.monitor import initialize_monitor, replay_monitor
from tiewtrade.infra.risk_limits.records import RiskAction
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.infra.risk_limits.storage import process_request, read_setting


async def serialize(
    engine: AsyncEngine,
    admin: AsyncEngine,
    owner: UUID,
    first: Callable[[UserSession], Awaitable[None]],
    second: Callable[[UserSession], Awaitable[None]],
) -> None:
    held, release = asyncio.Event(), asyncio.Event()
    pid: asyncio.Future[int] = asyncio.get_running_loop().create_future()

    async def earlier() -> None:
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            await first(session)
            held.set()
            await release.wait()

    async def later() -> None:
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            pid.set_result((await session.execute("SELECT pg_backend_pid()")).scalar_one())
            await second(session)

    tasks = [asyncio.create_task(earlier())]
    try:
        await asyncio.wait_for(held.wait(), 3)
        tasks.append(asyncio.create_task(later()))
        backend = await asyncio.wait_for(pid, 3)
        async with asyncio.timeout(3):
            while True:
                async with admin.connect() as connection:
                    blocked: bool = (
                        await connection.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid))>0"), {"pid": backend}
                        )
                    ).scalar_one()
                if blocked:
                    break
                assert not tasks[-1].done(), "competing transaction bypassed the owner fence"
                await asyncio.sleep(0.01)
        release.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 5)
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("change", ["BUY", "SELL", "CORRECTION"])
async def test_reset_serializes_with_fill_and_correction_using_its_original_cut(
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    change: str,
) -> None:
    await seed_setting(engine_engine, owner)
    scope = submission(owner, wallet).scope
    lease = await publish(publication, await start(publication), "1000")
    original = _fact(uuid4(), 1, quote="1000")
    original_id, next_id = uuid4(), uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, scope))
        await enable_financial_writer(session)
        await apply_position_event(
            session, wallet.episode_id, original_id, PositionEventKind.RECORD, original
        )
    await publish(publication, lease, "900")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await replay_monitor(session, await read_setting(session, scope))
        assert (await read_setting(session, scope)).latched
    value = replace(
        submission(owner, wallet), action=RiskAction.RESET, expected_revision=2, amount=None
    )
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(session, value)
    token = await claim(engine_engine, owner, receipt)

    async def reset(session: UserSession) -> None:
        await process_request(session, token)

    async def financial(session: UserSession) -> None:
        await enable_financial_writer(session)
        fact = (
            replace(original, quote_amount=Money.of(1100, "USDT"))
            if change == "CORRECTION"
            else replace(original, execution_id=uuid4(), source_sequence=2)
            if change == "BUY"
            else replace(
                original,
                execution_id=uuid4(),
                source_sequence=2,
                side=ExecutionSide.SELL,
                gross_quantity=Quantity.of("0.5", "BTC"),
                quote_amount=Money.of(450, "USDT"),
            )
        )
        for _ in range(2):
            await apply_position_event(
                session,
                wallet.episode_id,
                next_id,
                PositionEventKind.REPLACE if change == "CORRECTION" else PositionEventKind.RECORD,
                fact,
                original_id if change == "CORRECTION" else None,
            )

    await serialize(engine_engine, migrator_engine, owner, reset, financial)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        setting = await read_setting(session, scope)
        evaluation = await replay_monitor(session, setting)
        book, _ = await authoritative_book(session, scope)
        expected = {
            "BUY": ("100", "0", "100", True),
            "SELL": ("50", "0", "0", False),
            "CORRECTION": ("200", "0", "0", False),
        }[change]
        assert book.pairs[0].allowance == Money.of(expected[0], "USDT")
        assert book.pairs[0].adjusted_realized == Money.of(expected[1], "USDT")
        assert evaluation.loss == Money.of(expected[2], "USDT")
        assert evaluation.latched is expected[3]
        baseline = (await session.execute("SELECT snapshot FROM risk_limit_baselines")).scalar_one()
        assert baseline["source_sequence"] == 1
        assert (
            await session.execute("SELECT count(*) FROM paper_position_events")
        ).scalar_one() == 2
        assert (
            await session.execute("SELECT count(*) FROM risk_limit_baselines")
        ).scalar_one() == 1


async def test_decrease_commits_before_queued_buy_cannot_create_a_new_order(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.execution_market.test_dispatch import intent
    from tests.infra.risk_limits.test_execution import fill_buy, runtime
    from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
    from tiewtrade.infra.paper_orders.request_worker import process_request as transfer
    from tiewtrade.infra.paper_orders.requests import admit_new_request
    from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with user_session(api_engine, owner) as session:
            queued = await admit_new_request(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
            change = await submit_request(
                session,
                replace(
                    submission(owner, wallet),
                    action=RiskAction.DECREASE,
                    expected_revision=1,
                    amount=Money.of("0.01", "USDT"),
                ),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute("SELECT next_attempt_at FROM paper_order_request_dispatch")
            ).scalar_one()
            queued_claim = await claim_request(
                session, DueRequest(queued.request_id, owner, due), worker="decrease-race"
            )
        assert queued_claim is not None
        change_claim = await claim(engine_engine, owner, change)

        async def decrease(session: UserSession) -> None:
            await process_request(session, change_claim)

        async def buy(session: UserSession) -> None:
            await transfer(session, queued_claim, policy=TransactionalRiskPolicy())

        await serialize(engine_engine, migrator_engine, owner, decrease, buy)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = (
                await session.execute("SELECT state FROM paper_order_request_results")
            ).scalar_one()
            assert result == "REJECTED"
            assert (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one() == 1
            assert (
                await session.execute("SELECT count(*) FROM paper_position_events")
            ).scalar_one() == 1
            assert (await read_setting(session, submission(owner, wallet).scope)).latched
            cash = (
                await session.execute("SELECT sum(amount) FROM paper_wallet_ledger")
            ).scalar_one()
            assert Money.of(cash, "USDT") == Money.of(9900, "USDT")


@pytest.mark.parametrize("wallet_first", [True, False])
async def test_wallet_reset_and_loss_reset_do_not_mix_episode_baselines(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    wallet_first: bool,
) -> None:
    from tests.infra.risk_limits.test_execution import runtime
    from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
    from tiewtrade.infra.paper_wallet.records import DuePaperCommand
    from tiewtrade.infra.paper_wallet.storage import claim_command, process_claimed

    async with runtime(api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"):
        async with user_session(api_engine, owner) as session:
            capital = await admit_command(
                session,
                action=PaperWalletAction.RESET,
                idempotency_key=uuid4(),
                capital_text="5000",
                expected_episode_id=wallet.episode_id,
            )
            loss = await submit_request(
                session,
                replace(
                    submission(owner, wallet),
                    action=RiskAction.RESET,
                    expected_revision=1,
                    amount=None,
                ),
            )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            capital_claim = await claim_command(
                session, DuePaperCommand(capital.command_id, owner), worker="capital-risk-race"
            )
        assert capital_claim is not None
        loss_claim = await claim(engine_engine, owner, loss)

        async def capital_reset(session: UserSession) -> None:
            assert (await process_claimed(session, capital_claim)).failure_code is None

        async def loss_reset(session: UserSession) -> None:
            await process_request(session, loss_claim)

        await serialize(
            engine_engine,
            migrator_engine,
            owner,
            capital_reset if wallet_first else loss_reset,
            loss_reset if wallet_first else capital_reset,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            current = await get_wallet(session)
            assert current is not None and current.episode_id != wallet.episode_id
            assert current.balance == Money.of(5000, "USDT")
            result = (
                await session.execute(
                    "SELECT state,failure_code FROM risk_limit_results WHERE request_id=:id",
                    {"id": loss.receipt_id},
                )
            ).one()
            assert result.state == ("REJECTED" if wallet_first else "APPLIED")
            assert result.failure_code == ("RISK_SCOPE_CONFLICT" if wallet_first else None)
            assert (
                await session.execute("SELECT count(*) FROM risk_limit_baselines")
            ).scalar_one() == int(not wallet_first)
            scope = replace(
                submission(owner, wallet).scope, episode_id=UUID(str(current.episode_id))
            )
            assert (await read_setting(session, scope)).limit == Money.of(1000, "USDT")


@pytest.mark.parametrize("side", list(ExecutionSide))
async def test_loss_reset_cannot_revoke_an_old_active_order_cancellation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    side: ExecutionSide,
) -> None:
    from tests.infra.execution_market.test_dispatch import intent
    from tests.infra.risk_limits.test_execution import drive, fill_buy, runtime
    from tiewtrade.core.orders import BaseSize, OrderType, TimeInForce
    from tiewtrade.infra.paper_orders.dispatch import submit_order
    from tiewtrade.infra.paper_wallet import get_wallet
    from tiewtrade.infra.risk_limits.stops import consume_stop

    scope = submission(owner, wallet).scope
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        resting = replace(
            intent(owner, wallet.episode_id),
            kind=OrderType.LIMIT,
            side=side,
            size=BaseSize(Quantity.of(1 if side is ExecutionSide.BUY else "0.1", "BTC")),
            limit_price=Money.of(90 if side is ExecutionSide.BUY else 120, "USDT"),
            time_in_force=TimeInForce.GTC,
        )
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=resting)
        await sources.next_book()
        await drive(engine_engine, owner, command.command_id)
        async with user_session(api_engine, owner) as session:
            change = await submit_request(
                session,
                replace(
                    submission(owner, wallet),
                    action=RiskAction.DECREASE,
                    expected_revision=1,
                    amount=Money.of("0.01", "USDT"),
                ),
            )
        changed = await claim(engine_engine, owner, change)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, changed)
            setting = await read_setting(session, scope)
            assert setting.latched
            stop = UUID(
                str((await session.execute("SELECT id FROM risk_stop_requests")).scalar_one())
            )
        async with user_session(api_engine, owner) as session:
            reset_receipt = await submit_request(
                session,
                replace(
                    submission(owner, wallet),
                    action=RiskAction.RESET,
                    expected_revision=setting.revision,
                    amount=None,
                ),
            )
        reset_claim = await claim(engine_engine, owner, reset_receipt)

        async def reset(session: UserSession) -> None:
            await process_request(session, reset_claim)

        async def old_stop(session: UserSession) -> None:
            await consume_stop(session, stop)

        async def reserved(session: UserSession) -> tuple[Money, Quantity]:
            row = (
                await session.execute(
                    """SELECT quote_reserved,base_reserved FROM paper_reservations
                    WHERE order_id=:id""",
                    {"id": resting.order_id},
                )
            ).one()
            return Money.of(row.quote_reserved, "USDT"), Quantity.of(row.base_reserved, "BTC")

        await serialize(engine_engine, migrator_engine, owner, reset, old_stop)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            assert not (await read_setting(session, scope)).latched
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": resting.order_id},
                )
            ).scalar_one() == "ACCEPTED"
            assert await reserved(session) == (
                Money.of(90 if side is ExecutionSide.BUY else 0, "USDT"),
                Quantity.of("0.1" if side is ExecutionSide.SELL else 0, "BTC"),
            )
            cancel = UUID(
                str(
                    (
                        await session.execute(
                            "SELECT id FROM paper_order_commands WHERE action='CANCEL'"
                        )
                    ).scalar_one()
                )
            )
        await drive(engine_engine, owner, cancel)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            for _ in range(2):
                await consume_stop(session, stop)
            assert (
                await session.execute(
                    "SELECT status FROM paper_order_projections WHERE order_id=:id",
                    {"id": resting.order_id},
                )
            ).scalar_one() == "CANCELED"
            assert await reserved(session) == (Money.of(0, "USDT"), Quantity.of(0, "BTC"))
            assert (
                await session.execute(
                    """SELECT count(*) FROM paper_order_events
                    WHERE order_id=:id AND event_kind='CANCELED'""",
                    {"id": resting.order_id},
                )
            ).scalar_one() == 1
            held = (
                await session.execute("SELECT held_quantity FROM paper_position_projections")
            ).scalar_one()
            assert Quantity.of(held, "BTC") == Quantity.of("0.999", "BTC")
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(9900, "USDT")
            progress = (
                await session.execute(
                    "SELECT target_set_complete,pending_count FROM risk_stop_progress"
                )
            ).one()
            assert progress.target_set_complete and progress.pending_count == 0
