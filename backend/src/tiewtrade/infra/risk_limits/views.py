"""Atomic owner/source/price evidence; cached READY alone never authorizes a trade."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from tiewtrade.core.money import Money, MoneyError, Quantity
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.positions import PositionError
from tiewtrade.core.risk_limits import (
    RiskBook,
    RiskEvaluation,
    RiskPrice,
    RiskReason,
    RiskScope,
    RiskSetting,
    RiskUnavailableError,
    evaluate_risk,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions.views import position_metadata_ready
from tiewtrade.infra.risk_limits.books import book_from_payload
from tiewtrade.infra.risk_limits.prices import decode_frame, read_frames
from tiewtrade.infra.risk_limits.storage import read_setting


@dataclass(frozen=True, slots=True)
class RiskEvidence:
    evaluation: RiskEvaluation
    book: RiskBook | None
    prices: tuple[RiskPrice, ...]
    admission_enabled: bool
    price_watermark: int | None = None
    input_ready_at: datetime | None = None
    unavailable_since: datetime | None = None
    pause_alert_due: bool = False


# Every component uses one PostgreSQL statement snapshot, including the latest
# price watermark. API readers need neither financial writer grants nor a lock
# on the producer. Money values become text before the JSON decoder sees them.
_EVIDENCE = """SELECT o.*,e.setting_revision,e.replay_pending AS evaluation_pending,
  e.reason AS evaluation_reason,e.unavailable_since,
  c.publication_enabled,c.admission_enabled,p.watermark AS current_watermark,
  f.id AS frame_id,f.payload AS price_payload,f.proof AS frame_proof,
  f.captured_at AS frame_at,
  f.proof=encode(sha256(convert_to(f.payload::text,'UTF8')),'hex') AS frame_valid,
  clock_timestamp() AS now,to_jsonb(metadata) AS metadata,
  coalesce(b.sequence,0) AS latest_boundary,
  coalesce(b.price_watermark,0) AS boundary_watermark,b.recorded_at AS boundary_at,
  coalesce((SELECT jsonb_agg(jsonb_build_object('base',x.base,'quote',x.quote,
    'held',x.held_quantity::text,'cost',x.total_cost::text) ORDER BY x.base,x.quote)
    FROM paper_position_projections x WHERE x.episode_id=:episode),'[]'::jsonb) positions
FROM (SELECT * FROM risk_protocol_control LIMIT 1) c
CROSS JOIN (SELECT * FROM risk_price_publication LIMIT 1) p
LEFT JOIN LATERAL (SELECT sequence,price_watermark,recorded_at FROM risk_financial_boundaries
  WHERE mode=:mode ORDER BY sequence DESC LIMIT 1) b ON true
