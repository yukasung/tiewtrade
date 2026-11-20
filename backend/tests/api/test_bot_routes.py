"""F-20 owner, mode and session contracts on the real API."""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import csrf_headers, register
from tiewtrade.core.orders import TradingMode
from tiewtrade.infra.bots.requests import submit_start
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session


def test_bot_start_stays_closed_without_capabilities(client: TestClient) -> None:
    assert client.get("/paper/bots/status").status_code == 401
    register(client)
    key = str(uuid4())
    for mode, reason in (
        ("paper", "BOT_STRATEGY_UNAVAILABLE"),
        ("live", "LIVE_EXECUTION_UNAVAILABLE"),
    ):
        status = client.get(f"/{mode}/bots/status")
        assert status.status_code == 200
        assert status.json()["mode"] == mode.upper()
        assert status.json()["can_start"] is False
        assert status.json()["unavailable_reason"] == reason
        forbidden = client.post(
            f"/{mode}/bots/requests",
            json={"strategy_config_ref": "missing"},
            headers={"Idempotency-Key": key},
        )
        assert forbidden.status_code == 403
        refused = client.post(
            f"/{mode}/bots/requests",
            json={"strategy_config_ref": "missing"},
            headers={**csrf_headers(client), "Idempotency-Key": key},
        )
        assert refused.status_code == 503
        assert refused.json() == {"detail": reason}
        assert client.get(f"/{mode}/bots/requests/by-key/{key}").status_code == 404


