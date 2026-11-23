"""Shared CLOSED-candle inputs, independent of either strategy implementation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from tiewtrade.core.indicators import IndicatorStatus, IndicatorValue
from tiewtrade.core.market_data import Candle, CandleFinality, Timeframe
from tiewtrade.core.money import Money, Quantity, Scalar
from tiewtrade.core.orders import OrderScope, TradingMode
from tiewtrade.core.positions import PositionPair
from tiewtrade.core.strategies import StrategyInput
from tiewtrade.core.strategy_candles import StrategyCandleInput


def money(value: str) -> Money:
    return Money.of(value, "USDT")


def snapshot(*, rsi: str = "61", offset: int = 0) -> StrategyInput:
    start = datetime(2026, 11, 20, tzinfo=UTC) + timedelta(minutes=5 * offset)
    candle = Candle(
        "BTC",
        "USDT",
        Timeframe.M5,
        start,
        start + timedelta(minutes=5),
        money("100"),
        money("110"),
        money("99"),
        money("105"),
        Quantity.of(1, "BTC"),
        CandleFinality.CLOSED,
        start + timedelta(minutes=5),
    )
    return StrategyInput(
        PositionPair("BTC", "USDT"),
        candle.end_at,
        1,
        1,
        money("105"),
        money("1000"),
        Quantity.of(0, "BTC"),
        OrderScope(UUID(int=1), UUID(int=2), TradingMode.PAPER),
        UUID(int=3),
        f"candle:{offset}",
        tuple(
            (key, IndicatorValue(value, IndicatorStatus.READY))
            for key, value in (
                ("rsi14", Scalar.of(rsi)),
                ("ema20", money("102")),
                ("ema50", money("101")),
                ("atr14", money("2")),
            )
        ),
        candle_input=StrategyCandleInput(
            candle, 250, "fixture:1", False, False, 0, 0, money("0.01"), arm_validated=True
        ),
    )
