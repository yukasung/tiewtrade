from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tests.infra.risk_limits.test_requests import seed_setting, submission
from tiewtrade.core.money import Money
from tiewtrade.core.risk_limits import RiskEvaluation, RiskReason
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order, submit_order
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.monitor import persist_evaluation
from tiewtrade.infra.risk_limits.stops import consume_stop
from tiewtrade.infra.risk_limits.storage import read_setting


async def breach(engine: AsyncEngine, owner: UUID, wallet: PaperWalletSnapshot) -> UUID:
    await seed_setting(engine, owner)
    scope = submission(owner, wallet).scope
    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
        setting = await read_setting(session, scope)
        await persist_evaluation(
            session,
            setting,
            RiskEvaluation(
                scope,
                setting.revision,
                2,
                datetime.now(UTC),
                RiskReason.BREACHED,
                Money.of(100, "USDT"),
                True,
                True,
            ),
            watermark=0,
            replay_pending=False,
        )
        return UUID(str((await session.execute("SELECT id FROM risk_stop_requests")).scalar_one()))


async def test_queued_opening_is_terminal_and_enrollment_completeness_is_explicit(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    stop = await breach(engine_engine, owner, wallet)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await consume_stop(session, stop, limit=1)
        progress = (await session.execute("SELECT * FROM risk_stop_progress")).one()
        assert progress.target_count == 1 and progress.pending_count == 0
        assert not progress.target_set_complete
        result = (await session.execute("SELECT * FROM paper_order_request_results")).one()
        assert result.request_id == receipt.request_id and result.state == "REJECTED"
        assert (
            await session.execute("SELECT state FROM paper_order_request_dispatch")
        ).scalar_one() == "TERMINAL"
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await consume_stop(session, stop, limit=1)
        progress = (await session.execute("SELECT * FROM risk_stop_progress")).one()
        assert progress.target_set_complete and progress.pending_count == 0
        assert (await session.execute("SELECT count(*) FROM risk_stop_targets")).scalar_one() == 1
        assert (
            await session.execute("SELECT count(*) FROM paper_order_commands")
        ).scalar_one() == 0


async def test_active_remainder_cancels_via_f15_and_releases_reservations_once(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()
    try:
        value = intent(owner, wallet.episode_id)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
            due = (
                await session.execute(
                    """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
                    WHERE command_id=:id RETURNING next_attempt_at""",
                    {"id": command.command_id},
                )
            ).scalar_one()
            accepted = await claim_order(
                session, DueOrder(command.command_id, owner, due), worker="risk-stop-accept"
            )
        # A global bounded round may select only older owners left by other
        # tests. This fixture needs this actual accepted order before breach.
        assert accepted is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, accepted, policy=AllowPolicy())
            assert (
                await session.execute("SELECT status FROM paper_order_projections")
            ).scalar_one() == "ACCEPTED"
        stop = await breach(engine_engine, owner, wallet)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await consume_stop(session, stop)
            progress = (await session.execute("SELECT * FROM risk_stop_progress")).one()
            assert (
                progress.target_set_complete
                and progress.target_count == progress.pending_count == 1
            )
            assert (
                await session.execute("SELECT quote_reserved FROM paper_reservations")
            ).scalar_one() > 0
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    """SELECT c.id,d.next_attempt_at FROM paper_order_commands c
                JOIN paper_order_dispatch d ON d.command_id=c.id WHERE c.action='CANCEL'""",
                )
            ).one()
            token = await claim_order(
                session,
                DueOrder(UUID(str(due.id)), owner, due.next_attempt_at),
                worker="risk-stop-cancel",
            )
        assert token is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, token, policy=None)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("UPDATE risk_stop_progress SET due_at=clock_timestamp()")
            await consume_stop(session, stop)
            await consume_stop(session, stop)
            progress = (await session.execute("SELECT * FROM risk_stop_progress")).one()
            assert progress.pending_count == 0 and progress.failed_count == 0
            assert (
                await session.execute("SELECT status FROM paper_order_projections")
            ).scalar_one() == "CANCELED"
            assert (
                await session.execute("SELECT quote_reserved FROM paper_reservations")
            ).scalar_one() == 0
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_order_commands WHERE action='CANCEL'"
                )
            ).scalar_one() == 1
    finally:
        await market.dispose()


