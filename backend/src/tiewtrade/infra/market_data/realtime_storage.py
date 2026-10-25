"""Durable public prices, guarded by DB-clock leases and row locks."""

from datetime import datetime
from typing import Any
from uuid import UUID

from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import money_from_columns, money_to_columns
from tiewtrade.infra.db.session import (
    MarketDataSession,
    PresentedSession,
    UserSession,
    require_market_data_session,
    require_user_session,
)
from tiewtrade.infra.market_data.catalog import SOURCE, runtime_pairs
from tiewtrade.infra.market_data.realtime_records import (
    FeedLease,
    PriceSnapshot,
    StoredPrice,
    WriterLeaseLost,
)

Session = MarketDataSession | UserSession | PresentedSession

# Evaluated inside the mutation, after its table-lock wait, using the DB clock.
_WRITER_FENCE = """source=:source AND owner=:owner AND generation=:generation
  AND lease_until>clock_timestamp()"""


def _writer_params(lease: FeedLease) -> dict[str, object]:
    return {"source": lease.source, "owner": lease.owner, "generation": lease.generation}


def _feed(row: Any) -> FeedLease:
    if row is None:
        raise WriterLeaseLost()
    return FeedLease(
        row["source"],
        row["generation"],
        row["owner"],
        row["lease_until"],
        row["connected"],
        row["last_failure_code"],
    )


async def database_now(session: Session) -> datetime:
    checked = (
        session
        if isinstance(session, PresentedSession)
        else require_user_session(session)
        if isinstance(session, UserSession)
        else require_market_data_session(session)
    )
    now: datetime = (await checked.execute("SELECT clock_timestamp()")).scalar_one()
    return now


async def acquire_writer(session: MarketDataSession, owner: UUID) -> FeedLease | None:
    session = require_market_data_session(session)
    prior = (
        await session.execute(
            "SELECT lease_until FROM market_price_feed WHERE source=:source FOR UPDATE",
            {"source": SOURCE},
        )
    ).scalar_one_or_none()
    result = await session.execute(
        """INSERT INTO market_price_feed
      (source,generation,owner,lease_until,connected)
      VALUES (:source,1,:owner,clock_timestamp()+interval '5 seconds',false)
      ON CONFLICT(source) DO UPDATE SET generation=market_price_feed.generation+1,
        owner=EXCLUDED.owner,lease_until=clock_timestamp()+interval '5 seconds',
        connected=false,last_failure_code=NULL
      WHERE market_price_feed.lease_until<=clock_timestamp()
      RETURNING *""",
        {"source": SOURCE, "owner": owner},
    )
    row = result.mappings().one_or_none()
    if row is None:
        return None
    lease = _feed(row)
    for base, quote in sorted(await runtime_pairs(session)):
        await session.execute(
            """INSERT INTO market_latest_prices(source,base,quote,unavailable_since)
          VALUES(:source,:base,:quote,clock_timestamp()) ON CONFLICT DO NOTHING""",
            {"source": SOURCE, "base": base, "quote": quote},
        )
    await _invalidate(session, prior)
    return lease


async def _locked(session: MarketDataSession, lease: FeedLease) -> FeedLease:
    session = require_market_data_session(session)
    result = await session.execute(
        "SELECT * FROM market_price_feed WHERE source=:source FOR UPDATE", {"source": lease.source}
    )
    row = result.mappings().one_or_none()
    now = await database_now(session)
    if (
        row is None
        or row["owner"] != lease.owner
        or row["generation"] != lease.generation
        or row["lease_until"] <= now
    ):
        raise WriterLeaseLost()
    return _feed(row)


async def _invalidate(session: MarketDataSession, unavailable_at: datetime | None = None) -> None:
    await session.execute(
        """UPDATE market_latest_prices SET reconciled_generation=0,
      effective_readiness=CASE WHEN amount IS NULL THEN 'MISSING' ELSE 'RECOVERING' END,
      reason='UNRECONCILED', unavailable_since=least(unavailable_since,
        coalesce(:unavailable_at,clock_timestamp()),trade_at+interval '10 seconds'),
      revision=revision+1 WHERE source=:source""",
        {"source": SOURCE, "unavailable_at": unavailable_at},
    )


