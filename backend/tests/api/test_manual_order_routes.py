"""Real HTTP identity/CSRF, durable receipt recovery and production-closed admission."""

import asyncio
import base64
import json
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import csrf_headers, register
from tests.api.test_paper_wallet_routes import _run_worker
from tests.infra.execution_market.test_worker import AllowPolicy
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.paper_orders.request_dispatch import DueRequest, claim_request
from tiewtrade.infra.paper_orders.request_worker import process_request
from tiewtrade.services.api.app import app
from tiewtrade.services.api.manual_order_routes import manual_admission_policy


@pytest.fixture
def paper_policy() -> Iterator[None]:
    app.dependency_overrides[manual_admission_policy] = lambda: AllowPolicy()
    try:
        yield
    finally:
        app.dependency_overrides.pop(manual_admission_policy, None)


def wallet_for(client: TestClient) -> dict[str, object]:
    register(client)
    response = client.post(
        "/paper-wallet",
        json={"initial_capital": "10000"},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 202
    _run_worker()
    return dict(client.get("/paper-wallet").json()["wallet"])


def buy(wallet: dict[str, object]) -> dict[str, object]:
    return {
        "expected_wallet_id": wallet["wallet_id"],
        "expected_episode_id": wallet["episode_id"],
        "base": "BTC",
        "quote": "USDT",
        "kind": "MARKET",
        "side": "BUY",
        "quote_budget": "100",
    }


def test_production_readiness_and_admission_remain_closed(client: TestClient) -> None:
    assert client.get("/paper/trade").status_code == 401
    wallet = wallet_for(client)
    snapshot = client.get("/paper/trade?base=BTC")
    assert snapshot.status_code == 200, snapshot.text
    assert client.get("/paper/trade?base=USDT").status_code == 422
    assert "market_observed_at" in snapshot.json()
    assert not snapshot.json()["admission_ready"]
    assert "ORDER_SAFETY_UNAVAILABLE" in snapshot.json()["admission_reasons"]
    assert snapshot.json()["wallet"]["available_quote"] == "10000"
    result = client.post(
        "/paper/orders",
        json=buy(wallet),
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 503, result.text
    assert result.json()["detail"] == "ORDER_SAFETY_UNAVAILABLE"
    assert client.get("/paper/order-requests").json()["requests"] == []


def test_receipt_replay_conflict_lookup_and_safe_input(
    client: TestClient, paper_policy: None
) -> None:
    wallet = wallet_for(client)
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    body = buy(wallet)
    received = client.post("/paper/orders", json=body, headers=headers)
    assert received.status_code == 202, received.text
    receipt = received.json()
    assert receipt["intake_state"] == "PENDING" and receipt["command_state"] is None
    assert receipt["request_summary"]["quote_budget"] == "100"
    replay = client.post("/paper/orders", json=body, headers=headers)
    assert replay.status_code == 200
    assert {k: v for k, v in replay.json().items() if k != "snapshot_at"} == {
        k: v for k, v in receipt.items() if k != "snapshot_at"
    }
    conflict = client.post("/paper/orders", json={**body, "quote_budget": "101"}, headers=headers)
    assert conflict.status_code == 409
    lookup = client.get(f"/paper/order-requests/by-key/{key}?action=NEW")
    assert lookup.status_code == 200 and lookup.json()["request_id"] == receipt["request_id"]
    assert (
        client.get("/paper/order-requests").json()["requests"][0]["request_id"]
        == receipt["request_id"]
    )
    invalid_cases: list[dict[str, object]] = [
        {"quote_budget": 100},
        {"mode": "LIVE"},
        {"quote_budget": "NaN"},
    ]
    for invalid in invalid_cases:
        denied = client.post("/paper/orders", json={**body, **invalid}, headers=headers)
        assert denied.status_code == 422 and "NaN" not in denied.text and "LIVE" not in denied.text
    assert (
        client.post("/paper/orders", json=body, headers={"Idempotency-Key": key}).status_code == 403
    )
    # Existing durable requests remain recoverable even when readiness closes again.
    app.dependency_overrides.pop(manual_admission_policy)
    assert client.post("/paper/orders", json=body, headers=headers).status_code == 200


def test_worker_rejection_without_order_is_readable_and_owner_isolated(
    client: TestClient,
    paper_policy: None,
) -> None:
    wallet = wallet_for(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    received = client.post(
        "/paper/orders",
        json=buy(wallet),
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert received.status_code == 202, received.text
    receipt = received.json()

    async def process() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                request_id = UUID(receipt["request_id"])
                timestamp = (
                    await session.execute(
                        """SELECT next_attempt_at FROM paper_order_request_dispatch
                        WHERE request_id=:id""",
                        {"id": request_id},
                    )
                ).scalar_one()
                claim = await claim_request(
                    session, DueRequest(request_id, owner, timestamp), worker="http-inbox"
                )
                assert claim is not None
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, claim, policy=AllowPolicy())
        finally:
            await engine.dispose()

    asyncio.run(process())
    outcome = client.get(receipt["status_url"])
    assert outcome.status_code == 200
    assert outcome.json()["intake_state"] == "REJECTED"
    assert outcome.json()["intake_failure_code"] == "MANUAL_USE_REQUIRED"
    assert client.get(f"/paper/orders/{receipt['order_id']}").status_code == 404
    assert client.get("/paper/order-requests").json()["requests"] == []
    register(client)
    assert client.get(receipt["status_url"]).status_code == 404
    denied = client.post(
        f"/paper/orders/{receipt['order_id']}/cancel",
        json={k: v for k, v in buy(wallet).items() if k.startswith("expected_")},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert denied.status_code == 404


def drive_request(owner: UUID, receipt_id: UUID, *, initialize_use: bool = False) -> None:
    """Drive only the specified owner/request; never depend on a global scan's batch order."""
    from tests.infra.execution_market.test_worker import ready_public_sources
    from tiewtrade.infra.paper_orders.dispatch import DueOrder, claim_order
    from tiewtrade.infra.paper_orders.worker import process_claimed_order

    async def drive() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        api = create_engine_for(DatabaseRole.API)
        market = None
        try:
            if initialize_use:
                async with user_session(api, owner) as session:
                    await session.execute(
                        "INSERT INTO user_trading_preferences(user_id,use) VALUES(:owner,'MANUAL')",
                        {"owner": owner},
                    )
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                timestamp = (
                    await session.execute(
                        """SELECT next_attempt_at FROM paper_order_request_dispatch
                        WHERE request_id=:id""",
                        {"id": receipt_id},
                    )
                ).scalar_one()
                claim = await claim_request(
                    session, DueRequest(receipt_id, owner, timestamp), worker="http-drive"
                )
                assert claim is not None
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_request(session, claim, policy=AllowPolicy())
                command_id = (
                    await session.execute(
                        "SELECT command_id FROM paper_order_request_results WHERE request_id=:id",
                        {"id": receipt_id},
                    )
                ).scalar_one()
            market, _, _, _ = await ready_public_sources()
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                timestamp = (
                    await session.execute(
                        "SELECT next_attempt_at FROM paper_order_dispatch WHERE command_id=:id",
                        {"id": command_id},
                    )
                ).scalar_one()
                order_claim = await claim_order(
                    session, DueOrder(command_id, owner, timestamp), worker="http-f15"
                )
                assert order_claim is not None
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await process_claimed_order(session, order_claim, policy=AllowPolicy())
        finally:
            if market is not None:
                await market.dispose()
            await engine.dispose()
            await api.dispose()

    asyncio.run(drive())


def test_downstream_rejection_is_returned_without_an_order_row(
    client: TestClient,
    paper_policy: None,
) -> None:
    wallet = wallet_for(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    received = client.post(
        "/paper/orders",
        json={**buy(wallet), "quote_budget": "20000"},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert received.status_code == 202, received.text
    receipt = received.json()
    drive_request(owner, UUID(receipt["request_id"]), initialize_use=True)
    outcome = client.get(receipt["status_url"])
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()["intake_state"] == "TRANSFERRED"
    assert outcome.json()["command_state"] == "REJECTED"
    assert outcome.json()["command_failure_code"] == "ORDER_INSUFFICIENT_FUNDS"
    assert outcome.json()["command_snapshot"]["status"] == "REJECTED"
    assert outcome.json()["order_state"] is None
    assert client.get(f"/paper/orders/{receipt['order_id']}").status_code == 404


def test_limit_read_views_and_cancel_work_with_opening_policy_closed(
    client: TestClient,
    paper_policy: None,
) -> None:
    wallet = wallet_for(client)
    owner = UUID(client.get("/auth/me").json()["user_id"])
    body = {
        **buy(wallet),
        "kind": "LIMIT",
        "base_quantity": "1",
        "limit_price": "90",
        "time_in_force": "GTC",
    }
    del body["quote_budget"]
    accepted = client.post(
        "/paper/orders",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert accepted.status_code == 202, accepted.text
    receipt = accepted.json()
    drive_request(owner, UUID(receipt["request_id"]), initialize_use=True)
    detail = client.get(f"/paper/orders/{receipt['order_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["remaining_quantity"] == "1" and detail.json()["reserved_quote"] == "90"
    page = client.get(f"/paper/orders?episode_id={wallet['episode_id']}&limit=1")
    assert page.status_code == 200 and len(page.json()["orders"]) == 1
    assert client.get("/paper/trade?base=BTC").json()["wallet"]["available_quote"] == "9910"
    app.dependency_overrides.pop(manual_admission_policy)
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    cancel_body = {k: v for k, v in body.items() if k.startswith("expected_")}
    canceled = client.post(
        f"/paper/orders/{receipt['order_id']}/cancel", json=cancel_body, headers=headers
    )
    assert canceled.status_code == 202, canceled.text
    drive_request(owner, UUID(canceled.json()["request_id"]))
    outcome = client.get(canceled.json()["status_url"])
    assert outcome.status_code == 200 and outcome.json()["command_state"] == "SUCCEEDED"
    assert outcome.json()["order_state"] == "CANCELED"
    assert (
        client.post(
            f"/paper/orders/{receipt['order_id']}/cancel", json=cancel_body, headers=headers
        ).status_code
        == 200
    )
    assert client.get("/paper/trade?base=BTC").json()["wallet"]["available_quote"] == "10000"


def test_order_throttle_is_independent_and_replays_do_not_spend_quota(
    client: TestClient,
    paper_policy: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from tiewtrade.infra.auth.throttle import Bucket
    from tiewtrade.services.api import throttling

    frozen = datetime.now(UTC)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> "FrozenDateTime":
            return cls.fromisoformat(frozen.isoformat())

    monkeypatch.setattr(throttling, "datetime", FrozenDateTime)
    wallet = wallet_for(client)
    headers = {**csrf_headers(client), "Idempotency-Key": str(uuid4())}
    first = client.post("/paper/orders", json=buy(wallet), headers=headers)
    assert first.status_code == 202
    for _ in range(20):
        assert client.post("/paper/orders", json=buy(wallet), headers=headers).status_code == 200
    for _ in range(19):
        accepted = client.post(
            "/paper/orders",
            json=buy(wallet),
            headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
        )
        assert accepted.status_code == 202, accepted.text
    limited = client.post(
        "/paper/orders",
        json=buy(wallet),
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert limited.status_code == 429 and "Retry-After" in limited.headers
    owner = UUID(client.get("/auth/me").json()["user_id"])

    async def inspect_cancel_bucket() -> None:
        from tiewtrade.services.api.throttling import spend_token

        engine = create_engine_for(DatabaseRole.API)
        try:
            await spend_token(engine, owner, Bucket.PAPER_ORDER_CANCEL)
        finally:
            await engine.dispose()

    asyncio.run(inspect_cancel_bucket())


@pytest.mark.parametrize("identity", [None, 3, 1.5, True, {}, []])
def test_discovery_rejects_non_string_cursor_parts_with_safe_code(
    client: TestClient, identity: object
) -> None:
    register(client)
    owner = client.get("/auth/me").json()["user_id"]
    cursor = base64.urlsafe_b64encode(
        json.dumps([owner, "unresolved", "2026-10-25T00:00:00+00:00", identity]).encode()
    ).decode()
    result = client.get("/paper/order-requests", params={"cursor": cursor})
    assert result.status_code == 409
    assert result.json() == {"detail": "ORDER_CONFLICT"}


def test_stale_price_keeps_its_original_observation_time(client: TestClient) -> None:
    from tests.infra.execution_market.test_worker import ready_public_sources
    from tiewtrade.infra.db.session import market_data_session

    register(client)

    async def publish_then_disconnect() -> str:
        market, _, _, _ = await ready_public_sources()
        try:
            async with market_data_session(market) as session:
                observed = (
                    await session.execute(
                        "SELECT received_at FROM market_latest_prices WHERE base='BTC'"
                    )
                ).scalar_one()
                await session.execute(
                    "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
                )
                return str(observed.isoformat())
        finally:
            await market.dispose()

    original = asyncio.run(publish_then_disconnect())
    response = client.get("/paper/trade?base=BTC")
    assert response.status_code == 200
    assert response.json()["market_observed_at"] == original
    assert response.json()["market_observed_at"] != response.json()["snapshot_at"]
    assert "ORDER_PRICE_UNAVAILABLE" in response.json()["admission_reasons"]


@pytest.mark.parametrize("action", ["NEW", "CANCEL"])
def test_closed_episode_refusal_is_recoverable_after_reset(
    client: TestClient, paper_policy: None, action: str
) -> None:
    wallet = wallet_for(client)
    reset = client.post(
        "/paper-wallet/reset",
        json={"initial_capital": "5000", "expected_episode_id": wallet["episode_id"]},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    _run_worker()
    assert (
        client.get(f"/paper-wallet/commands/{reset.json()['command_id']}").json()["state"]
        == "SUCCEEDED"
    )
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    path = "/paper/orders" if action == "NEW" else f"/paper/orders/{uuid4()}/cancel"
    body = buy(wallet)
    if action == "CANCEL":
        body = {k: v for k, v in body.items() if k.startswith("expected_")}
    # Closure proof remains available even when production opening admission closes.
    app.dependency_overrides.pop(manual_admission_policy)
    for _ in range(2):
        response = client.post(path, json=body, headers=headers)
        assert response.status_code == 409
        assert response.json() == {"detail": "MANUAL_ORDER_EPISODE_CLOSED"}
        assert client.get(f"/paper/order-requests/by-key/{key}?action={action}").status_code == 404
    assert client.get("/paper/order-requests").json()["requests"] == []
    # A random or another owner's episode is not evidence of a durable closure.
    body["expected_episode_id"] = str(uuid4())
    response = client.post(path, json=body, headers=headers)
    assert response.json()["detail"] != "MANUAL_ORDER_EPISODE_CLOSED"
    register(client)
    body["expected_episode_id"] = wallet["episode_id"]
    response = client.post(
        path, json=body, headers={**csrf_headers(client), "Idempotency-Key": key}
    )
    assert response.json()["detail"] != "MANUAL_ORDER_EPISODE_CLOSED"
