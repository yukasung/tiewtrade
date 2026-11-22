"""Strict owner config/gate tests for the acceptance-only strategy."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import csrf_headers, register
from tiewtrade.services.api.app import app

NAME = "paper-green-atr-test"
PAYLOAD = {"strategy_name": NAME, "base": "BTC", "timeframe": "1m", "capital_per_entry": "100"}


def test_configuration_gate_owner_scope_idempotency_and_live_refusal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client)
    headers = {**csrf_headers(client), "Idempotency-Key": str(uuid4())}
    assert NAME not in client.get("/paper/bots/strategy").json()["strategies"]
    assert (
        client.post("/paper/bots/configurations", json=PAYLOAD, headers=headers).status_code == 503
    )
    monkeypatch.setattr(app.state, "paper_test_strategy_enabled", True, raising=False)
    assert NAME in client.get("/paper/bots/strategy").json()["strategies"]
    created = client.post("/paper/bots/configurations", json=PAYLOAD, headers=headers)
    assert created.status_code == 200
    assert (
        client.post("/paper/bots/configurations", json=PAYLOAD, headers=headers).json()
        == created.json()
    )
    assert (
        client.post(
            "/paper/bots/configurations",
            json=PAYLOAD | {"capital_per_entry": "101"},
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/paper/bots/configurations",
            json={"base": "BTC", "capital_per_entry": "100"},
            headers=headers,
        ).status_code
        == 409
    )
    reference = created.json()["reference"]
    path = f"/paper/bots/configurations/{reference.split(':')[1]}?strategy_name={NAME}"
    assert client.get(path).json() == created.json()
    assert (
        client.post(
            "/live/bots/requests", json={"strategy_config_ref": reference}, headers=headers
        ).status_code
        == 503
    )
    monkeypatch.setattr(app.state, "paper_test_strategy_enabled", False)
    monkeypatch.setattr(
        app.state, "bot_paper_configurations", frozenset({reference}), raising=False
    )
    assert (
        client.post(
            "/paper/bots/requests", json={"strategy_config_ref": reference}, headers=headers
        ).status_code
        == 503
    )
    client.cookies.clear()
    client.get("/auth/csrf")
    register(client)
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"max_entries": 1},
        {"capital_per_entry": True},
        {"capital_per_entry": "-1"},
        {"timeframe": "30m"},
        {"timeframe": None},
        {"unknown": 1},
    ],
)
def test_test_strategy_config_is_strict(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object]
) -> None:
    register(client)
    monkeypatch.setattr(app.state, "paper_test_strategy_enabled", True, raising=False)
    response = client.post(
        "/paper/bots/configurations",
        json=PAYLOAD | changes,
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 422
