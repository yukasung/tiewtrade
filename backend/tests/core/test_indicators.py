from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tiewtrade.core.indicators import IndicatorStatus, IndicatorStream
from tiewtrade.core.market_data import Candle, CandleFinality, Timeframe
from tiewtrade.core.money import Money, Quantity, Scalar

START = datetime(2026, 10, 9, tzinfo=UTC)


def test_restore_rejects_impossible_history_without_mutating_stream() -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, START + timedelta(days=1))
    for index in range(10):
        bar = candle(index)
        stream.feed(bar.open_at, bar, bar.end_at)
    original = stream.export_state()
    bad_states = (
        replace(original, seed_open_at=candle(9).open_at),
        replace(original, blocked=True, refresh_dependency=candle(0).open_at),
    )
    for state in bad_states:
        with pytest.raises(ValueError, match="count exceeds seed history"):
            stream.restore_state(state)
        assert stream.export_state() == original


def test_accepted_count_preserves_hold_and_resets_on_gap() -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, START + timedelta(days=1))
    bar = candle(0)
    stream.feed(bar.open_at, bar, bar.end_at)
    assert stream.state.accepted_count == 1
    bar = replace(candle(1), finality=CandleFinality.OPEN)
    stream.feed(bar.open_at, bar, bar.end_at)
    assert stream.state.accepted_count == 1
    bar = candle(2)
    stream.feed(bar.open_at, bar, bar.end_at)
    assert stream.state.accepted_count == 2
    stream.restore_state(stream.export_state())
    stream.feed(candle(3).open_at, None, None)
    assert stream.state.accepted_count == 0
    bar = candle(4)
    stream.feed(bar.open_at, bar, bar.open_at)
    assert stream.export_state().blocked and stream.state.accepted_count == 0
    bar = candle(5, CandleFinality.CLOSED)
    stream.feed(bar.open_at, bar, bar.end_at)
    assert stream.state.accepted_count == 0
    stream.restore_state(stream.export_state())
    stream.feed(candle(6).open_at, None, None)
    bar = candle(7)
    stream.feed(bar.open_at, bar, bar.end_at)
    assert not stream.blocked and stream.state.accepted_count == 1
    stream.restore_state(stream.export_state())


def candle(index: int, finality: CandleFinality = CandleFinality.UNCONFIRMED) -> Candle:
    moment = START + timedelta(minutes=index)
    return Candle(
        "BTC",
        "USDT",
        Timeframe.M1,
        moment,
        moment + timedelta(minutes=1),
        Money.of(100, "USDT"),
        Money.of(101, "USDT"),
        Money.of(99, "USDT"),
        Money.of(100, "USDT"),
        Quantity.of(1, "BTC"),
        finality,
        moment,
    )


def test_constant_price_golden_and_exact_warmup() -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, START + timedelta(days=1))
    for index in range(201):
        bar = candle(index)
        point = stream.feed(bar.open_at, bar, bar.end_at)
        for name, boundary, expected in [
            ("ema20", 20, 100),
            ("ema50", 50, 100),
            ("ema200", 200, 100),
            ("atr14", 15, 2),
            ("macd_line", 26, 0),
            ("macd_signal", 34, 0),
            ("macd_histogram", 34, 0),
        ]:
            value = point.values[name]
            if index + 1 < boundary:
                assert value.status is IndicatorStatus.WARM_UP and value.value is None
            else:
                assert value.value == Money.of(expected, "USDT")
        if index >= 14:
            assert point.values["rsi14"].value == Scalar.of(50)
        assert point.finality is CandleFinality.UNCONFIRMED


def test_refresh_blocks_until_gap_and_taints_closed_input() -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, START + timedelta(days=1))
    first = candle(0)
    assert (
        stream.feed(first.open_at, first, first.open_at).values["ema20"].status
        is IndicatorStatus.REFRESH_REQUIRED
    )
    second = candle(1, CandleFinality.CLOSED)
    assert (
        stream.feed(second.open_at, second, None).values["ema20"].status
        is IndicatorStatus.REFRESH_REQUIRED
    )
    assert stream.feed(candle(2).open_at, None, None).values["ema20"].status is IndicatorStatus.GAP
    third = candle(3)
    stream.feed(third.open_at, third, third.end_at)
    fourth = candle(4, CandleFinality.CLOSED)
    assert stream.feed(fourth.open_at, fourth, None).finality is CandleFinality.UNCONFIRMED


def _text(ticks: int) -> str:
    sign = "-" if ticks < 0 else ""
    whole, fractional = divmod(abs(ticks), 10**18)
    return f"{sign}{whole}.{fractional:018d}"


