"""Bounded F-11 prepared reads and commit-time public-source fencing for bots."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from time import monotonic
from uuid import UUID

from sqlalchemy import RowMapping

from tiewtrade.core.indicators import FORMULA_VERSION, NAMES, IndicatorStatus, IndicatorValue
from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleWindow,
    Timeframe,
    advance,
    align_floor,
    slot_count,
)
from tiewtrade.core.money import Money, MoneyError, Quantity, Scalar
from tiewtrade.core.strategies import StrategyDescriptor, StrategyDocument, StrategyInput
from tiewtrade.core.strategy_candles import StrategyCandleInput
from tiewtrade.core.strategy_config import CANDLE_STRATEGIES
from tiewtrade.infra.bots.baskets import signal_exit_guarded
from tiewtrade.infra.bots.candle_sources import candle_source_state, price_recovery_at
from tiewtrade.infra.bots.indicator_tail import (
    IndicatorTailProof,
    read_bot_indicator_page,
    require_tail_proof,
)
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.indicators.prepared import (
    PreparedNotReadyError,
    PreparedNumericError,
    fresh_proof_valid,
    read_generation_authority,
    rollout_control,
)
from tiewtrade.infra.indicators.read_contract import CursorClaims, DatasetChangedError
from tiewtrade.infra.market_data.candle_closure import (
    ClosureUnavailableError,
    current_proof,
    proof_reference,
)
from tiewtrade.infra.market_data.catalog import SOURCE
from tiewtrade.infra.market_data.order_book_storage import read_latest_book


class BotInputsUnavailableError(ValueError):
    """Declared public inputs are not ready; no fallback or cursor advance is allowed."""


@dataclass(frozen=True, slots=True)
class IndicatorInputs:
    generation: RowMapping
    values: tuple[tuple[str, IndicatorValue], ...]
    open_at: datetime
    revision: str
    rollout_epoch: object
    candle_input: StrategyCandleInput | None = None
    tail: IndicatorTailProof | None = None


def strategy_candle_identity(value: StrategyCandleInput) -> str:
    candle = value.candle
    return (
        f"candle:{candle.base}:{candle.quote}:{candle.timeframe.value}:"
        f"{candle.open_at.isoformat()}:{value.source_revision}"
    )


async def _candle_context(
    session: UserSession,
    snapshot: StrategyInput,
    *,
    timeframe: Timeframe,
    start: datetime,
    revision: str,
    count: int,
    indicator_epoch: UUID,
    lock_source: bool = False,
) -> StrategyCandleInput:
    source_state = await candle_source_state(session, snapshot.pair, timeframe, lock=lock_source)
    price_recovered = await price_recovery_at(session)
    if not source_state.ready:
        raise BotInputsUnavailableError("BOT_CANDLE_SOURCE_NOT_READY")
    row = (
        await session.execute(
            """SELECT * FROM market_candles WHERE source=:source AND base=:base AND quote=:quote
        AND timeframe=:timeframe AND open_at=:start""",
            {
                "source": SOURCE,
                "base": snapshot.pair.base,
                "quote": snapshot.pair.quote,
                "timeframe": timeframe.value,
                "start": start,
            },
        )
    ).one_or_none()
    progress = (
        await session.execute(
            "SELECT guard_revision,eligible_after,reconciliation_required,recovery_required,"
            "source_recovery_at,price_recovery_at,indicator_source_epoch "
            "FROM bot_strategy_progress WHERE run_id=:run",
            {"run": snapshot.run_id},
        )
    ).one_or_none()
    if row is None or progress is None:
        raise BotInputsUnavailableError("BOT_CANDLE_NOT_READY")
    if progress.reconciliation_required:
        raise BotInputsUnavailableError("BOT_INVENTORY_NOT_READY")
    candle = Candle(
        row.base,
        row.quote,
        timeframe,
        row.open_at,
        row.end_at,
        Money.of(row.open, row.quote),
        Money.of(row.high, row.quote),
        Money.of(row.low, row.quote),
        Money.of(row.close, row.quote),
        Quantity.of(row.volume, row.base),
        CandleFinality(row.finality),
        row.observed_at,
    )
    if candle.finality is CandleFinality.UNCONFIRMED:
        raise BotInputsUnavailableError("BOT_CANDLE_UNCONFIRMED")
    if candle.finality is not CandleFinality.CLOSED:
        raise BotInputsUnavailableError("BOT_CANDLE_NOT_READY")
    try:
        closure_proof = proof_reference(await current_proof(session, candle))
    except ClosureUnavailableError:
        raise BotInputsUnavailableError("BOT_CANDLE_UNCONFIRMED") from None
    exited = await signal_exit_guarded(session, snapshot.run_id, start, timeframe)
    basket = (
        await session.execute(
            """SELECT b.status,b.target,b.reconciliation_required,
        count(e.order_id) FILTER(WHERE e.quantity>0) AS open_entries
        FROM bot_strategy_baskets b LEFT JOIN bot_strategy_entries e ON e.basket_id=b.id
        WHERE b.run_id=:run AND b.status<>'CLOSED' GROUP BY b.id""",
            {"run": snapshot.run_id},
        )
    ).one_or_none()
    if basket is not None and basket.reconciliation_required:
        raise BotInputsUnavailableError("BOT_INVENTORY_NOT_READY")
    source = await read_latest_book(session, snapshot.pair)
    return StrategyCandleInput(
        candle,
        count,
        revision,
        progress.recovery_required
        or progress.price_recovery_at != price_recovered
        or progress.indicator_source_epoch != indicator_epoch
        or (
            source_state.recovery_at is not None
            and (
                progress.source_recovery_at is None
                or source_state.recovery_at > progress.source_recovery_at
            )
        )
        or candle.end_at <= progress.eligible_after,
        exited,
        progress.guard_revision,
        0 if basket is None else basket.open_entries,
        source.metadata.market.price_tick,
        basket is not None
        and (
            basket.status == "TRIGGERED"
            or (
                basket.target is not None
                and not snapshot.price < Money.of(basket.target, snapshot.pair.quote)
            )
        ),
        closure_proof=closure_proof,
    )


async def read_bot_indicators(
    session: UserSession,
    descriptor: StrategyDescriptor,
    snapshot: StrategyInput,
    state: StrategyDocument | None = None,
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
        page = await read_bot_indicator_page(
            session, claims, control, now, deadline, allow_tail=descriptor.name in CANDLE_STRATEGIES
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
    if len(points) != 1 or points[0].open_at != start:
        raise BotInputsUnavailableError("INDICATOR_NOT_READY")
    inherited_unconfirmed = points[0].finality is CandleFinality.UNCONFIRMED
    if inherited_unconfirmed and descriptor.name not in CANDLE_STRATEGIES:
        raise BotInputsUnavailableError("BOT_CANDLE_UNCONFIRMED")
    if points[0].finality not in (CandleFinality.CLOSED, CandleFinality.UNCONFIRMED):
        raise BotInputsUnavailableError("INDICATOR_NOT_READY")
    values = tuple(
        (name, points[0].values[name]) for name in sorted(descriptor.required_indicators)
    )
    if any(value.status is not IndicatorStatus.READY or value.value is None for _, value in values):
        raise BotInputsUnavailableError("INDICATOR_NOT_READY")
    revision = (
        f"{FORMULA_VERSION}:{page.generation['id']}:{page.result.revision}:{start.isoformat()}"
    )
    candle_input = None
    if descriptor.name in CANDLE_STRATEGIES:
        seed = points[0].seed_open_at
        count = 0 if seed is None else slot_count(CandleWindow(seed, end), timeframe)
        if count < 250:
            raise BotInputsUnavailableError("BOT_CANDLE_WARM_UP")
        candle_input = await _candle_context(
            session,
            snapshot,
            timeframe=timeframe,
            start=start,
            revision=revision,
            count=count,
            indicator_epoch=page.generation["source_epoch"],
        )
        # F11 retains aggregate history provenance. Only a current receipt for
        # the actual CLOSED signal permits eligible UNCONFIRMED warm-up history.
        if inherited_unconfirmed and candle_input.closure_proof is None:
            raise BotInputsUnavailableError("BOT_CANDLE_UNCONFIRMED")
        fields = {} if state is None else dict(state.fields)
        reset_at, reset = fields.get("reset_open_at"), fields.get("reset_close")
        if isinstance(reset_at, str) and isinstance(reset, Money):
            try:
                arm_start = datetime.fromisoformat(reset_at)
                if not page.generation["calculation_start"] <= arm_start < start:
                    raise ValueError("ARM outside current proof")
                arm_claims = CursorClaims.model_validate(
                    claims.model_dump()
                    | {
                        "calculation_start": arm_start,
                        "calculation_end": advance(arm_start, timeframe, 1),
                        "result_start": arm_start,
                        "result_end": advance(arm_start, timeframe, 1),
                        "next_open_at": arm_start,
                    }
                )
                arm_page = await read_bot_indicator_page(
                    session, arm_claims, control, now, deadline, allow_tail=True
                )
                arm_close = (
                    await session.execute(
                        "SELECT close FROM market_candles WHERE source=:source AND base=:base "
                        "AND quote=:quote AND timeframe=:timeframe "
                        "AND open_at=:start AND finality='CLOSED'",
                        {
                            "source": SOURCE,
                            "base": snapshot.pair.base,
                            "quote": snapshot.pair.quote,
                            "timeframe": timeframe.value,
                            "start": arm_start,
                        },
                    )
                ).scalar_one_or_none()
                arm_points = arm_page.result.points
                arm_rsi = arm_points[0].values["rsi14"] if len(arm_points) == 1 else None
                validated = (
                    arm_page.generation["id"] == page.generation["id"]
                    and arm_rsi is not None
                    and arm_rsi.status is IndicatorStatus.READY
                    and isinstance(arm_rsi.value, Scalar)
                    and arm_rsi.value.amount < 30
                    and arm_close is not None
                    and Money.of(arm_close, snapshot.pair.quote) == reset
                )
                candle_input = replace(candle_input, arm_validated=validated)
            except (
                PreparedNotReadyError,
                PreparedNumericError,
                DatasetChangedError,
                ValueError,
                TimeoutError,
                MoneyError,
            ):
                pass  # The existing ARM is unproven; a fresh ARM may still replace it.
    return IndicatorInputs(
        page.generation,
        values,
        start,
        revision,
        control["rollout_epoch"],
        candle_input,
        page.tail,
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
        or not await fresh_proof_valid(
            session,
            generation,
            now,
            through=None if inputs.tail is None else inputs.tail.prefix_end,
        )
        or (
            inputs.tail is not None
            and not await require_tail_proof(session, generation, inputs.tail)
        )
    ):
        raise BotInputsUnavailableError("INDICATOR_SOURCE_CHANGED")

    if inputs.candle_input is not None:
        head, failure = await read_generation_authority(
            session,
            generation["base"],
            generation["quote"],
            Timeframe(generation["timeframe"]),
            generation["formula_version"],
        )
        if head is None or head["id"] != generation["id"] or failure is not None:
            raise BotInputsUnavailableError("INDICATOR_SOURCE_CHANGED")


async def require_current_candle(
    session: UserSession, snapshot: StrategyInput, inputs: IndicatorInputs
) -> None:
    if inputs.candle_input is None:
        return
    old = inputs.candle_input
    current = await _candle_context(
        session,
        snapshot,
        timeframe=old.candle.timeframe,
        start=old.candle.open_at,
        revision=old.source_revision,
        count=old.contiguous_count,
        indicator_epoch=inputs.generation["source_epoch"],
        lock_source=True,
    )
    if replace(current, arm_validated=old.arm_validated) != old:
        raise BotInputsUnavailableError("BOT_CANDLE_AUTHORITY_CHANGED")
