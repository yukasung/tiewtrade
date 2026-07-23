from decimal import Decimal
from pathlib import Path
from uuid import UUID

from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.replay.csv_candles import load_candles_csv
from tiewtrade.replay.paper_spot import ReplayResult, run_paper_spot_replay
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "btcusdt_5m_tracer.csv"


def test_replaying_the_tracer_fixture_is_deterministic() -> None:
    first = replay_fixture()
    second = replay_fixture()

    assert first == second
    assert first.accepted_candles == 40
    assert first.current_entries == 0
    assert first.closed_baskets == 1
    assert first.realized_pnl == Decimal("13.84062222")
    assert first.to_json() == second.to_json()


def replay_fixture() -> ReplayResult:
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    return run_paper_spot_replay(
        load_candles_csv(FIXTURE_PATH, market_data),
        session=SessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000080"),
            preset_version="rsi-step-grid-v1",
            market_type=MarketType.SPOT,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("1000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=4),
            spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
        ),
        market_data=market_data,
        symbol_rules=SymbolRules(
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        preset=RsiStepGridPreset.v1(),
    )
