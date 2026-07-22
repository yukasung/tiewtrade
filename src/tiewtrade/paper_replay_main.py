import argparse
import sys
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.replay.csv_candles import load_candles_csv
from tiewtrade.replay.paper_spot import run_paper_spot_replay
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules

_SESSION_ID = UUID("00000000-0000-0000-0000-000000000080")
_ACCOUNT_PROFILE_ID = UUID("00000000-0000-0000-0000-000000000001")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        market_data = MarketDataConfig(
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
        )
        preset = RsiStepGridPreset.v1()
        session = SessionConfig(
            session_id=_SESSION_ID,
            account_profile_id=_ACCOUNT_PROFILE_ID,
            preset_version=preset.version,
            market_type=MarketType.SPOT,
            trade_mode=TradeMode.PAPER,
            available_capital=arguments.available_capital,
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=arguments.max_entries),
            spot_policy=SpotTradingPolicy(
                trading_capital_ratio=arguments.trading_capital_ratio
            ),
        )
        result = run_paper_spot_replay(
            load_candles_csv(arguments.csv_path, market_data),
            session=session,
            market_data=market_data,
            symbol_rules=SymbolRules(
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.001"),
                min_notional=Decimal("5"),
            ),
            preset=preset,
        )
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(result.to_json())
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--available-capital", required=True, type=Decimal)
    parser.add_argument("--trading-capital-ratio", required=True, type=Decimal)
    parser.add_argument("--max-entries", required=True, type=int)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
