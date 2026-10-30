import asyncio
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.positions.test_storage import _fact
from tests.infra.risk_limits.test_prices import publication as publication
from tests.infra.risk_limits.test_requests import seed_setting, submission
from tests.infra.risk_limits.test_worker import claim
from tiewtrade.core.money import Money
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.core.risk_limits import RiskReason
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.realtime_records import FeedLease
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    database_now,
    read_snapshot,
    renew_writer,
    set_connected,
    write_price,
)
from tiewtrade.infra.paper_orders.initialization import enable_financial_writer
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.positions import PositionEventKind, apply_position_event
from tiewtrade.infra.risk_limits.monitor import initialize_monitor, replay_monitor
from tiewtrade.infra.risk_limits.records import RiskAction
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.infra.risk_limits.storage import process_request, read_setting
from tiewtrade.infra.risk_limits.views import current_evaluation


async def publish(market: AsyncEngine, lease: FeedLease, amount: str) -> FeedLease:
    async with market_data_session(market) as session:
        lease = await renew_writer(session, lease)
        now = await database_now(session)
        prior = next(row for row in (await read_snapshot(session)).rows if row.base == "BTC")
        quote = QuoteObservation(
            "primary_spot",
            "BTC",
            "USDT",
            Money.of(amount, "USDT"),
            1 if prior.observation is None else prior.observation.trade_id + 1,
            now,
            now,
            ObservationKind.STREAM,
        )
        assert await write_price(
            session,
            lease,
            replace(
                prior,
                observation=quote,
                reconciled_generation=lease.generation,
                effective_readiness="READY",
                reason=None,
                unavailable_since=None,
            ),
        )
    return lease


async def start(market: AsyncEngine) -> FeedLease:
    async with market_data_session(market) as session:
        lease = await acquire_writer(session, uuid4())
        assert lease is not None
        return await set_connected(session, lease, True)


@pytest.fixture(params=[False, True], ids=["separate-reads", "captured-snapshot"])
def replay_inputs(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if not request.param:
        return
    from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
    from tiewtrade.infra.risk_limits.monitor_snapshot import read_monitor_snapshot

    original = replay_monitor

    async def captured(session: UserSession, setting: Any, **kwargs: Any) -> Any:
        await lock_risk_owner(session, setting.scope.mode)
        snapshot = await read_monitor_snapshot(session)
        return await original(
            session, setting, **{**kwargs, "publication_fence": False}, snapshot=snapshot
        )

    monkeypatch.setattr(__name__ + ".replay_monitor", captured)


async def test_missed_transient_breach_survives_price_recovery_and_duplicate_round(
    replay_inputs: None,
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner)
    lease = await publish(publication, await start(publication), "1000")
    scope = submission(owner, wallet).scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        setting = await read_setting(session, scope)
        initial = await initialize_monitor(session, setting)
        assert initial.reason is RiskReason.READY and initial.loss == Money.of(0, "USDT")
        await enable_financial_writer(session)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1, quote="1000"),
        )
    lease = await publish(publication, lease, "900")
    await publish(publication, lease, "1200")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        decision = await replay_monitor(session, await read_setting(session, scope))
        assert decision.reason is RiskReason.BREACHED
        assert decision.latched and decision.loss == Money.of(0, "USDT")
        assert (await read_setting(session, scope)).revision == 2
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        again = await replay_monitor(session, await read_setting(session, scope))
        assert again.latched and not again.new_breach
        assert (await session.execute("SELECT count(*) FROM risk_limit_events")).scalar_one() == 1


async def test_pre_fill_price_is_not_valued_using_post_fill_holdings(
    replay_inputs: None,
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner)
    lease = await publish(publication, await start(publication), "1")
    scope = submission(owner, wallet).scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, scope))
    # A cheap price before the BUY must never cause a false loss on future holdings.
    lease = await publish(publication, lease, "10")
    await publish(publication, lease, "1000")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await enable_financial_writer(session)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1, quote="1000"),
        )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        decision = await replay_monitor(session, await read_setting(session, scope))
        assert decision.reason is RiskReason.READY and not decision.latched
        assert decision.loss == Money.of(0, "USDT")


