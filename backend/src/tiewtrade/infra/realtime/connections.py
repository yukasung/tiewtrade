"""Three RLS-scoped connection slots, leased and fenced by opaque IDs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tiewtrade.infra.db.session import UserSession, require_user_session

USER_CONNECTION_SLOTS = (1, 2, 3)


@dataclass(frozen=True, slots=True)
class ConnectionLease:
    user_id: UUID
    slot: int
    connection_id: UUID
    lease_until: datetime


async def _bounded(session: UserSession) -> UserSession:
    session = require_user_session(session)
    await session.execute("SET LOCAL lock_timeout = '500ms'")
    await session.execute("SET LOCAL statement_timeout = '500ms'")
    return session


async def claim(session: UserSession, connection_id: UUID) -> ConnectionLease | None:
    session = await _bounded(session)
    for slot in USER_CONNECTION_SLOTS:
        result = await session.execute(
            """INSERT INTO market_price_connections
            (user_id,slot,connection_id,lease_until)
            VALUES (:user_id,:slot,:connection_id,clock_timestamp()+interval '5 seconds')
            ON CONFLICT (user_id,slot) DO UPDATE SET
              connection_id=EXCLUDED.connection_id,
              lease_until=clock_timestamp()+interval '5 seconds'
            WHERE market_price_connections.lease_until <= clock_timestamp()
            RETURNING lease_until""",
            {"user_id": session.user_id, "slot": slot, "connection_id": connection_id},
        )
        until = result.scalar_one_or_none()
        if until is not None:
            return ConnectionLease(session.user_id, slot, connection_id, until)
    return None


async def renew(session: UserSession, lease: ConnectionLease) -> ConnectionLease | None:
    session = await _bounded(session)
    await session.execute(
        """SELECT connection_id FROM market_price_connections
        WHERE user_id=:user_id AND slot=:slot FOR UPDATE""",
        {"user_id": lease.user_id, "slot": lease.slot},
    )
    result = await session.execute(
        """UPDATE market_price_connections SET
        lease_until=clock_timestamp()+interval '5 seconds'
        WHERE user_id=:user_id AND slot=:slot AND connection_id=:connection_id
          AND lease_until > clock_timestamp() RETURNING lease_until""",
        {"user_id": lease.user_id, "slot": lease.slot, "connection_id": lease.connection_id},
    )
    until = result.scalar_one_or_none()
    return (
        None
        if until is None
        else ConnectionLease(lease.user_id, lease.slot, lease.connection_id, until)
    )


async def release(session: UserSession, lease: ConnectionLease) -> None:
    session = await _bounded(session)
    await session.execute(
        """DELETE FROM market_price_connections
        WHERE user_id=:user_id AND slot=:slot AND connection_id=:connection_id""",
        {"user_id": lease.user_id, "slot": lease.slot, "connection_id": lease.connection_id},
    )
