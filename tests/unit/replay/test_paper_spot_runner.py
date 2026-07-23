from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.replay.paper_spot import ReplayResult, run_paper_spot_replay
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules


def test_replay_result_serializes_a_stable_compact_json_summary() -> None:
    result = ReplayResult(40, 0, 1, Decimal("13.84062222"))

    assert result.to_json() == (
        '{"accepted_candles":40,"closed_baskets":1,'
        '"current_entries":0,"realized_pnl":"13.84062222"}'
    )


def test_replay_rejects_a_candle_that_the_session_does_not_accept() -> None:
    candle = Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("101"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("100"),
        volume=Decimal("1"),
    )

    with pytest.raises(ValueError, match="rejected candle"):
        run_paper_spot_replay(
            (candle, candle),
            session=session_config(),
            market_data=MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
            symbol_rules=symbol_rules(),
            preset=RsiStepGridPreset.v1(),
        )


def test_replay_rejects_an_empty_iterable() -> None:
    with pytest.raises(ValueError, match="at least one candle"):
        run_paper_spot_replay(
            (),
            session=session_config(),
            market_data=MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
            symbol_rules=symbol_rules(),
            preset=RsiStepGridPreset.v1(),
        )


def session_config() -> SessionConfig:
    return SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000080"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("2"),
        entry_policy=EntryPolicy(max_entries=4),
        spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
    )


def symbol_rules() -> SymbolRules:
    return SymbolRules(
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )
