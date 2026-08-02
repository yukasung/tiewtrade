from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.support.dataclass_validation import replace_unchecked
from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    BotRuntimeState,
    DataFreshness,
    OpenOrderSnapshot,
    OpenOrdersTabSnapshot,
    PositionBasketTabSnapshot,
    TradingWorkspaceSnapshot,
    WorkspaceHeaderSnapshot,
    WorkspaceReadState,
    WorkspaceTabState,
    configured_workspace_snapshot,
    empty_open_orders_tab,
    empty_position_basket_tab,
    empty_workspace_snapshot,
    failed_open_orders_tab,
    failed_position_basket_tab,
    failed_workspace_snapshot,
    loading_open_orders_tab,
    loading_position_basket_tab,
    loading_workspace_snapshot,
    ready_open_orders_tab,
    ready_position_basket_tab,
    stale_open_orders_tab,
    stale_position_basket_tab,
    stale_workspace_snapshot,
)


def test_configured_snapshot_exposes_exact_header_facts() -> None:
    session = configured_spot_session()
    observed_at = datetime(2026, 8, 1, 12, tzinfo=UTC)

    snapshot = configured_workspace_snapshot(session, observed_at_utc=observed_at)

    assert snapshot.read_state is WorkspaceReadState.READY
    assert snapshot.header is not None
    assert snapshot.header.symbol == "BTCUSDT"
    assert snapshot.header.timeframe == "5m"
    assert snapshot.header.trade_mode.value == "paper"
    assert snapshot.header.market_type.value == "spot"
    assert snapshot.header.runtime_state is BotRuntimeState.CONFIGURED
    assert snapshot.header.data_freshness is DataFreshness.NOT_STARTED
    assert snapshot.data_as_of_utc is observed_at


def test_decimal_and_utc_order_and_basket_facts_remain_exact() -> None:
    created_at = datetime(2026, 8, 1, 12, tzinfo=UTC)
    order = _order(created_at)
    basket = _basket(created_at)

    assert type(order.price) is Decimal
    assert type(basket.unrealized_pnl) is Decimal
    assert order.created_at_utc is created_at
    assert basket.updated_at_utc is created_at
    with pytest.raises(FrozenInstanceError):
        order.status = "FILLED"  # type: ignore[misc]


def test_loading_error_and_stale_preserve_last_known_durable_data() -> None:
    ready = configured_workspace_snapshot(
        configured_spot_session(),
        observed_at_utc=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )

    loading = loading_workspace_snapshot(ready)
    failed = failed_workspace_snapshot(ready, "Workspace data is unavailable")
    stale = stale_workspace_snapshot(ready)
    assert ready.header is not None

    for snapshot in (loading, failed):
        assert snapshot.header == ready.header
        assert snapshot.orders == ready.orders
        assert snapshot.basket == ready.basket
        assert snapshot.data_as_of_utc == ready.data_as_of_utc
    assert stale.header == replace(ready.header, data_freshness=DataFreshness.STALE)
    assert stale.orders == ready.orders
    assert stale.basket == ready.basket
    assert stale.data_as_of_utc == ready.data_as_of_utc
    assert loading.read_state is WorkspaceReadState.LOADING
    assert failed.read_state is WorkspaceReadState.ERROR
    assert stale.read_state is WorkspaceReadState.STALE
    assert stale.header is not None
    assert stale.header.data_freshness is DataFreshness.STALE


@pytest.mark.parametrize(
    ("factory", "expected"),
    [
        (
            lambda: _order(datetime(2026, 8, 1, 12)),
            "created_at_utc must use UTC",
        ),
        (
            lambda: _basket(
                datetime(2026, 8, 1, 12, tzinfo=timezone(timedelta(hours=7)))
            ),
            "updated_at_utc must use UTC",
        ),
        (
            lambda: replace_unchecked(_order(_utc()), price=1),
            "price must be a Decimal",
        ),
        (
            lambda: replace_unchecked(_basket(_utc()), unrealized_pnl=1),
            "unrealized_pnl must be a Decimal",
        ),
        (lambda: replace(_order(_utc()), quantity=Decimal("-1")), "quantity"),
        (lambda: replace(_basket(_utc()), entry_count=-1), "entry_count"),
        (lambda: replace(_order(_utc()), order_id=""), "order_id must not be empty"),
        (lambda: replace(_basket(_utc()), lifecycle=""), "lifecycle must not be empty"),
    ],
)
def test_snapshot_facts_reject_invalid_values(
    factory: Callable[[], object], expected: str
) -> None:
    with pytest.raises(ValueError, match=expected):
        factory()


