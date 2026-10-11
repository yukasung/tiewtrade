"""Prepared checkpoint state must replay the uninterrupted full scan exactly."""

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_UP, localcontext
from typing import cast

import pytest

from tiewtrade.core.indicators import IndicatorPoint, IndicatorStream
from tiewtrade.core.market_data import Candle, CandleFinality, CandleWindow, Timeframe
from tiewtrade.core.money import InvalidInputTypeError, Money, Quantity
from tiewtrade.infra.indicators.codec import (
    CheckpointCodecError,
    decode_checkpoint,
    encode_checkpoint,
)

START = datetime(2026, 10, 1, tzinfo=UTC)
SPAN = timedelta(minutes=1)
COUNT = 2003
WINDOW = CandleWindow(START, START + COUNT * SPAN)
AS_OF = WINDOW.end + SPAN
IDENTITY = {"generation_id": "gen-1", "source": "primary_spot"}


def _slot(index: int) -> tuple[datetime, Candle | None, datetime | None]:
    moment = START + index * SPAN
    if index in {47, 1002, 1750}:
        return moment, None, None
    whole, tenth = divmod(index % 41, 10)
    price = Money.of(f"{100 + whole}.{tenth}12345678901234567", "USDT")
    high = price + Money.of("0.5", "USDT")
    low = price - Money.of("0.5", "USDT")
    finality = CandleFinality.UNCONFIRMED if index % 3 == 0 else CandleFinality.CLOSED
    fetched = moment if index in {999, 1000} else moment + SPAN
    return (
        moment,
        Candle(
            "BTC",
            "USDT",
            Timeframe.M1,
            moment,
            moment + SPAN,
            price,
            high,
            low,
            price,
            Quantity.of("1.123456789", "BTC"),
            finality,
            moment,
        ),
        fetched,
    )


def _encode(stream: IndicatorStream, next_index: int) -> dict[str, object]:
    return encode_checkpoint(
        stream, **IDENTITY, calculation=WINDOW, next_open_at=START + next_index * SPAN
    )


def _decode(payload: object, next_index: int) -> IndicatorStream:
    return decode_checkpoint(
        payload,
        **IDENTITY,
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.M1,
        as_of=AS_OF,
        calculation=WINDOW,
        next_open_at=START + next_index * SPAN,
    )


@pytest.mark.parametrize("batch_size", [1, 2, 16])
def test_checkpoint_replay_matches_full_scan_at_boundaries(batch_size: int) -> None:
    slots = tuple(_slot(index) for index in range(COUNT))
    reference = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    expected = tuple(reference.feed(*slot) for slot in slots)
    builder = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    checkpoints = {0: _encode(builder, 0)}
    for index, slot in enumerate(slots, 1):
        builder.feed(*slot)
        if index in {1000, 2000, COUNT}:
            checkpoints[index] = _encode(builder, index)
    assert builder.export_state() == reference.export_state()
    for start in (0, 1000, 2000):
        replay = _decode(json.loads(json.dumps(checkpoints[start])), start)
        observed: list[IndicatorPoint] = []
        for index in range(start, COUNT, batch_size):
            batch = slots[index : index + batch_size]
            observed.extend(
                replay.feed_batch(batch, output_indices=tuple(range(len(batch)))).points
            )
        assert tuple(observed) == expected[start:]
        assert replay.export_state() == reference.export_state()
    assert _decode(checkpoints[COUNT], COUNT).export_state() == reference.export_state()
    assert max(len(json.dumps(value).encode()) for value in checkpoints.values()) < 16 * 1024


@pytest.mark.parametrize("page_start", [999, 1000, 1001, 1999, 2000, 2001])
def test_page_start_before_at_after_checkpoint(page_start: int) -> None:
    slots = tuple(_slot(index) for index in range(COUNT))
    reference = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    expected = tuple(reference.feed(*slot) for slot in slots)
    builder = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    checkpoint = 0 if page_start < 1000 else 1000 if page_start < 2000 else 2000
    for slot in slots[:checkpoint]:
        builder.feed(*slot)
    restored = _decode(_encode(builder, checkpoint), checkpoint)
    for slot in slots[checkpoint:page_start]:
        restored.feed(*slot)
    observed = tuple(restored.feed(*slot) for slot in slots[page_start : page_start + 2])
    assert observed == expected[page_start : page_start + 2]


