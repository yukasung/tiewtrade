from enum import StrEnum


class OrderType(StrEnum):
    """Order types the platform sends (data model §6.5)."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"

    @property
    def needs_price(self) -> bool:
        """Only a LIMIT order carries a limit price."""
        return self is OrderType.LIMIT

    @property
    def needs_stop_price(self) -> bool:
        """The conditional types carry a trigger price."""
        return self in (OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET)


class TimeInForce(StrEnum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class OwnerType(StrEnum):
    """Who created the order (D-02, D-14).

    ``EXTERNAL`` is an order the user placed on Binance directly. It is recognised by the
    absence of a platform Client Order ID and is recorded so balances and PnL match the
    exchange (FR-LIVE-06).
    """

    BOT = "BOT"
    MANUAL = "MANUAL"
    EXTERNAL = "EXTERNAL"


class BracketRole(StrEnum):
    """The leg an order plays inside a Bracket (FR-ORD-14, FR-ORD-15)."""

    ENTRY = "ENTRY"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"


class OrderStatus(StrEnum):
    """Lifecycle of an order (FR-ORD-03, data model §6.5).

    ``PENDING_NEW`` is recorded before the venue confirms anything, so a timeout can be
    resolved by querying the Client Order ID rather than blindly retrying (FR-LIVE-07).
    """

    PENDING_NEW = "PENDING_NEW"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

    @property
    def is_open(self) -> bool:
        """Whether the order can still fill; matches the ``orders_open`` index."""
        return self in _OPEN

    @property
    def is_terminal(self) -> bool:
        """Whether the order is finished and can no longer change."""
        return self not in _OPEN


_OPEN = frozenset({OrderStatus.PENDING_NEW, OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED})
