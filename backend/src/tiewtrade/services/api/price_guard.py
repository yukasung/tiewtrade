"""Default-deny ASGI socket authentication and bounded admission."""

import asyncio
from contextlib import suppress
from uuid import uuid4

from fastapi import HTTPException, WebSocket
from starlette.types import ASGIApp, Receive, Scope, Send

from tiewtrade.infra.auth import Bucket, hash_token
from tiewtrade.infra.db.session import presented_session, user_session
from tiewtrade.infra.realtime.connections import claim, release
from tiewtrade.services.api.authentication import Authenticated, presented_owner
from tiewtrade.services.api.routing_policy import classify
from tiewtrade.services.api.settings import PRICE_SETTINGS, SESSION_COOKIE, price_origins
from tiewtrade.services.api.throttling import spend_token


class PriceScopeGuard:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "websocket":
            await self.app(scope, receive, send)
            return
        socket = WebSocket(scope, receive, send)
        if classify("WEBSOCKET", scope["path"]) is None:
            await socket.close(1008)
            return
        state = scope["app"].state
        reservation = state.price_budget.reserve()
        if reservation is None:
            await socket.close(1008)
            return
        lease = None
        try:
            peer = None if socket.client is None else socket.client.host
            if not await state.price_admission.admit(peer):
                await socket.close(1008)
                return
            if socket.headers.get("origin") not in price_origins():
                await socket.close(1008)
                return
            token = socket.cookies.get(SESSION_COOKIE, "")
            if not token:
                await socket.close(1008)
                return
            token_hash = hash_token(token)
            async with asyncio.timeout(PRICE_SETTINGS.query_timeout):
                async with presented_session(state.price_engine, token_hash=token_hash) as session:
                    owner = await presented_owner(session)
            if owner is None:
                await socket.close(1008)
                return
            async with asyncio.timeout(PRICE_SETTINGS.query_timeout):
                await spend_token(state.price_engine, owner.user_id, Bucket.PRICE_STREAM_HANDSHAKE)
            async with asyncio.timeout(PRICE_SETTINGS.query_timeout):
                async with user_session(state.price_engine, owner.user_id) as user:
                    lease = await claim(user, uuid4())
            if lease is None:
                await socket.close(1008)
                return
            socket.state.authenticated = Authenticated(
                owner.user_id, token_hash, owner.absolute_expires_at
            )
            socket.state.price_lease = lease
            socket.state.price_reservation = reservation
            await self.app(scope, receive, send)
        except asyncio.CancelledError:
            pass
        except HTTPException:
            with suppress(RuntimeError):
                await socket.close(1008)
        except Exception:
            with suppress(RuntimeError):
                await socket.close(1011)
        finally:
            if lease is not None:
                # Cancellation never lets old cleanup erase a replacement owner.
                async def cleanup() -> None:
                    with suppress(Exception):
                        async with asyncio.timeout(PRICE_SETTINGS.query_timeout):
                            async with user_session(state.price_engine, lease.user_id) as session:
                                await release(session, lease)

                cleanup_task = asyncio.create_task(cleanup())
                with suppress(asyncio.CancelledError):
                    await asyncio.shield(cleanup_task)
            reservation.close()
