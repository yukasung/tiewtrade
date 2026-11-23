"""F-21 real API read-only protection and flat replacement contracts."""

import asyncio
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.api.conftest import csrf_headers, register
from tests.api.test_protection_routes import enable
from tests.api.test_protection_routes import restore_protocol as restore_protocol
from tests.infra.execution_market.conftest import (
    _internal_database_template as _internal_database_template,
)
from tests.infra.execution_market.conftest import (
    internal_database as internal_database,
)
from tests.infra.execution_market.conftest import (
    internal_database_factory as internal_database_factory,
)
from tests.infra.execution_market.test_bot_indicator_inputs import seed_prepared
from tests.infra.execution_market.test_strategy_baskets import entry, f21_run
from tests.infra.positions.conftest import create_production_wallet
from tests.infra.risk_limits.test_execution import runtime
from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.services.api.app import app
from tiewtrade.services.engine.bot import StrategyRegistry, run_bot_control_round


@pytest.fixture
def client(internal_database: None) -> Iterator[TestClient]:
    """The status test owns market/indicator/accounting state, including its API pools."""
    with TestClient(app) as started:
        started.get("/auth/csrf")
        yield started


@pytest.mark.parametrize("has_inventory", [False, True])
def test_status_offers_replacement_only_when_flat_and_keeps_managed_tp_readonly(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    has_inventory: bool,
) -> None:
    register(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    enable()
    monkeypatch.setattr(app.state, "bot_f21_enabled", True, raising=False)

    async def check() -> None:
        roles = (
            DatabaseRole.API,
            DatabaseRole.ENGINE,
            DatabaseRole.ENGINE_SCAN,
            DatabaseRole.MIGRATOR,
        )
        api, engine, scan, migrator = [create_engine_for(role) for role in roles]
        try:
            wallet = await create_production_wallet(api, engine, scan, owner)
            async with runtime(
                api, engine, migrator, owner, wallet, limit="1000", account_use="BOT"
            ) as source:
                old = await f21_run(engine, owner, wallet)
                group_id = None
                if has_inventory:
                    # Entry injects a signal at accounting commit; retain the real F11
                    # authority required at queued admission, as in basket fixtures.
                    async with migrator.begin() as connection:
                        await connection.execute(text("SELECT activate_indicator_source_proof()"))
                        at: datetime = (
                            await connection.execute(text("SELECT clock_timestamp()"))
                        ).scalar_one()
                    await seed_prepared(migrator, 2, at, timeframe=Timeframe.M5)
                    _, group_id = await entry(engine, owner, wallet, old, source)
                async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                    await session.execute(
                        "UPDATE bot_runs SET status='STOPPED',revision=revision+1 WHERE id=:id",
                        {"id": old},
                    )
                response = client.get("/paper/bots/status")
                assert response.status_code == 200, response.text
                status = response.json()
                assert status["run_id"] == str(old) and status["status"] == "STOPPED"
                assert status["pinned_configuration"]["capital_per_entry"] == "100"
                assert status["can_start"] is (not has_inventory)
                if has_inventory:
                    assert status["replacement"] is None
                    rows = client.get(f"/paper/protections?episode_id={wallet.episode_id}")
                    assert rows.status_code == 200, rows.text
                    protection = rows.json()["protections"][0]
                    assert protection["strategy_managed"] is True
                    payload = {
                        "expected_wallet_id": str(wallet.wallet_id),
                        "expected_episode_id": str(wallet.episode_id),
                        "expected_revision": protection["revision"],
                        "quantity": protection["quantity"],
                        "take_profit_price": "120",
                    }
                    refusal = client.post(
                        f"/paper/protections/{group_id}/replace",
                        json=payload,
                        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
                    )
                    assert refusal.status_code == 409 and refusal.json() == {
                        "detail": "ORDER_CONFLICT"
                    }
                else:
                    proof = status["replacement"]
                    assert proof["run_id"] == str(old) and proof["stop_id"] is None
                    config = client.post(
                        "/paper/bots/configurations",
                        json={
                            "base": "BTC",
                            "capital_per_entry": "17.000000000000000001",
                            "max_entries": 3,
                        },
                        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
                    )
                    assert config.status_code == 200
                    start = client.post(
                        "/paper/bots/requests",
                        json={
                            "strategy_config_ref": config.json()["reference"],
                            "replacement": proof,
                        },
                        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
                    )
                    assert start.status_code == 202
                    result = await run_bot_control_round(
                        engine=engine, scan_engine=scan, registry=StrategyRegistry(enable_f21=True)
                    )
                    assert result.applied == 1 and result.refused == 0
                    async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                        assert (
                            await session.execute(
                                "SELECT status FROM bot_runs WHERE id=:id", {"id": old}
                            )
                        ).scalar_one() == "RETIRED"
                    current = client.get("/paper/bots/status").json()
                    assert current["run_id"] != str(old) and current["status"] == "STARTING"
                    assert (
                        current["pinned_configuration"]["capital_per_entry"]
                        == "17.000000000000000001"
                    )
        finally:
            for resource in (api, engine, scan, migrator):
                await resource.dispose()

    asyncio.run(check())
