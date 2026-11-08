"""Isolated F-17 browser composition; recorded data and real PostgreSQL, never Live."""

import asyncio
from dataclasses import replace
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy import text

from tests import e2e_manual_order_app as manual
from tests.infra.execution_market.test_worker import ready_public_sources
from tests.infra.protections.test_lifecycle import execute
from tests.infra.protections.test_validation import publish_price
from tiewtrade.core.money import Quantity
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import publish_input
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions.views import held_and_reserved
from tiewtrade.infra.protections.storage import groups
from tiewtrade.infra.protections.worker import process_group, process_request

app = FastAPI(lifespan=manual.lifespan)


@app.post("/__e2e/protections/enable", status_code=204)
async def enable() -> None:
    manual.guard()
    engine = create_engine_for(DatabaseRole.MIGRATOR)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("UPDATE paper_protection_protocol SET enabled=true"))
    finally:
        await engine.dispose()


@app.post("/__e2e/protections/drive")
async def drive(body: manual.Owner) -> dict[str, object]:
    manual.guard()
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            pending = (
                await session.execute(
                    "SELECT id FROM paper_protection_requests r WHERE NOT EXISTS "
                    "(SELECT 1 FROM paper_protection_results s WHERE s.request_id=r.id)"
                )
            ).all()
            for row in pending:
                await process_request(session, row.id)
            wallet = await get_wallet(session)
            assert wallet is not None
            episode = wallet.episode_id
            rows = await groups(session, episode, PositionPair("BTC", "USDT"))
            for group in rows:
                await process_group(session, group.value.protection_id)
        return {"processed": len(rows)}
    finally:
        await engine.dispose()


class Price(manual.Owner):
    price: str


@app.post("/__e2e/protections/price", status_code=204)
async def price(body: Price) -> None:
    manual.guard()
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        await publish_price(market, body.price)
    finally:
        await market.dispose()


@app.post("/__e2e/protections/settle")
async def settle(body: manual.Owner) -> dict[str, object]:
    """Drive recorded input through the real writer; never force a due timestamp."""
    manual.guard()
    engine = create_engine_for(DatabaseRole.ENGINE)
    market, lease, book, metadata = await ready_public_sources()
    try:

        async def execute_due(command: UUID) -> None:
            async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
                row = (
                    await session.execute(
                        "SELECT next_attempt_at,clock_timestamp() AS now FROM paper_order_dispatch "
                        "WHERE command_id=:id",
                        {"id": command},
                    )
                ).one()
                delay = max(0.0, (row.next_attempt_at - row.now).total_seconds())
            if delay:
                await asyncio.sleep(delay + 0.005)
            await execute(engine, body.user_id, command)

        async def closing_commands() -> list[UUID]:
            async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
                return list(
                    (
                        await session.execute(
                            """SELECT c.id FROM paper_order_commands c
                    JOIN paper_order_dispatch d ON d.command_id=c.id
                    WHERE d.state='PENDING' AND (c.action='CANCEL' OR EXISTS(
                      SELECT 1 FROM paper_protection_exits x WHERE x.command_id=c.id))
                    ORDER BY c.action='CANCEL' DESC,c.id"""
                        )
                    ).scalars()
                )

        for command in await closing_commands():
            await execute_due(command)
        await asyncio.sleep(0.23)
        async with market_data_session(market) as market_session:
            now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                market_session,
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
        for command in await closing_commands():
            await execute_due(command)
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            wallet = await get_wallet(session)
            assert wallet is not None
            rows = await groups(session, wallet.episode_id, PositionPair("BTC", "USDT"))
            for group in rows:
                await process_group(session, group.value.protection_id)
            held, reserved = await held_and_reserved(
                session, wallet.episode_id, PositionPair("BTC", "USDT")
            )
            counts = (
                await session.execute("""SELECT
                (SELECT count(*) FROM paper_protection_exits) AS exits,
                (SELECT count(*) FROM paper_execution_links
                  WHERE position_event_kind='RECORD') AS fills,
                (SELECT count(*) FROM paper_protection_events WHERE kind='TRIGGER') AS triggers,
                (SELECT count(*) FROM audit_events WHERE action='PROTECTION_EVENT') AS audits""")
            ).one()
            cash = await get_wallet(session)
            assert cash is not None
            return {
                "balance": cash.balance.as_parts()["amount"],
                "held": held.as_parts()["quantity"],
                "reserved": reserved.as_parts()["quantity"],
                "exits": counts.exits,
                "fills": counts.fills,
                "triggers": counts.triggers,
                "audits": counts.audits,
            }
    finally:
        await engine.dispose()
        await market.dispose()


@app.post("/__e2e/protections/coarse-step", status_code=204)
async def coarse_step(body: manual.Owner) -> None:
    """Publish a recorded coarse-step market fixture; never mount in production."""
    manual.guard()
    market, lease, book, metadata = await ready_public_sources()
    try:
        metadata = replace(
            metadata, market=replace(metadata.market, quantity_step=Quantity.of("0.01", "BTC"))
        )
        async with market_data_session(market) as session:
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            await publish_input(
                session,
                lease,
                replace(
                    book,
                    input_id=book.input_id + 1,
                    received_at=now,
                    verified_at=now,
                ),
                metadata,
            )
    finally:
        await market.dispose()


app.mount("/", manual.app)