def test_workspace_rejects_invalid_state_combinations() -> None:
    with pytest.raises(ValueError, match="READY snapshot requires a header"):
        TradingWorkspaceSnapshot(
            read_state=WorkspaceReadState.READY,
            header=None,
            open_orders=empty_open_orders_tab(),
            position_basket=empty_position_basket_tab(),
            data_as_of_utc=_utc(),
        )
    with pytest.raises(
        ValueError, match="EMPTY snapshot must not contain durable data"
    ):
        TradingWorkspaceSnapshot(
            read_state=WorkspaceReadState.EMPTY,
            header=_header(),
            open_orders=empty_open_orders_tab(),
            position_basket=empty_position_basket_tab(),
            data_as_of_utc=None,
        )
    with pytest.raises(ValueError, match="STALE snapshot requires data_as_of_utc"):
        TradingWorkspaceSnapshot(
            read_state=WorkspaceReadState.STALE,
            header=replace(_header(), data_freshness=DataFreshness.STALE),
            open_orders=empty_open_orders_tab(),
            position_basket=empty_position_basket_tab(),
            data_as_of_utc=None,
        )
    with pytest.raises(ValueError, match="READY snapshot must not have stale data"):
        TradingWorkspaceSnapshot(
            read_state=WorkspaceReadState.READY,
            header=replace(_header(), data_freshness=DataFreshness.STALE),
            open_orders=empty_open_orders_tab(),
            position_basket=empty_position_basket_tab(),
            data_as_of_utc=_utc(),
        )


def test_empty_and_loading_snapshots_can_honestly_represent_no_session() -> None:
    observed_at = _utc()

    empty = empty_workspace_snapshot(observed_at_utc=observed_at)
    loading = loading_workspace_snapshot(empty)

    assert empty.read_state is WorkspaceReadState.EMPTY
    assert empty.header is None
    assert empty.data_as_of_utc is observed_at
    assert loading.read_state is WorkspaceReadState.LOADING
    assert loading.header is None
    assert loading.data_as_of_utc is observed_at


def test_open_orders_tab_aggregates_one_row_per_order_and_sorts_latest_first() -> None:
    older = _order(_utc(minute=1), order_id="order-1", filled="0.001")
    newer = _order(_utc(minute=2), order_id="order-2", filled="0.002")

    tab = ready_open_orders_tab((older, newer), observed_at_utc=_utc(minute=3))

    assert tab.state is WorkspaceTabState.READY
    assert tuple(item.order_id for item in tab.orders) == ("order-2", "order-1")


def test_open_orders_tab_rejects_duplicate_order_rows_and_overfill() -> None:
    order = _order(_utc(), order_id="order-1", filled="0.003")

    with pytest.raises(ValueError, match="order_id must be unique"):
        ready_open_orders_tab((order, order), observed_at_utc=_utc(minute=1))
    with pytest.raises(ValueError, match="filled_quantity must not exceed quantity"):
        replace(order, filled_quantity=Decimal("0.004"))


def test_orders_and_position_tabs_transition_independently() -> None:
    orders = ready_open_orders_tab((_order(_utc()),), observed_at_utc=_utc())
    position = ready_position_basket_tab(_basket(_utc()), observed_at_utc=_utc())

    snapshot = replace(
        configured_workspace_snapshot(
            configured_spot_session(), observed_at_utc=_utc()
        ),
        open_orders=loading_open_orders_tab(orders),
        position_basket=stale_position_basket_tab(position),
    )

    assert snapshot.open_orders.state is WorkspaceTabState.LOADING
    assert snapshot.position_basket.state is WorkspaceTabState.STALE
    assert snapshot.orders == orders.orders
    assert snapshot.basket == position.basket


def test_workspace_compatibility_properties_expose_scoped_tab_data() -> None:
    workspace = configured_workspace_snapshot(
        configured_spot_session(), observed_at_utc=_utc()
    )
    order = _order(_utc())
    basket = _basket(_utc())

    updated = replace(
        workspace,
        open_orders=ready_open_orders_tab((order,), observed_at_utc=_utc()),
        position_basket=ready_position_basket_tab(basket, observed_at_utc=_utc()),
    )
    cleared = replace(
        updated,
        open_orders=empty_open_orders_tab(),
        position_basket=empty_position_basket_tab(),
    )

    assert updated.orders == (order,)
    assert updated.basket is basket
    assert cleared.orders == ()
    assert cleared.basket is None


def test_open_orders_tab_helpers_preserve_last_known_rows_by_state() -> None:
    ready = ready_open_orders_tab((_order(_utc()),), observed_at_utc=_utc())

    assert empty_open_orders_tab() == OpenOrdersTabSnapshot(
        state=WorkspaceTabState.EMPTY,
        orders=(),
        data_as_of_utc=None,
    )
    assert loading_open_orders_tab(ready).orders == ready.orders
    assert failed_open_orders_tab(ready, "Open orders are unavailable").message == (
        "Open orders are unavailable"
    )
    assert stale_open_orders_tab(ready).data_as_of_utc == ready.data_as_of_utc


