"""R16 owner-locked, transaction-local inputs for standalone chronological replay."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.positions.records import PositionSnapshot
from tiewtrade.infra.positions.storage import POSITION_SNAPSHOT_SQL, decode_position_snapshot
from tiewtrade.infra.risk_limits.prices import RiskPriceFrame, decode_frames


@dataclass(frozen=True, slots=True)
class MonitorSnapshot:
    owner_id: UUID
    owner: Any
    state: Any
    boundaries: list[Any]
    frames: list[Any]
    positions: list[Any]

    def read_frames(
        self, *, after: int, through: int, limit: int = 100
    ) -> tuple[RiskPriceFrame, ...]:
        rows = [row for row in self.frames if after < row["id"] <= through][:limit]
        return decode_frames(rows, after=after, through=through, limit=limit)

    def position(self, episode_id: UUID) -> PositionSnapshot | None:
        rows = [row for row in self.positions if row["episode_id"] == episode_id]
        return decode_position_snapshot(rows)


def _row(document: str) -> Any:
    # PostgreSQL numeric tokens go directly to exact strings, never Python float.
    row = json.loads(document, parse_float=str)
    for key in ("user_id", "wallet_id", "episode_id", "after_episode_id", "active_episode_id"):
        if row.get(key) is not None:
            row[key] = UUID(row[key])
    for key in ("captured_at", "recorded_at", "observed_at", "snapshot_at"):
        if row.get(key) is not None:
            row[key] = datetime.fromisoformat(row[key])
    return row


async def read_monitor_snapshot(session: UserSession) -> MonitorSnapshot:
    """Caller must hold the financial owner lock before this statement starts."""
    checked = require_user_session(session)
    # Reuse the exact F14 statement and validators. Only its episode binding is
    # supplied by the owner row; all parts use this statement's MVCC snapshot.
    positions_sql = POSITION_SNAPSHOT_SQL.replace(
        ":episode", "(SELECT active_episode_id FROM owner)"
    )
    rows = await checked.execute(
        f"""WITH owner AS MATERIALIZED (
          SELECT w.wallet_id,w.active_episode_id,s.revision,s.amount,s.latched,o.source_revision
          FROM paper_wallet_state w
          LEFT JOIN risk_limit_settings s ON s.user_id=w.user_id AND s.mode='PAPER'
          LEFT JOIN risk_owner_state o ON o.user_id=w.user_id AND o.mode='PAPER'
          WHERE w.user_id=:owner
        ), state AS MATERIALIZED (
          SELECT o.*,e.reason previous_reason,p.watermark captured_watermark
          FROM risk_owner_state o CROSS JOIN risk_price_publication p
          LEFT JOIN risk_limit_evaluations e ON (e.user_id,e.mode)=(o.user_id,o.mode)
          WHERE o.mode='PAPER'
        ), boundaries AS MATERIALIZED (
          SELECT b.* FROM risk_financial_boundaries b CROSS JOIN state s
          WHERE b.mode='PAPER' AND b.sequence>s.boundary_cursor
          ORDER BY b.sequence LIMIT 21
        ), frames AS MATERIALIZED (
          SELECT f.id,f.captured_at,f.proof,f.payload::text AS payload_json,
            f.proof=encode(sha256(convert_to(f.payload::text,'UTF8')),'hex') AS valid
          FROM market_risk_price_frames f CROSS JOIN state s
          WHERE f.id>=greatest(s.cursor,1)
            AND f.id<=least(s.captured_watermark,s.cursor+100)
          ORDER BY f.id LIMIT 101
        ), positions AS MATERIALIZED ({positions_sql})
        SELECT 'owner' kind,to_jsonb(r)::text document FROM owner r
        UNION ALL SELECT 'state',to_jsonb(r)::text FROM state r
        UNION ALL SELECT 'boundary',to_jsonb(r)::text FROM boundaries r
        UNION ALL SELECT 'frame',to_jsonb(r)::text FROM frames r
        UNION ALL SELECT 'position',to_jsonb(r)::text FROM positions r""",
        {"owner": checked.user_id},
    )
    groups: dict[str, list[Any]] = {
        key: [] for key in ("owner", "state", "boundary", "frame", "position")
    }
    for row in rows:
        groups[row.kind].append(_row(row.document))
    return MonitorSnapshot(
        checked.user_id,
        next(iter(groups["owner"]), None),
        next(iter(groups["state"]), None),
        sorted(groups["boundary"], key=lambda row: row["sequence"]),
        sorted(groups["frame"], key=lambda row: row["id"]),
        sorted(groups["position"], key=lambda row: (row["base"] or "", row["quote"] or "")),
    )
