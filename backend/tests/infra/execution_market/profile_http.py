"""NC12 authenticated HTTP intake using the production ASGI app and durable sessions."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, nullcontext
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_internal import activated_protocols, guard_database
from tests.infra.execution_market.profile_parent_poll import ParentPollGate
from tiewtrade.core.orders import BaseSize, OrderIntent, QuoteBudget
from tiewtrade.infra.auth import deadlines_for_new_session, issue, new_token
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders.dispatch import OrderCommand, get_order_command
from tiewtrade.services.api.app import app, lifespan
from tiewtrade.services.api.settings import CSRF_HEADER, SESSION_COOKIE


def order_body(owner: f15.OwnerState, intent: OrderIntent) -> dict[str, str]:
    result = {
        "expected_wallet_id": str(owner.wallet.wallet_id),
        "expected_episode_id": str(owner.wallet.episode_id),
        "base": intent.pair.base,
        "quote": intent.pair.quote,
        "side": intent.side.value,
        "kind": intent.kind.value,
    }
    if isinstance(intent.size, QuoteBudget):
        result["quote_budget"] = intent.size.amount.as_parts()["amount"]
    elif isinstance(intent.size, BaseSize):
        result["base_quantity"] = intent.size.quantity.as_parts()["quantity"]
    if intent.limit_price is not None:
        result["limit_price"] = intent.limit_price.as_parts()["amount"]
    if intent.time_in_force is not None:
        result["time_in_force"] = intent.time_in_force.value
    return result


class HttpIntake:
    def __init__(
        self,
        engine: AsyncEngine,
        clients: dict[UUID, AsyncClient],
        gate: ParentPollGate | None,
        output: Path,
    ) -> None:
        self.engine, self.clients, self.gate = engine, clients, gate
        # Test receipt references only; authoritative identities remain in PostgreSQL.
        self.orders: dict[tuple[UUID, UUID], UUID] = {}
        self.stream = (output / "http-intake.jsonl").open("w", encoding="utf-8")

    def order_id(self, owner: f15.OwnerState, key: UUID) -> UUID:
        return self.orders[owner.user_id, key]

    async def submit(self, owner: f15.OwnerState, intent: OrderIntent) -> OrderCommand:
        return await self.request(
            owner, "/paper/orders", intent.idempotency_key, order_body(owner, intent)
        )

    async def cancel(self, owner: f15.OwnerState, order_id: UUID, key: UUID) -> OrderCommand:
        return await self.request(
            owner,
            f"/paper/orders/{order_id}/cancel",
            key,
            {
                "expected_wallet_id": str(owner.wallet.wallet_id),
                "expected_episode_id": str(owner.wallet.episode_id),
            },
        )

    async def request(
        self, owner: f15.OwnerState, path: str, key: UUID, body: dict[str, str]
    ) -> OrderCommand:
        import json

        client = self.clients[owner.user_id]
        started = monotonic()
        record: dict[str, Any] = {"owner": str(owner.user_id), "key": str(key), "started": started}
        try:
            # No automatic POST retry or key replacement after any unknown result.
            async with asyncio.timeout(60):
                response = await client.post(path, json=body, headers={"Idempotency-Key": str(key)})
                record.update(http_status=response.status_code, acknowledged=monotonic())
                if response.status_code not in (200, 202):
                    raise RuntimeError(f"INTERNAL_HTTP_INTAKE_REJECTED_{response.status_code}")
                value = response.json()
                request_id = UUID(value["request_id"])
                record["request_id"] = str(request_id)
                while value["command_id"] is None:
                    if value["intake_state"] == "REJECTED":
                        raise RuntimeError("INTERNAL_HTTP_TRANSFER_REJECTED")
                    await asyncio.sleep(f15.RESULT_POLL_SECONDS)
                    async with (
                        self.gate.permit(owner.user_id, "http_request_result")
                        if self.gate is not None
                        else nullcontext()
                    ):
                        response = await client.get(f"/paper/order-requests/{request_id}")
                    if response.status_code != 200:
                        raise RuntimeError(f"INTERNAL_HTTP_RESULT_REJECTED_{response.status_code}")
                    value = response.json()
                command_id = UUID(value["command_id"])
                async with f15.poll_session(
                    self.engine, owner.user_id, "http_command", self.gate
                ) as session:
                    command = await get_order_command(session, command_id)
                    order_id = (
                        await session.execute(
                            "SELECT order_id FROM paper_order_commands WHERE id=:id",
                            {"id": command_id},
                        )
                    ).scalar_one()
                if command is None or str(order_id) != value["order_id"]:
                    raise RuntimeError("INTERNAL_HTTP_COMMAND_IDENTITY_MISMATCH")
                actual = UUID(value["order_id"])
                identity = (owner.user_id, key)
                if identity in self.orders and self.orders[identity] != actual:
                    raise RuntimeError("INTERNAL_HTTP_REPLAY_IDENTITY_CHANGED")
                self.orders[identity] = actual
                record.update(command_id=str(command_id), order_id=str(actual), outcome="RETURNED")
                return command
        except BaseException as error:
            record["outcome"] = type(error).__name__
            raise
        finally:
            record["finished"] = monotonic()
            # Never log cookies, headers, credentials, raw request/response or exception text.
            self.stream.write(json.dumps(record) + "\n")
            self.stream.flush()


@asynccontextmanager
async def internal_intake(
    owners: list[f15.OwnerState],
    *,
    engine: AsyncEngine,
    api: AsyncEngine,
    migrator: AsyncEngine,
    gate: ParentPollGate | None,
    output: Path,
) -> AsyncIterator[HttpIntake]:
    guard_database(dict(os.environ))
    auth = create_engine_for(DatabaseRole.AUTH)
    intake = None
    try:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(activated_protocols(migrator))
            # ASGI HTTP exercises real authentication/CSRF/routes; browser E2E separately
            # covers network/UI. No dependency overrides or test routes are installed.
            await stack.enter_async_context(lifespan(app))
            clients = {}
            for owner in owners:
                async with user_session(api, owner.user_id) as session:
                    await session.execute(
                        "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                        {"owner": owner.user_id},
                    )
                token, token_hash = new_token()
                async with user_session(auth, owner.user_id, role=DatabaseRole.AUTH) as session:
                    now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                    deadlines = deadlines_for_new_session(now)
                    await issue(
                        session,
                        token_hash=token_hash,
                        idle_expires_at=deadlines.idle_expires_at,
                        absolute_expires_at=deadlines.absolute_expires_at,
                    )
                client = await stack.enter_async_context(
                    AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="https://internal-paper.test",
                        timeout=60,
                    )
                )
                client.cookies.set(SESSION_COOKIE, token)
                csrf = await client.get("/auth/csrf")
                if csrf.status_code != 200:
                    raise RuntimeError("INTERNAL_HTTP_CSRF_FAILED")
                client.headers[CSRF_HEADER] = csrf.json()["csrf_token"]
                who = await client.get("/auth/me")
                if who.status_code != 200 or who.json()["user_id"] != str(owner.user_id):
                    raise RuntimeError("INTERNAL_HTTP_AUTH_FAILED")
                clients[owner.user_id] = client
            intake = HttpIntake(engine, clients, gate, output)
            f15.save(
                output / "http-composition.json",
                {
                    "transport": "production ASGI HTTP",
                    "api_instances": 1,
                    "clients": len(clients),
                    "policy": "TransactionalRiskPolicy",
                    "risk_setting": "UNSET per original Paper fixture",
                    "dependency_overrides": False,
                },
            )
            yield intake
    finally:
        if intake is not None:
            intake.stream.close()
        await auth.dispose()
