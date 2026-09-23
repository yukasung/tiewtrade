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
