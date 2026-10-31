import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tests.infra.risk_limits.test_requests import seed_setting, submission
from tiewtrade.core.money import Money
from tiewtrade.core.orders import OrderOrigin, SafetyUnavailableError
from tiewtrade.core.risk_limits import RiskEvaluation, RiskReason
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.dispatch import (
    DueOrder,
    OrderCommand,
    claim_order,
    submit_order,
)
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits import stops
from tiewtrade.infra.risk_limits.monitor import persist_evaluation
from tiewtrade.infra.risk_limits.stops import consume_stop
from tiewtrade.infra.risk_limits.storage import read_setting
from tiewtrade.infra.trading_stops.storage import global_exclusive_lock


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


@pytest.mark.parametrize("cancel_boundary", ["before_commit", "after_commit"])
async def test_active_remainder_cancels_via_f15_and_releases_reservations_once(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    cancel_boundary: str,
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
        if cancel_boundary == "before_commit":
            with pytest.raises(RuntimeError, match="injected cancel commit loss"):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    await process_claimed_order(session, token, policy=None)
                    raise RuntimeError("injected cancel commit loss")
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                due = (
                    await session.execute(
                        """UPDATE paper_order_dispatch
                        SET lease_until=clock_timestamp()-interval '1 second',
                          next_attempt_at=clock_timestamp()
                        WHERE command_id=:id RETURNING next_attempt_at""",
                        {"id": token.command_id},
                    )
                ).scalar_one()
                token = await claim_order(
                    session,
                    DueOrder(token.command_id, owner, due),
                    worker="risk-stop-cancel-restart",
                )
            assert token is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, token, policy=None)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            terminal_due = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                    {"id": token.command_id},
                )
            ).scalar_one()
            replay = await claim_order(
                session,
                DueOrder(token.command_id, owner, terminal_due),
                worker="risk-stop-cancel-lost-ack",
            )
        assert replay is None
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


async def test_platform_stop_cancels_active_bot_remainder_but_keeps_sent_manual_order(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    market, _, _, _ = await ready_public_sources()
    manual = intent(owner, wallet.episode_id)
    bot = replace(
        intent(owner, wallet.episode_id),
        origin=OrderOrigin.BOT,
    )
    try:
        accepted = []
        for value in (manual, bot):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
                due = (
                    await session.execute(
                        """UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp()
                        WHERE command_id=:id RETURNING next_attempt_at""",
                        {"id": command.command_id},
                    )
                ).scalar_one()
                token = await claim_order(
                    session,
                    DueOrder(command.command_id, owner, due),
                    worker=f"platform-{value.origin.value.lower()}",
                )
            assert token is not None
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_claimed_order(session, token, policy=AllowPolicy())
            accepted.append(value.order_id)

        authority = uuid4()
        child = uuid4()
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                """INSERT INTO trading_stop_requests
                (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,
                 fingerprint,reason_code,generation,recorded_at)
                VALUES(:id,:owner,:owner,'PAPER','STOP','USER','SYSTEM',:key,
                  :fingerprint,'TEST_PLATFORM_CHILD',1,clock_timestamp())""",
                {
                    "id": authority,
                    "owner": owner,
                    "key": uuid4(),
                    "fingerprint": "0" * 64,
                },
            )
            await session.execute(
                """INSERT INTO risk_stop_requests
                (id,user_id,mode,event_id,wallet_id,episode_id,risk_revision,recorded_at,
                 authority_request_id,cause,target_policy)
                VALUES(:id,:owner,'PAPER',NULL,:wallet,:episode,NULL,clock_timestamp(),
                  :authority,'PLATFORM','BOT_ONLY')""",
                {
                    "id": child,
                    "owner": owner,
                    "wallet": wallet.wallet_id,
                    "episode": wallet.episode_id,
                    "authority": authority,
                },
            )
            await session.execute(
                "INSERT INTO risk_stop_progress(stop_id,user_id,mode) VALUES(:id,:owner,'PAPER')",
                {"id": child, "owner": owner},
            )
            await consume_stop(session, child)
            targets = set(
                await session.execute(
                    "SELECT order_id FROM risk_stop_targets WHERE stop_id=:stop",
                    {"stop": child},
                )
            )
            assert targets == {(bot.order_id,)}
            cancel = (
                await session.execute(
                    """SELECT c.id,d.next_attempt_at FROM paper_order_commands c
                    JOIN paper_order_dispatch d ON d.command_id=c.id
                    WHERE c.action='CANCEL' AND c.order_id=:order""",
                    {"order": bot.order_id},
                )
            ).one()
            token = await claim_order(
                session,
                DueOrder(UUID(str(cancel.id)), owner, cancel.next_attempt_at),
                worker="platform-bot-cancel",
            )
        assert token is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_claimed_order(session, token, policy=None)
            statuses = {
                UUID(str(row.order_id)): str(row.status)
                for row in await session.execute(
                    """SELECT order_id,status FROM paper_order_projections
                    WHERE order_id=ANY(:orders)""",
                    {"orders": accepted},
                )
            }
            reservations = {
                UUID(str(row.order_id)): row.quote_reserved
                for row in await session.execute(
                    """SELECT order_id,quote_reserved FROM paper_reservations
                    WHERE order_id=ANY(:orders)""",
                    {"orders": accepted},
                )
            }
        assert statuses == {manual.order_id: "ACCEPTED", bot.order_id: "CANCELED"}
        assert reservations[manual.order_id] > 0
        assert reservations[bot.order_id] == 0
    finally:
        await market.dispose()


