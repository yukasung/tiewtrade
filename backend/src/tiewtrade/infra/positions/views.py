"""Narrow owner reads using the existing source-readiness function and API grants."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db.session import UserSession, require_user_session


def position_metadata_ready(row: Mapping[str, Any] | None) -> bool:
    return row is not None and (
        row["position_availability"] == "READY"
        and row["position_proof"] is not None
        and row["position_record_count"] == row["position_sequence"]
        and row["position_max_sequence"] == row["position_sequence"]
        and row["position_pair_count"] == row["position_projection_count"]
        and row["position_revision_mismatch"] == 0
    )


async def ready_position_metadata(session: UserSession, episode_id: UUID) -> dict[str, Any] | None:
    checked = require_user_session(session)
    row = (
        (
            await checked.execute(
                "SELECT * FROM paper_wallet_reset_readiness(:episode)", {"episode": episode_id}
            )
        )
        .mappings()
        .one_or_none()
    )
    data = None if row is None else dict(row)
    return data if position_metadata_ready(data) else None


async def held_and_reserved(
    session: UserSession,
    episode_id: UUID,
    pair: PositionPair,
) -> tuple[Quantity, Quantity]:
    if await ready_position_metadata(session, episode_id) is None:
        raise SourceUnavailableError("authoritative holdings are unavailable")
    row = (
        await session.execute(
            """SELECT (SELECT held_quantity FROM paper_position_projections
            WHERE episode_id=:episode AND base=:base AND quote=:quote) AS held,
          (SELECT coalesce(sum(base_reserved),0) FROM paper_reservations
            WHERE episode_id=:episode AND base=:base AND quote=:quote) AS reserved""",
            {"episode": episode_id, "base": pair.base, "quote": pair.quote},
        )
    ).one()
    return Quantity.of(0 if row.held is None else row.held, pair.base), Quantity.of(
        row.reserved, pair.base
    )
