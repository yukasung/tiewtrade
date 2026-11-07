"""HTTP transport preserves the five-command oracle and fails without automatic POST retries."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, MockTransport, Request, Response
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_http import HttpIntake, order_body
from tiewtrade.core.orders import OrderStatus
from tiewtrade.infra.paper_orders.dispatch import OrderCommand
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot
from tiewtrade.services.api.manual_order_models import NewOrderInput


def owner() -> f15.OwnerState:
    return f15.OwnerState(
        uuid4(), cast(PaperWalletSnapshot, SimpleNamespace(wallet_id=uuid4(), episode_id=uuid4()))
    )


@pytest.mark.parametrize("factory", [f15.market_buy, f15.limit_sell, f15.market_sell])
def test_wire_amounts_validate_against_production_schema(factory: Any) -> None:
    current = owner()
    intent = factory(current, uuid4(), 0)
    body = order_body(current, intent)
    parsed: Any = TypeAdapter(NewOrderInput).validate_python(body)
    assert parsed.expected_episode_id == current.wallet.episode_id
    assert body["base"] == "BTC" and body["quote"] == "USDT"
    assert all(isinstance(value, str) for value in body.values())


@pytest.mark.parametrize("failure", [None, "reject", "unknown", "identity"])
async def test_http_request_records_no_secrets_and_does_not_retry_post(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str | None
) -> None:
    current = owner()
    command_id, order_id, request_id = uuid4(), uuid4(), uuid4()
    sent = []

    async def handle(request: Request) -> Response:
        sent.append(request.method)
        if failure == "unknown":
            raise TimeoutError("private-payload-must-not-be-recorded")
        return Response(
            503 if failure == "reject" else 202,
            json={
                "request_id": str(request_id),
                "order_id": str(order_id),
                "command_id": str(command_id),
                "intake_state": "TRANSFERRED",
            },
        )

    @asynccontextmanager
    async def session(*args: Any, **kwargs: Any) -> Any:
        yield SimpleNamespace(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    scalar_one=lambda: uuid4() if failure == "identity" else order_id
                )
            )
        )

    monkeypatch.setattr(f15, "poll_session", session)
    monkeypatch.setattr(
        "tests.infra.execution_market.profile_http.get_order_command",
        AsyncMock(return_value=OrderCommand(command_id, "SUCCEEDED")),
    )
    async with AsyncClient(
        transport=MockTransport(handle), base_url="https://internal.test"
    ) as client:
        client.headers["X-CSRF-Token"] = "private-token"
        transport = HttpIntake(
            cast(AsyncEngine, object()), {current.user_id: client}, None, tmp_path
        )
        intent = f15.market_buy(current, uuid4(), 0)
        try:
            if failure is None:
                result = await transport.submit(current, intent)
                assert result.command_id == command_id
                assert transport.order_id(current, intent.idempotency_key) == order_id
            else:
                with pytest.raises(TimeoutError if failure == "unknown" else RuntimeError):
                    await transport.submit(current, intent)
        finally:
            transport.stream.close()
    assert sent == ["POST"]
    evidence = (tmp_path / "http-intake.jsonl").read_text()
    assert "private" not in evidence
    assert json.loads(evidence)["outcome"] == (
        "RETURNED"
        if failure is None
        else "TimeoutError"
        if failure == "unknown"
        else "RuntimeError"
    )


async def test_cycle_uses_server_order_identity_for_replay_and_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = owner()
    identities: dict[UUID, UUID] = {}
    submissions = []
    cancellations = []

    class Sender:
        def order_id(self, owner: f15.OwnerState, key: Any) -> Any:
            return identities[key]

        async def submit(self, owner: f15.OwnerState, intent: Any) -> OrderCommand:
            identities.setdefault(intent.idempotency_key, uuid4())
            submissions.append(intent)
            return OrderCommand(uuid4(), "SUCCEEDED")

        async def cancel(self, owner: f15.OwnerState, order_id: Any, key: Any) -> OrderCommand:
            cancellations.append(order_id)
            return OrderCommand(uuid4(), "SUCCEEDED")

    async def command(
        engine: Any, owner_id: Any, value: OrderCommand, **kwargs: Any
    ) -> OrderCommand:
        return value

    wait = AsyncMock()
    monkeypatch.setattr(f15, "wait_command", command)
    monkeypatch.setattr(f15, "wait_status", wait)
    counters = f15.Counters()
    await f15.cycle(cast(AsyncEngine, object()), current, uuid4(), 0, counters, [], sender=Sender())
    assert counters == f15.Counters(
        offered=5, admitted=5, completed=5, fills=2, cancels=1, replays=1, cycles=1
    )
    resting, replay = submissions[1:3]
    actual = identities[resting.idempotency_key]
    assert resting.order_id != actual and replay.order_id == actual
    assert cancellations == [actual]
    assert wait.await_args_list[1].args[2:4] == (actual, OrderStatus.ACCEPTED)


@pytest.mark.usefixtures("internal_database")
async def test_real_authenticated_cycle_and_owner_isolation(
    api_engine: AsyncEngine,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    import asyncio

    from tests.infra.execution_market.profile_http import internal_intake
    from tiewtrade.infra.db import DatabaseRole, create_engine_for
    from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy

    owners = await f15.seed_owners(api_engine, engine_engine, scan_engine, 2)
    source = create_engine_for(DatabaseRole.MARKET_DATA)
    stop = asyncio.Event()
    worker_stop = tmp_path / "stop"
    publisher = worker = None
    try:
        async with internal_intake(
            owners,
            engine=engine_engine,
            api=api_engine,
            migrator=migrator_engine,
            gate=None,
            output=tmp_path,
        ) as intake:
            publisher = asyncio.create_task(
                f15.market_publisher(source, stop, {"target_hz": 10}, heartbeat_per_book=True)
            )
            worker = asyncio.create_task(
                f15.run_worker_process(
                    "internal-http-safety",
                    worker_stop,
                    tmp_path / "worker.json",
                    claim_limit=1,
                    coordinate_claims=True,
                    policy=TransactionalRiskPolicy(),
                    manual_intake=True,
                    protection_rounds=True,
                )
            )
            await asyncio.sleep(0.3)
            counters = f15.Counters()
            async with asyncio.timeout(60):
                await f15.with_publisher(
                    f15.cycle(engine_engine, owners[0], uuid4(), 0, counters, [], sender=intake),
                    publisher,
                )
            assert counters.completed == 5 and counters.replays == 1
            assert all(
                row["passed"]
                for row in await f15.verify(
                    engine_engine, [owners[0]], baseline_orders=0, cycles_per_owner=1
                )
            )
            record = json.loads((tmp_path / "http-intake.jsonl").read_text().splitlines()[0])
            foreign = await intake.clients[owners[1].user_id].get(
                f"/paper/order-requests/{record['request_id']}"
            )
            assert foreign.status_code == 404
            client = intake.clients[owners[0].user_id]
            client.headers.pop("X-CSRF-Token")
            rejected = await client.post(
                "/paper/orders",
                json=order_body(owners[0], f15.market_buy(owners[0], uuid4(), 1)),
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert rejected.status_code == 403
    finally:
        worker_stop.touch()
        if worker is not None:
            await asyncio.wait_for(worker, 10)
        stop.set()
        if publisher is not None:
            await publisher
        await source.dispose()
