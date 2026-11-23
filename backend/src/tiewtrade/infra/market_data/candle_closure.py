"""Durable source closure matching; every mutation shares the canonical source scope."""

import json
import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import RowMapping

from tiewtrade.core.candle_closure import (
    ClosureCandidate,
    ClosureResult,
    candle_fingerprint,
    verify_closure,
)
from tiewtrade.core.candle_preview import CandleObservation, Progress, compare
from tiewtrade.core.market_data import (
    Candle,
    CandleWindow,
    Timeframe,
    retention_cutoff,
)
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import MarketDataSession, UserSession, require_market_data_session
from tiewtrade.infra.indicators.source import begin_source_write, require_source_write
from tiewtrade.infra.market_data.candle_preview import PreviewLease, fence
from tiewtrade.infra.market_data.catalog import SOURCE, runtime_symbol_map
from tiewtrade.infra.market_data.storage import _stored, coalesce_demand, database_now
from tiewtrade.infra.market_data.storage import closure_control as control


class ClosureUnavailableError(InfraError):
    code = "CANDLE_CLOSURE_UNAVAILABLE"


type ReadSession = MarketDataSession | UserSession


async def prepare_write(session: MarketDataSession, *, acquire: bool = False) -> bool:
    require_market_data_session(session)
    current = await control(session)
    if current is None:
        return False
    compatible = os.environ.get("TIEWTRADE_CANDLE_CLOSURE_ENABLED") == "1"
    if acquire and compatible:
        await begin_source_write(session)
        current = await control(session)
        assert current is not None
    if not current["enabled"]:
        return False
    if not compatible:
        raise ClosureUnavailableError("compatible closure writer required")
    await require_source_write(session)
    if not (await session.execute("SELECT candle_closure_triggers_valid()")).scalar_one():
        raise ClosureUnavailableError("closure guards unavailable")
    await session.execute("SELECT set_config('tiewtrade.candle_closure_writer','1',true)")
    return True


def key(c: Candle) -> dict[str, object]:
    return {
        "source": SOURCE,
        "base": c.base,
        "quote": c.quote,
        "timeframe": c.timeframe.value,
        "open_at": c.open_at,
    }


_WHERE = (
    "source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe AND open_at=:open_at"
)


def payload(c: Candle) -> dict[str, str]:
    return {
        "base": c.base,
        "quote": c.quote,
        "timeframe": c.timeframe.value,
        "open_at": c.open_at.isoformat(),
        "end_at": c.end_at.isoformat(),
        "open": c.open.as_parts()["amount"],
        "high": c.high.as_parts()["amount"],
        "low": c.low.as_parts()["amount"],
        "close": c.close.as_parts()["amount"],
        "volume": c.volume.as_parts()["quantity"],
    }


def observation(row: RowMapping | Mapping[str, Any]) -> CandleObservation:
    # _stored's timestamp fields are canonical-only; provide the saved receive time.
    value = _stored(
        dict(row)
        | {
            "finality": "UNCONFIRMED",
            "observed_at": row["received_at"],
            "fetch_started_at": row["received_at"],
            "last_checked_at": row["received_at"],
        }
    )
    return CandleObservation(
        value.candle,
        row["event_at"],
        row["received_at"],
        row["trade_count"],
        row["first_trade_id"],
        row["last_trade_id"],
        row["closed_hint"],
    )


async def connection_ready(session: ReadSession) -> bool:
    return bool(
        (
            await session.execute(
                """SELECT connected AND bootstrapped AND failure_code IS NULL
        AND lease_until>clock_timestamp() FROM market_candle_feed_state WHERE source=:source""",
                {"source": SOURCE},
            )
        ).scalar_one_or_none()
    )


async def connection_changed(session: MarketDataSession) -> None:
    if await prepare_write(session):
        await session.execute(
            "UPDATE market_candle_closure_control SET recovery_at=clock_timestamp() WHERE id=1"
        )


async def _state(session: ReadSession, candle: Candle) -> RowMapping | None:
    return (
        (
            await session.execute(
                "SELECT * FROM market_candle_closure_state WHERE " + _WHERE, key(candle)
            )
        )
        .mappings()
        .one_or_none()
    )


