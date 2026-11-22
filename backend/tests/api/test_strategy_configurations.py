from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import csrf_headers, register
from tests.infra.execution_market.profile_candle_closure import configuration_payload
from tiewtrade.core.strategy_config import PAPER_TEST_STRATEGY, STRATEGY_NAME
from tiewtrade.services.api.app import app


@pytest.mark.parametrize("strategy", [PAPER_TEST_STRATEGY, STRATEGY_NAME])
def test_campaign_configuration_uses_the_existing_http_contract(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, strategy: str
) -> None:
    monkeypatch.setattr(app.state, "paper_test_strategy_enabled", True, raising=False)
    register(client)
    body = configuration_payload("BTC", strategy)
    headers = {**csrf_headers(client), "Idempotency-Key": str(uuid4())}
    created = client.post("/paper/bots/configurations", json=body, headers=headers)
    assert created.status_code == 200
    prefix = "paper-test:" if strategy == PAPER_TEST_STRATEGY else "f21:"
    assert created.json()["reference"].startswith(prefix)
    assert (
        created.json()
        == client.post("/paper/bots/configurations", json=body, headers=headers).json()
    )


def test_configuration_recovery_does_not_activate_trading(client: TestClient) -> None:
    payload = {"base": "BTC", "capital_per_entry": "100", "max_entries": 3}
    assert client.post("/paper/bots/configurations", json=payload).status_code == 403
    client.get("/auth/csrf")
    assert (
        client.post(
            "/paper/bots/configurations",
            json=payload,
            headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
        ).status_code
        == 401
    )
    register(client)
    headers = {**csrf_headers(client), "Idempotency-Key": str(uuid4())}
    first = client.post("/paper/bots/configurations", json=payload, headers=headers)
    assert first.status_code == 200
    reference = first.json()["reference"]
    assert (
        client.post("/paper/bots/configurations", json=payload, headers=headers).json()
        == first.json()
    )
    stored = client.get(f"/paper/bots/configurations/{reference[4:]}")
    assert stored.status_code == 200 and stored.json() == first.json()
    start = client.post(
        "/paper/bots/requests", json={"strategy_config_ref": reference}, headers=headers
    )
    assert start.status_code == 503
    changed = client.post(
        "/paper/bots/configurations", json=payload | {"max_entries": 4}, headers=headers
    )
    assert changed.status_code == 409
    client.cookies.clear()
    client.get("/auth/csrf")
    register(client)
    assert client.get(f"/paper/bots/configurations/{reference[4:]}").status_code == 404


@pytest.mark.parametrize("bad", [0, 11, True, 1.5])
def test_configuration_count_is_strict_and_error_is_sanitized(client: TestClient, bad: Any) -> None:
    register(client)
    response = client.post(
        "/paper/bots/configurations",
        json={"base": "BTC", "capital_per_entry": "100", "max_entries": bad},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "BOT_INPUT_INVALID"}