async def renew_writer(session: MarketDataSession, lease: FeedLease) -> FeedLease:
    await _locked(session, lease)
    result = await session.execute(
        f"""UPDATE market_price_feed SET
      lease_until=clock_timestamp()+interval '5 seconds' WHERE {_WRITER_FENCE} RETURNING *""",
        _writer_params(lease),
    )
    return await _locked(session, _feed(result.mappings().one_or_none()))


async def begin_generation(session: MarketDataSession, lease: FeedLease) -> FeedLease:
    await _locked(session, lease)
    result = await session.execute(
        f"""UPDATE market_price_feed SET generation=generation+1,
      connected=false,last_failure_code=NULL WHERE {_WRITER_FENCE} RETURNING *""",
        _writer_params(lease),
    )
    updated = _feed(result.mappings().one_or_none())
    await _invalidate(session)
    return await _locked(session, updated)


async def set_connected(
    session: MarketDataSession, lease: FeedLease, connected: bool, failure_code: str | None = None
) -> FeedLease:
    current = await _locked(session, lease)
    result = await session.execute(
        f"""UPDATE market_price_feed SET connected=:connected,
      last_failure_code=:failure WHERE {_WRITER_FENCE} RETURNING *""",
        {**_writer_params(lease), "connected": connected, "failure": failure_code},
    )
    updated = _feed(result.mappings().one_or_none())
    if current.connected != connected or current.last_failure_code != failure_code:
        if not connected:
            await _invalidate(session)
        else:
            await session.execute(
                "UPDATE market_latest_prices SET revision=revision+1 WHERE source=:source",
                {"source": lease.source},
            )
    return await _locked(session, updated)


async def write_price(session: MarketDataSession, lease: FeedLease, row: StoredPrice) -> bool:
    await _locked(session, lease)
    if row.source != lease.source or (row.base, row.quote) not in await runtime_pairs(session):
        raise ValueError("unsupported realtime pair")
    observation = row.observation
    if observation is not None and (observation.source, observation.base, observation.quote) != (
        row.source,
        row.base,
        row.quote,
    ):
        raise ValueError("observation pair mismatch")
    params: dict[str, object] = {
        **_writer_params(lease),
        "source": row.source,
        "base": row.base,
        "quote": row.quote,
        "amount": None if observation is None else money_to_columns(observation.amount)[0],
        "trade_id": None if observation is None else observation.trade_id,
        "trade_at": None if observation is None else observation.trade_time,
        "received_at": None if observation is None else observation.received_at,
        "kind": None if observation is None else observation.observation_kind.value,
        "reconciled": row.reconciled_generation,
        "readiness": row.effective_readiness,
        "reason": row.reason,
        "unavailable": row.unavailable_since,
        "ambiguous": row.order_ambiguous_at,
    }
    result = await session.execute(
        f"""UPDATE market_latest_prices SET
      amount=:amount,trade_id=:trade_id,trade_at=:trade_at,received_at=:received_at,
      observation_kind=:kind,reconciled_generation=:reconciled,effective_readiness=:readiness,
      reason=:reason,unavailable_since=:unavailable,order_ambiguous_at=:ambiguous,revision=revision+1
      WHERE source=:source AND base=:base AND quote=:quote
      AND EXISTS (SELECT 1 FROM market_price_feed WHERE {_WRITER_FENCE}) AND
      (amount,trade_at,reconciled_generation,effective_readiness,reason,unavailable_since,order_ambiguous_at)
      IS DISTINCT FROM
      (:amount,:trade_at,:reconciled,:readiness,:reason,:unavailable,:ambiguous)
      RETURNING revision""",
        params,
    )
    # A price-row lock can delay execution after SQL has evaluated the fence.
    # Check again before returning so lease loss rolls back the entire transaction.
    await _locked(session, lease)
    return result.scalar_one_or_none() is not None


