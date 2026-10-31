"""R6 API price catch-up is read-only and cannot replace the engine's final gate."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market.test_dispatch import intent
from tests.infra.risk_limits.test_execution import fill_buy, runtime
from tests.infra.risk_limits.test_requests import submission
from tests.infra.risk_limits.test_worker import claim as claim_risk_request
from tiewtrade.core.money import Money
from tiewtrade.core.risk_limits import RiskReason, RiskUnavailableError
from tiewtrade.infra.db import DatabaseRole, repeatable_user_session, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, set_connected
from tiewtrade.infra.paper_orders.manual_policy import manual_policy_for
from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
from tiewtrade.infra.paper_orders.request_worker import process_request
from tiewtrade.infra.paper_orders.requests import admit_new_request
from tiewtrade.infra.paper_orders.views import request_view
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.infra.risk_limits.monitor import replay_monitor
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.risk_limits.records import RiskAction
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.infra.risk_limits.storage import process_request as apply_risk_request
from tiewtrade.infra.risk_limits.storage import read_setting
from tiewtrade.infra.risk_limits.views import read_evidence, wallet_evidence


async def test_api_and_paper_snapshot_catch_up_without_writing_projection(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        await sources.price("101")
        async with repeatable_user_session(api_engine, owner) as session:
            setting = await read_setting(session, submission(owner, wallet).scope)
            before = (
                await session.execute("SELECT cursor,book,replay_pending FROM risk_owner_state")
            ).one()
            assert (
                await read_evidence(session, setting)
            ).evaluation.reason is RiskReason.SOURCE_UNAVAILABLE
            current = await read_evidence(session, setting, api_price_tail=True)
            assert current.evaluation.reason is RiskReason.READY
            assert current.evaluation.loss == Money.of(0, "USDT")
            snapshot = await wallet_evidence(session)
            assert snapshot is not None
            assert snapshot[1].evaluation.reason is current.evaluation.reason
            assert snapshot[1].evaluation.loss == current.evaluation.loss
            assert snapshot[1].evaluation.source_revision == current.evaluation.source_revision
            after = (
                await session.execute("SELECT cursor,book,replay_pending FROM risk_owner_state")
            ).one()
            assert before == after
        async with user_session(api_engine, owner) as session:
            value = intent(owner, wallet.episode_id)
            policy = await manual_policy_for(session, value, delegate=TransactionalRiskPolicy())
            policy.check(value)
            assert (
                await session.execute("SELECT count(*) FROM risk_stop_requests")
            ).scalar_one() == 0


async def test_transient_tail_breach_refuses_even_after_recovery_without_api_latch(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="10"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        await sources.price("90")
        await sources.price("100")
        async with user_session(api_engine, owner) as session:
            value = intent(owner, wallet.episode_id)
            policy = await manual_policy_for(session, value, delegate=TransactionalRiskPolicy())
            with pytest.raises(RiskUnavailableError):
                policy.check(value)
            assert not (
                await session.execute("SELECT latched FROM risk_limit_settings")
            ).scalar_one()
            assert (
                await session.execute("SELECT count(*) FROM risk_stop_requests")
            ).scalar_one() == 0
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            result = await replay_monitor(
                session, await read_setting(session, submission(owner, wallet).scope)
            )
            assert result.latched
            assert (
                await session.execute("SELECT count(*) FROM risk_stop_requests")
            ).scalar_one() == 1


@pytest.mark.parametrize("updates,ready", [(50, True), (51, False)])
async def test_api_tail_is_bounded_to_one_hundred_verified_frames(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    updates: int,
    ready: bool,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        for _ in range(updates):
            await sources.price("100")
        async with repeatable_user_session(api_engine, owner) as session:
            lag = (
                await session.execute(
                    "SELECT p.watermark-o.cursor FROM risk_owner_state o "
                    "CROSS JOIN risk_price_publication p"
                )
            ).scalar_one()
            assert lag == updates * 2
            result = await read_evidence(
                session,
                await read_setting(session, submission(owner, wallet).scope),
                api_price_tail=True,
            )
            assert result.evaluation.reason is (
                RiskReason.READY if ready else RiskReason.SOURCE_UNAVAILABLE
            )


@pytest.mark.parametrize(
    "fault",
    ["owner_pending", "evaluation_pending", "boundary", "pre_boundary_price", "source", "setting"],
)
async def test_api_tail_cannot_repair_an_incomplete_financial_snapshot(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    fault: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        await sources.price("100")
        statements = {
            "owner_pending": "UPDATE risk_owner_state SET replay_pending=true",
            "evaluation_pending": "UPDATE risk_limit_evaluations SET replay_pending=true",
            "boundary": "UPDATE risk_owner_state SET boundary_cursor=0",
            "pre_boundary_price": "UPDATE risk_owner_state SET cursor=0",
            "source": "UPDATE risk_owner_state SET source_revision=source_revision+1",
            "setting": "UPDATE risk_limit_evaluations SET setting_revision=setting_revision+1",
        }
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(statements[fault])
        async with repeatable_user_session(api_engine, owner) as session:
            result = await read_evidence(
                session,
                await read_setting(session, submission(owner, wallet).scope),
                api_price_tail=True,
            )
            assert result.evaluation.reason is RiskReason.SOURCE_UNAVAILABLE


@pytest.mark.parametrize("fault", ["missing", "checksum"])
async def test_api_tail_fails_closed_on_unproved_history(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="10"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        await sources.price("100")
        original = UserSession.execute

        async def failed_read(
            session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
        ) -> Any:
            result = await original(session, statement, parameters)
            if "FROM market_risk_price_frames WHERE id" not in statement:
                return result
            rows = [dict(row) for row in result.mappings().all()]
            assert rows
            if fault == "missing":
                rows = []
            else:
                rows[0]["valid"] = False
            failed = Mock()
            failed.mappings.return_value.all.return_value = rows
            return failed

        with monkeypatch.context() as patch:
            patch.setattr(UserSession, "execute", failed_read)
            async with repeatable_user_session(api_engine, owner) as session:
                result = await read_evidence(
                    session,
                    await read_setting(session, submission(owner, wallet).scope),
                    api_price_tail=True,
                )
                assert result.evaluation.reason is RiskReason.SOURCE_UNAVAILABLE


async def test_engine_recheck_blocks_a_new_breach_after_api_accepts(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="10"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        await sources.price("100")
        value = intent(owner, wallet.episode_id)
        async with user_session(api_engine, owner) as session:
            policy = await manual_policy_for(session, value, delegate=TransactionalRiskPolicy())
            policy.check(value)
            receipt = await admit_new_request(session, wallet_id=wallet.wallet_id, intent=value)
        await sources.price("90")
        await sources.price("100")
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            due = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_request_dispatch WHERE request_id=:id",
                    {"id": receipt.request_id},
                )
            ).scalar_one()
            claim = await claim_request(
                session, DueRequest(receipt.request_id, owner, due), worker="r6-final-check"
            )
        assert claim is not None
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, claim, policy=TransactionalRiskPolicy())
        async with user_session(api_engine, owner) as session:
            result = await request_view(session, receipt.request_id)
            assert result is not None and result.intake_state == "REJECTED"
            assert (
                await session.execute(
                    "SELECT count(*) FROM paper_orders WHERE id=:id", {"id": value.order_id}
                )
            ).scalar_one() == 0
            current = await get_wallet(session)
            assert current is not None and current.balance == Money.of(9900, "USDT")


async def test_api_tail_recovers_from_price_outage_without_changing_engine_projection(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with market_data_session(sources.market) as session:
            feed = (await read_snapshot(session)).feed
            assert feed is not None
            await set_connected(session, feed, False)
        async with repeatable_user_session(api_engine, owner) as session:
            setting = await read_setting(session, submission(owner, wallet).scope)
            result = await read_evidence(session, setting, api_price_tail=True)
            assert result.evaluation.reason is RiskReason.PRICE_UNAVAILABLE
            cursor = (await session.execute("SELECT cursor FROM risk_owner_state")).scalar_one()
        async with market_data_session(sources.market) as session:
            feed = (await read_snapshot(session)).feed
            assert feed is not None
            await set_connected(session, feed, True)
        await sources.price("100")
        async with repeatable_user_session(api_engine, owner) as session:
            result = await read_evidence(session, setting, api_price_tail=True)
            assert result.evaluation.reason is RiskReason.READY
            assert not result.evaluation.latched
            assert (
                await session.execute("SELECT cursor FROM risk_owner_state")
            ).scalar_one() == cursor


async def test_api_tail_rejects_setting_snapshot_from_before_a_real_risk_reset(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with user_session(api_engine, owner) as session:
            setting = await read_setting(session, submission(owner, wallet).scope)
            receipt = await submit_request(
                session,
                replace(
                    submission(owner, wallet),
                    action=RiskAction.RESET,
                    amount=None,
                    expected_revision=setting.revision,
                    key=uuid4(),
                ),
            )
        claim = await claim_risk_request(engine_engine, owner, receipt)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await apply_risk_request(session, claim)
        await sources.price("101")
        async with repeatable_user_session(api_engine, owner) as session:
            current = await read_setting(session, setting.scope)
            assert current.revision == setting.revision + 1
            assert (
                await read_evidence(session, setting, api_price_tail=True)
            ).evaluation.reason is RiskReason.SOURCE_UNAVAILABLE
            assert (
                await read_evidence(session, current, api_price_tail=True)
            ).evaluation.reason is RiskReason.READY


async def test_http_snapshot_uses_tail_provenance_and_restarts_pause_after_recovery(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    owner: UUID,
    wallet: PaperWalletSnapshot,
) -> None:
    from datetime import UTC, datetime

    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from tiewtrade.services.api.request_identity import Authenticated, current_user
    from tiewtrade.services.api.risk_limit_routes import router

    app = FastAPI()
    app.state.api_engine = api_engine
    app.include_router(router)
    app.dependency_overrides[current_user] = lambda: Authenticated(owner, "test", datetime.now(UTC))
    async with runtime(
        api_engine, engine_engine, migrator_engine, owner, wallet, limit="1000"
    ) as sources:
        await fill_buy(api_engine, engine_engine, owner, wallet, sources)
        async with market_data_session(sources.market) as session:
            feed = (await read_snapshot(session)).feed
            assert feed is not None
            await set_connected(session, feed, False)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            setting = await read_setting(session, submission(owner, wallet).scope)
            await replay_monitor(session, setting)
            await session.execute("""UPDATE risk_limit_evaluations
              SET unavailable_since=clock_timestamp()-interval '6 minutes',pause_alert_due=true""")
            previous = (await session.execute("SELECT * FROM risk_limit_evaluations")).one()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            paused = await client.get("/paper/risk-limit")
            assert paused.status_code == 200, paused.text
            assert paused.json()["pause_alert_due"]
            async with market_data_session(sources.market) as session:
                feed = (await read_snapshot(session)).feed
                assert feed is not None
                await set_connected(session, feed, True)
            await sources.price("101")
            async with user_session(api_engine, owner) as session:
                latest = (
                    await session.execute("""SELECT id,captured_at
                  FROM market_risk_price_frames ORDER BY id DESC LIMIT 1""")
                ).one()
            response = await client.get("/paper/risk-limit")
            assert response.status_code == 200, response.text
            recovered = response.json()
            assert recovered["reason"] == "READY" and recovered["loss"] == "0"
            assert recovered["unavailable_since"] is None and not recovered["pause_alert_due"]
            assert recovered["price_watermark"] == latest.id > previous.price_watermark
            assert datetime.fromisoformat(recovered["evaluated_at"]) > previous.evaluated_at
            assert datetime.fromisoformat(recovered["input_ready_at"]) == latest.captured_at
            async with market_data_session(sources.market) as session:
                feed = (await read_snapshot(session)).feed
                assert feed is not None
                await set_connected(session, feed, False)
            restarted = (await client.get("/paper/risk-limit")).json()
            assert restarted["reason"] == "RISK_PRICE_UNAVAILABLE"
            assert not restarted["pause_alert_due"]
            assert datetime.fromisoformat(restarted["unavailable_since"]) > previous.evaluated_at
        async with user_session(api_engine, owner) as session:
            assert (await session.execute("SELECT * FROM risk_limit_evaluations")).one() == previous