def test_position_basket_tab_helpers_preserve_last_known_basket_by_state() -> None:
    ready = ready_position_basket_tab(_basket(_utc()), observed_at_utc=_utc())

    assert empty_position_basket_tab() == PositionBasketTabSnapshot(
        state=WorkspaceTabState.EMPTY,
        basket=None,
        data_as_of_utc=None,
    )
    assert loading_position_basket_tab(ready).basket is ready.basket
    assert (
        failed_position_basket_tab(
            ready, "Position / Basket data is unavailable"
        ).message
        == "Position / Basket data is unavailable"
    )
    assert stale_position_basket_tab(ready).data_as_of_utc == ready.data_as_of_utc


def test_failed_tabs_reject_raw_backend_messages_and_accept_safe_display_copy() -> None:
    open_orders = ready_open_orders_tab((_order(_utc()),), observed_at_utc=_utc())
    position_basket = ready_position_basket_tab(_basket(_utc()), observed_at_utc=_utc())

    assert (
        failed_open_orders_tab(open_orders, "Open orders are unavailable").message
        == "Open orders are unavailable"
    )
    assert (
        failed_position_basket_tab(
            position_basket, "Position / Basket data is unavailable"
        ).message
        == "Position / Basket data is unavailable"
    )
    with pytest.raises(ValueError, match="message must be sanitized"):
        failed_open_orders_tab(open_orders, "RuntimeError: api_key=secret")
    with pytest.raises(ValueError, match="message must be sanitized"):
        failed_position_basket_tab(position_basket, "sqlite failure at /private/tmp")


@pytest.mark.parametrize(
    ("factory", "expected"),
    [
        (
            lambda: OpenOrdersTabSnapshot(
                state=WorkspaceTabState.EMPTY,
                orders=(_order(_utc()),),
                data_as_of_utc=None,
            ),
            "EMPTY tab must not contain durable data",
        ),
        (
            lambda: OpenOrdersTabSnapshot(
                state=WorkspaceTabState.READY,
                orders=(_order(_utc()),),
                data_as_of_utc=None,
            ),
            "READY tab requires data_as_of_utc",
        ),
        (
            lambda: OpenOrdersTabSnapshot(
                state=WorkspaceTabState.LOADING,
                orders=(),
                data_as_of_utc=None,
                message="loading",
            ),
            "LOADING tab must not contain a message",
        ),
        (
            lambda: PositionBasketTabSnapshot(
                state=WorkspaceTabState.ERROR,
                basket=None,
                data_as_of_utc=None,
            ),
            "ERROR tab requires a message",
        ),
        (
            lambda: PositionBasketTabSnapshot(
                state=WorkspaceTabState.STALE,
                basket=_basket(_utc()),
                data_as_of_utc=None,
            ),
            "STALE tab requires data_as_of_utc",
        ),
    ],
)
def test_tab_snapshots_reject_invalid_state_combinations(
    factory: Callable[[], object], expected: str
) -> None:
    with pytest.raises(ValueError, match=expected):
        factory()


def _order(
    created_at: datetime,
    *,
    order_id: str = "order-1",
    filled: str = "0.00100000",
) -> OpenOrderSnapshot:
    return OpenOrderSnapshot(
        order_id=order_id,
        created_at_utc=created_at,
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        price=Decimal("66321.1200"),
        quantity=Decimal("0.00300000"),
        filled_quantity=Decimal(filled),
        status="PARTIALLY_FILLED",
    )


def _basket(updated_at: datetime) -> BasketSnapshot:
    return BasketSnapshot(
        symbol="BTCUSDT",
        market_type="spot",
        entry_count=2,
        total_quantity=Decimal("0.00600000"),
        average_entry_price=Decimal("66000.1250"),
        current_price=Decimal("66321.1200"),
        take_profit_price=Decimal("67000.0000"),
        unrealized_pnl=Decimal("1.92600000"),
        liquidation_price=None,
        lifecycle="ACTIVE_PAIR",
        updated_at_utc=updated_at,
    )


def _header() -> WorkspaceHeaderSnapshot:
    snapshot = configured_workspace_snapshot(
        configured_spot_session(), observed_at_utc=_utc()
    )
    assert snapshot.header is not None
    return snapshot.header


def _utc(*, minute: int = 0) -> datetime:
    return datetime(2026, 8, 1, 12, minute, tzinfo=UTC)