def test_checkpoint_ambient_decimal_context_parity() -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    for index in range(1000):
        stream.feed(*_slot(index))
    payload = _encode(stream, 1000)
    next_slot = _slot(1000)
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        restored = _decode(payload, 1000)
        assert restored.feed(*next_slot) == stream.feed(*next_slot)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", True),
        ("generation_id", "other"),
        ("source", "other"),
        ("quote", "EUR"),
        ("formula_version", "future"),
        ("next_open_at", "2026-10-01T16:41:00.000000+00:00"),
        ("last_open_at", None),
        ("blocked", 1),
        ("unconfirmed", "false"),
        ("seed_open_at", "2030-01-01T00:00:00.000000+00:00"),
        ("refresh_dependency", "2030-01-01T00:00:00.000000+00:00"),
        ("previous", "1e2"),
        ("averages", []),
        ("previous", "NaN"),
        ("previous", "1" * 100),
    ],
)
def test_damaged_checkpoint_fails_closed(field: str, value: object) -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    for index in range(1000):
        stream.feed(*_slot(index))
    payload = copy.deepcopy(_encode(stream, 1000))
    payload[field] = value
    with pytest.raises(CheckpointCodecError):
        _decode(payload, 1000)


def test_checkpoint_rejects_oversized_payload_and_noncanonical_money() -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    for index in range(1000):
        stream.feed(*_slot(index))
    payload = _encode(stream, 1000)
    damaged = copy.deepcopy(payload)
    damaged["previous"] = "100.000000000000000000"
    with pytest.raises(CheckpointCodecError):
        _decode(damaged, 1000)
    damaged = copy.deepcopy(payload)
    damaged["junk"] = "x" * 16000
    with pytest.raises(CheckpointCodecError):
        _decode(damaged, 1000)


@pytest.fixture(scope="module")
def mature_checkpoint() -> dict[str, object]:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    for index in range(2000):
        stream.feed(*_slot(index))
    payload = _encode(stream, 2000)
    assert _decode(payload, 2000).export_state() == stream.export_state()
    return payload


@pytest.mark.parametrize(("first", "second"), [(1, 3), (6, 7), (6, 8)])
def test_checkpoint_rejects_reordered_mature_averages(
    mature_checkpoint: dict[str, object],
    first: int,
    second: int,
) -> None:
    payload = copy.deepcopy(mature_checkpoint)
    averages = cast(list[dict[str, object]], payload["averages"])
    assert averages[first]["value"] is not None
    assert averages[second]["value"] is not None
    assert averages[first]["value"] != averages[second]["value"]
    averages[first], averages[second] = averages[second], averages[first]
    with pytest.raises(CheckpointCodecError, match="identity or order"):
        _decode(payload, 2000)


@pytest.mark.parametrize("name", [None, 1, "unknown", "ema12"])
def test_checkpoint_rejects_invalid_average_identity(
    mature_checkpoint: dict[str, object],
    name: object,
) -> None:
    payload = copy.deepcopy(mature_checkpoint)
    averages = cast(list[dict[str, object]], payload["averages"])
    averages[1]["name"] = name
    with pytest.raises(CheckpointCodecError, match="identity or order"):
        _decode(payload, 2000)


def test_checkpoint_rejects_untagged_averages(mature_checkpoint: dict[str, object]) -> None:
    payload = copy.deepcopy(mature_checkpoint)
    averages = cast(list[dict[str, object]], payload["averages"])
    for average in averages:
        del average["name"]
    with pytest.raises(CheckpointCodecError, match="shape"):
        _decode(payload, 2000)


@pytest.mark.parametrize("count", [True, -1, "249", None, 0])
def test_checkpoint_rejects_invalid_accepted_count(
    mature_checkpoint: dict[str, object],
    count: object,
) -> None:
    payload = copy.deepcopy(mature_checkpoint)
    payload["accepted_count"] = count
    with pytest.raises(CheckpointCodecError):
        _decode(payload, 2000)


@pytest.mark.parametrize("corruption", ["empty_averages", "late_seed", "early_dependency"])
def test_checkpoint_rejects_impossible_history(
    mature_checkpoint: dict[str, object],
    corruption: str,
) -> None:
    payload = copy.deepcopy(mature_checkpoint)
    if corruption == "empty_averages":
        for average in cast(list[dict[str, object]], payload["averages"]):
            average["pending"] = []
            average["value"] = None
    elif corruption == "late_seed":
        payload["seed_open_at"] = payload["last_open_at"]
    else:
        payload["blocked"] = True
        payload["refresh_dependency"] = "2026-10-02T01:00:00.000000+00:00"
    with pytest.raises(CheckpointCodecError):
        _decode(payload, 2000)


