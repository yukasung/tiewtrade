"""Owned acceptance composition. Never imported by the production application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException

from tests import e2e_strategy_app as base
from tests.e2e_manual_order_app import Owner
from tiewtrade.core.money import Money
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session


@asynccontextmanager
async def lifespan(instance: FastAPI) -> AsyncIterator[None]:
    previous = base._closes
    base._closes = ("355",)
    try:
        async with base.lifespan(instance, enable_paper_test=True):
            yield
    finally:
        base._closes = previous


app = FastAPI(lifespan=lifespan)


class ExitInput(Owner):
    leg: Literal["TP", "SL"]


@app.post("/__e2e/paper-test/cross-target", status_code=204)
async def cross_target(body: ExitInput) -> None:
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            row = (
                await session.execute(
                    "SELECT a.take_profit,a.stop_loss FROM bot_test_entry_anchors a "
                    "JOIN bot_runs r ON r.id=a.run_id WHERE r.status='RUNNING' "
                    "AND a.execution_id IS NOT NULL AND a.failure_code IS NULL"
                )
            ).one_or_none()
            if row is None:
                raise HTTPException(409, "TEST_ENTRY_NOT_FILLED")
            price = Money.of(row.take_profit if body.leg == "TP" else row.stop_loss, "USDT")
            price = price + Money.of(1, "USDT") if body.leg == "TP" else price - Money.of(1, "USDT")
        base.public_price(price.as_parts()["amount"])
    finally:
        await engine.dispose()


app.mount("/", base.app)
