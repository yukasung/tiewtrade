from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.order_book_fixtures import capability
from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.infra.db import CatalogRevisionConflictError
from tiewtrade.infra.platform.records import CatalogEntry, CatalogStatus, CatalogView
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
        expected_revision: int,
        failure_code: str,
    ) -> None:
        assert expected_revision == 7
        failures.append(failure_code)

    async def read(_session: object) -> CatalogView:
        return CatalogView(
            CatalogSnapshot(7, frozenset()),
            (CatalogEntry("SOL", "USDT", CatalogStatus.PREPARING, 3, datetime.now(UTC)),),
            True,
        )

    monkeypatch.setattr(catalog, "presented_session", session)
    monkeypatch.setattr(catalog, "user_session", session)
    monkeypatch.setattr(catalog, "read_catalog", read)
    monkeypatch.setattr(catalog, "requested_symbols", requested)
    monkeypatch.setattr(catalog, "preparing_symbols", preparing)
    monkeypatch.setattr(catalog, "reconcile_maintenance_proofs", reconcile)
    monkeypatch.setattr(catalog, "_fail_preparation", fail)

    activated = await catalog.activate_ready_symbols(
        cast(AsyncEngine, object()), cast(ExecutionCapabilitySource, FailingCapabilitySource(error))
    )

    assert activated == 0
    assert failures == ([] if terminal_code is None else [terminal_code])


@pytest.mark.parametrize("venue_failure", [False, True])
@pytest.mark.parametrize("replaced_before_check", [False, True])
async def test_delayed_venue_result_cannot_transition_a_replacement_command(
    monkeypatch: pytest.MonkeyPatch,
    venue_failure: bool,
    replaced_before_check: bool,
) -> None:
    requester = UUID(int=7)
    revision = 9 if replaced_before_check else 7
    venue_calls = 0
    attempted: list[int] = []
    replacement_state = "PREPARING"

    @asynccontextmanager
    async def session(*_args: object, **_kwargs: object) -> AsyncIterator[object]:
        yield object()

    async def requested(_session: object) -> tuple[tuple[str, str, int, UUID], ...]:
        return ()

    async def preparing(_session: object) -> tuple[tuple[str, str, int, UUID], ...]:
        return (("SOL", "USDT", 3, requester),)

    async def reconcile(_session: object) -> int:
        return 0

    async def read(_session: object) -> CatalogView:
        return CatalogView(
            CatalogSnapshot(revision, frozenset()),
            (
                CatalogEntry(
                    "SOL",
                    "USDT",
                    CatalogStatus.PREPARING,
                    8 if revision == 9 else 3,
                    datetime.now(UTC),
                ),
            ),
            True,
        )

    class Source:
        async def capability(self, symbol: Symbol) -> object:
            nonlocal revision, venue_calls
            venue_calls += 1
            # Another coordinator fails the old command and the same requester retries ADD.
            revision = 9
            if venue_failure:
                raise VenueProtocolError()
            return capability(datetime.now(UTC), symbol=symbol)

    async def transition(_session: object, **kwargs: object) -> int:
        nonlocal replacement_state
        expected = cast(int, kwargs["expected_revision"])
        attempted.append(expected)
        if expected != revision:
            raise CatalogRevisionConflictError()
        replacement_state = "FAILED" if venue_failure else "ACTIVE"
        return revision + 1

    monkeypatch.setattr(catalog, "presented_session", session)
    monkeypatch.setattr(catalog, "user_session", session)
    monkeypatch.setattr(catalog, "requested_symbols", requested)
    monkeypatch.setattr(catalog, "preparing_symbols", preparing)
    monkeypatch.setattr(catalog, "reconcile_maintenance_proofs", reconcile)
    monkeypatch.setattr(catalog, "read_catalog", read)
    monkeypatch.setattr(catalog, "activate", transition)
    monkeypatch.setattr(catalog, "fail_preparation", transition)

    assert (
        await catalog.activate_ready_symbols(
            cast(AsyncEngine, object()), cast(ExecutionCapabilitySource, Source())
        )
        == 0
    )
    assert replacement_state == "PREPARING"
    assert venue_calls == (0 if replaced_before_check else 1)
    assert attempted == ([] if replaced_before_check else [7])
