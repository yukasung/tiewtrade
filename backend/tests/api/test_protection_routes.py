"""HTTP authentication, CSRF, durable key lookup and owner-scoped pagination."""

import asyncio
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.api.conftest import cookies_now, csrf_headers, use_cookies
from tests.api.test_manual_order_routes import paper_policy as paper_policy
from tests.api.test_manual_order_routes import wallet_for
from tiewtrade.infra.db import DatabaseRole, create_engine_for


def seed_protection(client: TestClient) -> str:
    from tests.infra.protections.test_lifecycle import buy
    from tiewtrade.infra.db import user_session
    from tiewtrade.infra.paper_wallet import get_wallet

    enable()
    owner = UUID(client.get("/auth/me").json()["user_id"])

    async def seed() -> str:
        api = create_engine_for(DatabaseRole.API)
        engine = create_engine_for(DatabaseRole.ENGINE)
        scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
        market = None
        try:
            async with user_session(api, owner) as session:
                snapshot = await get_wallet(session)
                assert snapshot is not None
            market, _, _, _, group_id = await buy(api, engine, scan, owner, snapshot)
            return str(group_id)
        finally:
            if market is not None:
                await market.dispose()
            await api.dispose()
            await engine.dispose()
            await scan.dispose()

    return asyncio.run(seed())


def test_other_owner_and_wrong_episode_cannot_read_or_mutate_protection(client: TestClient) -> None:
    wallet = wallet_for(client)
    group_id = seed_protection(client)
    public = client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()[
        "protections"
    ][0]
    key = str(uuid4())
    result = client.post(
        f"/paper/protections/{group_id}/cancel",
        json={
            "expected_wallet_id": wallet["wallet_id"],
            "expected_episode_id": wallet["episode_id"],
            "expected_revision": public["revision"],
        },
        headers={**csrf_headers(client), "Idempotency-Key": key},
    )
    assert result.status_code == 202, result.text
    request_id = result.json()["request_id"]
    original_cookies = cookies_now(client)
    client.cookies.clear()
    client.get("/auth/csrf")
    other_wallet = wallet_for(client)
    assert client.get(f"/paper/protection-requests/{request_id}").status_code == 404
    assert client.get(f"/paper/protection-requests/by-key/{key}?action=CANCEL").status_code == 404
    assert client.get("/paper/protection-requests").json()["requests"] == []
    assert (
        client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()["protections"]
        == []
    )
    for target in (group_id, str(uuid4())):
        for action in ("cancel", "replace"):
            body = {
                "expected_wallet_id": other_wallet["wallet_id"],
                "expected_episode_id": other_wallet["episode_id"],
                "expected_revision": public["revision"],
            }
            if action == "replace":
                body.update(quantity="0.5", take_profit_price="120", stop_loss_price="90")
            denied = client.post(
                f"/paper/protections/{target}/{action}",
                json=body,
                headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
            )
            assert denied.status_code == 404 and denied.json() == {"detail": "PROTECTION_NOT_FOUND"}
    use_cookies(client, original_cookies)
    wrong_episode = client.post(
        f"/paper/protections/{group_id}/cancel",
        json={
            "expected_wallet_id": wallet["wallet_id"],
            "expected_episode_id": other_wallet["episode_id"],
            "expected_revision": public["revision"],
        },
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert wrong_episode.status_code == 404
    unchanged = client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()[
        "protections"
    ][0]
    assert unchanged["revision"] == public["revision"] and unchanged["quantity"] == "0.999"


def enable(value: bool = True) -> None:
    async def apply() -> None:
        engine = create_engine_for(DatabaseRole.MIGRATOR)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("UPDATE paper_protection_protocol SET enabled=:value"), {"value": value}
                )
        finally:
            await engine.dispose()

    asyncio.run(apply())


@pytest.fixture(autouse=True)
def restore_protocol() -> Iterator[None]:
    try:
        yield
    finally:
        enable(False)