@pytest.mark.parametrize("count", [1, 11, 12, 14, 15, 25, 26, 33, 34, 199, 200])
def test_checkpoint_count_tracks_each_warmup_boundary(count: int) -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    for index in range(count):
        moment, bar, fetched = _slot(index)
        # Keep this case contiguous so the accepted counts exercise every boundary.
        if bar is None:
            _, bar, _ = _slot(index + 1)
            assert bar is not None
            bar = replace(bar, open_at=moment, end_at=moment + SPAN)
            fetched = bar.end_at
        stream.feed(moment, bar, fetched)
    assert stream.state.accepted_count == count
    window = CandleWindow(START, START + count * SPAN)
    payload = encode_checkpoint(stream, **IDENTITY, calculation=window, next_open_at=window.end)
    restored = decode_checkpoint(
        payload,
        **IDENTITY,
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.M1,
        as_of=AS_OF,
        calculation=window,
        next_open_at=window.end,
    )
    assert restored.export_state() == stream.export_state()
    assert restored.feed(*_slot(count)) == stream.feed(*_slot(count))


@pytest.mark.parametrize("corruption", ["pending_count", "price_history", "previous", "count"])
def test_checkpoint_rejects_inconsistent_warmup_history(corruption: str) -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    for index in range(3):
        stream.feed(*_slot(index))
    window = CandleWindow(START, START + 3 * SPAN)
    payload = encode_checkpoint(stream, **IDENTITY, calculation=window, next_open_at=window.end)
    averages = cast(list[dict[str, object]], payload["averages"])
    if corruption == "pending_count":
        averages[0]["pending"] = cast(list[str], averages[0]["pending"])[:-1]
    elif corruption == "price_history":
        averages[0]["pending"] = ["100", "100", payload["previous"]]
    elif corruption == "previous":
        payload["previous"] = "200"
    else:
        payload["accepted_count"] = 2
    with pytest.raises(CheckpointCodecError):
        decode_checkpoint(
            payload,
            **IDENTITY,
            base="BTC",
            quote="USDT",
            timeframe=Timeframe.M1,
            as_of=AS_OF,
            calculation=window,
            next_open_at=window.end,
        )


def _price_stream(prices: tuple[str, ...], *, minimal_range: bool = False) -> IndicatorStream:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, AS_OF)
    for index, text in enumerate(prices):
        moment, bar, fetched = _slot(index)
        assert bar is not None
        close = Money.of(text, "USDT")
        bar = replace(
            bar,
            open=close,
            high=close if minimal_range else close + Money.of(1, "USDT"),
            low=close if minimal_range else close - Money.of(1, "USDT"),
            close=close,
        )
        stream.feed(moment, bar, fetched)
    return stream


def _mixed_warm_stream(*, minimal_range: bool = False) -> IndicatorStream:
    return _price_stream(("100", "101", "100", "100", "102"), minimal_range=minimal_range)


@pytest.mark.parametrize("corruption", ["both_positive", "wrong_gain", "wrong_loss", "wrong_order"])
def test_checkpoint_rejects_warm_gain_loss_inconsistent_with_closes(corruption: str) -> None:
    stream = _mixed_warm_stream()
    window = CandleWindow(START, START + stream.state.accepted_count * SPAN)
    payload = encode_checkpoint(stream, **IDENTITY, calculation=window, next_open_at=window.end)
    original = stream.export_state()

    def restore(value: object) -> IndicatorStream:
        return decode_checkpoint(
            value,
            **IDENTITY,
            base="BTC",
            quote="USDT",
            timeframe=Timeframe.M1,
            as_of=AS_OF,
            calculation=window,
            next_open_at=window.end,
        )

    assert restore(payload).export_state() == original
    averages = cast(list[dict[str, object]], payload["averages"])
    assert averages[6]["pending"] == ["1", "0", "0", "2"]
    assert averages[7]["pending"] == ["0", "1", "0", "0"]
    if corruption == "both_positive":
        averages[7]["pending"] = ["1", "1", "0", "0"]
    elif corruption == "wrong_gain":
        averages[6]["pending"] = ["2", "0", "0", "2"]
    elif corruption == "wrong_loss":
        averages[7]["pending"] = ["0", "2", "0", "0"]
    else:
        averages[6]["pending"] = ["2", "0", "0", "1"]
    with pytest.raises(CheckpointCodecError):
        restore(payload)
    assert stream.export_state() == original


