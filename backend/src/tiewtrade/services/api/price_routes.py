"""Authenticated server-observed public price snapshots."""

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, WebSocket

from tiewtrade.core.realtime_prices import MAX_PRICE_AGE, Readiness, readiness
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import presented_session
from tiewtrade.infra.market_data.catalog import SOURCE
from tiewtrade.infra.market_data.realtime_records import PriceSnapshot
from tiewtrade.infra.market_data.realtime_storage import database_now, read_public_snapshot
from tiewtrade.infra.realtime.connections import ConnectionLease
from tiewtrade.infra.realtime.connections import renew as renew_connection
from tiewtrade.services.api.authentication import Authenticated, current_user, presented_owner
from tiewtrade.services.api.price_models import PriceRow, PricesView
from tiewtrade.services.api.resources import engine_for
from tiewtrade.services.api.settings import PRICE_SETTINGS

router = APIRouter(prefix="/market-data/prices", tags=["market-data"])


def snapshot_view(snapshot: PriceSnapshot, *, delivery_connected: bool) -> PricesView:
    feed = snapshot.feed
    now = snapshot.server_time
    stored = {(r.base, r.quote): r for r in snapshot.rows}
    rows: list[PriceRow] = []
    pairs = snapshot.catalog_pairs or frozenset((row.base, row.quote) for row in snapshot.rows)
    for base, unit in sorted(pairs):
        row = stored.get((base, unit))
        q = None if row is None else row.observation
        reconciled = (
            feed is not None
            and row is not None
            and row.reconciled_generation == feed.generation
            and row.order_ambiguous_at is None
        )
        state = readiness(
            quote=q,
            connected=feed is not None and feed.connected,
            reconciled=reconciled,
            producer_alive=feed is not None and feed.lease_until > now,
            now=now,
        )
        since = None if row is None else row.unavailable_since
        if state is Readiness.READY:
            since = None
        elif q is not None and now - q.trade_time > MAX_PRICE_AGE:
            deadline = q.trade_time + MAX_PRICE_AGE
            since = deadline if since is None else min(since, deadline)
        if feed is not None and feed.lease_until <= now:
            since = feed.lease_until if since is None else min(since, feed.lease_until)
        alert_due = since is not None and now - since >= timedelta(seconds=60)
        reason = state.value
        failure_codes = {
            "VENUE_PROTOCOL",
            "VENUE_RATE_LIMITED",
            "VENUE_UNAVAILABLE",
            "VENUE_REJECTED",
            "SUBSCRIPTION_ACK_TIMEOUT",
        }
        if state in (Readiness.MISSING, Readiness.RECOVERING):
            if row is not None and row.reason in failure_codes:
                reason = row.reason
            if feed is not None and not feed.connected and feed.last_failure_code in failure_codes:
                reason = feed.last_failure_code
        if row is not None and row.order_ambiguous_at is not None:
            reason = "VENUE_PROTOCOL" if row.reason == "VENUE_PROTOCOL" else "ORDER_UNCONFIRMED"
        if not delivery_connected:
            state, reason = Readiness.RECOVERING, "DELIVERY_UNAVAILABLE"
        rows.append(
            PriceRow(
                source=SOURCE,
                base=base,
                quote=unit,
                amount=None if q is None else q.amount.as_parts()["amount"],
                trade_at=None if q is None else q.trade_time,
                received_at=None if q is None else q.received_at,
                revision=str(0 if row is None else row.revision),
                generation=str(0 if feed is None else feed.generation),
                readiness=state.value,
                reason=reason,
                valid_until=None
                if q is None or feed is None
                else min(q.trade_time + MAX_PRICE_AGE, feed.lease_until),
                unavailable_since=since,
                alert_due=alert_due,
            )
        )
    return PricesView(
        catalog_revision=str(snapshot.catalog_revision or 0),
        server_time=now,
        delivery_status="CONNECTED" if delivery_connected else "RECOVERING",
        rows=rows,
    )


@router.get("")
async def prices(
    request: Request, response: Response, who: Annotated[Authenticated, Depends(current_user)]
) -> PricesView:
    async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
        snapshot = await read_public_snapshot(session)
    response.headers["Cache-Control"] = "no-store"
    broadcaster = getattr(request.app.state, "price_broadcaster", None)
    return snapshot_view(
        snapshot, delivery_connected=bool(broadcaster is not None and broadcaster.connected)
    )


