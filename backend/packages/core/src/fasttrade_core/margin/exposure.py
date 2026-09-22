from dataclasses import dataclass
from decimal import Decimal

from fasttrade_core._decimal import calc
from fasttrade_core.market import LeverageBrackets


@dataclass(frozen=True, slots=True)
class FuturesExposure:
    """An open USDⓈ-M position valued at the current Mark Price (calculation spec §2.1-§2.3).

    ``quantity`` is signed: positive Long, negative Short.
    """

    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    leverage: int
    brackets: LeverageBrackets

    def __post_init__(self) -> None:
        if self.leverage < 1:
            raise ValueError("leverage must be at least 1")
        if self.mark_price <= 0 or self.entry_price <= 0:
            raise ValueError("prices must be positive")

    @property
    @calc
    def notional(self) -> Decimal:
        return abs(self.quantity) * self.mark_price

    @property
    @calc
    def unrealized_pnl(self) -> Decimal:
        return self.quantity * (self.mark_price - self.entry_price)

    @property
    @calc
    def initial_margin(self) -> Decimal:
        # Verify (calculation spec §2.2): Binance displays position margin using Mark Price.
        return self.notional / self.leverage

    @property
    @calc
    def maintenance_margin(self) -> Decimal:
        return self.brackets.maintenance_margin(self.notional)