async def _resolve(
    session: MarketDataSession,
    state: RowMapping,
    c: Candle,
    *,
    outcome: str,
    fetch_started_at: datetime,
    metadata: dict[str, object] | None = None,
) -> UUID:
    fingerprint = candle_fingerprint(c)
    previous = state["result_id"]
    if previous is not None:
        old = (
            (
                await session.execute(
                    "SELECT * FROM market_candle_closure_results WHERE id=:id", {"id": previous}
                )
            )
            .mappings()
            .one()
        )
        if old["outcome"] == outcome and old["fingerprint"] == fingerprint:
            return UUID(str(previous))
    identity = uuid5(UUID(str(state["observation_id"])), f"{outcome}:{fingerprint}:{previous}")
    current = await control(session)
    assert current is not None and current["enabled"]
    source = (await session.execute("SELECT epoch,revision FROM indicator_source_guard")).one()
    document: dict[str, object] = dict(payload(c))
    if metadata:
        document["details"] = metadata
    await session.execute(
        """INSERT INTO market_candle_closure_results
      (id,observation_id,outcome,fingerprint,previous_result_id,canonical,fetch_started_at,
       observed_at,policy_version,activation_epoch,source_epoch,source_fence)
      VALUES(:id,:observation,:outcome,:fingerprint,:previous,CAST(:document AS jsonb),:fetch,
       :observed,1,:activation,:epoch,:revision) ON CONFLICT(id) DO NOTHING""",
        {
            "id": identity,
            "observation": state["observation_id"],
            "outcome": outcome,
            "fingerprint": fingerprint,
            "previous": previous,
            "document": json.dumps(document),
            "fetch": fetch_started_at,
            "observed": c.observed_at,
            "activation": current["activation_epoch"],
            "epoch": source.epoch,
            "revision": source.revision,
        },
    )
    await session.execute(
        "UPDATE market_candle_closure_state SET status=:outcome,result_id=:id, "
        "recovery_at=CASE WHEN status IN ('CONFLICT','INVALIDATED') OR "
        ":outcome IN ('CONFLICT','INVALIDATED') THEN clock_timestamp() ELSE recovery_at END WHERE "
        + _WHERE,
        key(c) | {"outcome": outcome, "id": identity},
    )
    return identity


async def invalidate(
    session: MarketDataSession,
    c: Candle,
    *,
    fetch_started_at: datetime,
    reason: str,
    native: CandleObservation | None = None,
    settled_only: bool = False,
) -> bool:
    if not await prepare_write(session):
        return False
    state = await _state(session, c)
    if state is None or (settled_only and state["status"] not in ("MATCHED", "INVALIDATED")):
        return False
    details: dict[str, object] = {"reason": reason}
    if native is not None:
        details |= {
            "native": payload(native.candle),
            "closed_hint": native.closed_hint,
            "trade_count": native.trade_count,
            "first_trade_id": native.first_trade_id,
            "last_trade_id": native.last_trade_id,
            "event_at": native.event_at.isoformat(),
            "received_at": native.received_at.isoformat(),
        }
    await _resolve(
        session,
        state,
        c,
        outcome="INVALIDATED",
        fetch_started_at=fetch_started_at,
        metadata=details,
    )
    await session.execute(
        "UPDATE market_candles SET finality='UNCONFIRMED',closure_proof_id=NULL WHERE "
        + _WHERE
        + " AND finality='CLOSED'",
        key(c),
    )
    return True


