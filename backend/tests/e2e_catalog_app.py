"""Browser-test composition for F-37; never imported by the production entrypoint."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import presented_session
from tiewtrade.infra.platform import enable_mutations, read_catalog, reconcile_removal_effects
from tiewtrade.services.api.app import app as production_app
from tiewtrade.services.api.app import lifespan as production_lifespan
from tiewtrade.services.platform_bootstrap.main import _bootstrap
from tiewtrade.venues import FakeVenue, Symbol
from tiewtrade.venues.binance_th.order_book_mapping import capability_from_pair
from tiewtrade.venues.order_books import ExecutionCapability


class FreshFakeVenue(FakeVenue):
    async def capability(self, symbol: Symbol) -> ExecutionCapability:
        return replace(await super().capability(symbol), observed_at=datetime.now(UTC))


def _capability_payload() -> dict[str, object]:
    return {
        "symbol": "SOLUSDT",
        "baseAsset": "SOL",
        "quoteAsset": "USDT",
        "status": "TRADING",
        "orderTypes": ["MARKET", "LIMIT"],
        "filters": [
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.01",
                "maxPrice": "10000",
                "tickSize": "0.01",
            },
            {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
            {
                "filterType": "MIN_NOTIONAL",
                "minNotional": "5",
                "applyToMarket": True,
                "avgPriceMins": 0,
            },
        ],
    }


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with production_lifespan(production_app):
        symbol = Symbol("SOL", "USDT")
        observed = capability_from_pair(symbol, _capability_payload(), datetime.now(UTC))
        production_app.state.catalog_capability_source = FreshFakeVenue(
            capabilities={symbol: observed}
        )
        yield


app = FastAPI(lifespan=lifespan)


class PrepareRequest(BaseModel):
    user_id: UUID


@app.post("/__e2e/catalog/prepare", status_code=204)
async def prepare(body: PrepareRequest) -> None:
    """Bootstrap the browser-created owner and open the real protocol gate."""
    await _bootstrap(body.user_id)
    generation = UUID(os.environ["TIEWTRADE_CATALOG_DEPLOYMENT_GENERATION"])
    expires = datetime.now(UTC) + timedelta(minutes=2)
    for role, kind in (
        (DatabaseRole.API, "API"),
        (DatabaseRole.ENGINE, "ENGINE"),
        (DatabaseRole.MARKET_DATA, "MARKET_DATA"),
        (DatabaseRole.INDICATOR_BUILDER, "INDICATOR_BUILDER"),
    ):
        engine = create_engine_for(role)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "SELECT catalog_protocol_heartbeat"
                        "(:kind,:instance,:version,:generation,:expires)"
                    ),
                    {
                        "kind": kind,
                        "instance": uuid4(),
                        "version": 1,
                        "generation": generation,
                        "expires": expires,
                    },
                )
        finally:
            await engine.dispose()
    engine = create_engine_for(DatabaseRole.API)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.API) as session:
            revision = (await read_catalog(session)).snapshot.revision
            await enable_mutations(
                session,
                deployment_generation=generation,
                expected_revision=revision,
            )
    finally:
        await engine.dispose()


@app.post("/__e2e/catalog/reconcile", status_code=204)
async def reconcile() -> None:
    """Run the real durable effect reconciliation without exposing it in production."""
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with presented_session(engine, role=DatabaseRole.ENGINE) as session:
            await reconcile_removal_effects(session)
    finally:
        await engine.dispose()


app.mount("/", production_app)