@pytest.mark.parametrize("minimal_range", [True, False])
def test_checkpoint_accepts_warm_true_range_at_or_above_price_change(minimal_range: bool) -> None:
    stream = _mixed_warm_stream(minimal_range=minimal_range)
    window = CandleWindow(START, START + stream.state.accepted_count * SPAN)
    zero = Money.of(0, "USDT")
    assert stream.state.averages[8].pending[2] == (zero if minimal_range else Money.of(2, "USDT"))
    for gain, loss, true_range in zip(
        stream.state.averages[6].pending,
        stream.state.averages[7].pending,
        stream.state.averages[8].pending,
        strict=True,
    ):
        if minimal_range:
            assert true_range == gain + loss
        else:
            assert true_range > gain + loss
    payload = encode_checkpoint(stream, **IDENTITY, calculation=window, next_open_at=window.end)
    restored = decode_checkpoint(
        payload,
        **IDENTITY,
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.M1,
        as_of=AS_OF,
        calculation=window,
        next_open_at=window.end,
    )
    assert restored.export_state() == stream.export_state()
    assert restored.feed(*_slot(5)) == stream.feed(*_slot(5))


@pytest.mark.parametrize(
    ("index", "value"),
    [(0, "0"), (0, "0.999999999999999999"), (1, "0"), (3, "1.999999999999999999")],
)
def test_checkpoint_rejects_warm_true_range_below_gain_plus_loss(index: int, value: str) -> None:
    stream = _mixed_warm_stream()
    original = stream.export_state()
    window = CandleWindow(START, START + stream.state.accepted_count * SPAN)
    payload = encode_checkpoint(stream, **IDENTITY, calculation=window, next_open_at=window.end)
    averages = cast(list[dict[str, object]], payload["averages"])
    cast(list[str], averages[8]["pending"])[index] = value
    with pytest.raises(CheckpointCodecError) as error:
        decode_checkpoint(
            payload,
            **IDENTITY,
            base="BTC",
            quote="USDT",
            timeframe=Timeframe.M1,
            as_of=AS_OF,
            calculation=window,
            next_open_at=window.end,
        )
    assert isinstance(error.value.__cause__, InvalidInputTypeError)
    assert "true range is below gain plus loss" in str(error.value.__cause__)
    assert stream.export_state() == original


@pytest.mark.parametrize("corruption", ["zero_atr", "below_by_tick", "overflowing_gain_loss_sum"])
def test_checkpoint_rejects_mature_atr_below_average_price_change(
    mature_checkpoint: dict[str, object],
    corruption: str,
) -> None:
    payload = copy.deepcopy(mature_checkpoint)
    averages = cast(list[dict[str, object]], payload["averages"])
    gain = Money.of(cast(str, averages[6]["value"]), "USDT")
    loss = Money.of(cast(str, averages[7]["value"]), "USDT")
    assert gain > Money.of(0, "USDT") and loss > Money.of(0, "USDT")
    if corruption == "zero_atr":
        averages[8]["value"] = "0"
    elif corruption == "below_by_tick":
        below = gain + loss - Money.of("0.000000000000000001", "USDT")
        averages[8]["value"] = below.as_parts()["amount"]
    else:
        averages[6]["value"] = averages[7]["value"] = "90000000000000000000"
        averages[8]["value"] = "90000000000000000000"
    with pytest.raises(CheckpointCodecError) as error:
        _decode(payload, 2000)
    assert isinstance(error.value.__cause__, InvalidInputTypeError)
    assert "mature ATR is below" in str(error.value.__cause__)


@pytest.mark.parametrize("count", [15, 16])
@pytest.mark.parametrize("pattern", ["flat", "integer", "fractional", "large"])
def test_mature_atr_accepts_equal_and_floor_rounded_price_change(count: int, pattern: str) -> None:
    pair = {
        "flat": ("100", "100"),
        "integer": ("100", "101"),
        "fractional": ("100", "100.000000000000000001"),
        "large": ("1", "90000000000000000000"),
    }[pattern]
    stream = _price_stream(tuple(pair[index % 2] for index in range(count)), minimal_range=True)
    gain, loss, atr = (stream.state.averages[index].value for index in (6, 7, 8))
    assert gain is not None and loss is not None and atr is not None
    assert not atr < gain + loss
    if pattern == "flat":
        assert atr == gain == loss == Money.of(0, "USDT")
    elif count == 15 and pattern == "integer":
        assert atr == gain + loss
    elif pattern == "fractional":
        assert atr == gain + loss + Money.of("0.000000000000000001", "USDT")
    window = CandleWindow(START, START + count * SPAN)
    payload = encode_checkpoint(stream, **IDENTITY, calculation=window, next_open_at=window.end)
    restored = decode_checkpoint(
        payload,
        **IDENTITY,
        base="BTC",
        quote="USDT",
        timeframe=Timeframe.M1,
        as_of=AS_OF,
        calculation=window,
        next_open_at=window.end,
    )
    assert restored.export_state() == stream.export_state()
    assert restored.feed(*_slot(count)) == stream.feed(*_slot(count))
