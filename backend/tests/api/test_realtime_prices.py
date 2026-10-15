import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.api.conftest import register


def test_unknown_websocket_is_closed_centrally(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect("/unknown", headers={"origin": "http://localhost:5173"}),
    ):
        pass
    assert error.value.code == 1008


def test_missing_origin_is_rejected(client: TestClient) -> None:
    register(client)
    with (
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect("/market-data/prices/stream"),
    ):
        pass
    assert error.value.code == 1008


def test_authenticated_prices_no_store(client: TestClient) -> None:
    register(client)
    response = client.get("/market-data/prices")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert len(response.json()["rows"]) == 2


def test_stream_full_schema_and_commands_rejected(client: TestClient) -> None:
    from tiewtrade.services.api.price_models import PricesView

    register(client)
    with client.websocket_connect(
        "/market-data/prices/stream", headers={"origin": "http://localhost:5173"}
    ) as socket:
        PricesView.model_validate(socket.receive_json())
        socket.send_text("{}")
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1008


def test_logout_revokes_existing_stream(client: TestClient) -> None:
    from tests.api.conftest import csrf_headers

    register(client)
    with client.websocket_connect(
        "/market-data/prices/stream", headers={"origin": "http://localhost:5173"}
    ) as socket:
        socket.receive_json()
        response = client.post("/auth/logout", headers=csrf_headers(client))
        assert response.status_code == 200
        with pytest.raises(WebSocketDisconnect) as error:
            while True:
                socket.receive_json()
        assert error.value.code == 4401


def test_per_user_three_connections_and_cleanup(client: TestClient) -> None:
    from contextlib import ExitStack

    register(client)
    with ExitStack() as stack:
        for _ in range(3):
            socket = stack.enter_context(
                client.websocket_connect(
                    "/market-data/prices/stream", headers={"origin": "http://localhost:5173"}
                )
            )
            socket.receive_json()
        with (
            pytest.raises(WebSocketDisconnect) as error,
            client.websocket_connect(
                "/market-data/prices/stream", headers={"origin": "http://localhost:5173"}
            ),
        ):
            pass
        assert error.value.code == 1008
    with client.websocket_connect(
        "/market-data/prices/stream", headers={"origin": "http://localhost:5173"}
    ) as socket:
        socket.receive_json()


async def test_public_reader_has_no_identity_or_price_write_permission() -> None:
    from tiewtrade.infra.db import DatabaseRole, create_engine_for
    from tiewtrade.infra.db.errors import InfraError
    from tiewtrade.infra.db.session import presented_session
    from tiewtrade.infra.market_data.realtime_storage import read_snapshot

    engine = create_engine_for(DatabaseRole.API)
    try:
        async with presented_session(engine) as session:
            snapshot = await read_snapshot(session)
            assert snapshot.server_time.tzinfo is not None
            assert (await session.execute("SELECT count(*) FROM sessions")).scalar_one() == 0
        with pytest.raises(InfraError):
            async with presented_session(engine) as session:
                await session.execute("DELETE FROM market_latest_prices")
    finally:
        await engine.dispose()


def test_first_authorization_check_has_500ms_deadline(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    import time

    from tiewtrade.infra.auth.sessions import SessionOwner
    from tiewtrade.infra.db.session import PresentedSession
    from tiewtrade.services.api import price_routes
    from tiewtrade.services.api.authentication import presented_owner as original

    async def slow(session: PresentedSession) -> SessionOwner | None:
        await asyncio.sleep(0.6)
        return await original(session)

    register(client)
    monkeypatch.setattr(price_routes, "presented_owner", slow)
    started = time.monotonic()
    with client.websocket_connect(
        "/market-data/prices/stream", headers={"origin": "http://localhost:5173"}
    ) as socket:
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1011
    assert time.monotonic() - started < 0.6


def test_session_idle_expiry_closes_existing_socket_with_4401(client: TestClient) -> None:
    import asyncio
    import time

    from tiewtrade.infra.auth import hash_token
    from tiewtrade.infra.db import DatabaseRole, create_engine_for
    from tiewtrade.infra.db.session import presented_session
    from tiewtrade.services.api.settings import SESSION_COOKIE

    register(client)
    token_hash = hash_token(str(client.cookies.get(SESSION_COOKIE)))

    async def expire() -> None:
        engine = create_engine_for(DatabaseRole.API)
        try:
            async with presented_session(engine, token_hash=token_hash) as session:
                await session.execute(
                    "UPDATE sessions SET idle_expires_at="
                    "clock_timestamp()+interval '200 milliseconds'"
                )
        finally:
            await engine.dispose()

    with client.websocket_connect(
        "/market-data/prices/stream", headers={"origin": "http://localhost:5173"}
    ) as socket:
        socket.receive_json()
        asyncio.get_event_loop().run_until_complete(expire())
        started = time.monotonic()
        with pytest.raises(WebSocketDisconnect) as error:
            while True:
                socket.receive_json()
        assert error.value.code == 4401
        assert time.monotonic() - started < 1