def test_receipt_lookup_preserves_owner_and_mode_scope(client: TestClient) -> None:
    register(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    key, request_id = uuid4(), uuid4()

    async def seed() -> None:
        engine = create_engine_for(DatabaseRole.API)
        try:
            async with user_session(engine, owner) as session:
                await submit_start(
                    session,
                    mode=TradingMode.PAPER,
                    request_id=request_id,
                    key=key,
                    payload={"strategy_config_ref": "test"},
                )
        finally:
            await engine.dispose()

    asyncio.run(seed())
    assert client.get(f"/paper/bots/requests/by-key/{key}").json()["request_id"] == str(request_id)
    assert client.get(f"/paper/bots/requests/{request_id}").json()["key"] == str(key)
    assert client.get(f"/live/bots/requests/by-key/{key}").status_code == 404
    client.cookies.clear()
    client.get("/auth/csrf")
    register(client)
    assert client.get(f"/paper/bots/requests/by-key/{key}").status_code == 404
    assert client.get(f"/paper/bots/requests/{request_id}").status_code == 404


def test_enabled_paper_intake_recovers_the_same_receipt_and_rejects_key_conflict(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tiewtrade.services.api.app import app

    register(client)
    monkeypatch.setattr(
        app.state, "bot_paper_configurations", frozenset({"reviewed-v1"}), raising=False
    )
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    payload = {"strategy_config_ref": "reviewed-v1"}
    first = client.post("/paper/bots/requests", json=payload, headers=headers)
    assert first.status_code == 202
    assert first.json()["pending"]
    pending = client.get("/paper/bots/status").json()
    assert pending["pending_request_id"] == first.json()["request_id"]
    assert pending["status"] is None and pending["can_start"] is False
    assert client.get("/live/bots/status").json()["pending_request_id"] is None
    recovered = client.get(f"/paper/bots/requests/by-key/{key}")
    assert recovered.json() == first.json()
    replay = client.post("/paper/bots/requests", json=payload, headers=headers)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    conflict = client.post(
        "/paper/bots/requests", json={"strategy_config_ref": "other-v1"}, headers=headers
    )
    assert conflict.status_code == 409
    assert client.post("/live/bots/requests", json=payload, headers=headers).status_code == 503


def test_status_reads_current_episode_exposure_under_owner_rls(client: TestClient) -> None:
    from tests.api.test_manual_order_routes import wallet_for

    wallet = wallet_for(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    run = uuid4()

    async def seed() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
                       strategy_version,configuration_version,state_version,configuration,
                       strategy_state,status) VALUES(:id,:owner,'PAPER',:wallet,:episode,
                       'private-fixture',1,1,1,'{}','{}','STOPPED')""",
                    {
                        "id": run,
                        "owner": owner,
                        "wallet": UUID(str(wallet["wallet_id"])),
                        "episode": UUID(str(wallet["episode_id"])),
                    },
                )
        finally:
            await engine.dispose()

    asyncio.run(seed())
    response = client.get("/paper/bots/status")
    assert response.status_code == 200, response.text
    assert response.json()["run_id"] == str(run)
    assert response.json()["exposure_available"] is True
    assert response.json()["positions"] == []
    assert response.json()["protections"] == []
    assert "configuration" not in response.json()
    assert client.get("/live/bots/status").json()["run_id"] is None
    client.cookies.clear()
    client.get("/auth/csrf")
    register(client)
    other = client.get("/paper/bots/status").json()
    assert other["run_id"] is None and other["positions"] == [] and other["protections"] == []


def test_status_bounds_allocations_and_keeps_failed_protection_visible(client: TestClient) -> None:
    from dataclasses import replace

    from tests.api.test_manual_order_routes import wallet_for
    from tests.api.test_protection_routes import enable, seed_protection
    from tiewtrade.core.money import Money, Quantity
    from tiewtrade.core.orders import OrderOrigin, OrderScope
    from tiewtrade.core.positions import PositionPair
    from tiewtrade.core.protections import Protection, ProtectionPrices, ProtectionState
    from tiewtrade.infra.protections.storage import create, load, save

    wallet = wallet_for(client)
    try:
        original = UUID(seed_protection(client))
        owner = UUID(client.get("/auth/me").json()["user_id"])
        failed = uuid4()

        async def seed() -> None:
            engine = create_engine_for(DatabaseRole.ENGINE)
            try:
                async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                    group = await load(session, original)
                    assert group is not None
                    await save(
                        session,
                        group,
                        replace(
                            group.value,
                            state=ProtectionState.CANCELED,
                            quantity=Quantity.of(0, "BTC"),
                            revision=group.value.revision + 1,
                        ),
                        kind="CANCEL",
                        disposed=group.disposed + group.value.quantity,
                    )
                    await session.execute(
                        """INSERT INTO bot_runs(id,user_id,mode,wallet_id,episode_id,strategy_name,
                           strategy_version,configuration_version,state_version,configuration,
                           strategy_state,status) VALUES(:run,:owner,'PAPER',:wallet,:episode,
                           'status-fixture',1,1,1,'{}','{}','STOPPED')""",
                        {
                            "run": uuid4(),
                            "owner": owner,
                            "wallet": UUID(str(wallet["wallet_id"])),
                            "episode": UUID(str(wallet["episode_id"])),
                        },
                    )
                    for index in range(21):
                        protection = Protection(
                            failed if index == 20 else uuid4(),
                            OrderScope(owner, UUID(str(wallet["episode_id"])), TradingMode.PAPER),
                            OrderOrigin.MANUAL,
                            ProtectionPrices(
                                PositionPair("BTC", "USDT"), stop_loss=Money.of(90, "USDT")
                            ),
                            Quantity.of("0.01", "BTC"),
                            ProtectionState.FAILED if index == 20 else ProtectionState.ARMED,
                        )
                        await create(session, protection, UUID(str(wallet["wallet_id"])))
            finally:
                await engine.dispose()

        asyncio.run(seed())
        response = client.get("/paper/bots/status")
        assert response.status_code == 200, response.text
        status = response.json()
        assert len(status["protections"]) == 20 and status["protections_more"] is True
        assert str(failed) in {row["protection_id"] for row in status["protections"]}
        assert status["positions"][0]["quantity"] == "0.999"
        # F-17 still discovers every record through its bounded cursor pages.
        cursor = None
        seen: set[str] = set()
        while True:
            page = client.get(
                "/paper/protections",
                params={
                    "episode_id": str(wallet["episode_id"]),
                    **({} if cursor is None else {"cursor": cursor}),
                },
            )
            assert page.status_code == 200, page.text
            seen.update(row["protection_id"] for row in page.json()["protections"])
            cursor = page.json()["next_cursor"]
            if cursor is None:
                break
        assert len(seen) == 22
    finally:
        enable(False)
