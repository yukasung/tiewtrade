from enum import StrEnum


class Venue(StrEnum):
    BINANCE_COM = "BINANCE_COM"
    BINANCE_TH = "BINANCE_TH"


class MarketType(StrEnum):
    SPOT = "SPOT"
    USDM_FUTURES = "USDM_FUTURES"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def sign(self) -> int:
        """+1 for BUY, -1 for SELL (signed quantity convention, calculation spec §1)."""
        return 1 if self is OrderSide.BUY else -1


class MarginMode(StrEnum):
    CROSS = "CROSS"
    ISOLATED = "ISOLATED"


class LiquidityRole(StrEnum):
    """Which side of the book a fill took, selecting the fee rate (calculation spec §1, §2.8).

    Paper derives it from the Fill Model (§4.2); Live takes it from what Binance reports.
    """

    MAKER = "MAKER"
    TAKER = "TAKER"


class TradingMode(StrEnum):
    """Paper or Live (FR-ACC-04).

    An attribute of the Exchange Account that a Portfolio inherits and can never change.
    The Workspace notional limit is counted per mode, so the two never share a budget
    (FR-PLN-04).
    """

    PAPER = "PAPER"
    LIVE = "LIVE"
