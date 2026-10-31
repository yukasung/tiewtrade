"""F-08 HTTP contract: authentication, CSRF, ownership and rollback."""

from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from tests.api.conftest import csrf_headers, register
from tests.api.test_totp_flow import enable_totp
from tiewtrade.infra.api_keys import store_key
from tiewtrade.infra.crypto import KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session


def owner(client: TestClient) -> UUID:
    return UUID(client.get("/auth/me").json()["user_id"])


def seed_key(user_id: UUID, *, active: bool = True, public: str | None = None) -> UUID:
    async def seed() -> UUID:
        api = create_engine_for(DatabaseRole.API)
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(api, user_id) as session:
                key_id = await store_key(
                    session,
                    KeySource.from_environment(KeyPurpose.VENUE_API_SECRET),
                    user_id=user_id,
                    label="fixture " + uuid4().hex,
                    key_public=public if public is not None else "fixture-" + uuid4().hex,
                    secret="fixture-only-not-a-real-secret",
                )
            if active:
                async with user_session(engine, user_id, role=DatabaseRole.ENGINE) as session:
                    await session.execute(
                        "UPDATE user_api_keys SET status='ACTIVE', "
                        "verified_at=clock_timestamp() WHERE id=:id",
                        {"id": key_id},
                    )
            return key_id
        finally:
            await api.dispose()
            await engine.dispose()

    return asyncio.get_event_loop().run_until_complete(seed())


def select(client: TestClient, use: str = "MANUAL") -> Response:
    return cast(
        Response,
        client.post(
            "/trading-account/use",
            json={"use": use},
            headers=csrf_headers(client),
        ),
    )


def test_summary_requires_session(client: TestClient) -> None:
    assert client.get("/trading-account").status_code == 401


def test_before_selection_has_no_default_or_key(client: TestClient) -> None:
    register(client)
    assert client.get("/trading-account").json() == {
        "use": None,
        "key": None,
        "may_trade": False,
        "may_change_use": False,
    }


def test_account_summary_is_isolated_from_the_previous_owner(client: TestClient) -> None:
    from tests.api.test_totp_flow import sign_out

    register(client)
    assert select(client, "BOT").status_code == 201
    sign_out(client)
    register(client)
    assert client.get("/trading-account").json() == {
        "use": None,
        "key": None,
        "may_trade": False,
        "may_change_use": False,
    }


@pytest.mark.parametrize("use", ["MANUAL", "BOT"])
def test_select_and_delete_keeps_account_preference(client: TestClient, use: str) -> None:
    register(client)
    key_id = seed_key(owner(client))
    result = select(client, use)
    assert result.status_code == 201, result.text
    view = result.json()
    assert view["use"] == use and view["key"]["id"] == str(key_id)
    assert view["may_trade"] is False and view["may_change_use"] is False
    assert client.get("/trading-account").json() == view
    assert select(client, use).status_code == 409
    assert client.delete(f"/api-keys/{key_id}", headers=csrf_headers(client)).status_code == 204
    after = client.get("/trading-account").json()
    assert after == {"use": use, "key": None, "may_trade": False, "may_change_use": False}


@pytest.mark.parametrize("key_status", [None, "PENDING", "ACTIVE"])
def test_key_status_does_not_gate_initial_selection(
    client: TestClient, key_status: str | None
) -> None:
    register(client)
    if key_status is not None:
        seed_key(owner(client), active=key_status == "ACTIVE")
    result = select(client)
    assert result.status_code == 201
    assert result.json()["use"] == "MANUAL"


@pytest.mark.parametrize("requested", ["MANUAL", "BOT"])
def test_existing_preference_refuses_changes(client: TestClient, requested: str) -> None:
    register(client)
    user_id = owner(client)

    async def seed_preference() -> None:
        api = create_engine_for(DatabaseRole.API)
        try:
            async with user_session(api, user_id) as session:
                await session.execute(
                    "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                    {"owner": user_id},
                )
        finally:
            await api.dispose()

    asyncio.get_event_loop().run_until_complete(seed_preference())
    result = select(client, requested)
    assert result.status_code == 409
    assert result.json() == {"detail": "TRADING_ACCOUNT_ACTIVITY_UNKNOWN"}
    assert client.get("/trading-account").json()["use"] == "MANUAL"


