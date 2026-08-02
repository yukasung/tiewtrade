from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.trading.session_config import MarketType, TradeMode


class WorkspaceReadState(StrEnum):
    LOADING = "loading"
    EMPTY = "empty"
    READY = "ready"
    ERROR = "error"
    STALE = "stale"


class WorkspaceTabState(StrEnum):
    LOADING = "loading"
    EMPTY = "empty"
    READY = "ready"
    ERROR = "error"
    STALE = "stale"


class BotRuntimeState(StrEnum):
    NO_SESSION = "no_session"
    CONFIGURED = "configured"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    BLOCKED = "blocked"


class DataFreshness(StrEnum):
    NOT_STARTED = "not_started"
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


_SAFE_OPEN_ORDERS_TAB_MESSAGES = frozenset({"Open orders are unavailable"})
_SAFE_POSITION_BASKET_TAB_MESSAGES = frozenset(
    {"Position / Basket data is unavailable"}
)


@dataclass(frozen=True, slots=True)
class WorkspaceHeaderSnapshot:
    symbol: str
    timeframe: str
    trade_mode: TradeMode
    market_type: MarketType
    preset_version: str
    runtime_state: BotRuntimeState
    data_freshness: DataFreshness

    def __post_init__(self) -> None:
        _require_text(self.symbol, "symbol")
        _require_text(self.timeframe, "timeframe")
        _require_text(self.preset_version, "preset_version")
        if not isinstance(self.trade_mode, TradeMode):
            raise ValueError("trade_mode must be a TradeMode")
        if not isinstance(self.market_type, MarketType):
            raise ValueError("market_type must be a MarketType")
        if not isinstance(self.runtime_state, BotRuntimeState):
            raise ValueError("runtime_state must be a BotRuntimeState")
        if not isinstance(self.data_freshness, DataFreshness):
            raise ValueError("data_freshness must be a DataFreshness")


@dataclass(frozen=True, slots=True)
class OpenOrderSnapshot:
    order_id: str
    created_at_utc: datetime
    symbol: str
    side: str
    order_type: str
    price: Decimal | None
    quantity: Decimal
    filled_quantity: Decimal
    status: str

    def __post_init__(self) -> None:
        _require_text(self.order_id, "order_id")
        _require_utc(self.created_at_utc, "created_at_utc")
        _require_text(self.symbol, "symbol")
        _require_text(self.side, "side")
        _require_text(self.order_type, "order_type")
        _require_decimal(self.price, "price", allow_none=True)
        _require_non_negative_decimal(self.quantity, "quantity")
        _require_non_negative_decimal(self.filled_quantity, "filled_quantity")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity must not exceed quantity")
        _require_text(self.status, "status")


@dataclass(frozen=True, slots=True)
class BasketSnapshot:
    symbol: str
    market_type: str
    entry_count: int
    total_quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal
    take_profit_price: Decimal
    unrealized_pnl: Decimal
    liquidation_price: Decimal | None
    lifecycle: str
    updated_at_utc: datetime

    def __post_init__(self) -> None:
        _require_text(self.symbol, "symbol")
        _require_text(self.market_type, "market_type")
        if type(self.entry_count) is not int or self.entry_count < 0:
            raise ValueError("entry_count must be a non-negative integer")
        _require_non_negative_decimal(self.total_quantity, "total_quantity")
        _require_decimal(self.average_entry_price, "average_entry_price")
        _require_decimal(self.current_price, "current_price")
        _require_decimal(self.take_profit_price, "take_profit_price")
        _require_decimal(self.unrealized_pnl, "unrealized_pnl")
        _require_decimal(self.liquidation_price, "liquidation_price", allow_none=True)
        _require_text(self.lifecycle, "lifecycle")
        _require_utc(self.updated_at_utc, "updated_at_utc")


