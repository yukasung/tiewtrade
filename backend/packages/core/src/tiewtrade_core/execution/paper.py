from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade_core.execution.book import TopOfBook
from tiewtrade_core.execution.fills import (
    PaperFill,
    limit_fill_on_submit,
    market_fill,
    resting_limit_fill,
)
from tiewtrade_core.execution.report import ExecutionReport, ReportKind
from tiewtrade_core.orders import Order, OrderStatus, OrderType

ReportSink = Callable[[ExecutionReport], None]


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """The market data a Paper fill needs for one symbol (FR-ORD-13).

    Supplied by the caller, never fetched: the core reads nothing. ``tick_size`` comes from
    the symbol's filters and decides the grid a fill price must sit on.
    """

    book: TopOfBook
    last_price: Decimal
    tick_size: Decimal

    def __post_init__(self) -> None:
        if self.last_price <= 0:
            raise ValueError("last price must be positive")
        if self.tick_size <= 0:
            raise ValueError("tick size must be positive")


class PaperExecutionAdapter:
    """Implements ``ExecutionAdapter`` with the Paper Fill Model (D-05, architecture §4.2).

    It holds no orders. The engine already owns them — they are rows in ``orders`` with an
    open status (data model §6.5) — and a second copy here would be a second truth that a
    restart would lose, which Paper replay could not reconstruct (architecture §7.5). The
    engine passes an order back in when its symbol moves.

    Market data arrives through ``update_market`` rather than as a method parameter, so the
    adapter satisfies the port's ``submit(order) -> None`` signature without the port having
    to carry something Live would never use — Binance prices its own fills.

    Reports go to the ``sink`` given at construction. Paper calls it before ``submit``
    returns, because Paper computes the outcome synchronously inside the engine's
    transaction (architecture §7.1); Live delivers the same report shape later from the User
    Data Stream. The engine applies either with ``Order.apply_fill``, ``accept`` or
    ``reject``, never learning which side it is on (P-03, P-04).
    """

    def __init__(self, sink: ReportSink, *, slippage_rate: Decimal) -> None:
        self._sink = sink
        self._slippage_rate = slippage_rate
        self._markets: dict[str, MarketSnapshot] = {}

    def update_market(self, symbol: str, snapshot: MarketSnapshot) -> None:
        """Record the latest prices for a symbol. The engine calls this as data arrives."""
        self._markets[symbol] = snapshot

    def submit(self, order: Order) -> None:
        """Price an order the moment it is sent (calculation spec §4.1, §4.2).

        A market order always fills. A limit order fills at once when it is marketable and
        otherwise is only acknowledged, resting until a price goes through it. Conditional
        types rest until their trigger fires, which the Order Manager drives.

        Calling this again with the same order is safe, as the port requires (NFR-05).
        Only an order the venue has not seen yet — ``PENDING_NEW`` — is priced. A retry
        after a timeout carries an order the engine has already acknowledged, and pricing
        it again would invent a second fill at whatever the price has since become. The
        order's own status is the venue state under Paper, so no second record is needed
        here (C-20).
        """
        if order.status.is_terminal:
            raise ValueError(f"cannot submit an order that is already {order.status}")
        if order.status is not OrderStatus.PENDING_NEW:
            return  # already at the venue; a retry must not fill it twice

        market = self._market(order.symbol)
        fill = self._fill_on_submit(order, market)
        if fill is None:
            self._emit(order.client_order_id, ReportKind.ACCEPTED)
            return
        self._emit_fill(order, fill)

    def on_price(self, order: Order) -> None:
        """Re-price a resting order against the current market (calculation spec §4.2).

        Called for each open order when its symbol's price changes. A resting limit fills
        only when the last price goes **through** it; touching does nothing, so the engine
        can call this on every tick without side effects.
        """
        if not order.is_open:
            raise ValueError("only an open order can be re-priced")
        if order.order_type is not OrderType.LIMIT or order.price is None:
            return

        market = self._market(order.symbol)
        fill = resting_limit_fill(order.side, order.price, market.last_price)
        if fill is not None:
            self._emit_fill(order, fill)

    def cancel(self, client_order_id: str) -> None:
        """Cancel a resting order. Paper always succeeds: there is no venue to refuse."""
        self._emit(client_order_id, ReportKind.CANCELED)

    def _market(self, symbol: str) -> MarketSnapshot:
        snapshot = self._markets.get(symbol)
        if snapshot is None:
            raise ValueError(f"no market data for {symbol}")
        return snapshot

    def _fill_on_submit(self, order: Order, market: MarketSnapshot) -> PaperFill | None:
        """The fill an order gets the moment it is sent, or None when it rests instead.

        Both reasons to rest look the same to the caller and are treated the same: a limit
        that is not marketable (§4.2), and a conditional type that waits for its trigger.
        """
        if order.order_type is OrderType.MARKET:
            return market_fill(
                order.side,
                market.book,
                slippage_rate=self._slippage_rate,
                tick_size=market.tick_size,
            )
        if order.order_type is OrderType.LIMIT:
            if order.price is None:
                raise ValueError("a limit order must carry a price")
            return limit_fill_on_submit(
                order.side,
                order.price,
                market.book,
                slippage_rate=self._slippage_rate,
                tick_size=market.tick_size,
            )
        return None

    def _emit(self, client_order_id: str, kind: ReportKind) -> None:
        self._sink(ExecutionReport(client_order_id=client_order_id, kind=kind))

    def _emit_fill(self, order: Order, fill: PaperFill) -> None:
        """Report a fill for the whole remaining quantity: Paper never splits one (FR-ORD-09)."""
        self._sink(
            ExecutionReport(
                client_order_id=order.client_order_id,
                kind=ReportKind.FILLED,
                quantity=order.remaining_quantity,
                price=fill.price,
                liquidity=fill.liquidity,
            )
        )