async def test_effect_pages_are_bounded_owner_bound_and_keep_their_watermark(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from dataclasses import replace
    from uuid import uuid4

    import pytest

    from tiewtrade.core.orders import TradingMode
    from tiewtrade.infra.risk_limits.records import RiskConflictError
    from tiewtrade.infra.risk_limits.stop_views import effect_page

    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        for _ in range(105):
            await admit_new_request(
                session,
                wallet_id=wallet.wallet_id,
                intent=replace(value, order_id=uuid4(), idempotency_key=uuid4()),
            )
    stop = await breach(engine_engine, owner, wallet)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        for _ in range(6):
            await consume_stop(session, stop)
    async with user_session(api_engine, owner) as session:
        default_page = await effect_page(session, TradingMode.PAPER, stop)
        maximum_page = await effect_page(session, TradingMode.PAPER, stop, limit=100)
        assert default_page is not None and len(default_page["items"]) == 20
        assert maximum_page is not None and len(maximum_page["items"]) == 100
        page = await effect_page(session, TradingMode.PAPER, stop, limit=1)
        assert page is not None and len(page["items"]) == 1 and page["next_cursor"] is not None
        assert await effect_page(session, TradingMode.LIVE, stop) is None
        with pytest.raises(RiskConflictError):
            await effect_page(session, TradingMode.PAPER, stop, limit=101)
        with pytest.raises(RiskConflictError):
            await effect_page(
                session, TradingMode.PAPER, stop, cursor=page["next_cursor"], state_filter="FAILED"
            )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute("""INSERT INTO risk_stop_effects
          (stop_id,user_id,mode,target_kind,target_id,state,attempt,details)
          SELECT stop_id,user_id,mode,target_kind,target_id,'FAILED',1,'{}'
          FROM risk_stop_targets""")
        await consume_stop(session, stop)
    collected = [page["items"][0]["target_id"]]
    token = page["next_cursor"]
    async with user_session(api_engine, owner) as session:
        while token:
            following = await effect_page(session, TradingMode.PAPER, stop, limit=1, cursor=token)
            assert (
                following is not None and following["effects_revision"] == page["effects_revision"]
            )
            assert following["snapshot_at"] == page["snapshot_at"]
            assert following["items"][0]["state"] == "REJECTED"
            collected.append(following["items"][0]["target_id"])
            token = following["next_cursor"]
    assert len(set(collected)) == 105
    async with user_session(api_engine, uuid4()) as session:
        assert await effect_page(session, TradingMode.PAPER, stop) is None


async def test_stop_cut_is_not_lost_when_latch_clears_before_inbox_transfer(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
    from tiewtrade.infra.paper_orders.request_worker import process_request

    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        due = (
            await session.execute("SELECT next_attempt_at FROM paper_order_request_dispatch")
        ).scalar_one()
        token = await claim_request(
            session, DueRequest(receipt.request_id, owner, due), worker="old-stop"
        )
    assert token is not None
    stop = await breach(engine_engine, owner, wallet)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        # State produced by an explicit later loss reset; it cannot revoke this stop.
        await session.execute("UPDATE risk_limit_settings SET revision=revision+1,latched=false")
        await process_request(session, token, policy=AllowPolicy())
        await consume_stop(session, stop)
        assert (
            await session.execute("SELECT state FROM paper_order_request_results")
        ).scalar_one() == "REJECTED"
        assert (
            await session.execute("SELECT count(*) FROM paper_order_commands")
        ).scalar_one() == 0
        assert (await session.execute("SELECT count(*) FROM risk_stop_targets")).scalar_one() == 1


async def test_post_reset_request_in_older_transaction_survives_stop_cut(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.manual_orders.test_bridge import select_use
    from tiewtrade.services.engine.manual_order import run_manual_order_round

    await select_use(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        started = (await session.execute("SELECT now()")).scalar_one()
        stop = await breach(engine_engine, owner, wallet)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as engine_session:
            # The later explicit reset must not apply the old cut to new intake.
            await engine_session.execute(
                "UPDATE risk_limit_settings SET revision=revision+1,latched=false"
            )
        receipt = await admit_new_request(
            session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
        )
        times = (
            await session.execute(
                """SELECT r.recorded_at,s.recorded_at AS cut
            FROM paper_order_requests r CROSS JOIN risk_stop_requests s
            WHERE r.id=:id AND s.id=:stop""",
                {"id": receipt.request_id, "stop": stop},
            )
        ).one()
        assert started < times.cut < times.recorded_at
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await consume_stop(session, stop)
        assert (await session.execute("SELECT count(*) FROM risk_stop_targets")).scalar_one() == 0
    await run_manual_order_round(
        engine=engine_engine,
        scan_engine=scan_engine,
        worker="new-after-reset",
        policy=AllowPolicy(),
    )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        assert (
            await session.execute(
                "SELECT state FROM paper_order_request_results WHERE request_id=:id",
                {"id": receipt.request_id},
            )
        ).scalar_one() == "TRANSFERRED"
        assert (
            await session.execute("SELECT count(*) FROM paper_order_commands")
        ).scalar_one() == 1
