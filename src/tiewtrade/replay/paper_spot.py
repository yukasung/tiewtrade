import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.application.paper_spot_session import PaperSpotSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.session_config import SessionConfig
from tiewtrade.trading.symbol_rules import SymbolRules


@dataclass(frozen=True, slots=True)
class ReplayResult:
    accepted_candles: int
    current_entries: int
    closed_baskets: int
    realized_pnl: Decimal

    def to_json(self) -> str:
        return json.dumps(
            {
                "accepted_candles": self.accepted_candles,
                "closed_baskets": self.closed_baskets,
                "current_entries": self.current_entries,
                "realized_pnl": format(self.realized_pnl, "f"),
            },
            separators=(",", ":"),
        )


def run_paper_spot_replay(
    candles: Iterable[Candle],
    *,
    session: SessionConfig,
    market_data: MarketDataConfig,
    symbol_rules: SymbolRules,
    preset: RsiStepGridPreset,
) -> ReplayResult:
    paper_session = PaperSpotSession(session, market_data, symbol_rules, preset)
    accepted_candles = 0
    realized_pnl = Decimal("0")
    current_entries = 0
    closed_baskets = 0

    for candle in candles:
        snapshot = paper_session.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )
        if not snapshot.accepted:
            raise ValueError("rejected candle during replay")

        accepted_candles += 1
        current_entries = snapshot.basket_entry_count
        closed_baskets = snapshot.closed_basket_count
        if snapshot.closed_basket is not None:
            realized_pnl += snapshot.closed_basket.realized_pnl

    if accepted_candles == 0:
        raise ValueError("replay requires at least one candle")

    return ReplayResult(
        accepted_candles=accepted_candles,
        current_entries=current_entries,
        closed_baskets=closed_baskets,
        realized_pnl=realized_pnl,
    )