async def test_platform_exclusive_fence_waits_for_shared_order_admission(
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    value = intent(owner, wallet.episode_id)
    admission_ready = asyncio.Event()
    release_admission = asyncio.Event()

    async def admit_before_stop() -> OrderCommand:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            command = await submit_order(session, wallet_id=wallet.wallet_id, intent=value)
            admission_ready.set()
            await release_admission.wait()
            return command

    async def take_platform_fence() -> None:
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await global_exclusive_lock(session)

    admission_task = asyncio.create_task(admit_before_stop())
    await admission_ready.wait()
    stop_task = asyncio.create_task(take_platform_fence())
    await asyncio.sleep(0.05)
    assert not stop_task.done(), "exclusive platform fence must wait for shared admission fence"
    release_admission.set()
    command, _ = await asyncio.gather(admission_task, stop_task)

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        persisted = (
            await session.execute(
                "SELECT count(*) FROM paper_order_commands WHERE id=:command",
                {"command": command.command_id},
            )
        ).scalar_one()
    assert persisted == 1


async def test_failed_stop_target_sets_minute_alert_and_keeps_retrying(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = intent(owner, wallet.episode_id)
    async with user_session(api_engine, owner) as session:
        request = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)

    authority = uuid4()
    stop_id = uuid4()
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await session.execute(
            """INSERT INTO trading_stop_requests
            (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,
             fingerprint,reason_code,generation,recorded_at)
            VALUES(:id,:owner,:owner,'PAPER','STOP','USER','SYSTEM',:key,
              :fingerprint,'TEST_RETRY_ALERT',1,clock_timestamp()-interval '2 minutes')""",
            {"id": authority, "owner": owner, "key": uuid4(), "fingerprint": "1" * 64},
        )
        await session.execute(
            """INSERT INTO risk_stop_requests
            (id,user_id,mode,event_id,wallet_id,episode_id,risk_revision,recorded_at,
             authority_request_id,cause,target_policy)
            VALUES(:id,:owner,'PAPER',NULL,:wallet,:episode,NULL,
              clock_timestamp()-interval '2 minutes',:authority,'USER','ALL')""",
            {
                "id": stop_id,
                "owner": owner,
                "wallet": wallet.wallet_id,
                "episode": wallet.episode_id,
                "authority": authority,
            },
        )
        await session.execute(
            "INSERT INTO risk_stop_progress(stop_id,user_id,mode) VALUES(:id,:owner,'PAPER')",
            {"id": stop_id, "owner": owner},
        )
        await session.execute(
            """INSERT INTO risk_stop_targets
            (stop_id,user_id,mode,target_kind,target_id,order_id)
            VALUES(:stop,:owner,'PAPER','REQUEST',:request,:order)""",
            {
                "stop": stop_id,
                "owner": owner,
                "request": request.request_id,
                "order": value.order_id,
            },
        )
        await session.execute(
            """INSERT INTO risk_stop_effects
            (stop_id,user_id,mode,target_kind,target_id,state,attempt,details)
            VALUES(:stop,:owner,'PAPER','REQUEST',:request,'PENDING',0,'{}'::jsonb)""",
            {"stop": stop_id, "owner": owner, "request": request.request_id},
        )

    original_request = stops._request

    async def unavailable(*args: object, **kwargs: object) -> str:
        raise RuntimeError("injected target failure")

    monkeypatch.setattr(stops, "_request", unavailable)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await consume_stop(session, stop_id)
        failed = (
            await session.execute(
                """SELECT p.pending_count,p.failed_count,p.alert_due,e.state,e.attempt,
                  e.next_attempt_at>clock_timestamp() backed_off
                FROM risk_stop_progress p JOIN risk_stop_effects e ON e.stop_id=p.stop_id
                WHERE p.stop_id=:stop ORDER BY e.sequence DESC LIMIT 1""",
                {"stop": stop_id},
            )
        ).one()
        assert failed == (1, 1, True, "FAILED", 1, True)
        await session.execute(
            """INSERT INTO risk_stop_effects
            (stop_id,user_id,mode,target_kind,target_id,state,attempt,next_attempt_at,details)
            SELECT stop_id,user_id,mode,target_kind,target_id,'FAILED',attempt,
              clock_timestamp(),'{}'::jsonb FROM risk_stop_effects
            WHERE stop_id=:stop ORDER BY sequence DESC LIMIT 1""",
            {"stop": stop_id},
        )

    monkeypatch.setattr(stops, "_request", original_request)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        await consume_stop(session, stop_id)
        progress = (
            await session.execute(
                """SELECT pending_count,failed_count,alert_due
                FROM risk_stop_progress WHERE stop_id=:stop""",
                {"stop": stop_id},
            )
        ).one()
        states = list(
            await session.execute(
                "SELECT state FROM risk_stop_effects WHERE stop_id=:stop ORDER BY sequence",
                {"stop": stop_id},
            )
        )
        target_count = (
            await session.execute(
                "SELECT count(*) FROM risk_stop_targets WHERE stop_id=:stop",
                {"stop": stop_id},
            )
        ).scalar_one()
    assert progress == (0, 0, False)
    assert [row.state for row in states] == ["PENDING", "FAILED", "FAILED", "REJECTED"]
    assert target_count == 1


async def test_effect_pages_are_bounded_owner_bound_and_keep_their_watermark(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
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
        plan = "\n".join(
            str(row[0])
            for row in await session.execute(
                """EXPLAIN (COSTS OFF)
                SELECT enrolled_sequence FROM risk_stop_targets
                WHERE stop_id=:stop AND mode='PAPER' AND enrolled_sequence>:last
                ORDER BY enrolled_sequence LIMIT 101""",
                {"stop": stop, "last": 0},
            )
        )
        assert "risk_stop_targets_stop_sequence" in plan
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


async def test_loss_reset_does_not_resume_shared_stop_cause(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from tests.infra.manual_orders.test_bridge import select_use

    await select_use(api_engine, owner)
    async with user_session(api_engine, owner) as session:
        await breach(engine_engine, owner, wallet)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as engine_session:
            await engine_session.execute(
                "UPDATE risk_limit_settings SET revision=revision+1,latched=false"
            )
        with pytest.raises(SafetyUnavailableError):
            await admit_new_request(
                session, wallet_id=wallet.wallet_id, intent=intent(owner, wallet.episode_id)
            )