@dataclass(frozen=True, slots=True)
class OpenOrdersTabSnapshot:
    state: WorkspaceTabState
    orders: tuple[OpenOrderSnapshot, ...]
    data_as_of_utc: datetime | None
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, WorkspaceTabState):
            raise ValueError("state must be a WorkspaceTabState")
        if type(self.orders) is not tuple or not all(
            isinstance(order, OpenOrderSnapshot) for order in self.orders
        ):
            raise ValueError("orders must be a tuple of OpenOrderSnapshot")
        if self.data_as_of_utc is not None:
            _require_utc(self.data_as_of_utc, "data_as_of_utc")
        if self.message is not None:
            _require_text(self.message, "message")
        _require_unique_order_ids(self.orders)
        self._validate_state_combination()

    def _validate_state_combination(self) -> None:
        if self.state is WorkspaceTabState.EMPTY:
            if self.orders:
                raise ValueError("EMPTY tab must not contain durable data")
            if self.message is not None:
                raise ValueError("EMPTY tab must not contain a message")
        elif self.state is WorkspaceTabState.READY:
            if not self.orders:
                raise ValueError("READY tab requires durable data")
            if self.data_as_of_utc is None:
                raise ValueError("READY tab requires data_as_of_utc")
            if self.message is not None:
                raise ValueError("READY tab must not contain a message")
        elif self.state is WorkspaceTabState.LOADING:
            if self.message is not None:
                raise ValueError("LOADING tab must not contain a message")
        elif self.state is WorkspaceTabState.ERROR:
            if self.message is None:
                raise ValueError("ERROR tab requires a message")
            _require_sanitized_open_orders_message(self.message)
        elif self.state is WorkspaceTabState.STALE:
            if self.data_as_of_utc is None:
                raise ValueError("STALE tab requires data_as_of_utc")
            if self.message is not None:
                raise ValueError("STALE tab must not contain a message")


@dataclass(frozen=True, slots=True)
class PositionBasketTabSnapshot:
    state: WorkspaceTabState
    basket: BasketSnapshot | None
    data_as_of_utc: datetime | None
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, WorkspaceTabState):
            raise ValueError("state must be a WorkspaceTabState")
        if self.basket is not None and not isinstance(self.basket, BasketSnapshot):
            raise ValueError("basket must be a BasketSnapshot")
        if self.data_as_of_utc is not None:
            _require_utc(self.data_as_of_utc, "data_as_of_utc")
        if self.message is not None:
            _require_text(self.message, "message")
        self._validate_state_combination()

    def _validate_state_combination(self) -> None:
        if self.state is WorkspaceTabState.EMPTY:
            if self.basket is not None:
                raise ValueError("EMPTY tab must not contain durable data")
            if self.message is not None:
                raise ValueError("EMPTY tab must not contain a message")
        elif self.state is WorkspaceTabState.READY:
            if self.basket is None:
                raise ValueError("READY tab requires durable data")
            if self.data_as_of_utc is None:
                raise ValueError("READY tab requires data_as_of_utc")
            if self.message is not None:
                raise ValueError("READY tab must not contain a message")
        elif self.state is WorkspaceTabState.LOADING:
            if self.message is not None:
                raise ValueError("LOADING tab must not contain a message")
        elif self.state is WorkspaceTabState.ERROR:
            if self.message is None:
                raise ValueError("ERROR tab requires a message")
            _require_sanitized_position_basket_message(self.message)
        elif self.state is WorkspaceTabState.STALE:
            if self.data_as_of_utc is None:
                raise ValueError("STALE tab requires data_as_of_utc")
            if self.message is not None:
                raise ValueError("STALE tab must not contain a message")


