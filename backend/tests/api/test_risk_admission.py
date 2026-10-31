"""Actual transaction risk composition in an isolated, explicitly activated test DB."""

import asyncio
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.api.conftest import csrf_headers
from tests.api.test_manual_order_routes import buy, wallet_for
from tests.infra.execution_market.test_worker import ready_public_sources
from tests.infra.risk_limits.test_worker import claim
from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot, renew_writer, set_connected
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.risk_limits.requests import receipt_by_key
from tiewtrade.infra.risk_limits.storage import process_request
from tiewtrade.services.api.app import app
from tiewtrade.services.api.manual_order_routes import manual_admission_policy
from tiewtrade.services.engine.risk_limit import run_risk_monitor_round


async def configure(owner: UUID, *, enabled: bool) -> None:
    migrator = create_engine_for(DatabaseRole.MIGRATOR)
    market = None
    api = create_engine_for(DatabaseRole.API)
    try:
        if enabled:
            market, _, _, _ = await ready_public_sources()
            async with user_session(api, owner) as session:
                await session.execute(
                    "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                    {"owner": owner},
                )
        async with migrator.begin() as connection:
            await connection.execute(
                text(
                    """UPDATE risk_protocol_control SET publication_enabled=:enabled,
                financial_enabled=:enabled,admission_enabled=:enabled"""
                ),
                {"enabled": enabled},
            )
        if enabled:
            assert market is not None
            async with market_data_session(market) as session:
                snapshot = await read_snapshot(session)
                assert snapshot.feed is not None
                await renew_writer(session, snapshot.feed)
    finally:
        await migrator.dispose()
        await api.dispose()
        if market is not None:
            await market.dispose()


async def apply_limit(owner: UUID, key: UUID) -> None:
    api, engine = create_engine_for(DatabaseRole.API), create_engine_for(DatabaseRole.ENGINE)
    try:
        async with user_session(api, owner) as session:
            receipt = await receipt_by_key(session, TradingMode.PAPER, key)
        assert receipt is not None
        token = await claim(engine, owner, receipt)
        async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
            await process_request(session, token)
    finally:
        await api.dispose()
        await engine.dispose()


@pytest.fixture
def risk_composition(client: TestClient) -> Iterator[tuple[UUID, dict[str, object]]]:
    wallet = wallet_for(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    try:
        asyncio.run(configure(owner, enabled=True))
        key = uuid4()
        response = client.post(
            "/paper/risk-limit",
            json={
                "expected_revision": 0,
                "expected_wallet_id": wallet["wallet_id"],
                "expected_episode_id": wallet["episode_id"],
                "amount": "100",
            },
            headers={**csrf_headers(client), "Idempotency-Key": str(key)},
        )
        assert response.status_code == 202, response.text
        asyncio.run(apply_limit(owner, key))
        assert client.get("/paper/risk-limit").json()["reason"] == "READY"
        app.dependency_overrides[manual_admission_policy] = lambda: TransactionalRiskPolicy()
        yield owner, wallet
    finally:
        app.dependency_overrides.pop(manual_admission_policy, None)
        asyncio.run(configure(owner, enabled=False))


def test_http_intake_uses_actual_owner_risk_evidence(
    client: TestClient,
    risk_composition: tuple[UUID, dict[str, object]],
) -> None:
    _, wallet = risk_composition
    snapshot = client.get("/paper/trade?base=BTC")
    assert snapshot.status_code == 200 and snapshot.json()["admission_ready"], snapshot.text
    response = client.post(
        "/paper/orders",
        json=buy(wallet),
        headers={
            **csrf_headers(client),
            "Idempotency-Key": str(uuid4()),
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["intake_state"] == "PENDING"
    assert response.json()["command_state"] is None


def test_paper_manual_intake_allows_an_unset_optional_limit(client: TestClient) -> None:
    wallet = wallet_for(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    try:
        asyncio.run(configure(owner, enabled=True))
        app.dependency_overrides[manual_admission_policy] = lambda: TransactionalRiskPolicy()
        snapshot = client.get("/paper/trade?base=BTC")
        assert snapshot.status_code == 200, snapshot.text
        assert snapshot.json()["admission_ready"]
        assert "RISK_LIMIT_UNSET" not in snapshot.json()["admission_reasons"]
        response = client.post(
            "/paper/orders",
            json=buy(wallet),
            headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 202, response.text

        async def count_risk_rows() -> tuple[int, int, int]:
            api = create_engine_for(DatabaseRole.API)
            try:
                async with user_session(api, owner) as session:
                    return (
                        int(
                            (
                                await session.execute(
                                    "SELECT count(*) FROM risk_limit_settings WHERE user_id=:owner",
                                    {"owner": owner},
                                )
                            ).scalar_one()
                        ),
                        int(
                            (
                                await session.execute(
                                    "SELECT count(*) FROM risk_limit_evaluations "
                                    "WHERE user_id=:owner",
                                    {"owner": owner},
                                )
                            ).scalar_one()
                        ),
                        int(
                            (
                                await session.execute(
                                    "SELECT count(*) FROM risk_limit_baselines "
                                    "WHERE user_id=:owner",
                                    {"owner": owner},
                                )
                            ).scalar_one()
                        ),
                    )
            finally:
                await api.dispose()

        assert asyncio.run(count_risk_rows()) == (0, 0, 0)

    finally:
        app.dependency_overrides.pop(manual_admission_policy, None)
        asyncio.run(configure(owner, enabled=False))


def test_price_disconnect_refusal_commits_one_durable_evaluation_hint(
    client: TestClient,
    risk_composition: tuple[UUID, dict[str, object]],
) -> None:
    owner, wallet = risk_composition

    async def disconnect() -> None:
        market = create_engine_for(DatabaseRole.MARKET_DATA)
        try:
            async with market_data_session(market) as session:
                snapshot = await read_snapshot(session)
                assert snapshot.feed is not None
                await set_connected(session, snapshot.feed, False)
        finally:
            await market.dispose()

    asyncio.run(disconnect())
    key = uuid4()
    for _ in range(2):
        response = client.post(
            "/paper/orders",
            json=buy(wallet),
            headers={
                **csrf_headers(client),
                "Idempotency-Key": str(key),
            },
        )
        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "RISK_PRICE_UNAVAILABLE"
    snapshot = client.get("/paper/trade?base=BTC").json()
    assert not snapshot["admission_ready"]
    assert "ORDER_PRICE_UNAVAILABLE" in snapshot["admission_reasons"]

    async def verify() -> None:
        api = create_engine_for(DatabaseRole.API)
        engine, scan = (
            create_engine_for(DatabaseRole.ENGINE),
            create_engine_for(DatabaseRole.ENGINE_SCAN),
        )
        try:
            async with user_session(api, owner) as session:
                assert (
                    await session.execute("SELECT count(*) FROM risk_evaluation_requests")
                ).scalar_one() == 1
                assert (
                    await session.execute("SELECT count(*) FROM paper_order_requests")
                ).scalar_one() == 0
            result = await run_risk_monitor_round(
                engine=engine, scan_engine=scan, limit=1, after_owner=UUID(int=owner.int - 1)
            )
            assert result.processed == 1 and result.next_owner == owner
            async with user_session(api, owner) as session:
                assert (
                    await session.execute("SELECT count(*) FROM risk_evaluation_results")
                ).scalar_one() == 1
        finally:
            await api.dispose()
            await engine.dispose()
            await scan.dispose()

    asyncio.run(verify())