async def reconcile(session: MarketDataSession, c: Candle) -> UUID | None:
    """Resolve a pending native observation against the current committed REST row."""
    if not await prepare_write(session):
        return None
    state = await _state(session, c)
    if state is None:
        return None
    row = (
        (
            await session.execute(
                "SELECT * FROM market_candles WHERE " + _WHERE + " FOR UPDATE", key(c)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    native = (
        (
            await session.execute(
                "SELECT * FROM market_candle_closure_observations WHERE id=:id",
                {"id": state["observation_id"]},
            )
        )
        .mappings()
        .one()
    )
    current = await control(session)
    if current is None or native["activation_epoch"] != current["activation_epoch"]:
        return None
    feed = (
        (
            await session.execute(
                "SELECT * FROM market_candle_feed_state WHERE source=:source FOR SHARE",
                {"source": SOURCE},
            )
        )
        .mappings()
        .one()
    )
    if (
        feed["owner"] != native["writer_id"]
        or feed["epoch"] != native["writer_epoch"]
        or not await connection_ready(session)
    ):
        return None
    stored = _stored(row)
    if state["status"] == "INVALIDATED":
        previous = (
            (
                await session.execute(
                    "SELECT * FROM market_candle_closure_results WHERE id=:id",
                    {"id": state["result_id"]},
                )
            )
            .mappings()
            .one()
        )
        if (
            previous["canonical"].get("details", {}).get("reason") != "REST_CONFLICT"
            or stored.fetch_started_at <= previous["fetch_started_at"]
            or stored.candle.observed_at <= previous["observed_at"]
        ):
            return None
    verdict = verify_closure(
        ClosureCandidate(observation(native)),
        stored.candle,
        fetch_started_at=stored.fetch_started_at,
        as_of=await database_now(session),
    )
    if verdict in (ClosureResult.NOT_SETTLED, ClosureResult.WRONG_SERIES):
        return None
    if verdict is ClosureResult.CONFLICT:
        await _resolve(
            session,
            state,
            stored.candle,
            outcome="CONFLICT",
            fetch_started_at=stored.fetch_started_at,
        )
        await session.execute(
            "UPDATE market_candles SET finality='UNCONFIRMED',closure_proof_id=NULL WHERE "
            + _WHERE
            + " AND finality='CLOSED'",
            key(c),
        )
        return None
    proof = await _resolve(
        session, state, stored.candle, outcome="MATCHED", fetch_started_at=stored.fetch_started_at
    )
    if row["finality"] != "CLOSED" or row["closure_proof_id"] != proof:
        await session.execute(
            "UPDATE market_candles SET finality='CLOSED',closure_proof_id=:proof WHERE " + _WHERE,
            key(c) | {"proof": proof},
        )
    return proof


async def record_candidate(
    session: MarketDataSession,
    lease: PreviewLease,
    native: CandleObservation,
    *,
    conflicting_with: CandleObservation | None = None,
) -> UUID | None:
    if not await prepare_write(session, acquire=True):
        return None
    current = await control(session)
    assert current is not None
    feed = await fence(session, lease)
    if not feed["connected"]:
        raise ClosureUnavailableError("closure connection unavailable")
    candidate = ClosureCandidate(native)
    c = native.candle
    symbol = (await runtime_symbol_map(session, modes=frozenset({"PUBLIC", "PREPARING"}))).get(
        (c.base, c.quote)
    )
    if symbol is None:
        raise ClosureUnavailableError("native closure pair unavailable")
    now = await database_now(session)
    if c.open_at < retention_cutoff(now, c.timeframe):
        return None
    if native.received_at > now or native.event_at > now:
        raise ClosureUnavailableError("native close time is in the future")
    identity = uuid5(
        lease.owner, f"{current['activation_epoch']}:{lease.epoch}:{candidate.fingerprint}"
    )
    state = await _state(session, c)
    if state is not None and state["observation_id"] != identity:
        prior = (
            (
                await session.execute(
                    "SELECT * FROM market_candle_closure_observations WHERE id=:id",
                    {"id": state["observation_id"]},
                )
            )
            .mappings()
            .one()
        )
        progress = compare(observation(prior), native)
        if progress is Progress.OLDER:
            return None
        if progress in (Progress.CONFLICT, Progress.NEWER) and (
            prior["activation_epoch"] == current["activation_epoch"]
            and prior["writer_id"] == lease.owner
            and prior["writer_epoch"] == lease.epoch
        ):
            await invalidate(
                session,
                c,
                fetch_started_at=native.received_at,
                reason="NATIVE_CONFLICT",
                native=native,
            )
            return None
        if (
            state["status"] == "MATCHED"
            and conflicting_with is None
            and progress is Progress.DUPLICATE
            and prior["activation_epoch"] == current["activation_epoch"]
            and prior["writer_id"] == lease.owner
            and prior["writer_epoch"] == lease.epoch
        ):
            return UUID(str(state["result_id"]))
    data = payload(c)
    await session.execute(
        """INSERT INTO market_candle_closure_observations
      (id,source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,symbol_revision,catalog_revision,
       trade_count,first_trade_id,last_trade_id,closed_hint,event_at,received_at,
       writer_id,writer_epoch,activation_epoch,fingerprint)
      VALUES(:id,:source,:base,:quote,:timeframe,:open_at,:end_at,:open,:high,:low,:close,:volume,:symbol_revision,:catalog_revision,
       :count,:first,:last,true,:event,:received,:writer,:epoch,:activation,:fingerprint)
       ON CONFLICT DO NOTHING""",
        data
        | key(c)
        | {
            "id": identity,
            "symbol_revision": symbol.revision,
            "catalog_revision": symbol.catalog_revision,
            "end_at": c.end_at,
            "count": native.trade_count,
            "first": native.first_trade_id,
            "last": native.last_trade_id,
            "event": native.event_at,
            "received": native.received_at,
            "writer": lease.owner,
            "epoch": lease.epoch,
            "activation": current["activation_epoch"],
            "fingerprint": candidate.fingerprint,
        },
    )
    if state is None or state["observation_id"] != identity:
        await session.execute(
            """INSERT INTO market_candle_closure_state
          (source,base,quote,timeframe,open_at,observation_id,status)
          VALUES(:source,:base,:quote,:timeframe,:open_at,:id,'WAITING_REST')
          ON CONFLICT(source,base,quote,timeframe,open_at) DO UPDATE SET
            observation_id=:id,result_id=NULL,status=CASE WHEN
            market_candle_closure_state.status IN ('CONFLICT','INVALIDATED')
            THEN 'CONFLICT' ELSE 'WAITING_REST' END""",
            key(c) | {"id": identity},
        )
    if conflicting_with is not None:
        await invalidate(
            session,
            c,
            fetch_started_at=native.received_at,
            reason="NATIVE_PROGRESSION_CONFLICT",
            native=conflicting_with,
        )
        return None
    proof = await reconcile(session, c)
    if proof is None:
        await coalesce_demand(
            session, c.base, c.quote, c.timeframe, CandleWindow(c.open_at, c.end_at)
        )
    return proof


async def current_proof(session: ReadSession, c: Candle) -> RowMapping | None:
    current = await control(session)
    if current is None:
        return None
    if not current["enabled"]:
        prior = (
            await session.execute(
                "SELECT closure_proof_id FROM market_candles WHERE " + _WHERE, key(c)
            )
        ).scalar_one_or_none()
        if prior is not None:
            raise ClosureUnavailableError("closure protocol disabled")
        return None
    if not await connection_ready(session):
        raise ClosureUnavailableError("closure source not ready")
    if not (await session.execute("SELECT candle_closure_triggers_valid()")).scalar_one():
        raise ClosureUnavailableError("closure guards unavailable")
    row = (
        (
            await session.execute(
                """SELECT r.* FROM market_candles c
      JOIN market_candle_closure_state s USING(source,base,quote,timeframe,open_at)
      JOIN market_candle_closure_results r ON r.id=c.closure_proof_id AND r.id=s.result_id
      JOIN market_candle_closure_observations o ON o.id=r.observation_id
      JOIN runtime_supported_symbols p ON p.base=o.base AND p.quote=o.quote
       AND p.revision=o.symbol_revision AND p.runtime_mode='PUBLIC'
      JOIN market_candle_feed_state f ON f.source=o.source
       AND f.owner=o.writer_id AND f.epoch=o.writer_epoch
      WHERE c.source=:source AND c.base=:base AND c.quote=:quote AND c.timeframe=:timeframe
       AND c.open_at=:open_at AND c.finality='CLOSED' AND s.status='MATCHED'
       AND r.outcome='MATCHED' AND r.policy_version=1 AND r.activation_epoch=:activation""",
                key(c) | {"activation": current["activation_epoch"]},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["fingerprint"] != candle_fingerprint(c):
        raise ClosureUnavailableError("closure proof not current")
    return row


def proof_reference(row: RowMapping | None) -> tuple[str, int, str] | None:
    return None if row is None else (str(row["id"]), row["policy_version"], row["fingerprint"])


async def reconcile_batch(session: MarketDataSession, candles: tuple[Candle, ...]) -> None:
    if not candles:
        return
    first = candles[0]
    opened = frozenset(
        (
            await session.execute(
                "SELECT open_at FROM market_candle_closure_state WHERE source=:source "
                "AND base=:base AND quote=:quote AND timeframe=:timeframe "
                "AND open_at=ANY(CAST(:opens AS timestamptz[])) ",
                key(first) | {"opens": [c.open_at for c in candles]},
            )
        ).scalars()
    )
    for c in {c.open_at: c for c in candles if c.open_at in opened}.values():
        await reconcile(session, c)


async def series_health(
    session: ReadSession,
    base: str,
    quote: str,
    timeframe: Timeframe,
    as_of: datetime,
) -> tuple[bool, datetime | None]:
    """Known contradictions block the series until repair; ordinary missing proof does not."""
    row = (
        await session.execute(
            "SELECT coalesce(bool_and(status NOT IN ('CONFLICT','INVALIDATED')),true) AS ready, "
            "max(recovery_at) AS recovery_at FROM market_candle_closure_state "
            "WHERE source=:source AND base=:base AND quote=:quote AND timeframe=:timeframe "
            "AND open_at>=:cutoff",
            {
                "source": SOURCE,
                "base": base,
                "quote": quote,
                "timeframe": timeframe.value,
                "cutoff": retention_cutoff(as_of, timeframe),
            },
        )
    ).one()
    return bool(row.ready), row.recovery_at
