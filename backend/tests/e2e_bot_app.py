"""Isolated F-20 UI composition. Never imported or mounted in production."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID, uuid4, uuid5

from fastapi import FastAPI
from sqlalchemy import text

from tests.e2e_manual_order_app import Owner, guard
from tests.e2e_risk_app import app as risk_app
from tests.e2e_risk_app import lifespan as risk_lifespan
from tests.infra.execution_market.test_bot_review_safety import DOC, PAIR, registry
from tiewtrade.core.money import Money
from tiewtrade.core.orders import (
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    QuoteBudget,
    TradingMode,
)
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.protections import ProtectionPrices
from tiewtrade.core.risk_limits import RiskScope
from tiewtrade.core.strategies import StrategyDecision
from tiewtrade.infra.bots.decisions import EvaluatedDecision, record_paper_decision
from tiewtrade.infra.bots.requests import submit_start
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command, get_wallet
from tiewtrade.infra.risk_limits.records import RiskAction, RiskSubmission
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.services.engine.bot import run_bot_control_round, run_bot_quote
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round


@asynccontextmanager
async def lifespan(instance: FastAPI) -> AsyncIterator[None]:
    guard()
    async with risk_lifespan(instance):
        migrator = create_engine_for(DatabaseRole.MIGRATOR)
        try:
            async with migrator.begin() as connection:
                await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
            yield
        finally:
            async with migrator.begin() as connection:
                await connection.execute(text("UPDATE paper_protection_protocol SET enabled=false"))
            await migrator.dispose()


app = FastAPI(lifespan=lifespan)


@app.post("/__e2e/bots/prepare", status_code=204)
async def prepare_owner(body: Owner) -> None:
    api, engine, scan = (
        create_engine_for(role)
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
        )
    )
    try:
        async with user_session(api, body.user_id) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'BOT')",
                {"owner": body.user_id},
            )
            await admit_command(
                session,
                action=PaperWalletAction.CREATE,
                idempotency_key=uuid4(),
                capital_text="10000",
                expected_episode_id=None,
            )
        await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="bot-browser-wallet")
        async with user_session(api, body.user_id) as session:
            wallet = await get_wallet(session)
            assert wallet is not None
            await submit_request(
                session,
                RiskSubmission(
                    RiskScope(
                        body.user_id,
                        TradingMode.PAPER,
                        UUID(str(wallet.wallet_id)),
                        UUID(str(wallet.episode_id)),
                    ),
                    RiskAction.SET,
                    uuid4(),
                    0,
                    Money.of(1000, "USDT"),
                ),
            )
    finally:
        await api.dispose()
        await engine.dispose()
        await scan.dispose()


class Phase(Owner):
    phase: Literal["pending", "start", "evaluate", "pause", "exposure"]


@app.post("/__e2e/bots/phase")
async def drive_phase(body: Phase) -> dict[str, str | None]:
    api, engine, scan, migrator = (
        create_engine_for(role)
        for role in (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MIGRATOR,
        )
    )
    try:
        if body.phase == "pending":
            async with user_session(api, body.user_id) as session:
                receipt = await submit_start(
                    session,
                    mode=TradingMode.PAPER,
                    request_id=uuid4(),
                    key=uuid4(),
                    payload={"strategy_config_ref": "fixture-v1"},
                )
                return {"request_id": str(receipt.request_id)}
        if body.phase == "start":
            await run_bot_control_round(engine=engine, scan_engine=scan, registry=registry())
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            run = (
                await session.execute(
                    "SELECT id,revision FROM bot_runs WHERE mode='PAPER' AND status<>'RETIRED'"
                )
            ).one()
        worker = uuid5(UUID(str(run.id)), "isolated-browser-worker")
        if body.phase in ("evaluate", "pause"):
            if body.phase == "pause":
                async with migrator.begin() as connection:
                    await connection.execute(
                        text("UPDATE risk_protocol_control SET admission_enabled=false")
                    )
            try:
                await run_bot_quote(
                    engine=engine,
                    owner=body.user_id,
                    run_id=run.id,
                    registry=registry(),
                    worker_id=worker,
                )
            finally:
                if body.phase == "pause":
                    async with migrator.begin() as connection:
                        await connection.execute(
                            text("UPDATE risk_protocol_control SET admission_enabled=true")
                        )
        if body.phase == "exposure":
            async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
                wallet = await get_wallet(session)
                assert wallet is not None
                order_id = uuid4()
                intent = OrderIntent(
                    order_id,
                    order_id,
                    OrderScope(body.user_id, UUID(str(wallet.episode_id)), TradingMode.PAPER),
                    PAIR,
                    OrderOrigin.BOT,
                    ExecutionSide.BUY,
                    OrderType.MARKET,
                    QuoteBudget(Money.of(100, "USDT")),
                )
                await record_paper_decision(
                    session,
                    EvaluatedDecision(
                        run.id,
                        uuid4(),
                        f"browser-exposure:{order_id}",
                        run.revision,
                        1,
                        1,
                        DOC,
                        StrategyDecision(
                            DOC,
                            (intent,),
                            ((order_id, ProtectionPrices(PAIR, stop_loss=Money.of(90, "USDT"))),),
                        ),
                    ),
                )
                return {"order_id": str(order_id), "run_id": str(run.id)}
        return {"run_id": str(run.id)}
    finally:
        await api.dispose()
        await engine.dispose()
        await scan.dispose()
        await migrator.dispose()


@app.post("/__e2e/bots/metrics")
async def metrics(body: Owner) -> dict[str, int]:
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            return {
                "stop_requests": int(
                    (
                        await session.execute(
                            "SELECT count(*) FROM trading_stop_requests "
                            "WHERE action='STOP' AND cause='USER'"
                        )
                    ).scalar_one()
                ),
                "orders": int(
                    (await session.execute("SELECT count(*) FROM paper_orders")).scalar_one()
                ),
                "position_events": int(
                    (
                        await session.execute("SELECT count(*) FROM paper_position_events")
                    ).scalar_one()
                ),
            }
    finally:
        await engine.dispose()


app.mount("/", risk_app)
