"""DB-clock fenced public execution ring; no user financial data enters this store."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

from tiewtrade.core.money import MoneyError
from tiewtrade.core.order_book import BookState, MarketInput
from tiewtrade.core.orders import (
    OrderConflictError,
    OrderConstraints,
    SourceUnavailableError,
    aware,
)
from tiewtrade.core.positions import PositionPair
from tiewtrade.infra.db.session import (
    MarketDataSession,
    UserSession,
    require_market_data_session,
    require_user_session,
)
from tiewtrade.infra.market_data.order_book_codec import (
    canonical,
    constraints_from_payload,
    constraints_payload,
    input_from_payload,
    input_payload,
)
from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost

SOURCE = "primary_spot"
BUFFER_SIZE = 4096


class ExecutionInputGapError(SourceUnavailableError):
    code = "EXECUTION_INPUT_GAP"


@dataclass(frozen=True, slots=True)
class BookLease:
    pair: PositionPair
    owner: UUID
    generation: int
    lease_until: datetime
    last_input_id: int


@dataclass(frozen=True, slots=True)
class ExecutionMetadata:
    market: OrderConstraints
    limit: OrderConstraints
    observed_at: datetime
    source_document: str

    def __post_init__(self) -> None:
        aware(self.observed_at)
        if self.market.pair != self.limit.pair or self.market.version != self.limit.version:
            raise ValueError("inconsistent execution metadata")
        if hashlib.sha256(self.source_document.encode()).hexdigest() != self.market.version:
            raise ValueError("metadata version does not identify the source document")


@dataclass(frozen=True, slots=True)
class StoredExecutionInput:
    market: MarketInput
    metadata: ExecutionMetadata
    digest: str


def metadata_payload(value: ExecutionMetadata) -> str:
    return canonical(
        {
            "market": constraints_payload(value.market),
            "limit": constraints_payload(value.limit),
            "observed_at": value.observed_at.isoformat(),
            "source_document": value.source_document,
        }
    )


def metadata_from_payload(value: Any) -> ExecutionMetadata:
    row = json.loads(value) if isinstance(value, str) else value
    return ExecutionMetadata(
        constraints_from_payload(row["market"]),
        constraints_from_payload(row["limit"]),
        datetime.fromisoformat(row["observed_at"]),
        row["source_document"],
    )


def _params(pair: PositionPair) -> dict[str, object]:
    return {"source": SOURCE, "base": pair.base, "quote": pair.quote}


def _lease(pair: PositionPair, row: Any) -> BookLease:
    if row is None:
        raise WriterLeaseLost()
    return BookLease(
        pair, row["owner"], row["generation"], row["lease_until"], row["last_input_id"]
    )


async def acquire_book_writer(
    session: MarketDataSession, pair: PositionPair, owner: UUID
) -> BookLease | None:
    session = require_market_data_session(session)
    row = (
        (
            await session.execute(
                """INSERT INTO market_execution_state
      (source,base,quote,owner,generation,lease_until)
      VALUES(:source,:base,:quote,:owner,1,clock_timestamp()+interval '5 seconds')
      ON CONFLICT(source,base,quote) DO UPDATE SET owner=EXCLUDED.owner,
        generation=market_execution_state.generation+1,
        lease_until=clock_timestamp()+interval '5 seconds',ready=false,failure_code='RECOVERING',
        revision=market_execution_state.revision+1
      WHERE market_execution_state.lease_until<=clock_timestamp() RETURNING *""",
                {**_params(pair), "owner": owner},
            )
        )
        .mappings()
        .one_or_none()
    )
    return None if row is None else _lease(pair, row)


async def _locked(session: MarketDataSession, lease: BookLease) -> Any:
    session = require_market_data_session(session)
    row = (
        (
            await session.execute(
                """WITH locked AS MATERIALIZED (
        SELECT * FROM market_execution_state
        WHERE source=:source AND base=:base AND quote=:quote FOR UPDATE
      ) SELECT locked.*,clock_timestamp() AS db_now FROM locked""",
                _params(lease.pair),
            )
        )
        .mappings()
        .one_or_none()
    )
    # The materialized row is locked before the outer query reads the DB clock.
    if (
        row is None
        or row["owner"] != lease.owner
        or row["generation"] != lease.generation
        or row["lease_until"] <= row["db_now"]
    ):
        raise WriterLeaseLost()
    return row


async def renew_book_writer(session: MarketDataSession, lease: BookLease) -> BookLease:
    await _locked(session, lease)
    row = (
        (
            await session.execute(
                """UPDATE market_execution_state
      SET lease_until=clock_timestamp()+interval '5 seconds'
      WHERE source=:source AND base=:base AND quote=:quote AND lease_until>clock_timestamp()
      RETURNING *""",
                _params(lease.pair),
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise WriterLeaseLost()
    await _locked(session, lease)
    return _lease(lease.pair, row)


async def invalidate_book(session: MarketDataSession, lease: BookLease, reason: str) -> None:
    await _locked(session, lease)
    if not reason or not reason.isascii() or not reason.replace("_", "").isalnum():
        raise ValueError("typed execution source reason required")
    await session.execute(
        """UPDATE market_execution_state SET ready=false,failure_code=:reason,
      revision=revision+1 WHERE source=:source AND base=:base AND quote=:quote""",
        {**_params(lease.pair), "reason": reason},
    )
    await _locked(session, lease)


async def publish_input(
    session: MarketDataSession,
    lease: BookLease,
    market: MarketInput,
    metadata: ExecutionMetadata,
) -> BookLease:
    row = await _locked(session, lease)
    if (
        market.pair != lease.pair
        or metadata.market.pair != lease.pair
        or market.generation != lease.generation
    ):
        raise ValueError("execution source scope mismatch")
    payload, capability = input_payload(market), metadata_payload(metadata)
    digest = hashlib.sha256((payload + "\n" + capability).encode()).hexdigest()
    params = {
        **_params(lease.pair),
        "input": market.input_id,
        "generation": market.generation,
        "received": market.received_at,
        "payload": payload,
        "capability": capability,
        "digest": digest,
        "kind": "BOOK" if isinstance(market, BookState) else "TRADE",
    }
    if market.input_id <= row["last_input_id"]:
        prior = (
            await session.execute(
                """SELECT digest FROM market_execution_buffer
          WHERE source=:source AND base=:base AND quote=:quote AND input_id=:input""",
                params,
            )
        ).scalar_one_or_none()
        if prior != digest:
            raise ExecutionInputGapError("publication replay is missing or conflicted")
        return _lease(lease.pair, row)
    if market.input_id != row["last_input_id"] + 1 or (
        row["received_at"] is not None and market.received_at < row["received_at"]
    ):
        raise ExecutionInputGapError("publication input gap or time reversal")
    if isinstance(market, BookState):
        market.require_ready(row["db_now"])
        if not row["ready"] and not market.rebase:
            raise ExecutionInputGapError("source recovery requires a rebase input")
    elif not row["ready"] or row["verified_at"] is None:
        raise SourceUnavailableError("source is not verified")
    await session.execute(
        """INSERT INTO market_execution_buffer
      (source,base,quote,slot,input_id,generation,kind,received_at,payload,capability,digest)
      VALUES(:source,:base,:quote,mod(CAST(:input AS bigint),4096),:input,:generation,:kind,
             :received,
             CAST(:payload AS jsonb),CAST(:capability AS jsonb),:digest)
      ON CONFLICT(source,base,quote,slot) DO UPDATE SET input_id=EXCLUDED.input_id,
        generation=EXCLUDED.generation,kind=EXCLUDED.kind,received_at=EXCLUDED.received_at,
        payload=EXCLUDED.payload,capability=EXCLUDED.capability,digest=EXCLUDED.digest""",
        params,
    )
    if isinstance(market, BookState):
        await session.execute(
            """UPDATE market_execution_state SET last_input_id=:input,
          received_at=:received,verified_at=:verified,book_payload=CAST(:payload AS jsonb),
          ready=true,failure_code=NULL,revision=revision+1
          WHERE source=:source AND base=:base AND quote=:quote""",
            {**params, "verified": market.verified_at},
        )
    else:
        await session.execute(
            """UPDATE market_execution_state SET last_input_id=:input,
          received_at=:received,revision=revision+1
          WHERE source=:source AND base=:base AND quote=:quote""",
            params,
        )
    final = await _locked(session, lease)
    return _lease(lease.pair, final)


@lru_cache(maxsize=256)
def _decode_execution_input(payload: str, capability: str) -> StoredExecutionInput:
    """Reuse immutable public decoding, never the fresh source/provenance checks."""
    market = input_from_payload(payload)
    metadata = metadata_from_payload(capability)
    digest = hashlib.sha256(
        (input_payload(market) + "\n" + metadata_payload(metadata)).encode()
    ).hexdigest()
    return StoredExecutionInput(market, metadata, digest)


async def read_inputs(
    session: UserSession | MarketDataSession,
    pair: PositionPair,
    *,
    after: int,
    limit: int = 20,
) -> tuple[StoredExecutionInput, ...]:
    session = (
        require_user_session(session)
        if isinstance(session, UserSession)
        else require_market_data_session(session)
    )
    if (
        type(after) is not int
        or after < 0
        or type(limit) is not int
        or not 1 <= limit <= BUFFER_SIZE
    ):
        raise ValueError("bounded input cursor required")
    # State and slots come from one statement/snapshot, including an empty buffer.
    rows = (
        (
            await session.execute(
                """SELECT s.ready,s.failure_code,s.lease_until,s.verified_at,
      s.last_input_id,s.generation AS current_generation,clock_timestamp() AS db_now,
      b.input_id,b.generation,b.received_at,b.payload::text AS payload,
      b.capability::text AS capability,b.digest
      FROM market_execution_state s LEFT JOIN LATERAL
        (SELECT * FROM market_execution_buffer b
         WHERE (b.source,b.base,b.quote)=(s.source,s.base,s.quote)
         AND input_id>:after ORDER BY input_id LIMIT :limit) b ON true
      WHERE s.source=:source AND s.base=:base AND s.quote=:quote ORDER BY b.input_id""",
                {**_params(pair), "after": after, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    if (
        not rows
        or not rows[0]["ready"]
        or rows[0]["lease_until"] <= rows[0]["db_now"]
        or (
            rows[0]["verified_at"] is None
            or rows[0]["verified_at"] > rows[0]["db_now"]
            or (rows[0]["db_now"] - rows[0]["verified_at"]).total_seconds() > 1
        )
    ):
        raise SourceUnavailableError("execution source unavailable")
    if after > rows[0]["last_input_id"] or after < max(0, rows[0]["last_input_id"] - BUFFER_SIZE):
        raise ExecutionInputGapError("consumer cursor outside retained window")
    result: list[StoredExecutionInput] = []
    for row in rows:
        if row["input_id"] is None:
            if after != row["last_input_id"]:
                raise ExecutionInputGapError("retained execution input is missing")
            continue
        try:
            decoded = _decode_execution_input(row["payload"], row["capability"])
            market, metadata, digest = decoded.market, decoded.metadata, decoded.digest
        except (KeyError, TypeError, ValueError, MoneyError):
            raise ExecutionInputGapError("stored execution input is malformed") from None
        if (market.input_id, market.generation, market.pair, market.received_at) != (
            row["input_id"],
            row["generation"],
            pair,
            row["received_at"],
        ) or metadata.market.pair != pair:
            raise ExecutionInputGapError("stored input provenance mismatch")
        if row["input_id"] != after + len(result) + 1 or digest != row["digest"]:
            raise ExecutionInputGapError("retained execution inputs are incomplete or corrupt")
        if market.generation != rows[0]["current_generation"]:
            raise ExecutionInputGapError("old generation requires consumer recovery")
        result.append(decoded)
    return tuple(result)


async def read_latest_book(
    session: UserSession | MarketDataSession, pair: PositionPair
) -> StoredExecutionInput:
    """Return the newest retained verified book for a consumer recovery rebase."""
    session = (
        require_user_session(session)
        if isinstance(session, UserSession)
        else require_market_data_session(session)
    )
    input_id = (
        await session.execute(
            """SELECT max(input_id) FROM market_execution_buffer
            WHERE source=:source AND base=:base AND quote=:quote
              AND payload->>'kind'='BOOK'""",
            _params(pair),
        )
    ).scalar_one_or_none()
    if input_id is None:
        raise ExecutionInputGapError("verified recovery book is unavailable")
    rows = await read_inputs(session, pair, after=int(input_id) - 1, limit=1)
    if not rows or not isinstance(rows[0].market, BookState):
        raise ExecutionInputGapError("verified recovery book is unavailable")
    return rows[0]


async def set_pair_dependency(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    pair: PositionPair,
    needed: bool,
) -> None:
    session = require_user_session(session)
    if type(needed) is not bool:
        raise ValueError("explicit pair dependency required")
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
        {"key": f"paper-wallet:{session.user_id}"},
    )
    if needed:
        active = (
            await session.execute(
                """SELECT 1 FROM paper_wallet_state s
          WHERE s.wallet_id=:wallet AND s.user_id=:user AND s.active_episode_id=:episode
          AND NOT EXISTS(SELECT 1 FROM paper_wallet_episode_closures c WHERE c.episode_id=:episode)
          FOR UPDATE""",
                {"wallet": wallet_id, "user": session.user_id, "episode": episode_id},
            )
        ).first()
        if active is None:
            raise OrderConflictError("inactive Paper episode cannot retain a feed")
    await session.execute(
        """INSERT INTO paper_market_dependencies
      (user_id,wallet_id,episode_id,source,base,quote,needed)
      VALUES(:user,:wallet,:episode,:source,:base,:quote,:needed)
      ON CONFLICT(user_id,episode_id,source,base,quote) DO UPDATE SET needed=EXCLUDED.needed""",
        {
            **_params(pair),
            "user": session.user_id,
            "wallet": wallet_id,
            "episode": episode_id,
            "needed": needed,
        },
    )


async def retained_pairs(session: MarketDataSession) -> tuple[PositionPair, ...]:
    session = require_market_data_session(session)
    rows = (
        (
            await session.execute("""SELECT base,quote FROM market_execution_demand
      WHERE references_count>0 ORDER BY base,quote""")
        )
        .mappings()
        .all()
    )
    return tuple(PositionPair(row["base"], row["quote"]) for row in rows)
