"""Strict, versioned checkpoint payload for prepared indicator generations."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from tiewtrade.core.indicators import (
    FORMULA_VERSION,
    IndicatorCheckpointState,
    IndicatorStream,
)
from tiewtrade.core.market_data import CandleWindow, Timeframe, align_floor
from tiewtrade.core.money import Money
from tiewtrade.core.money.errors import MoneyError
from tiewtrade.core.money.indicator_batch import AverageState, IndicatorBatchState

CODEC_VERSION = 1
MAX_PAYLOAD_BYTES = 16 * 1024
# The ordered identities belong to indicators-v1; equal periods are not equal states.
AVERAGE_SCHEMA = (
    ("ema12", 12),
    ("ema20", 20),
    ("ema26", 26),
    ("ema50", 50),
    ("ema200", 200),
    ("macd_signal", 9),
    ("rsi_gain14", 14),
    ("rsi_loss14", 14),
    ("atr14", 14),
)


class CheckpointCodecError(ValueError):
    """Untrusted checkpoint is unusable; callers must fail closed."""


def _time(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


def _read_time(value: object) -> datetime:
    if type(value) is not str:
        raise CheckpointCodecError("invalid checkpoint time")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CheckpointCodecError("invalid checkpoint time") from exc
    if moment.tzinfo is None or _time(moment) != value:
        raise CheckpointCodecError("noncanonical checkpoint time")
    return moment.astimezone(UTC)


def _optional_time(value: object) -> datetime | None:
    return None if value is None else _read_time(value)


def _object(value: object, keys: set[str]) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != keys:
        raise CheckpointCodecError("invalid checkpoint shape")
    return cast(Mapping[str, object], value)


def _money_text(value: Money) -> str:
    return value.as_parts()["amount"]


def _read_money(value: object, quote: str) -> Money:
    if type(value) is not str:
        raise CheckpointCodecError("invalid checkpoint amount")
    try:
        money = Money.of(value, quote)
    except (MoneyError, ValueError, ArithmeticError) as exc:
        raise CheckpointCodecError("invalid checkpoint amount") from exc
    if _money_text(money) != value:
        raise CheckpointCodecError("noncanonical checkpoint amount")
    return money


def _payload_size(payload: object) -> None:
    try:
        # JSONB's text representation inserts spaces; measure conservatively.
        size = len(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("ascii"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise CheckpointCodecError("invalid checkpoint JSON") from exc
    if size > MAX_PAYLOAD_BYTES:
        raise CheckpointCodecError("checkpoint payload too large")


def _boundary(calculation: CandleWindow, timeframe: Timeframe, next_open_at: datetime) -> None:
    if (
        calculation.start != align_floor(calculation.start, timeframe)
        or calculation.end != align_floor(calculation.end, timeframe)
        or next_open_at != align_floor(next_open_at, timeframe)
        or not calculation.start <= next_open_at <= calculation.end
        or (
            (next_open_at - calculation.start) // timeframe.span % 1000 != 0
            and next_open_at != calculation.end
        )
    ):
        raise CheckpointCodecError("invalid checkpoint boundary")


def _state_bounds(
    state: IndicatorCheckpointState,
    calculation: CandleWindow,
    timeframe: Timeframe,
    next_open_at: datetime,
) -> None:
    for moment in (state.seed_open_at, state.refresh_dependency):
        if moment is not None and (
            not calculation.start <= moment < next_open_at
            or moment != align_floor(moment, timeframe)
        ):
            raise CheckpointCodecError("checkpoint state outside calculation")


def encode_checkpoint(
    stream: IndicatorStream,
    *,
    generation_id: str,
    source: str,
    calculation: CandleWindow,
    next_open_at: datetime,
) -> dict[str, object]:
    """Export state before the next unprocessed slot, including the initial slot."""
    _boundary(calculation, stream.timeframe, next_open_at)
    state = stream.export_state()
    stream.restore_state(state)
    _state_bounds(state, calculation, stream.timeframe, next_open_at)
    expected_last = (
        None if next_open_at == calculation.start else next_open_at - stream.timeframe.span
    )
    if state.numeric.last_open != expected_last:
        raise CheckpointCodecError("checkpoint skips or repeats a slot")
    if not generation_id or not source:
        raise CheckpointCodecError("invalid checkpoint identity")
    payload: dict[str, object] = {
        "version": CODEC_VERSION,
        "generation_id": generation_id,
        "source": source,
        "base": stream.base,
        "quote": stream.quote,
        "timeframe": stream.timeframe.value,
        "formula_version": FORMULA_VERSION,
        "as_of": _time(stream.as_of),
        "start": _time(calculation.start),
        "end": _time(calculation.end),
        "next_open_at": _time(next_open_at),
        "last_open_at": _time(expected_last) if expected_last else None,
        "previous": _money_text(state.numeric.previous) if state.numeric.previous else None,
        "accepted_count": state.numeric.accepted_count,
        "averages": [
            {
                "name": name,
                "pending": [_money_text(value) for value in average.pending],
                "value": _money_text(average.value) if average.value else None,
            }
            for average, (name, _) in zip(state.numeric.averages, AVERAGE_SCHEMA, strict=True)
        ],
        "seed_open_at": _time(state.seed_open_at) if state.seed_open_at else None,
        "blocked": state.blocked,
        "unconfirmed": state.unconfirmed,
        "refresh_dependency": (
            _time(state.refresh_dependency) if state.refresh_dependency else None
        ),
    }
    _payload_size(payload)
    return payload


def decode_checkpoint(
    payload: object,
    *,
    generation_id: str,
    source: str,
    base: str,
    quote: str,
    timeframe: Timeframe,
    as_of: datetime,
    calculation: CandleWindow,
    next_open_at: datetime,
) -> IndicatorStream:
    """Validate storage state against trusted generation metadata before restoring."""
    _payload_size(payload)
    _boundary(calculation, timeframe, next_open_at)
    data = _object(
        payload,
        {
            "version",
            "generation_id",
            "source",
            "base",
            "quote",
            "timeframe",
            "formula_version",
            "as_of",
            "start",
            "end",
            "next_open_at",
            "last_open_at",
            "previous",
            "accepted_count",
            "averages",
            "seed_open_at",
            "blocked",
            "unconfirmed",
            "refresh_dependency",
        },
    )
    if (
        type(data["version"]) is not int
        or data["version"] != CODEC_VERSION
        or any(
            type(data[key]) is not str or data[key] != expected
            for key, expected in (
                ("generation_id", generation_id),
                ("source", source),
                ("base", base),
                ("quote", quote),
                ("timeframe", timeframe.value),
                ("formula_version", FORMULA_VERSION),
                ("as_of", _time(as_of)),
                ("start", _time(calculation.start)),
                ("end", _time(calculation.end)),
                ("next_open_at", _time(next_open_at)),
            )
        )
    ):
        raise CheckpointCodecError("checkpoint identity mismatch")
    expected_last = None if next_open_at == calculation.start else next_open_at - timeframe.span
    last_open = _optional_time(data["last_open_at"])
    if last_open != expected_last:
        raise CheckpointCodecError("checkpoint skips or repeats a slot")
    raw_averages = data["averages"]
    if type(raw_averages) is not list or len(raw_averages) != len(AVERAGE_SCHEMA):
        raise CheckpointCodecError("invalid checkpoint averages")
    averages: list[AverageState] = []
    for raw, (name, period) in zip(raw_averages, AVERAGE_SCHEMA, strict=True):
        entry = _object(raw, {"name", "pending", "value"})
        if type(entry["name"]) is not str or entry["name"] != name:
            raise CheckpointCodecError("invalid checkpoint average identity or order")
        pending = entry["pending"]
        if type(pending) is not list or len(pending) >= period:
            raise CheckpointCodecError("invalid checkpoint warm-up")
        averages.append(
            AverageState(
                tuple(_read_money(value, quote) for value in pending),
                None if entry["value"] is None else _read_money(entry["value"], quote),
            )
        )
    if type(data["blocked"]) is not bool or type(data["unconfirmed"]) is not bool:
        raise CheckpointCodecError("invalid checkpoint flags")
    count = data["accepted_count"]
    if type(count) is not int:
        raise CheckpointCodecError("invalid accepted input count")
    try:
        numeric = IndicatorBatchState(
            base,
            quote,
            timeframe.value,
            timeframe.span,
            FORMULA_VERSION,
            last_open,
            None if data["previous"] is None else _read_money(data["previous"], quote),
            tuple(averages),
            count,
        )
        state = IndicatorCheckpointState(
            numeric,
            _optional_time(data["seed_open_at"]),
            data["blocked"] is True,
            data["unconfirmed"] is True,
            _optional_time(data["refresh_dependency"]),
        )
        stream = IndicatorStream(base, quote, timeframe, as_of)
        stream.restore_state(state)
        _state_bounds(state, calculation, timeframe, next_open_at)
    except (MoneyError, ValueError, ArithmeticError, TypeError) as exc:
        raise CheckpointCodecError("invalid checkpoint state") from exc
    return stream
