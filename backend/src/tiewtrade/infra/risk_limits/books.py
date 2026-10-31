"""Risk accounting projections rebuilt exclusively from authoritative F-14 facts."""

from datetime import datetime
from typing import Any

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import PositionAvailability, PositionPair, PositionState
from tiewtrade.core.risk_limits import (
    PairRiskState,
    RiskBook,
    RiskScope,
    RiskUnavailableError,
    initial_risk_book,
    rebuild_pair_risk,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.positions import read_position_snapshot
from tiewtrade.infra.positions.storage import read_effective_executions_at
from tiewtrade.infra.risk_limits.prices import read_frame


def book_payload(book: RiskBook) -> dict[str, object]:
    return {
        "pairs": [
            {
                "base": item.position.pair.base,
                "quote": item.position.pair.quote,
                "held": str(item.position.held_quantity.amount),
                "cost": str(item.position.total_cost.amount),
                "realized": str(item.position.realized_pnl.amount),
                "sequence": item.position.last_sequence,
                "allowance": str(item.allowance.amount),
                "adjusted": str(item.adjusted_realized.amount),
            }
            for item in book.pairs
        ]
    }


def book_from_payload(scope: RiskScope, revision: int, payload: Any) -> RiskBook:
    return RiskBook(
        scope,
        revision,
        tuple(
            PairRiskState(
                PositionState(
                    PositionPair(row["base"], row["quote"]),
                    Quantity.of(row["held"], row["base"]),
                    Money.of(row["cost"], row["quote"]),
                    Money.of(row["realized"], row["quote"]),
                    int(row["sequence"]),
                ),
                Money.of(row["allowance"], "USDT"),
                Money.of(row["adjusted"], "USDT"),
            )
            for row in payload["pairs"]
        ),
    )


async def reconstruct_book(
    session: UserSession,
    scope: RiskScope,
    *,
    positions: tuple[PositionState, ...],
    revision: int,
    sequence: int,
) -> RiskBook:
    checked = require_user_session(session)
    baseline = (
        await checked.execute(
            """SELECT b.snapshot FROM risk_limit_settings s JOIN risk_limit_baselines b
        ON (b.id,b.user_id,b.mode)=(s.baseline_id,s.user_id,s.mode)
        WHERE s.mode=:mode AND b.episode_id=:episode AND b.wallet_id=:wallet""",
            {"mode": scope.mode.value, "episode": scope.episode_id, "wallet": scope.wallet_id},
        )
    ).scalar_one_or_none()
    if baseline is None:
        return initial_risk_book(scope, positions, source_revision=revision)
    cutoff = int(baseline["source_sequence"])
    if cutoff > sequence:
        raise RiskUnavailableError("baseline cutoff is ahead of the authoritative source")
    frame = await read_frame(checked, int(baseline["price_watermark"]))
    reset_at = datetime.fromisoformat(baseline["reset_at"])
    prices = {price.pair: price.price_at(reset_at) for price in frame.prices}
    pairs = []
    for position in positions:
        assert scope.episode_id is not None
        facts = await read_effective_executions_at(
            checked,
            scope.episode_id,
            position.pair,
            source_revision=revision,
            source_sequence=sequence,
        )
        by_sequence = {fact.source_sequence: fact for fact in facts}
        item = rebuild_pair_risk(
            position.pair,
            tuple(by_sequence.get(index) for index in range(1, sequence + 1)),
            cutoff=cutoff,
            reset_price=prices.get(position.pair),
        )
        if item.position != position:
            raise RiskUnavailableError("risk reconstruction disagrees with position source")
        pairs.append(item)
    return RiskBook(scope, revision, tuple(pairs))


async def authoritative_book(session: UserSession, scope: RiskScope) -> tuple[RiskBook, str]:
    checked = require_user_session(session)
    if scope.owner_id != checked.user_id or scope.episode_id is None:
        raise RiskUnavailableError("authoritative Paper source required")
    snapshot = await read_position_snapshot(checked, scope.episode_id)
    if snapshot is None or snapshot.activity.availability is not PositionAvailability.READY:
        raise RiskUnavailableError("position source is not ready")
    activity = snapshot.activity
    if activity.source_proof is None or activity.wallet_id != scope.wallet_id:
        raise RiskUnavailableError("position source scope or proof is unavailable")
    return await reconstruct_book(
        checked,
        scope,
        positions=snapshot.positions,
        revision=activity.revision,
        sequence=activity.source_sequence,
    ), activity.source_proof


def marker_positions(snapshot: Any) -> tuple[PositionState, ...]:
    return tuple(
        PositionState(
            PositionPair(row["base"], row["quote"]),
            Quantity.of(row["held_quantity"], row["base"]),
            Money.of(row["total_cost"], row["quote"]),
            Money.of(row["realized_pnl"], row["quote"]),
            int(row["last_sequence"]),
        )
        for row in snapshot["positions"]
    )