async def read_snapshot(session: Session) -> PriceSnapshot:
    session = (
        session
        if isinstance(session, PresentedSession)
        else require_user_session(session)
        if isinstance(session, UserSession)
        else require_market_data_session(session)
    )
    # One statement prevents mixing a feed generation with a later rows version.
    result = await session.execute("""SELECT p.*,f.generation AS feed_generation,f.owner,
      f.lease_until,f.connected,f.last_failure_code FROM market_latest_prices p
      JOIN market_price_feed f USING(source) ORDER BY base""")
    rows = result.mappings().all()
    feed = None
    prices = []
    for r in rows:
        if feed is None:
            feed = FeedLease(
                r["source"],
                r["feed_generation"],
                r["owner"],
                r["lease_until"],
                r["connected"],
                r["last_failure_code"],
            )
        observation = (
            None
            if r["amount"] is None
            else QuoteObservation(
                source=r["source"],
                base=r["base"],
                quote=r["quote"],
                amount=money_from_columns(r["amount"], r["quote"]),
                trade_id=r["trade_id"],
                trade_time=r["trade_at"],
                received_at=r["received_at"],
                observation_kind=ObservationKind(r["observation_kind"]),
            )
        )
        prices.append(
            StoredPrice(
                r["source"],
                r["base"],
                r["quote"],
                observation,
                r["reconciled_generation"],
                r["revision"],
                r["effective_readiness"],
                r["reason"],
                r["unavailable_since"],
                r["order_ambiguous_at"],
            )
        )
    return PriceSnapshot(feed, tuple(prices), await database_now(session))


async def read_public_snapshot(session: UserSession | PresentedSession) -> PriceSnapshot:
    """Read the active catalog fence and public price rows in one statement."""
    checked = session if isinstance(session, PresentedSession) else require_user_session(session)
    rows = (
        (
            await checked.execute(
                """SELECT c.current_revision,a.base,a.quote,p.source,p.amount,p.trade_id,
              p.trade_at,p.received_at,p.observation_kind,p.reconciled_generation,p.revision,
              p.effective_readiness,p.reason,p.unavailable_since,p.order_ambiguous_at,
              f.generation AS feed_generation,f.owner,f.lease_until,f.connected,
              f.last_failure_code,clock_timestamp() AS server_time
            FROM supported_symbol_catalog_control c
            LEFT JOIN active_supported_symbols a ON true
            LEFT JOIN market_latest_prices p ON p.source=:source
              AND p.base=a.base AND p.quote=a.quote
            LEFT JOIN market_price_feed f ON f.source=:source
            WHERE c.id=1 ORDER BY a.base""",
                {"source": SOURCE},
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        raise RuntimeError("supported-symbol catalog control is missing")
    first = rows[0]
    feed = (
        None
        if first["feed_generation"] is None
        else FeedLease(
            SOURCE,
            first["feed_generation"],
            first["owner"],
            first["lease_until"],
            first["connected"],
            first["last_failure_code"],
        )
    )
    pairs: set[tuple[str, str]] = set()
    prices: list[StoredPrice] = []
    for row in rows:
        if row["base"] is None:
            continue
        pair = str(row["base"]), str(row["quote"])
        pairs.add(pair)
        observation = (
            None
            if row["amount"] is None
            else QuoteObservation(
                source=SOURCE,
                base=pair[0],
                quote=pair[1],
                amount=money_from_columns(row["amount"], pair[1]),
                trade_id=row["trade_id"],
                trade_time=row["trade_at"],
                received_at=row["received_at"],
                observation_kind=ObservationKind(row["observation_kind"]),
            )
        )
        prices.append(
            StoredPrice(
                SOURCE,
                pair[0],
                pair[1],
                observation,
                0 if row["reconciled_generation"] is None else row["reconciled_generation"],
                0 if row["revision"] is None else row["revision"],
                "MISSING" if row["effective_readiness"] is None else row["effective_readiness"],
                row["reason"],
                row["unavailable_since"],
                row["order_ambiguous_at"],
            )
        )
    return PriceSnapshot(
        feed,
        tuple(prices),
        first["server_time"],
        int(first["current_revision"]),
        frozenset(pairs),
    )