def _oracle(prices: list[int]) -> list[dict[str, int | None]]:
    """Independent exact-fraction worksheet, including rounding after every step."""

    def floor(value: Fraction) -> int:
        return value.numerator // value.denominator

    ema: dict[int, int] = {}
    gains: list[int] = []
    losses: list[int] = []
    ranges: list[int] = []
    lines: list[int] = []
    gain = loss = atr = signal = None
    results = []
    for i, price in enumerate(prices):
        for n in (12, 20, 26, 50, 200):
            if i + 1 == n:
                ema[n] = floor(Fraction(sum(prices[:n]), n))
            elif i + 1 > n:
                ema[n] = floor(Fraction((n - 1) * ema[n] + 2 * price, n + 1))
        line = ema[12] - ema[26] if 26 in ema else None
        if line is not None:
            lines.append(line)
            if len(lines) == 9:
                signal = floor(Fraction(sum(lines), 9))
            elif len(lines) > 9:
                assert signal is not None
                signal = floor(Fraction(8 * signal + 2 * line, 10))
        if i:
            delta = price - prices[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))
            ranges.append(
                max(
                    2 * 10**18,
                    abs(price + 10**18 - prices[i - 1]),
                    abs(price - 10**18 - prices[i - 1]),
                )
            )
            if i == 14:
                gain = floor(Fraction(sum(gains), 14))
                loss = floor(Fraction(sum(losses), 14))
                atr = floor(Fraction(sum(ranges), 14))
            elif i > 14:
                assert gain is not None and loss is not None and atr is not None
                gain = floor(Fraction(13 * gain + gains[-1], 14))
                loss = floor(Fraction(13 * loss + losses[-1], 14))
                atr = floor(Fraction(13 * atr + ranges[-1], 14))
        rsi = None
        if gain is not None and loss is not None:
            rsi = (
                (50 if gain == loss == 0 else 100 if loss == 0 else 0) * 10**18
                if gain == 0 or loss == 0
                else floor(Fraction(100 * 10**18 * gain, gain + loss))
            )
        results.append(
            {
                "ema20": ema.get(20),
                "ema50": ema.get(50),
                "ema200": ema.get(200),
                "rsi14": rsi,
                "atr14": atr,
                "macd_line": line,
                "macd_signal": signal,
                "macd_histogram": line - signal
                if line is not None and signal is not None
                else None,
            }
        )
    return results


@pytest.mark.parametrize("batch_size", [1, 2, 16])
@settings(max_examples=12, deadline=None)
@given(st.lists(st.integers(-5 * 10**18, 5 * 10**18), min_size=205, max_size=240))
def test_batch_matches_independent_rounded_series(batch_size: int, offsets: list[int]) -> None:
    prices = [100 * 10**18 + offset for offset in offsets]
    expected = _oracle(prices)
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, START + timedelta(days=1))
    bars = []
    for i, price in enumerate(prices):
        moment = START + timedelta(minutes=i)
        close = Money.of(_text(price), "USDT")
        bar = Candle(
            "BTC",
            "USDT",
            Timeframe.M1,
            moment,
            moment + timedelta(minutes=1),
            close,
            Money.of(_text(price + 10**18), "USDT"),
            Money.of(_text(price - 10**18), "USDT"),
            close,
            Quantity.of(0, "BTC"),
            CandleFinality.UNCONFIRMED,
            moment,
        )
        bars.append((moment, bar, bar.end_at))
    for offset in range(0, len(bars), batch_size):
        slots = tuple(bars[offset : offset + batch_size])
        result = stream.feed_batch(slots, output_indices=tuple(range(len(slots))))
        for i, point in enumerate(result.points):
            for name, value in point.values.items():
                answer = expected[offset + i][name]
                if answer is None:
                    assert value.value is None and value.status is IndicatorStatus.WARM_UP
                elif name == "rsi14":
                    assert value.value == Scalar.of(_text(answer))
                else:
                    assert value.value == Money.of(_text(answer), "USDT")


def test_batch_controls_and_only_requested_outputs() -> None:
    stream = IndicatorStream("BTC", "USDT", Timeframe.M1, START + timedelta(days=1))
    first, third = candle(0), candle(2)
    result = stream.feed_batch(
        (
            (first.open_at, first, first.open_at),
            (candle(1).open_at, None, None),
            (third.open_at, third, third.end_at),
        ),
        output_indices=(2,),
    )
    assert len(result.points) == 1
    assert result.refresh_dependencies == (first.open_at, None, None)
    assert result.points[0].seed_open_at == third.open_at
    assert result.points[0].values["ema20"].status is IndicatorStatus.WARM_UP
    with pytest.raises(ValueError):
        stream.feed_batch(
            ((candle(3).open_at, candle(3), candle(3).end_at),), output_indices=(True,)
        )
