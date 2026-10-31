"""Immutable public price frames; no active-catalog filter may hide held exposure."""

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from tiewtrade.core.money import Money, MoneyError
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.core.risk_limits import RiskPrice, RiskUnavailableError
from tiewtrade.infra.db.session import UserSession, require_user_session


@dataclass(frozen=True, slots=True)
class RiskPriceFrame:
    watermark: int
    captured_at: datetime
    proof: str
    prices: tuple[RiskPrice, ...]


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise RiskUnavailableError("journal time is not aware")
    return result


def decode_frame(row: Any) -> RiskPriceFrame:
    payload = row["payload"]
    feed = payload["feed"]
    prices = []
    if feed is not None:
        for item in payload["rows"]:
            observation = (
                None
                if item["amount"] is None
                else QuoteObservation(
                    item["source"],
                    item["base"],
                    item["quote"],
                    Money.of(item["amount"], item["quote"]),
                    item["trade_id"],
                    _time(item["trade_at"]),
                    _time(item["received_at"]),
                    ObservationKind(item["observation_kind"]),
                )
            )
            prices.append(
                RiskPrice(
                    PositionPair(item["base"], item["quote"]),
                    observation,
                    feed["connected"],
                    item["reconciled_generation"] == feed["generation"],
                    _time(feed["lease_until"]),
                    feed["generation"],
                    item["revision"],
                )
            )
    return RiskPriceFrame(int(row["id"]), row["captured_at"], row["proof"], tuple(prices))


@lru_cache(maxsize=256)
def _decode_verified_frame(
    watermark: int, captured_at: datetime, proof: str, payload_json: str
) -> RiskPriceFrame:
    # Only read_frames calls this, after a fresh SQL completeness/checksum
    # check. All nested values are immutable and public; no owner evaluation or
    # authorization is cached. Text avoids decoding the same JSON per owner.
    return decode_frame(
        {
            "id": watermark,
            "captured_at": captured_at,
            "proof": proof,
            "payload": json.loads(payload_json),
        }
    )


async def price_watermark(session: UserSession) -> int:
    checked = require_user_session(session)
    return int((await checked.execute("SELECT watermark FROM risk_price_publication")).scalar_one())


async def read_frames(
    session: UserSession,
    *,
    after: int,
    through: int,
    limit: int = 100,
) -> tuple[RiskPriceFrame, ...]:
    """A missing or corrupt frame is unavailable, never a silently skipped price."""
    checked = require_user_session(session)
    if type(after) is not int or type(through) is not int or not 0 <= after <= through:
        raise ValueError("invalid risk price cursor")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("invalid risk frame page size")
    rows = (
        (
            await checked.execute(
                """SELECT id,captured_at,proof,payload::text AS payload_json,
        proof=encode(sha256(convert_to(payload::text,'UTF8')),'hex') AS valid
        FROM market_risk_price_frames WHERE id>:after AND id<=:through ORDER BY id LIMIT :limit""",
                {"after": after, "through": through, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return decode_frames(rows, after=after, through=through, limit=limit)


def decode_frames(
    rows: Any, *, after: int, through: int, limit: int = 100
) -> tuple[RiskPriceFrame, ...]:
    """Validate a freshly queried bounded page before decoding immutable frames."""
    expected = min(limit, through - after)
    if len(rows) != expected or any(
        int(row["id"]) != after + index or not row["valid"]
        for index, row in enumerate(rows, start=1)
    ):
        raise RiskUnavailableError("risk price journal is incomplete")
    try:
        return tuple(
            _decode_verified_frame(
                int(row["id"]), row["captured_at"], row["proof"], row["payload_json"]
            )
            for row in rows
        )
    except (KeyError, TypeError, ValueError, MoneyError):
        raise RiskUnavailableError("risk price journal frame is invalid") from None


async def read_frame(session: UserSession, watermark: int) -> RiskPriceFrame:
    if type(watermark) is not int or watermark <= 0:
        raise RiskUnavailableError("risk publication is not initialized")
    return (await read_frames(session, after=watermark - 1, through=watermark))[0]