def test_protection_receipt_replay_conflict_and_discovery(client: TestClient) -> None:
    wallet = wallet_for(client)
    enable()
    body = {
        "expected_wallet_id": wallet["wallet_id"],
        "expected_episode_id": wallet["episode_id"],
        "base": "BTC",
        "quantity": "0.1",
        "stop_loss_price": "90",
    }
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    receipt = client.post("/paper/protections", json=body, headers=headers)
    assert receipt.status_code == 202, receipt.text
    request_id = receipt.json()["request_id"]
    replay = client.post("/paper/protections", json=body, headers=headers)
    assert replay.status_code == 202 and replay.json()["request_id"] == request_id
    assert (
        client.post(
            "/paper/protections", json={**body, "quantity": "0.2"}, headers=headers
        ).status_code
        == 409
    )
    assert (
        client.get(f"/paper/protection-requests/by-key/{key}?action=CREATE").json()["request_id"]
        == request_id
    )
    assert (
        client.get("/paper/protection-requests").json()["requests"][0]["request_id"] == request_id
    )
    assert (
        client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()["protections"]
        == []
    )
    assert client.get(f"/paper/protection-requests/{uuid4()}").status_code == 404
    wrong = f"{uuid4()}:unresolved:{uuid4()}"
    assert client.get(f"/paper/protection-requests?cursor={wrong}").status_code == 409
    assert (
        client.post(
            "/paper/protections", json=body, headers={"Idempotency-Key": str(uuid4())}
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get(f"/paper/protection-requests/{request_id}").status_code == 401


def test_invalid_protection_amounts_and_live_paths_fail_safely(client: TestClient) -> None:
    wallet = wallet_for(client)
    enable()
    headers = {**csrf_headers(client), "Idempotency-Key": str(uuid4())}
    body = {
        "expected_wallet_id": wallet["wallet_id"],
        "expected_episode_id": wallet["episode_id"],
        "base": "BTC",
        "quantity": "0.1",
        "stop_loss_price": "90",
    }
    for invalid in (
        {"quantity": 0.1},
        {"quantity": "NaN"},
        {"mode": "LIVE"},
        {"api_secret": "must-not-echo"},
    ):
        result = client.post("/paper/protections", json={**body, **invalid}, headers=headers)
        assert result.status_code == 422, result.text
        assert "must-not-echo" not in result.text and "NaN" not in result.text
    # Unregistered Live mutations are denied by the shared fail-closed route policy.
    assert client.post("/live/protections", json=body, headers=headers).status_code == 403


@pytest.mark.parametrize("action", ["replace", "cancel"])
def test_mutation_replay_and_stale_revision_preserve_financial_state(
    client: TestClient, action: str
) -> None:
    from tiewtrade.core.money import Money, Quantity
    from tiewtrade.core.positions import PositionPair
    from tiewtrade.infra.db import user_session
    from tiewtrade.infra.paper_wallet import get_wallet
    from tiewtrade.infra.positions.views import held_and_reserved
    from tiewtrade.infra.protections.worker import process_request

    wallet = wallet_for(client)
    group_id = seed_protection(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    path = f"/paper/protections/{group_id}/{action}"
    before = client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()[
        "protections"
    ][0]
    body: dict[str, object] = {
        "expected_wallet_id": wallet["wallet_id"],
        "expected_episode_id": wallet["episode_id"],
        "expected_revision": before["revision"],
    }
    if action == "replace":
        body.update(quantity="0.5", take_profit_price="120", stop_loss_price="80")
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    accepted = client.post(path, json=body, headers=headers)
    assert accepted.status_code == 202, accepted.text
    identity = accepted.json()["request_id"]
    # Canonical amounts must identify the same request, even with trailing zeros.
    equivalent = {**body}
    if action == "replace":
        equivalent.update(quantity="0.5000", take_profit_price="120.00", stop_loss_price="80.0")
    replay = client.post(path, json=equivalent, headers=headers)
    assert replay.status_code == 202 and replay.json()["request_id"] == identity
    changed = [{"expected_revision": before["revision"] + 1}]
    if action == "replace":
        changed.extend(
            [{"quantity": "0.4"}, {"take_profit_price": "121"}, {"stop_loss_price": "79"}]
        )
    for difference in changed:
        rejected = client.post(path, json={**body, **difference}, headers=headers)
        assert rejected.status_code == 409 and rejected.json() == {"detail": "ORDER_CONFLICT"}

    async def apply(request_id: str) -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, UUID(request_id))
                cash = await get_wallet(session)
                assert cash is not None and cash.balance == Money.of("9900", "USDT")
                held, reserved = await held_and_reserved(
                    session, UUID(str(wallet["episode_id"])), PositionPair("BTC", "USDT")
                )
                assert held == Quantity.of("0.999", "BTC")
                assert reserved == Quantity.of(0, "BTC")
        finally:
            await engine.dispose()

    asyncio.run(apply(identity))
    terminal = client.get(f"/paper/protection-requests/{identity}").json()
    assert terminal["state"] == "APPLIED", terminal
    after = client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()[
        "protections"
    ][0]
    assert after["revision"] == before["revision"] + 1
    assert after["quantity"] == ("0.5" if action == "replace" else "0")
    # A new key with the old revision is durable intake, then a worker refusal.
    stale = client.post(
        path, json=body, headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())}
    )
    assert stale.status_code == 202, stale.text
    asyncio.run(apply(stale.json()["request_id"]))
    rejected = client.get(f"/paper/protection-requests/{stale.json()['request_id']}").json()
    assert rejected["state"] == "REJECTED" and rejected["failure_code"] == "ORDER_CONFLICT"
    # Completed request replay cannot apply a second mutation, even after revision changes.
    replay = client.post(path, json=equivalent, headers=headers)
    assert replay.status_code == 202 and replay.json()["request_id"] == identity
    assert replay.json()["state"] == "APPLIED"
    final = client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()[
        "protections"
    ][0]
    assert final["revision"] == after["revision"] and final["quantity"] == after["quantity"]
    assert client.get("/paper/protection-requests").json()["requests"] == []