@dataclass(slots=True)
class AuthorizationWindow:
    """Start-anchored permission; neither slow queries nor commit extend it."""

    first_started: float
    deadline: float = field(init=False)
    session_deadline: float = float("inf")
    confirmed: bool = False

    def __post_init__(self) -> None:
        self.deadline = self.first_started + PRICE_SETTINGS.query_timeout

    def query_budget(self, now: float) -> float:
        return max(0, min(PRICE_SETTINGS.query_timeout, self.deadline - now))

    def permits_send(self, now: float) -> bool:
        return self.confirmed and now < self.deadline

    def confirm(
        self, *, started: float, reference: float, remaining: float, completed: float
    ) -> bool:
        session_deadline = reference + remaining
        new_deadline = min(started + PRICE_SETTINGS.authorization_age, session_deadline)
        if completed >= self.deadline or completed >= new_deadline:
            return False
        self.session_deadline = session_deadline
        self.deadline = new_deadline
        self.confirmed = True
        return True


@router.websocket("/stream")
async def stream(socket: WebSocket) -> None:
    """Push-only channel; a single coordinator owns authorization and lease renewal."""
    state = socket.app.state
    who: Authenticated = socket.state.authenticated
    lease: ConnectionLease = socket.state.price_lease
    queue = state.price_broadcaster.listen()
    checked = asyncio.Event()
    authorization_changed = asyncio.Event()
    loop = asyncio.get_running_loop()
    authorization = AuthorizationWindow(first_started=loop.time())
    close_code = 1011

    async def coordinate() -> None:
        nonlocal lease, close_code
        while True:
            started = loop.time()
            budget = authorization.query_budget(started)
            if budget <= 0:
                return
            async with asyncio.timeout(budget):
                async with presented_session(
                    state.price_engine, token_hash=who.token_hash
                ) as session:
                    owner = await presented_owner(session)
                    if owner is None or owner.user_id != who.user_id:
                        close_code = 4401
                        return
                    user = await session.assume_user(who.user_id)
                    renewed = await renew_connection(user, lease)
                    if renewed is None:
                        close_code = 1013
                        return
                    reference = loop.time()
                    now = await database_now(user)
                    remaining = (
                        min(owner.idle_expires_at, owner.absolute_expires_at) - now
                    ).total_seconds()
                    lease = renewed
            if remaining <= 0:
                close_code = 4401
                return
            if not authorization.confirm(
                started=started, reference=reference, remaining=remaining, completed=loop.time()
            ):
                close_code = 4401 if loop.time() >= reference + remaining else 1011
                return
            checked.set()
            authorization_changed.set()
            await asyncio.sleep(max(0, started + PRICE_SETTINGS.coordinator_interval - loop.time()))

    async def watchdog() -> None:
        nonlocal close_code
        while True:
            authorization_changed.clear()
            remaining = authorization.deadline - loop.time()
            if remaining <= 0:
                close_code = 4401 if loop.time() >= authorization.session_deadline else 1011
                return
            with suppress(TimeoutError):
                async with asyncio.timeout(remaining):
                    await authorization_changed.wait()

    async def push() -> None:
        nonlocal close_code
        while True:
            snapshot, connected = await queue.get()
            await checked.wait()
            if not authorization.permits_send(loop.time()):
                close_code = 4401 if loop.time() >= authorization.session_deadline else 1011
                return
            try:
                async with asyncio.timeout(PRICE_SETTINGS.send_timeout):
                    await socket.send_json(
                        snapshot_view(snapshot, delivery_connected=connected).model_dump(
                            mode="json"
                        )
                    )
            except TimeoutError:
                close_code = 1013
                return

    async def receive() -> None:
        nonlocal close_code
        while True:
            message = await socket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message["type"] == "websocket.receive":
                # All application frames are forbidden, including empty/binary/oversized frames.
                close_code = 1008
                return

    tasks: list[asyncio.Task[None]] = []
    try:
        await socket.accept()
        socket.state.price_reservation.accepted()
        tasks = [
            asyncio.create_task(coordinate()),
            asyncio.create_task(watchdog()),
            asyncio.create_task(push()),
            asyncio.create_task(receive()),
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        close_code = 4401 if loop.time() >= authorization.session_deadline else 1011
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        state.price_broadcaster.unlisten(queue)
        with suppress(RuntimeError, TimeoutError, asyncio.CancelledError):
            async with asyncio.timeout(PRICE_SETTINGS.query_timeout):
                await socket.close(close_code)
