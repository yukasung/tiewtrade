"""Isolated F18 browser harness. Production composition, recorded public inputs only.

No test policy or test route is mounted by the production application.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from tests.e2e_manual_order_app import Owner, guard
from tests.infra.execution_market.test_worker import ready_public_sources
from tests.infra.risk_limits.test_execution import Runtime
from tiewtrade.core.orders import AdmissionPolicy, TradingMode
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, set_connected
from tiewtrade.infra.paper_orders.request_dispatch import ClaimedRequest
from tiewtrade.infra.paper_orders.request_worker import process_request as transfer_request
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner
from tiewtrade.infra.risk_limits.records import RiskReceipt, RiskSubmission
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.services.api import risk_limit_routes
from tiewtrade.services.api.app import app as production_app
from tiewtrade.services.api.app import lifespan as production_lifespan
from tiewtrade.services.engine import manual_order as manual_order_worker
from tiewtrade.services.engine.paper_order_main import serve as orders
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round
from tiewtrade.services.engine.risk_limit_main import serve as risk

_disconnect_owner: UUID | None = None
_price = "110"
_connected = True
_runtime: Runtime | None = None
_hold_transfer_owner: UUID | None = None
_held_transfer: asyncio.Event | None = None
_release_transfer: asyncio.Event | None = None
_cache_backups: dict[UUID, dict[str, Any]] = {}
_corrections: dict[UUID, UUID] = {}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _runtime, _held_transfer, _release_transfer, _hold_transfer_owner
    guard()
    original_submit = submit_request

    async def submit(session: UserSession, value: RiskSubmission) -> RiskReceipt:
        global _disconnect_owner
        if value.scope.owner_id == _disconnect_owner:
            _disconnect_owner = None
            await session.execute("SELECT pg_terminate_backend(pg_backend_pid())")
        return await original_submit(session, value)

    _held_transfer, _release_transfer = asyncio.Event(), asyncio.Event()

    async def held_transfer(
        session: UserSession, claim: ClaimedRequest, *, policy: AdmissionPolicy | None
    ) -> None:
        global _hold_transfer_owner
        if session.user_id == _hold_transfer_owner:
            _hold_transfer_owner = None
            assert _held_transfer is not None and _release_transfer is not None
            _held_transfer.set()
            await _release_transfer.wait()
        await transfer_request(session, claim, policy=policy)

    transfer_patch = patch.object(manual_order_worker, "process_request", held_transfer)
    transfer_patch.start()
    submit_patch = patch.object(risk_limit_routes, "submit_request", submit)
    submit_patch.start()
    market, lease, book, metadata = await ready_public_sources()
    _runtime = Runtime(market, lease, book, metadata)
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    tasks: list[asyncio.Task[None]] = []

    async def publisher() -> None:
        assert _runtime is not None
        connected = True
        published_price = None
        next_price = 0.0
        loop = asyncio.get_running_loop()
        while True:
            await _runtime.next_book()
            if connected != _connected:
                async with market_data_session(market) as session:
                    snapshot = await read_snapshot(session)
                    assert snapshot.feed is not None
                    await set_connected(session, snapshot.feed, _connected)
                connected = _connected
            if connected and (published_price != _price or loop.time() >= next_price):
                await _runtime.price(_price)
                published_price = _price
                next_price = loop.time() + 2
            await asyncio.sleep(0.2)

    try:
        async with migrator.begin() as connection:
            await connection.execute(
                text("""UPDATE risk_protocol_control SET
                publication_enabled=true,financial_enabled=true,admission_enabled=true""")
            )
        async with production_lifespan(production_app):
            tasks = [
                asyncio.create_task(publisher()),
                asyncio.create_task(risk()),
                asyncio.create_task(orders()),
            ]
            yield
    finally:
        submit_patch.stop()
        transfer_patch.stop()
        if _release_transfer is not None:
            _release_transfer.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        async with migrator.begin() as connection:
            await connection.execute(
                text("""UPDATE risk_protocol_control SET
                admission_enabled=false,financial_enabled=false,publication_enabled=false""")
            )
        await market.dispose()
        await migrator.dispose()
        _runtime = None
        _held_transfer = _release_transfer = None
        _hold_transfer_owner = None


app = FastAPI(lifespan=lifespan)


@app.post("/__e2e/risk/prepare", status_code=204)
async def prepare_owner(body: Owner) -> None:
    api, engine, scan = (
        create_engine_for(role)
        for role in (DatabaseRole.API, DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
    )
    try:
        async with user_session(api, body.user_id) as session:
            await session.execute(
                "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                {"owner": body.user_id},
            )
            await admit_command(
                session,
                action=PaperWalletAction.CREATE,
                idempotency_key=uuid4(),
                capital_text="10000",
                expected_episode_id=None,
            )
        await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="risk-browser-wallet")
    finally:
        await api.dispose()
        await engine.dispose()
        await scan.dispose()


@app.post("/__e2e/risk/disconnect-intake", status_code=204)
async def disconnect_intake(body: Owner) -> None:
    global _disconnect_owner
    _disconnect_owner = body.user_id


@app.post("/__e2e/risk/hold-transfer", status_code=204)
async def hold_transfer(body: Owner) -> None:
    global _hold_transfer_owner
    assert _held_transfer is not None and _release_transfer is not None
    _held_transfer.clear()
    _release_transfer.clear()
    _hold_transfer_owner = body.user_id


@app.get("/__e2e/risk/transfer-held")
async def transfer_held() -> dict[str, bool]:
    return {"held": _held_transfer is not None and _held_transfer.is_set()}


@app.post("/__e2e/risk/release-transfer", status_code=204)
async def release_transfer() -> None:
    assert _release_transfer is not None
    _release_transfer.set()


class PublicPrice(BaseModel):
    amount: str = "110"
    connected: bool = True


@app.post("/__e2e/risk/price", status_code=204)
async def price(body: PublicPrice) -> None:
    global _price, _connected
    # Recorded public input selection only; no financial state mutation.
    from tiewtrade.core.money import Money

    Money.of(body.amount, "USDT")
    _price, _connected = body.amount, body.connected


@app.post("/__e2e/risk/cache-gap", status_code=204)
async def cache_gap(body: Owner) -> None:
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            await lock_risk_owner(session, TradingMode.PAPER)
            book = (
                await session.execute("SELECT book FROM risk_owner_state WHERE mode='PAPER'")
            ).scalar_one()
            _cache_backups[body.user_id] = json.loads(json.dumps(book))
            broken = json.loads(json.dumps(book))
            assert broken["pairs"]
            broken["pairs"][0]["held"] = "0"  # impossible derived cost/holdings, not F14 facts
            await session.execute(
                "UPDATE risk_owner_state SET book=CAST(:book AS jsonb) WHERE mode='PAPER'",
                {"book": json.dumps(broken)},
            )
    finally:
        await engine.dispose()


@app.post("/__e2e/risk/repair-cache", status_code=204)
async def repair_cache(body: Owner) -> None:
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            await lock_risk_owner(session, TradingMode.PAPER)
            await session.execute(
                "UPDATE risk_owner_state SET book=CAST(:book AS jsonb) WHERE mode='PAPER'",
                {"book": json.dumps(_cache_backups.pop(body.user_id))},
            )
    finally:
        await engine.dispose()


@app.post("/__e2e/risk/replay-correction")
async def replay_correction(body: Owner) -> dict[str, int | bool]:
    from tiewtrade.core.money import Money
    from tiewtrade.infra.paper_orders.codec import execution_from_payload
    from tiewtrade.infra.paper_orders.corrections import correct_fill
    from tiewtrade.infra.paper_wallet import get_wallet
    from tiewtrade.infra.positions import PositionEventKind

    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            await lock_risk_owner(session, TradingMode.PAPER)
            wallet = await get_wallet(session)
            assert wallet is not None
            before = wallet.balance
            linked = (
                await session.execute("""SELECT l.position_event_id,l.order_event_id,e.payload
                FROM paper_execution_links l JOIN paper_order_events e ON e.id=l.order_event_id
                WHERE l.position_event_kind='RECORD' ORDER BY e.sequence LIMIT 1""")
            ).one()
            for _ in range(2):
                await correct_fill(
                    session,
                    wallet_id=wallet.wallet_id,
                    episode_id=wallet.episode_id,
                    order_event_id=linked.order_event_id,
                    correction_event_id=_corrections.setdefault(body.user_id, uuid4()),
                    supersedes_position_event_id=linked.position_event_id,
                    kind=PositionEventKind.REPLACE,
                    fact=execution_from_payload(linked.payload["execution"]),
                )
            after = Money.of(
                (
                    await session.execute(
                        "SELECT sum(amount) FROM paper_wallet_ledger WHERE episode_id=:episode",
                        {"episode": wallet.episode_id},
                    )
                ).scalar_one(),
                "USDT",
            )
            records = int(
                (
                    await session.execute(
                        "SELECT count(*) FROM paper_position_events WHERE event_kind='RECORD'"
                    )
                ).scalar_one()
            )
            replacements = int(
                (
                    await session.execute(
                        "SELECT count(*) FROM paper_position_events WHERE event_kind='REPLACE'"
                    )
                ).scalar_one()
            )
            fills = int(
                (
                    await session.execute(
                        "SELECT count(*) FROM paper_order_events WHERE event_kind='FILL'"
                    )
                ).scalar_one()
            )
            return {
                "unchanged_cash": before == after,
                "records": records,
                "replacements": replacements,
                "fill_events": fills,
            }
    finally:
        await engine.dispose()


app.mount("/", production_app)
