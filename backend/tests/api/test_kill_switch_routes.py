from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import cookies_now, csrf_headers, register, use_cookies


@pytest.fixture(autouse=True)
def enable_stop_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED", "1")


def test_user_stop_is_one_click_replayable_and_mode_scoped(client: TestClient) -> None:
    register(client)
    key = str(uuid4())
    headers = {**csrf_headers(client), "Idempotency-Key": key}

    stopped = client.post("/paper/kill-switch/stop", headers=headers)
    assert stopped.status_code == 202
    assert stopped.json()["mode"] == "PAPER"
    assert stopped.json()["state"] == "REQUEST_PENDING"

    replay = client.post("/paper/kill-switch/stop", headers=headers)
    assert replay.status_code == 200
    assert replay.json()["request_id"] == stopped.json()["request_id"]

    status = client.get("/paper/kill-switch")
    assert status.status_code == 200
    assert status.json()["stop_id"] == stopped.json()["stop_id"]
    assert status.json()["progress"] == "STOPPING"
    assert client.get("/live/kill-switch").json()["stop_id"] is None


def test_stop_rejects_unknown_body_fields_without_echoing_input(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    register(client)
    secret_marker = "must-not-be-echoed"
    response = client.post(
        "/paper/kill-switch/stop",
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
        json={"owner": secret_marker},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "TRADING_STOP_INPUT_INVALID"}
    assert secret_marker not in response.text
    assert secret_marker not in caplog.text


def test_stop_resources_hide_owner_and_mode_mismatches_with_uniform_not_found(
    client: TestClient,
) -> None:
    register(client)
    first_owner = cookies_now(client)
    stopped = client.post(
        "/paper/kill-switch/stop",
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert stopped.status_code == 202
    request_id = stopped.json()["request_id"]
    stop_id = stopped.json()["stop_id"]

    for path, detail in (
        (f"/live/kill-switch/requests/{request_id}", "TRADING_STOP_REQUEST_NOT_FOUND"),
        (f"/live/kill-switch/stops/{stop_id}/effects", "TRADING_STOP_NOT_FOUND"),
        (f"/live/kill-switch/stops/{stop_id}/resume-summary", "TRADING_STOP_NOT_FOUND"),
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {"detail": detail}

    client.cookies.clear()
    client.get("/auth/csrf")
    register(client)
    for path, detail in (
        (f"/paper/kill-switch/requests/{request_id}", "TRADING_STOP_REQUEST_NOT_FOUND"),
        (f"/paper/kill-switch/stops/{stop_id}/effects", "TRADING_STOP_NOT_FOUND"),
        (f"/paper/kill-switch/stops/{stop_id}/resume-summary", "TRADING_STOP_NOT_FOUND"),
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {"detail": detail}

    use_cookies(client, first_owner)
    assert client.get(f"/paper/kill-switch/requests/{request_id}").status_code == 200


def test_stop_authority_is_fail_closed_until_rolling_writer_gate_opens(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client)
    monkeypatch.delenv("TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED")
    response = client.post(
        "/paper/kill-switch/stop",
        headers={**csrf_headers(client), "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "TRADING_STOP_UNAVAILABLE"}


def test_platform_reason_rejects_whitespace_only() -> None:
    from pydantic import ValidationError

    from tiewtrade.services.api.kill_switch_models import PlatformStopInput

    with pytest.raises(ValidationError):
        PlatformStopInput(reason="   ")