LEFT JOIN risk_owner_state o ON o.mode=:mode
LEFT JOIN risk_limit_evaluations e ON e.user_id=o.user_id AND e.mode=o.mode
LEFT JOIN market_risk_price_frames f ON f.id=p.watermark
LEFT JOIN LATERAL paper_wallet_reset_readiness(:episode) metadata ON true"""


async def read_evidence(
    session: UserSession, setting: RiskSetting, *, api_price_tail: bool = False
) -> RiskEvidence:
    """API tail reads require the caller's owner lock or consistent read snapshot.

    Only public price frames may be replayed here. Financial source/boundary and
    pending checks remain mandatory; ENGINE callers retain the default protocol.
    """
    checked = require_user_session(session)
    if setting.scope.owner_id != checked.user_id:
        raise ValueError("risk evidence owner mismatch")
    row = (
        (
            await checked.execute(
                _EVIDENCE, {"mode": setting.scope.mode.value, "episode": setting.scope.episode_id}
            )
        )
        .mappings()
        .one()
    )
    unavailable = RiskEvaluation(
        setting.scope,
        setting.revision,
        0,
        row["now"],
        RiskReason.SOURCE_UNAVAILABLE,
        None,
        setting.latched,
        False,
    )
    enabled = bool(row["admission_enabled"]) and setting.scope.mode is TradingMode.PAPER
    unknown = RiskEvidence(unavailable, None, (), enabled)
    if setting.scope.mode is TradingMode.LIVE or not row["publication_enabled"]:
        return unknown
    try:
        frame = (
            None
            if not row["current_watermark"]
            else decode_frame(
                {
                    "id": row["frame_id"],
                    "payload": row["price_payload"],
                    "proof": row["frame_proof"],
                    "captured_at": row["frame_at"],
                }
            )
        )
        if frame is not None and not row["frame_valid"]:
            return unknown
        prices = () if frame is None else frame.prices
        source: Any = row["metadata"]
        if (
            row["wallet_id"] != setting.scope.wallet_id
            or row["episode_id"] != setting.scope.episode_id
            or row["replay_pending"]
            or row["evaluation_pending"]
            or row["setting_revision"] != setting.revision
            or row["boundary_cursor"] != row["latest_boundary"]
            or row["cursor"] < row["boundary_watermark"]
            or not position_metadata_ready(source)
            or source["position_revision"] != row["source_revision"]
            or source["position_proof"] != row["source_proof"]
        ):
            return RiskEvidence(unavailable, None, prices, enabled)
        lag = int(row["current_watermark"]) - int(row["cursor"])
        if lag < 0 or lag > (100 if api_price_tail else 0):
            return RiskEvidence(unavailable, None, prices, enabled)
        book = book_from_payload(setting.scope, int(row["source_revision"]), row["book"])
        positions = row["positions"]
        if len(positions) != len(book.pairs) or any(
            (position["base"], position["quote"])
            != (item.position.pair.base, item.position.pair.quote)
            or Quantity.of(position["held"], position["base"]) != item.position.held_quantity
            or Money.of(position["cost"], position["quote"]) != item.position.total_cost
            for position, item in zip(positions, book.pairs, strict=True)
        ):
            return RiskEvidence(unavailable, None, prices, enabled)
        pause_since = (
            row["unavailable_since"]
            if row["evaluation_reason"] == RiskReason.PRICE_UNAVAILABLE.value
            else None
        )
        if lag:
            frames = await read_frames(
                checked, after=int(row["cursor"]), through=int(row["current_watermark"])
            )
            observed_breach = False
            for historical in frames:
                decision = evaluate_risk(
                    setting, book, historical.prices, now=historical.captured_at, source_ready=True
                )
                observed_breach = observed_breach or decision.new_breach
                pause_since = (
                    pause_since or historical.captured_at
                    if decision.reason is RiskReason.PRICE_UNAVAILABLE
                    else None
                )
            if observed_breach:
                # Refuse even when a later frame recovers. Only the engine may
                # commit the durable latch/stop; POST records its existing hint.
                return RiskEvidence(
                    replace(unavailable, source_revision=book.source_revision),
                    book,
                    prices,
                    enabled,
                )
        # Tail verification can take time; freshness is checked at completion.
        now = (
            (await checked.execute("SELECT clock_timestamp()")).scalar_one() if lag else row["now"]
        )
        result = evaluate_risk(setting, book, prices, now=now, source_ready=True)
        # API cannot announce a new durable latch; the engine must commit the
        # decision and stop request. The intake records a durable evaluation hint.
        if result.new_breach:
            result = replace(unavailable, source_revision=book.source_revision, evaluated_at=now)
        pause_since = pause_since or now if result.reason is RiskReason.PRICE_UNAVAILABLE else None
        ready_at = max(
            (at for at in (row["frame_at"], row["boundary_at"]) if at is not None),
            default=None,
        )
        return RiskEvidence(
            result,
            book,
            prices,
            enabled,
            int(row["current_watermark"]),
            ready_at if result.loss is not None else None,
            pause_since,
            pause_since is not None and now - pause_since >= timedelta(minutes=5),
        )
    except (RiskUnavailableError, MoneyError, PositionError, ValueError, KeyError, TypeError):
        return unknown


async def current_evaluation(session: UserSession, setting: RiskSetting) -> RiskEvaluation:
    return (await read_evidence(session, setting)).evaluation


async def wallet_evidence(session: UserSession) -> tuple[RiskSetting, RiskEvidence] | None:
    wallet = await get_wallet(session)
    if wallet is None:
        return None
    scope = RiskScope(
        UUID(str(session.user_id)),
        TradingMode.PAPER,
        UUID(str(wallet.wallet_id)),
        UUID(str(wallet.episode_id)),
    )
    setting = await read_setting(session, scope)
    return setting, await read_evidence(session, setting, api_price_tail=True)
