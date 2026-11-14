"""Narrow owner reads using the existing source-readiness function and API grants."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.core.positions import PositionAvailability, PositionPair
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.positions.records import PositionSnapshot


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
    *,
    validated_snapshot: PositionSnapshot | None = None,
) -> tuple[Quantity, Quantity]:
    session = require_user_session(session)
    # The worker has decoded the complete snapshot under its owner financial lock.
    # Recheck its source version with the current quantities; never reuse quantities.
    activity = None if validated_snapshot is None else validated_snapshot.activity
    if activity is not None and (
        activity.user_id != session.user_id
        or activity.episode_id != episode_id
        or activity.mode != "PAPER"
        or activity.availability is not PositionAvailability.READY
        or activity.source_proof is None
    ):
        raise SourceUnavailableError("authoritative holdings are unavailable")
    if activity is None and await ready_position_metadata(session, episode_id) is None:
        raise SourceUnavailableError("authoritative holdings are unavailable")
    metadata_columns = ""
    metadata_source = ""
    if activity is not None:
        metadata_columns = ", a.availability, a.revision, a.source_sequence, a.source_proof"
        metadata_source = " FROM paper_position_activity a WHERE a.episode_id=:episode"
    row = (
        await session.execute(
            f"""SELECT (SELECT held_quantity FROM paper_position_projections
            WHERE episode_id=:episode AND base=:base AND quote=:quote) AS held,
          (SELECT coalesce(sum(base_reserved),0) FROM paper_reservations
            WHERE episode_id=:episode AND base=:base AND quote=:quote) AS reserved
          {metadata_columns}{metadata_source}""",
            {"episode": episode_id, "base": pair.base, "quote": pair.quote},
        )
    ).one_or_none()
    if row is None or (
        activity is not None
        and (
            row.availability != "READY"
            or row.revision != activity.revision
            or row.source_sequence != activity.source_sequence
            or row.source_proof != activity.source_proof
        )
    ):
        raise SourceUnavailableError("authoritative holdings are unavailable")
    return Quantity.of(0 if row.held is None else row.held, pair.base), Quantity.of(
        row.reserved, pair.base
    )