def test_throttled_protection_intake_keeps_recovery_and_pagination_available(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from tiewtrade.services.api import throttling

    frozen = datetime.now(UTC)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> "FrozenDateTime":
            return cls.fromisoformat(frozen.isoformat())

    monkeypatch.setattr(throttling, "datetime", FrozenDateTime)
    wallet = wallet_for(client)
    enable()
    body = {
        "expected_wallet_id": wallet["wallet_id"],
        "expected_episode_id": wallet["episode_id"],
        "base": "BTC",
        "quantity": "0.1",
        "stop_loss_price": "90",
    }
    identities = set()
    for _ in range(20):
        receipt = client.post(
            "/paper/protections",
            json=body,
            headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
        )
        assert receipt.status_code == 202, receipt.text
        identities.add(receipt.json()["request_id"])
    denied_key = str(uuid4())
    denied = client.post(
        "/paper/protections",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": denied_key},
    )
    assert denied.status_code == 429 and "Retry-After" in denied.headers
    assert (
        client.get(f"/paper/protection-requests/by-key/{denied_key}?action=CREATE").status_code
        == 404
    )
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, str | int] = {"limit": 3}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get("/paper/protection-requests", params=params)
        assert response.status_code == 200
        page = response.json()
        seen.extend(row["request_id"] for row in page["requests"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 20 and set(seen) == identities
    assert client.get("/paper/trade?base=BTC").json()["wallet"]["balance"] == "10000"


@pytest.mark.parametrize("attachment", ["bracket", "allocations"])
def test_manual_order_fingerprint_includes_protection_attachment(
    client: TestClient, paper_policy: None, attachment: str
) -> None:
    wallet = wallet_for(client)
    group_id = seed_protection(client)
    group = client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()[
        "protections"
    ][0]
    body: dict[str, object] = {
        "expected_wallet_id": wallet["wallet_id"],
        "expected_episode_id": wallet["episode_id"],
        "base": "BTC",
        "quote": "USDT",
        "kind": "MARKET",
    }
    if attachment == "bracket":
        body.update(
            side="BUY",
            quote_budget="100",
            protection={
                "take_profit_price": "120",
                "stop_loss_price": "80",
            },
        )
        equivalent: dict[str, object] = {
            "protection": {
                "take_profit_price": "120.00",
                "stop_loss_price": "80.0",
            }
        }
        changed: list[dict[str, object]] = [
            {"protection": None},
            {"protection": {"take_profit_price": "121", "stop_loss_price": "80"}},
            {"protection": {"take_profit_price": "120", "stop_loss_price": "79"}},
        ]
    else:
        allocation = {
            "protection_id": group_id,
            "expected_revision": group["revision"],
            "quantity": "0.1",
        }
        body.update(side="SELL", base_quantity="0.1", protection_allocations=[allocation])
        equivalent = {"protection_allocations": [{**allocation, "quantity": "0.1000"}]}
        changed = [{"protection_allocations": []}]
        changed.extend(
            [
                {"protection_allocations": [{**allocation, **difference}]}
                for difference in (
                    {"quantity": "0.09"},
                    {"expected_revision": group["revision"] + 1},
                    {"protection_id": str(uuid4())},
                )
            ]
        )
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    accepted = client.post("/paper/orders", json=body, headers=headers)
    assert accepted.status_code == 202, accepted.text
    replay = client.post("/paper/orders", json={**body, **equivalent}, headers=headers)
    assert (
        replay.status_code == 200 and replay.json()["request_id"] == accepted.json()["request_id"]
    )
    for difference in changed:
        refused = client.post("/paper/orders", json={**body, **difference}, headers=headers)
        assert refused.status_code == 409, refused.text
    requests = client.get("/paper/order-requests").json()["requests"]
    assert [row["request_id"] for row in requests] == [accepted.json()["request_id"]]
    # HTTP intake and retries do not mutate an allocated position before the writer runs.
    final = client.get(f"/paper/protections?episode_id={wallet['episode_id']}").json()[
        "protections"
    ][0]
    assert final["revision"] == group["revision"] and final["quantity"] == "0.999"