@dataclass(frozen=True, slots=True)
class TradingWorkspaceSnapshot:
    read_state: WorkspaceReadState
    header: WorkspaceHeaderSnapshot | None
    open_orders: OpenOrdersTabSnapshot
    position_basket: PositionBasketTabSnapshot
    data_as_of_utc: datetime | None
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.read_state, WorkspaceReadState):
            raise ValueError("read_state must be a WorkspaceReadState")
        if self.header is not None and not isinstance(
            self.header, WorkspaceHeaderSnapshot
        ):
            raise ValueError("header must be a WorkspaceHeaderSnapshot")
        if not isinstance(self.open_orders, OpenOrdersTabSnapshot):
            raise ValueError("open_orders must be an OpenOrdersTabSnapshot")
        if not isinstance(self.position_basket, PositionBasketTabSnapshot):
            raise ValueError("position_basket must be a PositionBasketTabSnapshot")
        if self.data_as_of_utc is not None:
            _require_utc(self.data_as_of_utc, "data_as_of_utc")
        if self.message is not None:
            _require_text(self.message, "message")
        self._validate_state_combination()

    @property
    def orders(self) -> tuple[OpenOrderSnapshot, ...]:
        return self.open_orders.orders

    @property
    def basket(self) -> BasketSnapshot | None:
        return self.position_basket.basket

    def _validate_state_combination(self) -> None:
        if self.read_state is WorkspaceReadState.EMPTY:
            if self.header is not None or self.orders or self.basket is not None:
                raise ValueError("EMPTY snapshot must not contain durable data")
            if self.message is not None:
                raise ValueError("EMPTY snapshot must not contain a message")
        elif self.read_state is WorkspaceReadState.READY:
            if self.header is None:
                raise ValueError("READY snapshot requires a header")
            if self.data_as_of_utc is None:
                raise ValueError("READY snapshot requires data_as_of_utc")
            if self.header.data_freshness is DataFreshness.STALE:
                raise ValueError("READY snapshot must not have stale data")
            if self.message is not None:
                raise ValueError("READY snapshot must not contain a message")
        elif self.read_state is WorkspaceReadState.ERROR:
            if self.message is None:
                raise ValueError("ERROR snapshot requires a message")
        elif self.read_state is WorkspaceReadState.STALE:
            if self.header is None:
                raise ValueError("STALE snapshot requires a header")
            if self.data_as_of_utc is None:
                raise ValueError("STALE snapshot requires data_as_of_utc")
            if self.header.data_freshness is not DataFreshness.STALE:
                raise ValueError("STALE snapshot requires stale data freshness")
            if self.message is not None:
                raise ValueError("STALE snapshot must not contain a message")
        elif self.message is not None:
            raise ValueError("LOADING snapshot must not contain a message")


def empty_workspace_snapshot(
    *, observed_at_utc: datetime | None = None
) -> TradingWorkspaceSnapshot:
    return TradingWorkspaceSnapshot(
        read_state=WorkspaceReadState.EMPTY,
        header=None,
        open_orders=empty_open_orders_tab(),
        position_basket=empty_position_basket_tab(),
        data_as_of_utc=observed_at_utc,
    )


def configured_workspace_snapshot(
    session: ConfiguredPaperSession, *, observed_at_utc: datetime
) -> TradingWorkspaceSnapshot:
    return TradingWorkspaceSnapshot(
        read_state=WorkspaceReadState.READY,
        header=WorkspaceHeaderSnapshot(
            symbol=session.market_data.symbol,
            timeframe=session.market_data.timeframe,
            trade_mode=session.config.trade_mode,
            market_type=session.config.market_type,
            preset_version=session.config.preset_version,
            runtime_state=BotRuntimeState.CONFIGURED,
            data_freshness=DataFreshness.NOT_STARTED,
        ),
        open_orders=empty_open_orders_tab(),
        position_basket=empty_position_basket_tab(),
        data_as_of_utc=observed_at_utc,
    )


def loading_workspace_snapshot(
    last_known: TradingWorkspaceSnapshot,
) -> TradingWorkspaceSnapshot:
    return replace(last_known, read_state=WorkspaceReadState.LOADING, message=None)


def failed_workspace_snapshot(
    last_known: TradingWorkspaceSnapshot, message: str
) -> TradingWorkspaceSnapshot:
    return replace(last_known, read_state=WorkspaceReadState.ERROR, message=message)


def stale_workspace_snapshot(
    last_known: TradingWorkspaceSnapshot,
) -> TradingWorkspaceSnapshot:
    if last_known.header is None:
        raise ValueError("STALE snapshot requires a header")
    return replace(
        last_known,
        read_state=WorkspaceReadState.STALE,
        header=replace(last_known.header, data_freshness=DataFreshness.STALE),
        message=None,
    )


def empty_open_orders_tab() -> OpenOrdersTabSnapshot:
    return OpenOrdersTabSnapshot(
        state=WorkspaceTabState.EMPTY,
        orders=(),
        data_as_of_utc=None,
    )