async def test_replay_budget_keeps_opening_unavailable_until_caught_up(
    replay_inputs: None,
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner)
    lease = await publish(publication, await start(publication), "1000")
    scope = submission(owner, wallet).scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, scope))
    await publish(publication, lease, "1001")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        first = await replay_monitor(session, await read_setting(session, scope), frame_budget=1)
        assert first.reason is RiskReason.SOURCE_UNAVAILABLE and first.loss is None
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        final = await replay_monitor(session, await read_setting(session, scope))
        assert final.reason is RiskReason.READY


async def test_set_and_loss_reset_apply_authoritative_baseline_atomically(
    replay_inputs: None,
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    lease = await publish(publication, await start(publication), "1000")
    value = submission(owner, wallet)
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(session, value)
    token = await claim(engine_engine, owner, receipt)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_request(session, token)
        result = (await session.execute("SELECT * FROM risk_limit_evaluations")).one()
        assert result.reason == "READY" and not result.replay_pending
        await enable_financial_writer(session)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1, quote="1000"),
        )
    await publish(publication, lease, "900")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await replay_monitor(session, await read_setting(session, value.scope))
        assert (await read_setting(session, value.scope)).latched
    reset = replace(value, action=RiskAction.RESET, key=uuid4(), expected_revision=2, amount=None)
    async with user_session(api_engine, owner) as session:
        reset_receipt = await submit_request(session, reset)
    token = await claim(engine_engine, owner, reset_receipt)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_request(session, token)
        result = (
            await session.execute(
                "SELECT * FROM risk_limit_results WHERE request_id=:id",
                {"id": reset_receipt.receipt_id},
            )
        ).one()
        assert result.state == "APPLIED" and result.revision == 3
        setting = await read_setting(session, value.scope)
        assert not setting.latched
        decision = await replay_monitor(session, setting)
        assert decision.reason is RiskReason.READY and decision.loss == Money.of(0, "USDT")
        assert (
            await session.execute("SELECT count(*) FROM risk_limit_baselines")
        ).scalar_one() == 1

        assert (
            await session.execute(
                "SELECT count(*) FROM audit_events WHERE action='RISK_LIMIT_RESET'"
            )
        ).scalar_one() == 1


async def test_read_rechecks_feed_disconnect_without_waiting_for_monitor(
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    await seed_setting(engine_engine, owner)
    lease = await publish(publication, await start(publication), "1000")
    scope = submission(owner, wallet).scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await enable_financial_writer(session)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1, quote="1000"),
        )
        await initialize_monitor(session, await read_setting(session, scope))
    async with user_session(api_engine, owner) as session:
        assert (
            await current_evaluation(session, await read_setting(session, scope))
        ).reason is RiskReason.READY
    async with market_data_session(publication) as session:
        await set_connected(session, lease, False)
    async with user_session(api_engine, owner) as session:
        assert (await current_evaluation(session, await read_setting(session, scope))).loss is None


async def test_episode_reset_replays_new_baseline_and_preserves_wallet_limit_and_latch(
    replay_inputs: None,
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.core.risk_limits import RiskScope
    from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
    from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

    await seed_setting(engine_engine, owner)
    await publish(publication, await start(publication), "1000")
    scope = submission(owner, wallet).scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, scope))
        await session.execute("UPDATE risk_limit_settings SET latched=true")
    async with user_session(api_engine, owner) as session:
        await admit_command(
            session,
            action=PaperWalletAction.RESET,
            idempotency_key=uuid4(),
            capital_text="20000",
            expected_episode_id=wallet.episode_id,
        )
    await run_paper_wallet_round(
        engine=engine_engine, scan_engine=scan_engine, worker="risk-episode"
    )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        current = await get_wallet(session)
        assert current is not None and current.episode_id != wallet.episode_id
        new_scope = RiskScope(
            owner, scope.mode, UUID(str(current.wallet_id)), UUID(str(current.episode_id))
        )
        setting = await read_setting(session, new_scope)
        assert setting.limit == Money.of(100, "USDT") and setting.latched
        decision = await replay_monitor(session, setting)
        assert decision.reason is RiskReason.BREACHED and decision.loss == Money.of(0, "USDT")


