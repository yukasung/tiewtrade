"""Database-only supported-symbol catalog storage.

Venue checks and orchestration stay in services. This module only calls the
database contracts that serialize revision and idempotency decisions.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Protocol, cast
from uuid import UUID, uuid5

from sqlalchemy.engine import RowMapping

from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.infra.db.errors import CatalogIdempotencyConflictError
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.platform.records import (
    CatalogAction,
    CatalogCommand,
    CatalogEffect,
    CatalogEntry,
    CatalogReason,
    CatalogStatus,
    CatalogView,
    ConstraintEvidence,
    ImpactPreview,
    PlatformRole,
)


class _Executor(Protocol):
    async def execute(
        self, statement: str, parameters: Mapping[str, object] | None = None
    ) -> object: ...


async def record_protocol_heartbeat(
    session: _Executor,
    *,
    process_kind: str,
    instance_id: UUID,
    protocol_version: int,
    deployment_generation: UUID,
    lease_expires_at: datetime,
) -> None:
    await session.execute(
        "SELECT catalog_protocol_heartbeat(:kind,:instance,:version,:generation,:expires)",
        {
            "kind": process_kind,
            "instance": instance_id,
            "version": protocol_version,
            "generation": deployment_generation,
            "expires": lease_expires_at,
        },
    )


async def role_for(session: UserSession) -> PlatformRole | None:
    checked = require_user_session(session)
    value = (
        await checked.execute(
            "SELECT role FROM platform_memberships WHERE user_id=:user_id",
            {"user_id": checked.user_id},
        )
    ).scalar_one_or_none()
    return None if value is None else PlatformRole(value)


async def enable_mutations(
    session: UserSession, *, deployment_generation: UUID, expected_revision: int
) -> None:
    checked = require_user_session(session)
    await checked.execute(
        "SELECT enable_supported_symbol_mutations(:requester,:generation,:revision)",
        {
            "requester": checked.user_id,
            "generation": deployment_generation,
            "revision": expected_revision,
        },
    )


async def read_catalog(session: UserSession) -> CatalogView:
    checked = require_user_session(session)
    rows = (
        (
            await checked.execute(
                """SELECT c.current_revision,c.mutations_enabled,
              f.base,f.quote,f.status,f.revision,f.updated_at,
              effect.status AS effect_status,effect.attempts,effect.bots_stopped,
              effect.commands_rejected,effect.orders_canceled,effect.orders_unresolved,
              effect.error_code,effect.updated_at AS effect_updated_at
            FROM supported_symbol_catalog_control c
            LEFT JOIN supported_symbol_fences f ON true
            LEFT JOIN supported_symbol_effects effect ON effect.event_revision=f.revision
            WHERE c.id=1 ORDER BY f.base,f.quote"""
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        raise RuntimeError("supported-symbol catalog control is missing")
    entries = tuple(
        CatalogEntry(
            row["base"],
            row["quote"],
            CatalogStatus(row["status"]),
            row["revision"],
            row["updated_at"],
            None
            if row["effect_status"] is None
            else CatalogEffect(
                row["effect_status"],
                row["attempts"],
                row["bots_stopped"],
                row["commands_rejected"],
                row["orders_canceled"],
                row["orders_unresolved"],
                row["error_code"],
                row["effect_updated_at"],
            ),
        )
        for row in rows
        if row["base"] is not None
    )
    return CatalogView(
        CatalogSnapshot(
            rows[0]["current_revision"],
            frozenset(
                (entry.base, entry.quote)
                for entry in entries
                if entry.status is CatalogStatus.ACTIVE
            ),
        ),
        entries,
        rows[0]["mutations_enabled"],
    )


async def request_add(
    session: UserSession,
    *,
    command_id: UUID,
    idempotency_key: str,
    base: str,
    quote: str,
    expected_revision: int,
    reason: CatalogReason,
    evidence: ConstraintEvidence,
) -> CatalogCommand:
    checked = require_user_session(session)
    row = (
        (
            await checked.execute(
                """SELECT * FROM request_supported_symbol_add(
              :command_id,:requester,:idempotency_key,:base,:quote,:expected_revision,
              :reason,:snapshot_id,:venue_symbol,:source_at,CAST(:payload AS jsonb),:digest)""",
                {
                    "command_id": command_id,
                    "requester": checked.user_id,
                    "idempotency_key": idempotency_key,
                    "base": base,
                    "quote": quote,
                    "expected_revision": expected_revision,
                    "reason": reason.value,
                    "snapshot_id": uuid5(command_id, evidence.digest),
                    "venue_symbol": evidence.venue_symbol,
                    "source_at": evidence.observed_at,
                    "payload": evidence.source_document,
                    "digest": evidence.digest,
                },
            )
        )
        .mappings()
        .one()
    )
    return _command(row)


async def replay_command(
    session: UserSession,
    *,
    idempotency_key: str,
    action: CatalogAction,
    base: str,
    quote: str,
    expected_revision: int,
    reason: CatalogReason,
) -> CatalogCommand | None:
    """Return an exact durable replay before an ADD retry touches the venue."""
    checked = require_user_session(session)
    row = (
        (
            await checked.execute(
                """SELECT id,action,base,quote,state,revision,created_at,completed_at,
                  expected_revision,reason_code
                FROM supported_symbol_commands
                WHERE requested_by=:requester AND idempotency_key=:idempotency_key""",
                {"requester": checked.user_id, "idempotency_key": idempotency_key},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    if (
        str(row["action"]),
        str(row["base"]),
        str(row["quote"]),
        int(str(row["expected_revision"])),
        str(row["reason_code"]),
    ) != (action.value, base, quote, expected_revision, reason.value):
        raise CatalogIdempotencyConflictError()
    return _command(row)


async def request_remove(
    session: UserSession,
    *,
    command_id: UUID,
    idempotency_key: str,
    base: str,
    quote: str,
    expected_revision: int,
    reason: CatalogReason,
) -> CatalogCommand:
    checked = require_user_session(session)
    row = (
        (
            await checked.execute(
                """SELECT * FROM request_supported_symbol_remove(
            :command_id,:requester,:idempotency_key,:base,:quote,
            :expected_revision,:reason)""",
                {
                    "command_id": command_id,
                    "requester": checked.user_id,
                    "idempotency_key": idempotency_key,
                    "base": base,
                    "quote": quote,
                    "expected_revision": expected_revision,
                    "reason": reason.value,
                },
            )
        )
        .mappings()
        .one()
    )
    return _command(row)


async def impact_preview(session: UserSession, base: str, quote: str) -> ImpactPreview:
    checked = require_user_session(session)
    row = (
        (
            await checked.execute(
                "SELECT * FROM supported_symbol_impact_preview(:base,:quote)",
                {"base": base, "quote": quote},
            )
        )
        .mappings()
        .one()
    )
    return ImpactPreview(
        base,
        quote,
        row["bots"],
        row["open_entry_orders"],
        row["protective_orders"],
        row["reduce_risk_orders"],
        row["positions"],
        row["complete"],
        row["snapshot_at"],
    )


def _command(values: RowMapping) -> CatalogCommand:
    return CatalogCommand(
        UUID(str(values["id"])),
        CatalogAction(str(values["action"])),
        str(values["base"]),
        str(values["quote"]),
        str(values["state"]),
        None if values["revision"] is None else int(str(values["revision"])),
        cast(datetime, values["created_at"]),
        cast(datetime | None, values["completed_at"]),
    )
