from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core._decimal import ZERO, calc
from tiewtrade_core.market import OrderSide

# Verify (C-01): Binance documents this buffer as 0.15%; older documents showed 0.05%.
MARKET_ORDER_PRICE_BUFFER = Decimal("0.0015")


@calc
def assuming_price(
    side: OrderSide,
    *,
    last_price: Decimal,
    mark_price: Decimal,
    limit_price: Decimal | None,
) -> Decimal:
    """Price Binance assumes when reserving margin for an order (calculation spec §2.2).

    Market orders pass ``limit_price=None``.
    """
    if limit_price is None:
        return last_price * (1 + MARKET_ORDER_PRICE_BUFFER)
    if side is OrderSide.BUY:
        return limit_price
    return max(last_price * (1 + MARKET_ORDER_PRICE_BUFFER), mark_price, limit_price)


@calc
def open_loss(
    side: OrderSide, quantity: Decimal, mark_price: Decimal, order_price: Decimal
) -> Decimal:
    """Open Loss = qty * |min(0, dir * (Mark Price - Order Price))| (calculation spec §2.2)."""
    return quantity * abs(min(ZERO, side.sign * (mark_price - order_price)))


@dataclass(frozen=True, slots=True)
class PendingOrder:
    """An open order of one symbol, valued for margin purposes."""

    side: OrderSide
    quantity: Decimal
    assuming_price: Decimal
    order_price: Decimal  # limit price, or the assuming price for a market order

    @property
    @calc
    def value(self) -> Decimal:
        return self.quantity * self.assuming_price


@calc
def margin_requirement(
    quantity: Decimal, mark_price: Decimal, leverage: int, orders: Iterable[PendingOrder]
) -> Decimal:
    """Combined margin requirement of one symbol (One-way), calculation spec §2.7:

    max(|Q*MP + BidValue|, |Q*MP - AskValue|) / L
    """
    bid_value = ZERO
    ask_value = ZERO
    for order in orders:
        if order.side is OrderSide.BUY:
            bid_value += order.value
        else:
            ask_value += order.value
    position_notional = quantity * mark_price
    return max(abs(position_notional + bid_value), abs(position_notional - ask_value)) / leverage


@calc
def order_margin(
    quantity: Decimal,
    mark_price: Decimal,
    leverage: int,
    existing_orders: Iterable[PendingOrder],
    new_order: PendingOrder,
) -> Decimal:
    """Margin a new order needs on top of what is already frozen (calculation spec §2.7).

    Orders that reduce the position therefore need zero additional margin.
    """
    existing = list(existing_orders)
    before = margin_requirement(quantity, mark_price, leverage, existing)
    after = margin_requirement(quantity, mark_price, leverage, [*existing, new_order])
    return max(ZERO, after - before) + open_loss(
        new_order.side, new_order.quantity, mark_price, new_order.order_price
    )


@calc
def frozen_margin(requirements: Iterable[Decimal], open_losses: Iterable[Decimal]) -> Decimal:
    return sum(requirements, ZERO) + sum(open_losses, ZERO)


@calc
def available_balance(
    cross_wallet_balance: Decimal, total_unrealized_pnl: Decimal, frozen: Decimal
) -> Decimal:
    """Available Balance for new cross orders (calculation spec §2.7).

    Until C-03 is verified, only losses count against the balance; unrealized profit is
    not usable margin.
    """
    usable_upnl = min(ZERO, total_unrealized_pnl)
    return max(ZERO, cross_wallet_balance + usable_upnl - frozen)
