import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import csrf_headers, register
from tests.api.test_paper_wallet_routes import _run_worker
from tests.api.test_totp_flow import code_now, enable_totp
from tiewtrade.infra.db import DatabaseRole, InfraError, create_engine_for, user_session
from tiewtrade.infra.risk_limits.records import RiskReceipt
from tiewtrade.infra.risk_limits.requests import submit_request
from tiewtrade.services.api import risk_limit_routes
from tiewtrade.services.api.routing_policy import rule_for
from tiewtrade.services.api.settings import TOTP_HEADER


def _wallet_body(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/paper-wallet",
        json={"initial_capital": "1500"},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 202, response.text
    _run_worker()
    wallet = client.get("/paper-wallet").json()["wallet"]
    return {
        "expected_revision": 0,
        "amount": "100",
        "expected_wallet_id": wallet["wallet_id"],
        "expected_episode_id": wallet["episode_id"],
    }


def _seed_setting(client: TestClient) -> None:
    owner = UUID(client.get("/auth/me").json()["user_id"])

    async def seed() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    """INSERT INTO risk_limit_settings(user_id,mode,revision,amount)
                    VALUES(:owner,'PAPER',1,100)""",
                    {"owner": owner},
                )
        finally:
            await engine.dispose()

    asyncio.run(seed())


def _seed_live_setting(client: TestClient) -> None:
    owner = UUID(client.get("/auth/me").json()["user_id"])

    async def seed() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        try:
            async with user_session(engine, owner, role=DatabaseRole.ENGINE) as session:
                await session.execute(
                    """INSERT INTO risk_limit_settings(user_id,mode,revision,amount)
                    VALUES(:owner,'LIVE',1,100)""",
                    {"owner": owner},
                )
        finally:
            await engine.dispose()

    asyncio.run(seed())


def test_risk_routes_require_session_and_csrf(client: TestClient) -> None:
    assert client.get("/paper/risk-limit").status_code == 401
    assert client.get("/live/risk-limit").status_code == 401
    register(client)
    assert client.post("/paper/risk-limit", json={}).status_code == 403


def test_intake_and_lookup_do_not_claim_applied_limit(client: TestClient) -> None:
    register(client)
    body = _wallet_body(client)
    unset = client.get("/paper/risk-limit")
    assert unset.status_code == 200 and unset.json()["amount"] is None
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    accepted = client.post("/paper/risk-limit", json=body, headers=headers)
    assert accepted.status_code == 202, accepted.text
    assert accepted.json()["state"] == "REQUEST_PENDING"
    replay = client.post("/paper/risk-limit", json={**body, "amount": "100.0"}, headers=headers)
    assert replay.status_code == 200 and replay.json() == accepted.json()
    assert client.get(f"/paper/risk-limit/requests/by-key/{key}").json() == accepted.json()
    assert (
        client.get(f"/paper/risk-limit/requests/{accepted.json()['receipt_id']}").json()
        == accepted.json()
    )
    assert client.get("/paper/risk-limit").json()["amount"] is None
    assert client.get("/live/risk-limit").json()["amount"] is None
    assert client.get(f"/live/risk-limit/requests/by-key/{key}").status_code == 404


@pytest.mark.parametrize(
    "extra",
    [
        {"mode": "LIVE"},
        {"amount": 100},
        {"owner": str(uuid4())},
        {"expected_revision": -1},
        {"expected_revision": True},
        {"expected_revision": 1.0},
        {"expected_revision": 2**63},
    ],
)
def test_risk_input_is_strict_and_never_echoes_rejected_payload(
    client: TestClient,
    extra: dict[str, object],
) -> None:
    register(client)
    body = _wallet_body(client)
    result = client.post(
        "/paper/risk-limit",
        json={**body, **extra},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 422 and result.json() == {"detail": "RISK_INPUT_INVALID"}


def test_reset_exemption_does_not_require_totp_or_classify_as_reduction(client: TestClient) -> None:
    register(client)
    body = _wallet_body(client)
    _seed_setting(client)
    body.pop("amount")
    body["expected_revision"] = 1
    result = client.post(
        "/paper/risk-limit/reset",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 202, result.text
    rule = rule_for("POST", "/paper/risk-limit/reset")
    assert rule is not None and not rule.reverify and not rule.risk_reducing


def test_paper_increase_needs_no_totp_and_has_no_recovery_grant(client: TestClient) -> None:
    register(client)
    body = _wallet_body(client)
    _seed_setting(client)
    body.update(expected_revision=1, amount="200")
    result = client.post(
        "/paper/risk-limit/increase",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 202, result.text
    rule = rule_for("POST", "/paper/risk-limit/increase")
    assert rule is not None and not rule.reverify and not rule.accepts_recovery_grant


def test_live_increase_still_requires_fresh_totp(client: TestClient) -> None:
    register(client)
    _seed_live_setting(client)
    body = {
        "expected_revision": 1,
        "amount": "200",
        "expected_wallet_id": None,
        "expected_episode_id": None,
    }
    key = str(uuid4())
    refused = client.post(
        "/live/risk-limit/increase",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": key},
    )
    assert refused.status_code == 403
    secret, _ = enable_totp(client)
    accepted = client.post(
        "/live/risk-limit/increase",
        json=body,
        headers={
            **csrf_headers(client),
            "Idempotency-Key": key,
            TOTP_HEADER: code_now(secret),
        },
    )
    assert accepted.status_code == 202, accepted.text
    rule = rule_for("POST", "/live/risk-limit/increase")
    assert rule is not None and rule.reverify and not rule.accepts_recovery_grant


def test_paper_increase_recovers_http_failure_with_the_same_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(client)
    body = _wallet_body(client)
    _seed_setting(client)
    body.update(expected_revision=1, amount="200")
    key = str(uuid4())
    real_submit = submit_request

    async def unavailable(*args: object, **kwargs: object) -> RiskReceipt:
        raise InfraError("controlled inbox connection loss")

    monkeypatch.setattr(risk_limit_routes, "submit_request", unavailable)
    failed = client.post(
        "/paper/risk-limit/increase",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": key},
    )
    assert failed.status_code == 503, failed.text
    lookup = client.get(f"/paper/risk-limit/requests/by-key/{key}")
    assert lookup.status_code == 404
    assert client.get("/paper/risk-limit").json()["amount"] == "100"
    monkeypatch.setattr(risk_limit_routes, "submit_request", real_submit)
    retry = client.post(
        "/paper/risk-limit/increase",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": key},
    )
    assert retry.status_code == 202 and retry.json()["state"] == "REQUEST_PENDING", retry.text
    conflict = client.post(
        "/paper/risk-limit/increase",
        json={**body, "amount": "201"},
        headers={**csrf_headers(client), "Idempotency-Key": key},
    )
    assert conflict.status_code == 409
    fresh_action_without_code = client.post(
        "/paper/risk-limit/increase",
        json=body,
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert fresh_action_without_code.status_code == 202


def test_concurrent_paper_increase_same_key_creates_one_receipt(client: TestClient) -> None:
    register(client)
    body = _wallet_body(client)
    _seed_setting(client)
    body.update(expected_revision=1, amount="200")
    key = uuid4()
    headers = {**csrf_headers(client), "Idempotency-Key": str(key)}

    def send() -> tuple[int, str]:
        result = client.post("/paper/risk-limit/increase", json=body, headers=headers)
        assert result.status_code in (200, 202), result.text
        return result.status_code, str(result.json()["receipt_id"])

    outcomes = send(), send()
    assert outcomes[0][1] == outcomes[1][1]