async def test_partial_sell_and_correction_rebuild_use_the_original_reset_price(
    replay_inputs: None,
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tiewtrade.core.money import Quantity
    from tiewtrade.core.positions import ExecutionSide
    from tiewtrade.infra.risk_limits.books import authoritative_book

    await seed_setting(engine_engine, owner)
    lease = await publish(publication, await start(publication), "1000")
    value = submission(owner, wallet)
    original = _fact(uuid4(), 1, quote="1000")
    original_id = uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, value.scope))
        await enable_financial_writer(session)
        await apply_position_event(
            session, wallet.episode_id, original_id, PositionEventKind.RECORD, original
        )
    lease = await publish(publication, lease, "900")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await replay_monitor(session, await read_setting(session, value.scope))
    reset = replace(value, action=RiskAction.RESET, key=uuid4(), expected_revision=2, amount=None)
    async with user_session(api_engine, owner) as session:
        receipt = await submit_request(session, reset)
    token = await claim(engine_engine, owner, receipt)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await process_request(session, token)
        assert not (await read_setting(session, value.scope)).latched
    await publish(publication, lease, "870")
    sell = replace(
        original,
        execution_id=uuid4(),
        side=ExecutionSide.SELL,
        gross_quantity=Quantity.of("0.5", "BTC"),
        quote_amount=Money.of(435, "USDT"),
        source_sequence=2,
    )
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await enable_financial_writer(session)
        await apply_position_event(
            session, wallet.episode_id, uuid4(), PositionEventKind.RECORD, sell
        )
        evaluation = await replay_monitor(session, await read_setting(session, value.scope))
        assert evaluation.loss == Money.of(30, "USDT")
        first, _ = await authoritative_book(session, value.scope)
        assert first.pairs[0].allowance == Money.of(50, "USDT")
        assert first.pairs[0].adjusted_realized == Money.of(-15, "USDT")
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await enable_financial_writer(session)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.REPLACE,
            replace(original, quote_amount=Money.of(1100, "USDT")),
            original_id,
        )
        evaluation = await replay_monitor(session, await read_setting(session, value.scope))
        assert evaluation.loss == Money.of(30, "USDT")
        corrected, _ = await authoritative_book(session, value.scope)
        assert corrected.pairs[0].allowance == Money.of(100, "USDT")
        assert corrected.pairs[0].adjusted_realized == Money.of(-15, "USDT")
        assert (
            await session.execute("SELECT count(*) FROM risk_limit_baselines")
        ).scalar_one() == 1
        before = corrected
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await replay_monitor(session, await read_setting(session, value.scope))
        after, _ = await authoritative_book(session, value.scope)
        assert after == before


