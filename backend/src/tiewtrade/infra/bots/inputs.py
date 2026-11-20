"""Bounded F-11 prepared reads and commit-time public-source fencing for bots."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic

from sqlalchemy import RowMapping

from tiewtrade.core.indicators import FORMULA_VERSION, NAMES, IndicatorStatus, IndicatorValue
from tiewtrade.core.market_data import CandleFinality, Timeframe, advance, align_floor
from tiewtrade.core.money import MoneyError
from tiewtrade.core.strategies import StrategyDescriptor, StrategyInput
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.indicators.prepared import (
    PreparedNotReadyError,
    PreparedNumericError,
    proof_valid,
    read_prepared,
    rollout_control,
)
from tiewtrade.infra.indicators.read_contract import CursorClaims, DatasetChangedError
from tiewtrade.infra.market_data.catalog import SOURCE


class BotInputsUnavailableError(ValueError):
    """Declared public inputs are not ready; no fallback or cursor advance is allowed."""


@dataclass(frozen=True, slots=True)
class IndicatorInputs:
    generation: RowMapping
    values: tuple[tuple[str, IndicatorValue], ...]
    open_at: datetime
    revision: str
    rollout_epoch: object


async def read_bot_indicators(
    session: UserSession, descriptor: StrategyDescriptor, snapshot: StrategyInput
) -> IndicatorInputs:
    """Read the last closed point at the explicit quote/feedback input time.

    This supplies dependencies, not a candle-close or catch-up trigger. No scan
    from the beginning of retention is allowed: F-11 restores a checkpoint and
    replays at most its bounded suffix.
    """
    if descriptor.timeframe is None or not descriptor.required_indicators <= set(NAMES):
        raise BotInputsUnavailableError("INDICATOR_NOT_READY")
    try:
        timeframe = Timeframe(descriptor.timeframe)
    except ValueError:
        raise BotInputsUnavailableError("INDICATOR_NOT_READY") from None
    end = align_floor(snapshot.observed_at, timeframe)
    start = advance(end, timeframe, -1)
    now: datetime = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    deadline = monotonic() + 1.5
    claims = CursorClaims(
        dataset_revision="",
        source=SOURCE,
        base=snapshot.pair.base,
        quote=snapshot.pair.quote,
        timeframe=timeframe,
        calculation_start=start,
        calculation_end=end,
        as_of=now,
        result_start=start,
        result_end=end,
        next_open_at=start,
        page_size=1,
        issued_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    try:
        control = await rollout_control(session, deadline)
        page = await read_prepared(
            session, claims, control, now, deadline, continuation=False, explicit_range=True
        )
    except (
        PreparedNotReadyError,
        PreparedNumericError,
        DatasetChangedError,
        ValueError,
        TimeoutError,
        MoneyError,
    ):
        raise BotInputsUnavailableError("INDICATOR_NOT_READY") from None
    points = page.result.points
    if (
        len(points) != 1
        or points[0].open_at != start
        or points[0].finality is not CandleFinality.CLOSED
    ):
        raise BotInputsUnavailableError("INDICATOR_NOT_READY")
    values = tuple(
        (name, points[0].values[name]) for name in sorted(descriptor.required_indicators)
    )
    if any(value.status is not IndicatorStatus.READY or value.value is None for _, value in values):
        raise BotInputsUnavailableError("INDICATOR_NOT_READY")
    return IndicatorInputs(
        page.generation,
        values,
        start,
        f"{FORMULA_VERSION}:{page.claims.generation_id}:{page.result.revision}:{start.isoformat()}",
        control["rollout_epoch"],
    )


async def require_current_indicators(session: UserSession, inputs: IndicatorInputs) -> None:
    """Fence source mutations, then validate proof/rollout against current database truth."""
    await session.execute("SELECT hold_bot_indicator_source()")
    now: datetime = (await session.execute("SELECT clock_timestamp()")).scalar_one()
    control = (
        (await session.execute("SELECT * FROM indicator_rollout_control WHERE id=1"))
        .mappings()
        .one()
    )
    generation = inputs.generation
    if (
        control["mode"] != "PREPARED"
        or control["source_proof_state"] != "READY"
        or control["rollout_epoch"] != inputs.rollout_epoch
        or not timedelta(0) <= now - generation["as_of"] <= timedelta(seconds=600)
        or not await proof_valid(session, generation, now)
    ):
        raise BotInputsUnavailableError("INDICATOR_SOURCE_CHANGED")
