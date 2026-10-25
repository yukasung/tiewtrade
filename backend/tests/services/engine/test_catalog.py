from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.services.engine import catalog
from tiewtrade.venues import (
    ExecutionCapabilitySource,
    Symbol,
    VenueError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueUnavailableError,
)


class FailingCapabilitySource:
    def __init__(self, error: VenueError) -> None:
        self.error = error

    async def capability(self, _symbol: Symbol) -> object:
        raise self.error

    async def close(self) -> None:
        return None


@pytest.mark.parametrize(
    ("error", "terminal_code"),
    [
        (VenueProtocolError(), "VENUE_PROTOCOL"),
        (VenueUnavailableError(), None),
        (VenueRateLimitedError(), None),
    ],
)
async def test_activation_retries_only_retry_safe_venue_failures(
    monkeypatch: pytest.MonkeyPatch,
    error: VenueError,
    terminal_code: str | None,
) -> None:
    requester = UUID(int=7)
    failures: list[str] = []

    @asynccontextmanager
    async def session(*_args: object, **_kwargs: object) -> AsyncIterator[object]:
        yield object()

    async def requested(_session: object) -> tuple[tuple[str, str, int, UUID], ...]:
        return ()

    async def preparing(_session: object) -> tuple[tuple[str, str, int, UUID], ...]:
        return (("SOL", "USDT", 3, requester),)

    async def reconcile(_session: object) -> int:
        return 0

    async def fail(
        _engine: AsyncEngine,
        _requester: UUID,
        _base: str,
        _quote: str,
        failure_code: str,
    ) -> None:
        failures.append(failure_code)

    monkeypatch.setattr(catalog, "presented_session", session)
    monkeypatch.setattr(catalog, "requested_symbols", requested)
    monkeypatch.setattr(catalog, "preparing_symbols", preparing)
    monkeypatch.setattr(catalog, "reconcile_maintenance_proofs", reconcile)
    monkeypatch.setattr(catalog, "_fail_preparation", fail)

    activated = await catalog.activate_ready_symbols(
        cast(AsyncEngine, object()), cast(ExecutionCapabilitySource, FailingCapabilitySource(error))
    )

    assert activated == 0
    assert failures == ([] if terminal_code is None else [terminal_code])
