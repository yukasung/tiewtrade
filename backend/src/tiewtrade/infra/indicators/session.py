"""Distinct builder sessions; source snapshot precedes every SELECT."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tiewtrade.infra.db.engine import DatabaseRole
from tiewtrade.infra.db.errors import (
    DatabaseTimeoutError,
    SessionKindError,
    translate_database_error,
)
from tiewtrade.infra.db.session import _assert_role, _begin, _execute


@dataclass(frozen=True, slots=True)
class IndicatorSourceSession:
    _connection: AsyncConnection

    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        return await _execute(self._connection, statement, parameters)


@dataclass(frozen=True, slots=True)
class IndicatorWriterSession:
    _connection: AsyncConnection

    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]:
        return await _execute(self._connection, statement, parameters)


@asynccontextmanager
async def indicator_source_session(engine: AsyncEngine) -> AsyncIterator[IndicatorSourceSession]:
    connection: AsyncConnection | None = None
    driver: Any = None
    succeeded = False
    cancellation: asyncio.CancelledError | None = None
    try:
        connection = await engine.connect()
        # Save the actual asyncpg transport before work starts, for synchronous abort.
        driver = (await connection.get_raw_connection()).driver_connection
        await connection.begin()
        await _execute(
            connection, "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY", None
        )
        await _assert_role(connection, DatabaseRole.INDICATOR_BUILDER)
        yield IndicatorSourceSession(connection)
        succeeded = True
    except asyncio.CancelledError as error:
        cancellation = error
        raise
    except (SQLAlchemyError, OSError) as error:
        raise translate_database_error(error) from None
    finally:
        if connection is not None:

            async def close_source() -> None:
                try:
                    if succeeded:
                        await connection.commit()
                    else:
                        await connection.rollback()
                finally:
                    await connection.close()

            task = asyncio.create_task(close_source())
            try:
                # Reserve part of the same two-second budget for abort/join.
                await asyncio.wait_for(asyncio.shield(task), 1.9)
            except BaseException as error:
                if driver is not None:
                    driver.terminate()
                task.cancel()
                # Never wait indefinitely for cancellation acknowledgement.
                await asyncio.wait({task}, timeout=0.05)
                task.add_done_callback(_consume_cleanup_result)
                discard = asyncio.create_task(connection.invalidate())
                await asyncio.wait({discard}, timeout=0.05)
                discard.add_done_callback(_consume_cleanup_result)
                if isinstance(error, asyncio.CancelledError):
                    raise
                if cancellation is not None:
                    raise cancellation from None
                raise DatabaseTimeoutError("indicator source cleanup failed") from None


def _consume_cleanup_result(task: asyncio.Task[None]) -> None:
    if not task.cancelled():
        task.exception()


@asynccontextmanager
async def indicator_writer_session(engine: AsyncEngine) -> AsyncIterator[IndicatorWriterSession]:
    async with _begin(engine, cleanup_seconds=2) as connection:
        await _assert_role(connection, DatabaseRole.INDICATOR_BUILDER)
        yield IndicatorWriterSession(connection)


def require_indicator_source_session(candidate: object) -> IndicatorSourceSession:
    if isinstance(candidate, IndicatorSourceSession):
        return candidate
    raise SessionKindError("indicator source requires IndicatorSourceSession")


def require_indicator_writer_session(candidate: object) -> IndicatorWriterSession:
    if isinstance(candidate, IndicatorWriterSession):
        return candidate
    raise SessionKindError("indicator writer requires IndicatorWriterSession")
