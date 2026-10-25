from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import RowMapping

from tiewtrade.core.market_data import Candle, Timeframe
from tiewtrade.core.timeframes import candle_storage_cutoff as retention_cutoff
from tiewtrade.infra.db import money_to_columns, quantity_to_columns
from tiewtrade.infra.db.session import MarketDataSession, require_market_data_session
from tiewtrade.infra.indicators.source import begin_source_write, require_source_write
from tiewtrade.infra.market_data.records import PartitionUnavailableError, StaleClaimError
from tiewtrade.infra.market_data.storage import database_now


@dataclass(frozen=True, slots=True)
class Claim:
    base: str
    quote: str
    timeframe: Timeframe
    token: UUID
    generation: int

    def parameters(self) -> dict[str, object]:
        return {
            "base": self.base,
            "quote": self.quote,
            "timeframe": self.timeframe.value,
            "token": self.token,
            "generation": self.generation,
        }


async def claim_next(session: MarketDataSession, worker: str) -> Claim | None:
    session = require_market_data_session(session)
    row = (
        (
            await session.execute("""SELECT d.* FROM market_candle_demand d
        JOIN runtime_supported_symbols s ON s.base=d.base AND s.quote=d.quote
          AND s.runtime_mode IN ('PUBLIC','PREPARING')
        WHERE d.next_attempt_at<=clock_timestamp() AND
          (d.token IS NULL OR d.lease_until<=clock_timestamp()) AND
          (d.status IN ('PENDING','RUNNING') OR
           (d.status IN ('FAILED','UNAVAILABLE') AND d.requested_at>d.checked_at
             AND d.requested_at>=d.next_attempt_at) OR
           (d.status='COMPLETE' AND (d.desired_start<d.leased_start
             OR d.desired_end>d.leased_end
             OR d.refresh_requested_at>coalesce(d.refresh_served_at,'-infinity'))))
        ORDER BY d.checked_at NULLS FIRST,d.requested_at,d.base,d.timeframe
        FOR UPDATE OF d SKIP LOCKED LIMIT 1""")
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    token = uuid4()
    generation = int(row["generation"]) + 1
    now = await database_now(session)
    params = {
        "base": row["base"],
        "quote": row["quote"],
        "timeframe": row["timeframe"],
        "token": token,
        "generation": generation,
        "worker": worker,
        "until": now + timedelta(seconds=120),
        "now": now,
    }
    await session.execute(
        """UPDATE market_candle_demand SET token=:token, worker=:worker,
        lease_until=:until,generation=:generation,status='RUNNING',
        attemptcount=CASE WHEN status='FAILED' THEN 0 ELSE attemptcount END,
        phase=CASE WHEN status='UNAVAILABLE' THEN 'REPAIR' ELSE phase END,
        repair_pass=CASE WHEN status='UNAVAILABLE' THEN 1 ELSE repair_pass END,
        repair_cursor=CASE WHEN status='UNAVAILABLE' THEN desired_start ELSE repair_cursor END,
        leased_start=CASE WHEN status='UNAVAILABLE' OR leased_start IS NULL
            THEN desired_start ELSE leased_start END,
        leased_end=CASE WHEN status='UNAVAILABLE' OR leased_end IS NULL
            THEN desired_end ELSE leased_end END,
        cursor=coalesce(cursor,desired_start), checked_at=:now
        WHERE base=:base AND quote=:quote AND timeframe=:timeframe""",
        params,
    )
    return Claim(
        str(row["base"]), str(row["quote"]), Timeframe(row["timeframe"]), token, generation
    )


async def lock_claim(session: MarketDataSession, claim: Claim) -> RowMapping:
    session = require_market_data_session(session)
    row = (
        (
            await session.execute(
                """SELECT d.* FROM market_candle_demand d
        JOIN runtime_supported_symbols s ON s.base=d.base AND s.quote=d.quote
          AND s.runtime_mode IN ('PUBLIC','PREPARING')
        WHERE d.base=:base AND d.quote=:quote AND d.timeframe=:timeframe
          AND d.token=:token AND d.generation=:generation
          AND d.lease_until>clock_timestamp()
        FOR UPDATE OF d""",
                claim.parameters(),
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise StaleClaimError()
    return row


_WORKER_COLUMNS = frozenset(
    {
        "status",
        "phase",
        "cursor",
        "repair_cursor",
        "repair_pass",
        "refresh_as_of",
        "refresh_cursor",
        "refresh_served_at",
        "fetch_unit_id",
        "fetch_start",
        "fetch_end",
        "fetch_started_at",
        "attemptcount",
        "next_attempt_at",
        "checked_at",
        "failure_code",
        "leased_start",
        "leased_end",
        "recent_cursor",
        "recent_end",
        "fetch_recent",
        "history_start",
        "history_checked_at",
        "desired_start",
    }
)


async def update_claim(
    session: MarketDataSession, claim: Claim, *, release: bool = False, **changes: Any
) -> None:
    await lock_claim(session, claim)
    if not changes.keys() <= _WORKER_COLUMNS:
        raise ValueError("unsupported worker column")
    assignments = [
        "next_attempt_at=greatest(next_attempt_at,:next_attempt_at)"
        if name == "next_attempt_at"
        else f"{name}=:{name}"
        for name in changes
    ]
    if release:
        assignments.extend(["token=NULL", "worker=NULL", "lease_until=NULL"])
    if not assignments:
        return
    await session.execute(
        "UPDATE market_candle_demand SET "
        + ",".join(assignments)
        + " WHERE token=:token AND generation=:generation",
        claim.parameters() | changes,
    )


_CANDLE_COLUMNS = (
    "open_at",
    "end_at",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "finality",
    "observed_at",
)
_OBSERVATION_FIELDS = ("open", "high", "low", "close", "volume", "finality")


async def write_candles(
    session: MarketDataSession,
    claim: Claim,
    candles: tuple[Candle, ...],
    fetch_started_at: datetime,
) -> None:
    await require_source_write(session)
    await lock_claim(session, claim)
    now = await database_now(session)
    cutoff = retention_cutoff(now, claim.timeframe)
    entries: list[tuple[Candle, dict[str, object]]] = []
    for candle in candles:
        if candle.open_at < cutoff:
            continue
        if (candle.base, candle.quote, candle.timeframe) != (
            claim.base,
            claim.quote,
            claim.timeframe,
        ):
            raise ValueError("wrong candle series")
        entry: dict[str, object] = {
            "open_at": candle.open_at,
            "end_at": candle.end_at,
            "open": money_to_columns(candle.open)[0],
            "high": money_to_columns(candle.high)[0],
            "low": money_to_columns(candle.low)[0],
            "close": money_to_columns(candle.close)[0],
            "volume": quantity_to_columns(candle.volume)[0],
            "finality": candle.finality.value,
            "observed_at": candle.observed_at,
        }
        entries.append((candle, entry))
    if not entries:
        return
    partitions = sorted({f"market_candles_{candle.open_at:%Y%m}" for candle, _ in entries})
    found = (
        (
            await session.execute(
                """SELECT name,to_regclass(name) AS relation
        FROM unnest(CAST(:names AS text[])) AS partitions(name)""",
                {"names": partitions},
            )
        )
        .mappings()
        .all()
    )
    if any(partition["relation"] is None for partition in found):
        if claim.timeframe not in (Timeframe.W1, Timeframe.MN1):
            raise PartitionUnavailableError()
        for candle, _ in entries:
            await session.execute(
                "SELECT ensure_history_partition(:base,:tf,:opened)",
                {"base": claim.base, "tf": claim.timeframe.value, "opened": candle.open_at},
            )
    params = claim.parameters() | {
        "opens": sorted({candle.open_at for candle, _ in entries}),
        "fetch_started_at": fetch_started_at,
        "now": now,
    }
    existing_rows = (
        await session.execute(
            """SELECT open_at,observed_at,open,high,low,
        close,volume,finality,ingestion_generation FROM market_candles
        WHERE source='primary_spot' AND base=:base AND quote=:quote AND timeframe=:timeframe
          AND open_at=ANY(CAST(:opens AS timestamptz[]))
        ORDER BY open_at FOR UPDATE""",
            params,
        )
    ).mappings()
    states: dict[datetime, Mapping[str, Any]] = {
        existing["open_at"]: dict(existing) for existing in existing_rows
    }
    writes: dict[datetime, dict[str, object]] = {}
    for candle, entry in entries:
        previous = states.get(candle.open_at)
        if (
            previous is not None
            and previous["observed_at"] == candle.observed_at
            and any(previous[name] != entry[name] for name in _OBSERVATION_FIELDS)
        ):
            raise ValueError("CONFLICTING_CANDLE_OBSERVATION")
        if previous is not None and (
            previous["ingestion_generation"] > claim.generation
            or previous["observed_at"] > candle.observed_at
            or (previous["finality"] == "CLOSED" and candle.finality.value != "CLOSED")
        ):
            continue
        states[candle.open_at] = entry | {"ingestion_generation": claim.generation}
        writes[candle.open_at] = entry
    if not writes:
        return
    values: list[str] = []
    for index, entry in enumerate(writes.values()):
        params.update({f"{name}_{index}": entry[name] for name in _CANDLE_COLUMNS})
        values.append(
            "('primary_spot',:base,:quote,:timeframe,"
            + ",".join(f":{name}_{index}" for name in _CANDLE_COLUMNS)
            + ",:fetch_started_at,:now,:generation)"
        )
    await session.execute(
        """INSERT INTO market_candles
        (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
         finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
        VALUES """
        + ",".join(values)
        + """
        ON CONFLICT (source,base,quote,timeframe,open_at) DO UPDATE SET
          open=excluded.open, high=excluded.high, low=excluded.low,
          close=excluded.close,volume=excluded.volume,finality=excluded.finality,
          observed_at=excluded.observed_at,fetch_started_at=excluded.fetch_started_at,
          last_checked_at=excluded.last_checked_at,ingestion_generation=excluded.ingestion_generation
        WHERE market_candles.ingestion_generation<=excluded.ingestion_generation
          AND market_candles.observed_at<=excluded.observed_at
          AND (market_candles.finality<>'CLOSED' OR excluded.finality='CLOSED')""",
        params,
    )


async def cleanup(session: MarketDataSession) -> int:
    session = require_market_data_session(session)
    await begin_source_write(session)
    policy = (
        await session.execute(
            "SELECT retention_policy FROM public.indicator_rollout_control WHERE id=1"
        )
    ).scalar_one()
    now = await database_now(session)
    ordinary_cutoff = retention_cutoff(now, Timeframe.D1)
    extended_cutoff = retention_cutoff(now, Timeframe.W1)
    if policy == "GRACE":
        grace = timedelta(hours=6, minutes=15)
        ordinary_cutoff -= grace
        extended_cutoff -= grace
    result = await session.execute(
        """DELETE FROM market_candles WHERE (tableoid,ctid) IN (
        SELECT tableoid,ctid FROM market_candles
        WHERE (timeframe IN ('1w','1M') AND open_at<:extended_cutoff)
           OR (timeframe NOT IN ('1w','1M') AND open_at<:ordinary_cutoff)
        LIMIT 10000)
        RETURNING open_at""",
        {"ordinary_cutoff": ordinary_cutoff, "extended_cutoff": extended_cutoff},
    )
    return len(result.all())
