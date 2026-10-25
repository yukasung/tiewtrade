"""F-16 isolated browser composition: real DB/API/bridge/F-15, recorded book, test policy.

Never imported by production. No endpoint below is mounted on the production app.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from tests.infra.execution_market.test_worker import AllowPolicy, ready_public_sources
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel
from tiewtrade.infra.audit import AuditAction
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.order_book_storage import publish_input, renew_book_writer
from tiewtrade.infra.paper_orders import requests as request_storage
from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order
from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
from tiewtrade.infra.paper_orders.request_worker import process_request
from tiewtrade.infra.paper_orders.requests import ManualRequest
from tiewtrade.infra.paper_orders.views import request_view
from tiewtrade.infra.paper_orders.worker import process_claimed_order
from tiewtrade.infra.paper_wallet import PaperWalletAction, admit_command
from tiewtrade.services.api.app import app as production_app
from tiewtrade.services.api.app import lifespan as production_lifespan
from tiewtrade.services.api.manual_order_routes import manual_admission_policy
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

_disconnect_owner: UUID | None = None
_disconnect_pid: int | None = None


def guard() -> None:
    name = os.environ.get("TIEWTRADE_E2E_DATABASE_NAME", "")
    if not name.startswith("tiewtrade_e2e"):
        raise RuntimeError("E2E_DATABASE_REJECTED")
    for role in ("API", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"):
        url = urlparse(os.environ.get(f"TIEWTRADE_DATABASE_URL_{role}", ""))
        if url.hostname not in ("127.0.0.1", "localhost", "::1") or url.path != f"/{name}":
            raise RuntimeError("E2E_DATABASE_REJECTED")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    guard()
    original_audit = request_storage.request_audit

    async def audited(
        session: UserSession,
        request: ManualRequest,
        *,
        action: AuditAction,
        command_id: UUID | None = None,
        failure_code: str | None = None,
    ) -> None:
        global _disconnect_owner, _disconnect_pid
        await original_audit(
            session, request, action=action, command_id=command_id, failure_code=failure_code
        )
        if session.user_id == _disconnect_owner and action is AuditAction.PAPER_ORDER_REQUESTED:
            _disconnect_owner = None
            _disconnect_pid = int((await session.execute("SELECT pg_backend_pid()")).scalar_one())
            # Terminate only this API connection, with its real inbox/audit transaction open.
            await session.execute("SELECT pg_terminate_backend(pg_backend_pid())")

    request_storage.request_audit = audited
    production_app.dependency_overrides[manual_admission_policy] = lambda: AllowPolicy()
    try:
        async with production_lifespan(production_app):
            yield
    finally:
        request_storage.request_audit = original_audit
        production_app.dependency_overrides.pop(manual_admission_policy, None)


app = FastAPI(lifespan=lifespan)


class Owner(BaseModel):
    user_id: UUID


class Drive(Owner):
    request_id: UUID
    fill: bool = False


@app.post("/__e2e/manual/disconnect-before-commit", status_code=204)
async def disconnect_before_commit(body: Owner) -> None:
    global _disconnect_owner, _disconnect_pid
    _disconnect_owner = body.user_id
    _disconnect_pid = None


@app.get("/__e2e/manual/disconnect-result")
async def disconnect_result() -> dict[str, str | None]:
    if _disconnect_pid is None:
        return {"result": None}
    engine = create_engine_for(DatabaseRole.ENGINE)
    try:
        async with engine.connect() as connection:
            alive: int = (
                await connection.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE pid=:pid"),
                    {"pid": _disconnect_pid},
                )
            ).scalar_one()
        return {"result": "CONNECTION_TERMINATED" if alive == 0 else "NOT_DISCONNECTED"}
    finally:
        await engine.dispose()


@app.post("/__e2e/manual/prepare", status_code=204)
async def prepare(body: Owner) -> None:
    api = create_engine_for(DatabaseRole.API)
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
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
        await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="browser-wallet")
        market, _, _, _ = await ready_public_sources()
        await market.dispose()
    finally:
        await api.dispose()
        await engine.dispose()
        await scan.dispose()


@app.post("/__e2e/manual/wallet-round", status_code=204)
async def wallet_round() -> None:
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    try:
        await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="browser-reset")
    finally:
        await engine.dispose()
        await scan.dispose()


@app.post("/__e2e/manual/source", status_code=204)
async def source() -> None:
    market, _, _, _ = await ready_public_sources()
    await market.dispose()


@app.post("/__e2e/manual/drive")
async def drive(body: Drive) -> dict[str, object]:
    engine = create_engine_for(DatabaseRole.ENGINE)
    market, lease, book, metadata = await ready_public_sources()
    try:
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            due_at = (
                await session.execute(
                    "SELECT next_attempt_at FROM paper_order_request_dispatch WHERE request_id=:id",
                    {"id": body.request_id},
                )
            ).scalar_one()
            claim = await claim_request(
                session, DueRequest(body.request_id, body.user_id, due_at), worker="browser-bridge"
            )
        if claim is not None:
            async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
                await process_request(session, claim, policy=AllowPolicy())
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            value = await request_view(session, body.request_id)
            assert value is not None and value.command_id is not None
            command_id = value.command_id
            is_limit = value.request.payload.get("kind") == "LIMIT"

        async def execute() -> None:
            async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    "UPDATE paper_order_dispatch SET next_attempt_at=clock_timestamp() "
                    "WHERE command_id=:id AND state='PENDING'",
                    {"id": command_id},
                )
                due = (
                    await session.execute(
                        "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                        {"id": command_id},
                    )
                ).scalar_one()
                order_claim = await claim_order(
                    session, DueOrder(command_id, body.user_id, due), worker="browser-f15"
                )
            if order_claim is not None:
                async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
                    await process_claimed_order(session, order_claim, policy=AllowPolicy())

        await execute()
        if body.fill:
            # The prior MARKET BUY consumed ten BTC at100. Recorded replenishment
            # adds ten fresh BTC, so the11-BTC LIMIT partially fills without reusing debt.
            if is_limit:
                book = replace(
                    book,
                    asks=(BookLevel(Money.of(100, "USDT"), Quantity.of(20, "BTC")), *book.asks[1:]),
                )
            # F-15 deliberately excludes inputs inside the admission latency window.
            await asyncio.sleep(0.12)
            async with market_data_session(market) as market_session:
                lease = await renew_book_writer(market_session, lease)
                now = (await market_session.execute("SELECT clock_timestamp()")).scalar_one()
                await publish_input(
                    market_session,
                    lease,
                    replace(
                        book,
                        input_id=lease.last_input_id + 1,
                        received_at=now,
                        verified_at=now,
                        rebase=False,
                    ),
                    metadata,
                )
            await asyncio.sleep(0.03)
            await execute()
        async with user_session(engine, body.user_id, role=DatabaseRole.ENGINE) as session:
            # DB assertions are independent of the browser's displayed state.
            rows = (
                await session.execute(
                    "SELECT count(*) FROM paper_order_commands WHERE idempotency_key="
                    "(SELECT idempotency_key FROM paper_order_requests WHERE id=:id)",
                    {"id": body.request_id},
                )
            ).scalar_one()
            current = await request_view(session, body.request_id)
            assert current is not None
            return {
                "commands": rows,
                "order_state": current.order_state,
                "command_state": current.command_state,
                "failure": current.command_failure_code,
            }
    finally:
        await engine.dispose()
        await market.dispose()


app.mount("/", production_app)