def test_select_requires_csrf_but_not_totp(client: TestClient) -> None:
    register(client)
    assert client.post("/trading-account/use", json={"use": "MANUAL"}).status_code == 403
    result = client.post(
        "/trading-account/use", json={"use": "MANUAL"}, headers=csrf_headers(client)
    )
    assert result.status_code == 201
    assert client.get("/trading-account").json()["use"] == "MANUAL"


@pytest.mark.parametrize(
    "body", [{"use": "secret-marker"}, {"use": "MANUAL", "key_id": "secret-marker"}]
)
def test_input_never_reflects_values(client: TestClient, body: dict[str, str]) -> None:
    register(client)
    result = client.post(
        "/trading-account/use",
        json=body,
        headers=csrf_headers(client),
    )
    assert result.status_code == 422
    assert result.json() == {"detail": "TRADING_ACCOUNT_INPUT_REJECTED"}


def test_audit_failure_rolls_back_selection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tiewtrade.services.api import trading_account_routes

    register(client)

    async def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(trading_account_routes, "record_event", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        select(client)
    assert client.get("/trading-account").json()["use"] is None


def test_old_wallet_endpoints_are_absent(client: TestClient) -> None:
    from tests.api.test_route_policy import route_keys

    assert all(not path.startswith("/wallets") for _, path in route_keys())


def test_trading_account_route_rules_are_closed_and_nonrenewing() -> None:
    from tiewtrade.services.api.routing_policy import ROUTE_RULES

    read = ROUTE_RULES[("GET", "/trading-account")]
    write = ROUTE_RULES[("POST", "/trading-account/use")]
    assert not read.public and not read.renews
    assert write.renews and not write.reverify and not write.accepts_recovery_grant


def test_api_key_add_still_requires_totp_after_selection(client: TestClient) -> None:
    from tests.api.test_api_key_routes import _add

    register(client)
    assert select(client).status_code == 201
    secret, _ = enable_totp(client)
    missing = client.post(
        "/api-keys",
        json={"label": "synthetic", "key": "synthetic", "secret": "synthetic"},
        headers=csrf_headers(client),
    )
    assert missing.status_code == 403
    result = _add(client, secret)
    assert result.status_code == 201
    assert client.get("/trading-account").json()["use"] == "MANUAL"


def test_recovery_login_does_not_block_account_selection(client: TestClient) -> None:
    from tests.api.test_totp_flow import sign_in, sign_out

    email = register(client)
    _, recovery = enable_totp(client)
    sign_out(client)
    sign_in(client, email)
    result = client.post(
        "/auth/totp/login", json={"recovery_code": recovery[0]}, headers=csrf_headers(client)
    )
    assert result.status_code == 200
    selected = client.post(
        "/trading-account/use", json={"use": "MANUAL"}, headers=csrf_headers(client)
    )
    assert selected.status_code == 201
    assert client.get("/trading-account").json()["use"] == "MANUAL"


def test_account_read_does_not_renew_session(client: TestClient) -> None:
    from tests.api.conftest import session_cookie
    from tiewtrade.infra.auth.sessions import hash_token
    from tiewtrade.infra.db.session import presented_session

    register(client)
    token_hash = hash_token(session_cookie(client))

    async def timestamps() -> tuple[object, ...]:
        engine = create_engine_for(DatabaseRole.API)
        try:
            async with presented_session(engine, token_hash=token_hash) as session:
                row = (
                    await session.execute(
                        "SELECT last_seen_at,idle_expires_at,absolute_expires_at FROM sessions"
                    )
                ).one()
                return tuple(row)
        finally:
            await engine.dispose()

    before = asyncio.get_event_loop().run_until_complete(timestamps())
    for _ in range(3):
        assert client.get("/trading-account").status_code == 200
    assert asyncio.get_event_loop().run_until_complete(timestamps()) == before