def ready_open_orders_tab(
    orders: tuple[OpenOrderSnapshot, ...], *, observed_at_utc: datetime
) -> OpenOrdersTabSnapshot:
    _require_utc(observed_at_utc, "observed_at_utc")
    _require_unique_order_ids(orders)
    return OpenOrdersTabSnapshot(
        state=WorkspaceTabState.READY,
        orders=tuple(sorted(orders, key=_open_order_sort_key, reverse=True)),
        data_as_of_utc=observed_at_utc,
    )


def loading_open_orders_tab(
    last_known: OpenOrdersTabSnapshot,
) -> OpenOrdersTabSnapshot:
    _require_open_orders_tab(last_known, "last_known")
    return replace(last_known, state=WorkspaceTabState.LOADING, message=None)


def failed_open_orders_tab(
    last_known: OpenOrdersTabSnapshot, message: str
) -> OpenOrdersTabSnapshot:
    _require_open_orders_tab(last_known, "last_known")
    return replace(last_known, state=WorkspaceTabState.ERROR, message=message)


def stale_open_orders_tab(
    last_known: OpenOrdersTabSnapshot,
) -> OpenOrdersTabSnapshot:
    _require_open_orders_tab(last_known, "last_known")
    if last_known.data_as_of_utc is None:
        raise ValueError("STALE tab requires data_as_of_utc")
    return replace(last_known, state=WorkspaceTabState.STALE, message=None)


def empty_position_basket_tab() -> PositionBasketTabSnapshot:
    return PositionBasketTabSnapshot(
        state=WorkspaceTabState.EMPTY,
        basket=None,
        data_as_of_utc=None,
    )


def ready_position_basket_tab(
    basket: BasketSnapshot, *, observed_at_utc: datetime
) -> PositionBasketTabSnapshot:
    _require_utc(observed_at_utc, "observed_at_utc")
    return PositionBasketTabSnapshot(
        state=WorkspaceTabState.READY,
        basket=basket,
        data_as_of_utc=observed_at_utc,
    )


def loading_position_basket_tab(
    last_known: PositionBasketTabSnapshot,
) -> PositionBasketTabSnapshot:
    _require_position_basket_tab(last_known, "last_known")
    return replace(last_known, state=WorkspaceTabState.LOADING, message=None)


def failed_position_basket_tab(
    last_known: PositionBasketTabSnapshot, message: str
) -> PositionBasketTabSnapshot:
    _require_position_basket_tab(last_known, "last_known")
    return replace(last_known, state=WorkspaceTabState.ERROR, message=message)


def stale_position_basket_tab(
    last_known: PositionBasketTabSnapshot,
) -> PositionBasketTabSnapshot:
    _require_position_basket_tab(last_known, "last_known")
    if last_known.data_as_of_utc is None:
        raise ValueError("STALE tab requires data_as_of_utc")
    return replace(last_known, state=WorkspaceTabState.STALE, message=None)


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_utc(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must use UTC")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must use UTC")


def _require_decimal(
    value: Decimal | None, name: str, *, allow_none: bool = False
) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, Decimal):
        raise ValueError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")


def _require_non_negative_decimal(value: Decimal, name: str) -> None:
    _require_decimal(value, name)
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _require_unique_order_ids(orders: tuple[OpenOrderSnapshot, ...]) -> None:
    order_ids = tuple(order.order_id for order in orders)
    if len(order_ids) != len(set(order_ids)):
        raise ValueError("order_id must be unique")


def _open_order_sort_key(order: OpenOrderSnapshot) -> tuple[datetime, str]:
    return order.created_at_utc, order.order_id


def _require_open_orders_tab(value: object, name: str) -> None:
    if not isinstance(value, OpenOrdersTabSnapshot):
        raise ValueError(f"{name} must be an OpenOrdersTabSnapshot")


def _require_position_basket_tab(value: object, name: str) -> None:
    if not isinstance(value, PositionBasketTabSnapshot):
        raise ValueError(f"{name} must be a PositionBasketTabSnapshot")


def _require_sanitized_open_orders_message(message: str) -> None:
    if message not in _SAFE_OPEN_ORDERS_TAB_MESSAGES:
        raise ValueError("message must be sanitized")


def _require_sanitized_position_basket_message(message: str) -> None:
    if message not in _SAFE_POSITION_BASKET_TAB_MESSAGES:
        raise ValueError("message must be sanitized")
