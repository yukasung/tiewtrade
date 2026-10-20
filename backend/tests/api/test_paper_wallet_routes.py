"""Authenticated F-13 contract from HTTP admission through the isolated worker."""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from tiewtrade import venues
from tiewtrade.infra import crypto
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.api import resources
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

from .conftest import csrf_headers, register


def _run_worker() -> None:
    async def run() -> None:
        engine = create_engine_for(DatabaseRole.ENGINE)
        scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
        try:
            await run_paper_wallet_round(engine=engine, scan_engine=scan, worker="api-test")
        finally:
            await engine.dispose()
            await scan.dispose()

    asyncio.run(run())


def test_create_replay_and_exact_snapshot(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    register(client)
    touched: list[str] = []

    def forbidden(*args: object, **kwargs: object) -> None:
        del args, kwargs
        touched.append("forbidden")
        raise AssertionError("Paper path touched Live credentials or venue code")

    monkeypatch.setattr(resources, "venue_keys", forbidden)
    monkeypatch.setattr(crypto, "unseal", forbidden)
    monkeypatch.setattr(venues, "live_wallet_factory", forbidden)
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}
    accepted = client.post(
        "/paper-wallet",
        json={"initial_capital": "1500.000000000000000001"},
        headers=headers,
    )
    assert accepted.status_code == 202, accepted.text
    command = accepted.json()
    assert command["state"] == "PENDING"
    assert command["status_url"] == f"/paper-wallet/commands/{command['command_id']}"

    _run_worker()
    terminal = client.get(command["status_url"])
    assert terminal.status_code == 200
    assert terminal.json()["state"] == "SUCCEEDED"
    wallet = client.get("/paper-wallet")
    assert wallet.status_code == 200
    assert wallet.json()["wallet"]["balance"] == {
        "amount": "1500.000000000000000001",
        "currency": "USDT",
    }
    assert terminal.json()["snapshot"] == {
        "wallet_id": wallet.json()["wallet"]["wallet_id"],
        "episode_id": wallet.json()["wallet"]["episode_id"],
        "initial_capital": {
            "amount": "1500.000000000000000001",
            "currency": "USDT",
        },
        "balance": {
            "amount": "1500.000000000000000001",
            "currency": "USDT",
        },
    }

    replay = client.post(
        "/paper-wallet",
        json={"initial_capital": "1500.000000000000000001"},
        headers=headers,
    )
    assert replay.status_code == 200
    assert replay.json() == terminal.json()
    conflict = client.post(
        "/paper-wallet",
        json={"initial_capital": "1600"},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "IDEMPOTENCY_CONFLICT"}
    assert touched == []


def test_strict_input_authentication_and_rate_limit(client: TestClient) -> None:
    assert client.get("/paper-wallet").status_code == 401
    register(client)
    assert (
        client.post(
            "/paper-wallet",
            json={"initial_capital": 2000},
            headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
        ).status_code
        == 422
    )

    replay_key = str(uuid4())
    for key in (replay_key, replay_key, str(uuid4()), str(uuid4())):
        response = client.post(
            "/paper-wallet",
            json={"initial_capital": "1000"},
            headers={**csrf_headers(client), "Idempotency-Key": key},
        )
        assert response.status_code == 422
    limited = client.post(
        "/paper-wallet",
        json={"initial_capital": "1000"},
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_reset_uses_server_readiness_and_preserves_terminal_replay(
    client: TestClient,
) -> None:
    register(client)
    create_key = str(uuid4())
    created = client.post(
        "/paper-wallet",
        json={"initial_capital": "1500"},
        headers={**csrf_headers(client), "Idempotency-Key": create_key},
    )
    assert created.status_code == 202, created.text
    _run_worker()
    before = client.get("/paper-wallet").json()["wallet"]
    assert before["reset_available"] is True
    assert before["reset_reason"] is None

    reset_key = str(uuid4())
    payload = {
        "initial_capital": "2500.125",
        "expected_episode_id": before["episode_id"],
    }
    accepted = client.post(
        "/paper-wallet/reset",
        json=payload,
        headers={**csrf_headers(client), "Idempotency-Key": reset_key},
    )
    assert accepted.status_code == 202, accepted.text
    _run_worker()
    terminal = client.get(accepted.json()["status_url"])
    assert terminal.status_code == 200
    assert terminal.json()["state"] == "SUCCEEDED"
    after = client.get("/paper-wallet").json()["wallet"]
    assert after["episode_id"] != before["episode_id"]
    assert after["sequence"] == 2
    assert after["initial_capital"] == {"amount": "2500.125", "currency": "USDT"}
    assert after["balance"] == after["initial_capital"]
    assert after["reset_available"] is True
    assert after["reset_reason"] is None

    replay = client.post(
        "/paper-wallet/reset",
        json={**payload, "initial_capital": "2500.1250"},
        headers={**csrf_headers(client), "Idempotency-Key": reset_key},
    )
    assert replay.status_code == 200
    assert replay.json() == terminal.json()
