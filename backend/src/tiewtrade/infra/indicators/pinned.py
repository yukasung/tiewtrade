"""One physical writer session per attempt, serialized short transactions."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from tiewtrade.core.money import MoneyError
from tiewtrade.infra.db.engine import DatabaseRole
from tiewtrade.infra.db.errors import (
    DatabaseTimeoutError,
    IndicatorBuildConfigurationError,
    IndicatorBuildOwnershipError,
    translate_database_error,
)
from tiewtrade.infra.db.session import _assert_role, _execute
from tiewtrade.infra.indicators.claims import (
    AttemptOutcome,
    BuildClaim,
    PublicationResult,
    claim_next,
    heartbeat,
    publish,
    release,
    seed_jobs,
)
from tiewtrade.infra.indicators.scheduling import coalesce_session
from tiewtrade.infra.indicators.session import IndicatorWriterSession


async def _finish_transaction(
    connection: AsyncConnection,
    transaction: AsyncTransaction,
    *,
    commit: bool,
) -> None:
    task = asyncio.create_task(transaction.commit() if commit else transaction.rollback())
    try:
        await asyncio.wait_for(asyncio.shield(task), 2)
    except BaseException:
        await connection.invalidate()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise


@dataclass(slots=True)
class PinnedIndicatorWriter:
    _connection: AsyncConnection
    backend_pid: int
    _serial: asyncio.Lock = field(default_factory=asyncio.Lock)
    _operations: asyncio.Lock = field(default_factory=asyncio.Lock)
    _claim: BuildClaim | None = None
    _tainted: bool = False
    _dispatch_used: bool = False
    _ownership_lost: bool = False

    def require_claim(self, claim: BuildClaim) -> None:
        if (
            self._claim != claim
            or self._ownership_lost
            or self._tainted
            or self._connection.invalidated
        ):
            raise IndicatorBuildOwnershipError("indicator writer attempt unavailable")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[IndicatorWriterSession]:
        async with self._serial:
            if self._tainted or self._connection.invalidated:
                raise IndicatorBuildOwnershipError("indicator writer session lost")
            try:
                transaction = await self._connection.begin()
                try:
                    await _execute(
                        self._connection,
                        """SELECT
                        set_config('lock_timeout','200ms',true),
                        set_config('statement_timeout','500ms',true)""",
                        None,
                    )
                    # A transaction pooler/session change cannot resume an old claim.
                    pid = int(
                        (
                            await _execute(self._connection, "SELECT pg_backend_pid()", None)
                        ).scalar_one()
                    )
                    if pid != self.backend_pid:
                        raise IndicatorBuildOwnershipError("indicator writer session changed")
                    yield IndicatorWriterSession(self._connection)
                except BaseException:
                    with suppress(SQLAlchemyError, OSError, TimeoutError):
                        await _finish_transaction(self._connection, transaction, commit=False)
                    raise
                else:
                    try:
                        await _finish_transaction(self._connection, transaction, commit=True)
                    except BaseException:
                        self._tainted = True
                        raise
            except (SQLAlchemyError, OSError) as error:
                raise translate_database_error(error) from None
            except TimeoutError:
                self._tainted = True
                raise DatabaseTimeoutError("indicator writer cleanup timed out") from None

    async def seed(self) -> int:
        async with self._operations, self.transaction() as session:
            return await seed_jobs(session)

    async def coalesce(self) -> int:
        # A fresh serialized transaction: no slot/job row locks before source guard.
        async with self._operations, self.transaction() as session:
            return await coalesce_session(session)

    async def claim(self, owner: UUID) -> BuildClaim | None:
        async with self._operations:
            if self._dispatch_used:
                raise IndicatorBuildOwnershipError("indicator writer requires a fresh acquisition")
            self._dispatch_used = True
            async with self.transaction() as session:
                result = await claim_next(session, owner)
            # No source may be opened on the strength of a claim before this commit.
            self._claim = result
            return result

    async def heartbeat(self) -> None:
        async with self._operations:
            if self._claim is None:
                raise IndicatorBuildOwnershipError("indicator writer has no attempt")
            self.require_claim(self._claim)
            try:
                async with self.transaction() as session:
                    await heartbeat(session, self._claim)
            except BaseException:
                self._ownership_lost = True
                raise

    async def finish(self, outcome: AttemptOutcome) -> None:
        """Invoke only after the builder joins CPU work and closes its source snapshot."""
        async with self._operations:
            if self._claim is None:
                raise IndicatorBuildOwnershipError("indicator writer has no attempt")
            async with self.transaction() as session:
                await release(session, self._claim, outcome)
            self._claim = None

    async def publish_ready(self, claim: BuildClaim) -> PublicationResult:
        """Call after scan_staging returns, with source closed and heartbeat joined."""
        return await self._publish(claim, numeric=False)

    async def publish_numeric_failure(
        self, claim: BuildClaim, error: MoneyError
    ) -> PublicationResult:
        """Caller must first join work/heartbeat and close source after a core numeric error."""
        if not isinstance(error, MoneyError):
            raise TypeError("typed domain numeric error required")
        return await self._publish(claim, numeric=True)

    async def _publish(self, claim: BuildClaim, *, numeric: bool) -> PublicationResult:
        async with self._operations:
            self.require_claim(claim)
            async with self.transaction() as session:
                result = await publish(session, claim, numeric=numeric)
            # Ambiguous commit must leave ownership orphaned, just like release.
            self._claim = None
            return result

    async def _cleanup(self) -> None:
        if self._tainted or self._claim is not None or self._connection.invalidated:
            # Unknown/active ownership becomes an orphan, never an automatic takeover.
            await self._connection.invalidate()
            return
        async with self._connection.begin():
            released = bool(
                (
                    await _execute(
                        self._connection, "SELECT public.unlock_indicator_build_lock()", None
                    )
                ).scalar_one()
            )
        if not released:
            await self._connection.invalidate()


@asynccontextmanager
async def pinned_indicator_writer(
    engine: AsyncEngine,
    *,
    connection_mode: Literal["direct", "session", "transaction", "statement"],
) -> AsyncIterator[PinnedIndicatorWriter | None]:
    if connection_mode not in ("direct", "session"):
        raise IndicatorBuildConfigurationError("indicator builder requires a physical session")
    connection: AsyncConnection | None = None
    pinned: PinnedIndicatorWriter | None = None
    acquired = False
    acquire_confirmed = False
    try:
        connection = await engine.connect()
        async with connection.begin():
            await _assert_role(connection, DatabaseRole.INDICATOR_BUILDER)
            row = (
                (
                    await _execute(
                        connection,
                        """SELECT public.try_indicator_build_lock() AS acquired,
                pg_backend_pid() AS pid""",
                        None,
                    )
                )
                .mappings()
                .one()
            )
            acquired = bool(row["acquired"])
            pinned = PinnedIndicatorWriter(connection, int(row["pid"]))
        acquire_confirmed = True
        yield pinned if acquired else None
    except (SQLAlchemyError, OSError) as error:
        raise translate_database_error(error) from None
    finally:
        if connection is not None:

            async def cleanup() -> None:
                try:
                    if not acquire_confirmed:
                        # A failed/reentrant acquire may have inherited an unknown lock count.
                        await connection.invalidate()
                    elif acquired and pinned is not None:
                        await pinned._cleanup()
                    elif connection is not None and connection.in_transaction():
                        # Acquire's commit was ambiguous: discard the physical session.
                        await connection.invalidate()
                except BaseException:
                    await connection.invalidate()
                    raise
                finally:
                    await connection.close()

            task = asyncio.create_task(cleanup())
            try:
                await asyncio.wait_for(asyncio.shield(task), 2)
            except BaseException:
                await connection.invalidate()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
