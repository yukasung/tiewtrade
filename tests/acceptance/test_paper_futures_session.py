from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from tiewtrade.application.paper_futures_session import (
    PaperFuturesSession,
    PaperFuturesSessionSnapshot,
    PaperFuturesSessionState,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.basket import BasketCloseReason
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.symbol_rules import SymbolRules


def test_configured_paper_futures_entry_and_replay_are_deterministic() -> None:
    candles = configured_entry_candles()

    first = replay(candles)
    second = replay(candles)

    assert first == second
    entry_snapshot = next(snapshot for snapshot in first if snapshot.entry_fill)
    assert entry_snapshot.capital_plan.trading_capital == Decimal("100000.0")
    assert entry_snapshot.capital_plan.collateral_buffer == Decimal("100000.0")
    assert entry_snapshot.capital_plan.initial_margin_per_entry == Decimal("10000.0")
    assert entry_snapshot.capital_plan.target_notional_per_entry == Decimal("30000.0")
    assert entry_snapshot.entry_fill is not None
    assert entry_snapshot.entry_fill.side is PositionSide.LONG


def test_configured_adverse_candle_terminates_session_with_liquidation() -> None:
    snapshots = replay(configured_liquidation_candles())

    snapshot = snapshots[-1]

    assert all(item.state is PaperFuturesSessionState.ACTIVE for item in snapshots[:-1])
    assert snapshots[-2].state is PaperFuturesSessionState.ACTIVE
    assert snapshot.accepted
    assert snapshot.exit_fill is not None
    assert snapshot.exit_fill.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.closed_basket is not None
    assert snapshot.closed_basket.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.state is PaperFuturesSessionState.LIQUIDATED


def replay(candles: list[Candle]) -> list[PaperFuturesSessionSnapshot]:
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    session = PaperFuturesSession(
        SessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000108"),
            preset_version="rsi-step-grid-v1",
            market_type=MarketType.FUTURES,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("200000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=10),
            spot_policy=None,
            futures_policy=FuturesTradingPolicy.v1(leverage=3),
        ),
        market_data,
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        RsiStepGridPreset.v1(),
    )
    return [
        session.process_completed_candle(current, received_at=current.close_time)
        for current in candles
    ]


def configured_entry_candles() -> list[Candle]:
    candles: list[Candle] = []
    close = Decimal("100")
    for index in range(15):
        candles.append(configured_candle(index, close=close))
        close -= Decimal("1")
    for index in range(15, 40):
        close += Decimal("1")
        candles.append(configured_candle(index, close=close))
    return candles


def configured_liquidation_candles() -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 7, 2, tzinfo=UTC)
    candle_count = int((end - start) / timedelta(minutes=5))
    candles: list[Candle] = []
    close = Decimal("100")
    direction = Decimal("-1")
    phase_count = 0

    for index in range(candle_count):
        close += direction
        candles.append(configured_candle(index, close=close, wide_range=True))
        phase_count += 1
        if phase_count == 15:
            direction = -direction
            phase_count = 0

    last = candles[-1]
    candles.append(
        Candle(
            symbol="BTCUSDT",
            timeframe="5m",
            open_time=last.close_time,
            open=last.close,
            high=Decimal("500"),
            low=Decimal("1"),
            close=last.close,
            volume=Decimal("1"),
        )
    )
    return candles


def configured_candle(
    index: int,
    *,
    close: Decimal,
    wide_range: bool = False,
) -> Candle:
    open_price = close - Decimal("0.5")
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5),
        open=open_price,
        high=Decimal("500") if wide_range else max(open_price, close) + Decimal("1"),
        low=Decimal("50") if wide_range else min(open_price, close) - Decimal("1"),
        close=close,
        volume=Decimal("1"),
    )
