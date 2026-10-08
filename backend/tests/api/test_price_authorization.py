import pytest

from tiewtrade.services.api.price_routes import AuthorizationWindow


def test_authorization_is_anchored_to_start_and_excludes_exact_deadline() -> None:
    window = AuthorizationWindow(first_started=20)
    assert window.query_budget(20) == 0.5
    assert not window.permits_send(20)
    assert window.confirm(started=20, reference=20.3, remaining=50, completed=20.4)
    assert window.permits_send(20.999999)
    assert not window.permits_send(21)
    assert window.query_budget(20.8) < 0.201
    assert window.query_budget(21) == 0


def test_slow_completion_does_not_extend_db_session_expiry() -> None:
    window = AuthorizationWindow(first_started=20)
    assert window.confirm(started=20, reference=20.1, remaining=0.2, completed=20.2)
    assert window.permits_send(20.299)
    assert not window.permits_send(20.301)
    assert not window.confirm(started=20.2, reference=20.25, remaining=0.05, completed=20.4)


def test_slow_query_cannot_resurrect_expired_authorization() -> None:
    window = AuthorizationWindow(first_started=20)
    assert window.confirm(started=20, reference=20, remaining=50, completed=20.1)
    assert not window.confirm(started=20.5, reference=20.8, remaining=50, completed=21)
    assert not window.permits_send(21)


@pytest.mark.parametrize("revoked", [False, True])
async def test_watchdog_cancels_blocked_query_and_blocked_sender(
    monkeypatch: pytest.MonkeyPatch,
    revoked: bool,
) -> None:
    import asyncio
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    from typing import Any, cast
    from uuid import uuid4

    from fastapi import WebSocket

    from tiewtrade.infra.auth.sessions import SessionOwner
    from tiewtrade.infra.db.session import PresentedSession, UserSession
    from tiewtrade.infra.market_data.realtime_records import PriceSnapshot
    from tiewtrade.infra.realtime.connections import ConnectionLease
    from tiewtrade.services.api import price_routes
    from tiewtrade.services.api.authentication import Authenticated

    now = datetime.now(UTC)
    who = Authenticated(uuid4(), "not-a-token", now + timedelta(hours=1))
    lease = ConnectionLease(who.user_id, 1, uuid4(), now + timedelta(seconds=5))
    sender_started = asyncio.Event()
    sender_cancelled = asyncio.Event()
    query_cancelled = asyncio.Event()
    forever = asyncio.Event()
    revocation = asyncio.Event()
    queries = 0
    queue: asyncio.Queue[tuple[PriceSnapshot, bool]] = asyncio.Queue(maxsize=1)
    queue.put_nowait((PriceSnapshot(None, (), now), True))

    async def assume(user_id: object) -> UserSession:
        return cast(UserSession, object())

    @asynccontextmanager
    async def session(*args: Any, **kwargs: Any) -> AsyncIterator[PresentedSession]:
        yield cast(PresentedSession, SimpleNamespace(assume_user=assume))

    async def owner(session: object) -> SessionOwner | None:
        nonlocal queries
        queries += 1
        if queries > 1:
            if revoked:
                assert revocation.is_set()
                return None
            try:
                await forever.wait()
            finally:
                query_cancelled.set()
        asyncio.get_running_loop().call_later(0.0001, revocation.set)
        return SessionOwner(who.user_id, now + timedelta(hours=1), now + timedelta(hours=1))

    async def renew(*args: Any) -> ConnectionLease:
        return lease

    async def clock(*args: Any) -> datetime:
        return now

    class Socket:
        def __init__(self) -> None:
            self.app = SimpleNamespace(
                state=SimpleNamespace(
                    price_engine=object(),
                    price_broadcaster=SimpleNamespace(
                        listen=lambda: queue, unlisten=lambda queue: None
                    ),
                )
            )
            self.state = SimpleNamespace(
                authenticated=who,
                price_lease=lease,
                price_reservation=SimpleNamespace(accepted=lambda: None),
            )
            self.closed: int | None = None

        async def accept(self) -> None:
            pass

        async def receive(self) -> dict[str, object]:
            await forever.wait()
            return {"type": "websocket.disconnect"}

        async def send_json(self, payload: object) -> None:
            sender_started.set()
            try:
                await forever.wait()
            finally:
                sender_cancelled.set()

        async def close(self, code: int) -> None:
            self.closed = code

    monkeypatch.setattr(price_routes, "presented_session", session)
    monkeypatch.setattr(price_routes, "presented_owner", owner)
    monkeypatch.setattr(price_routes, "renew_connection", renew)
    monkeypatch.setattr(price_routes, "database_now", clock)
    socket = Socket()
    started = asyncio.get_running_loop().time()
    task = asyncio.create_task(price_routes.stream(cast(WebSocket, socket)))
    await asyncio.wait_for(sender_started.wait(), 0.5)
    await asyncio.wait_for(task, 1.1)
    elapsed = asyncio.get_running_loop().time() - started
    assert elapsed < (0.55 if revoked else 1.05)
    assert queries == 2
    assert query_cancelled.is_set() is (not revoked)
    assert sender_cancelled.is_set()
    assert socket.closed == (4401 if revoked else 1011)