async def test_price_pause_timer_survives_restart_but_restarts_after_replayed_recovery(
    replay_inputs: None,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from datetime import timedelta

    from tests.infra.risk_limits.test_execution import fill_buy, runtime
    from tiewtrade.core.risk_limits import RiskEvaluation
    from tiewtrade.infra.risk_limits.monitor import persist_evaluation

    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with market_data_session(sources.market) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.feed is not None
            await set_connected(session, snapshot.feed, False)
        scope = submission(owner, wallet).scope
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            setting = await read_setting(session, scope)
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            # Controlled persisted pause age; no financial facts or immutable frames are edited.
            source = (
                await session.execute("SELECT source_revision FROM risk_owner_state")
            ).scalar_one()
            await persist_evaluation(
                session,
                setting,
                RiskEvaluation(
                    scope,
                    setting.revision,
                    source,
                    now - timedelta(minutes=5, seconds=1),
                    RiskReason.PRICE_UNAVAILABLE,
                    None,
                    False,
                    False,
                ),
                watermark=0,
                replay_pending=False,
            )
            await replay_monitor(session, setting)
            assert (
                await session.execute("SELECT pause_alert_due FROM risk_limit_evaluations")
            ).scalar_one()
        async with market_data_session(sources.market) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.feed is not None
            await set_connected(session, snapshot.feed, True)
            recovered_at = (await session.execute("SELECT clock_timestamp()")).scalar_one()
        await sources.price("100")
        async with market_data_session(sources.market) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.feed is not None
            await set_connected(session, snapshot.feed, False)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await replay_monitor(session, await read_setting(session, scope))
            assert result.reason is RiskReason.PRICE_UNAVAILABLE and result.loss is None
            row = (
                await session.execute(
                    "SELECT unavailable_since,pause_alert_due FROM risk_limit_evaluations"
                )
            ).one()
            assert row.unavailable_since >= recovered_at and not row.pause_alert_due


@pytest.mark.parametrize("final_fence", [False, True])
async def test_monitor_does_not_block_publication_or_skip_a_later_transient_breach(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    final_fence: bool,
) -> None:
    await seed_setting(engine_engine, owner)
    lease = await publish(publication, await start(publication), "1000")
    scope = submission(owner, wallet).scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, scope))
        await enable_financial_writer(session)
        await apply_position_event(
            session,
            wallet.episode_id,
            uuid4(),
            PositionEventKind.RECORD,
            _fact(uuid4(), 1, quote="1000"),
        )
    captured, release = asyncio.Event(), asyncio.Event()
    original = UserSession.execute

    async def paused_watermark(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        result = await original(session, statement, parameters)
        if "captured_watermark" in statement:
            captured.set()
            await release.wait()
        return result

    monkeypatch.setattr(UserSession, "execute", paused_watermark)

    async def round_once() -> None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await replay_monitor(
                session,
                await read_setting(session, scope),
                publication_fence=False,
                final_publication_fence=final_fence,
            )
            assert result.reason is (RiskReason.BREACHED if final_fence else RiskReason.READY)
            assert result.latched is final_fence

    task = asyncio.create_task(round_once())
    try:
        await asyncio.wait_for(captured.wait(), timeout=3)
        # Both commits must finish while the monitor still holds its owner lock.
        lease = await asyncio.wait_for(publish(publication, lease, "900"), timeout=3)
        await asyncio.wait_for(publish(publication, lease, "1200"), timeout=3)
        release.set()
        await asyncio.wait_for(task, timeout=3)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        result = await replay_monitor(
            session, await read_setting(session, scope), publication_fence=False
        )
        assert result.reason is RiskReason.BREACHED and result.latched
        assert result.loss == Money.of(0, "USDT")
        assert (await session.execute("SELECT count(*) FROM risk_stop_requests")).scalar_one() == 1


@pytest.mark.parametrize("frame_budget", [1, 100])
async def test_final_monitor_drain_commits_current_api_projection_within_frame_budget(
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    frame_budget: int,
) -> None:
    from tiewtrade.infra.risk_limits.prices import price_watermark
    from tiewtrade.infra.risk_limits.views import current_evaluation

    await seed_setting(engine_engine, owner)
    lease = await publish(publication, await start(publication), "1000")
    scope = submission(owner, wallet).scope
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await initialize_monitor(session, await read_setting(session, scope))
    original = UserSession.execute
    published = False

    async def advance_after_capture(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        nonlocal published, lease
        result = await original(session, statement, parameters)
        if "captured_watermark" in statement and not published:
            published = True
            # Historical replay still allows the producer to commit. Only the
            # final bounded tail takes the fence; no frame may be skipped.
            lease = await asyncio.wait_for(publish(publication, lease, "1001"), timeout=2)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(UserSession, "execute", advance_after_capture)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await replay_monitor(
                session,
                await read_setting(session, scope),
                publication_fence=False,
                final_publication_fence=True,
                frame_budget=frame_budget,
            )
            assert result.reason is (
                RiskReason.SOURCE_UNAVAILABLE if frame_budget == 1 else RiskReason.READY
            )
    assert published
    async with user_session(api_engine, owner) as session:
        current = await current_evaluation(session, await read_setting(session, scope))
        row = (await session.execute("SELECT cursor,replay_pending FROM risk_owner_state")).one()
        watermark = await price_watermark(session)
        if frame_budget == 1:
            assert row.replay_pending and row.cursor < watermark
            assert current.reason is RiskReason.SOURCE_UNAVAILABLE
        else:
            assert not row.replay_pending and row.cursor == watermark
            assert current.reason is RiskReason.READY and current.loss == Money.of(0, "USDT")
