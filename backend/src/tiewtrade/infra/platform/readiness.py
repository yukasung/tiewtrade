"""Revision-fenced readiness proof persistence for catalog workers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import Result

from tiewtrade.core.timeframes import Timeframe
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.platform.records import CatalogStatus, ConstraintEvidence


class _Executor(Protocol):
    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Result[Any]: ...


@dataclass(frozen=True, slots=True)
class RuntimeSymbol:
    base: str
    quote: str
    status: str
    revision: int
    catalog_revision: int
    mode: str


async def runtime_symbols(session: _Executor) -> tuple[RuntimeSymbol, ...]:
    result = await session.execute(
        """SELECT base,quote,status,revision,current_revision,runtime_mode
        FROM runtime_supported_symbols ORDER BY base,quote"""
    )
    return tuple(
        RuntimeSymbol(
            row["base"],
            row["quote"],
            row["status"],
            row["revision"],
            row["current_revision"],
            row["runtime_mode"],
        )
        for row in result.mappings()
    )


async def record_price_readiness(
    session: _Executor,
    *,
    base: str,
    quote: str,
    catalog_revision: int,
    price_at: datetime,
) -> None:
    await session.execute(
        "SELECT record_supported_symbol_price_readiness(:base,:quote,:revision,:ready_at)",
        {"base": base, "quote": quote, "revision": catalog_revision, "ready_at": price_at},
    )


async def record_timeframe_readiness(
    session: _Executor,
    *,
    base: str,
    quote: str,
    catalog_revision: int,
    timeframe: Timeframe,
    ready_at: datetime,
) -> None:
    await session.execute(
        """SELECT record_supported_symbol_timeframe_readiness(
        :base,:quote,:revision,:timeframe,:ready_at)""",
        {
            "base": base,
            "quote": quote,
            "revision": catalog_revision,
            "timeframe": timeframe.value,
            "ready_at": ready_at,
        },
    )


async def _symbols_with_status(
    session: _Executor, status: CatalogStatus
) -> tuple[tuple[str, str, int, UUID], ...]:
    result = await session.execute(
        """SELECT base,quote,revision,requested_by FROM supported_symbol_fences
        WHERE status=:status ORDER BY revision""",
        {"status": status.value},
    )
    return tuple(
        (row["base"], row["quote"], row["revision"], row["requested_by"])
        for row in result.mappings()
    )


async def preparing_symbols(session: _Executor) -> tuple[tuple[str, str, int, UUID], ...]:
    return await _symbols_with_status(session, CatalogStatus.PREPARING)


async def requested_symbols(session: _Executor) -> tuple[tuple[str, str, int, UUID], ...]:
    return await _symbols_with_status(session, CatalogStatus.REQUESTED)


async def prepare(
    session: UserSession,
    *,
    base: str,
    quote: str,
    expected_revision: int,
) -> int:
    checked = require_user_session(session)
    value = (
        await checked.execute(
            "SELECT prepare_supported_symbol(:requester,:base,:quote,:expected_revision)",
            {
                "requester": checked.user_id,
                "base": base,
                "quote": quote,
                "expected_revision": expected_revision,
            },
        )
    ).scalar_one()
    return int(value)


async def fail_preparation(
    session: UserSession,
    *,
    base: str,
    quote: str,
    expected_revision: int,
    failure_code: str,
) -> int:
    checked = require_user_session(session)
    value = (
        await checked.execute(
            """SELECT fail_supported_symbol_preparation(
            :requester,:base,:quote,:expected_revision,:failure_code)""",
            {
                "requester": checked.user_id,
                "base": base,
                "quote": quote,
                "expected_revision": expected_revision,
                "failure_code": failure_code,
            },
        )
    ).scalar_one()
    return int(value)


async def activate(
    session: UserSession,
    *,
    base: str,
    quote: str,
    expected_revision: int,
    validation_started_at: datetime,
    evidence: ConstraintEvidence,
) -> int:
    checked = require_user_session(session)
    snapshot_id = uuid4()
    value = (
        await checked.execute(
            """SELECT activate_supported_symbol(
            :requester,:base,:quote,:expected_revision,:snapshot_id,:venue_symbol,
            :validation_started_at,:source_at,CAST(:payload AS jsonb),:digest)""",
            {
                "requester": checked.user_id,
                "base": base,
                "quote": quote,
                "expected_revision": expected_revision,
                "snapshot_id": snapshot_id,
                "venue_symbol": evidence.venue_symbol,
                "validation_started_at": validation_started_at,
                "source_at": evidence.observed_at,
                "payload": evidence.source_document,
                "digest": evidence.digest,
            },
        )
    ).scalar_one()
    return int(value)
