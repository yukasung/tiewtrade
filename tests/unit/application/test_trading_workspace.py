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
    TradingWorkspaceSnapshot,
    WorkspaceHeaderSnapshot,
    WorkspaceReadState,
    configured_workspace_snapshot,
    empty_workspace_snapshot,
    failed_workspace_snapshot,
    loading_workspace_snapshot,
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
    assert stale.header == replace(
        ready.header, data_freshness=DataFreshness.STALE
    )
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
            orders=(),
            basket=None,
            data_as_of_utc=_utc(),
        )
    with pytest.raises(
        ValueError, match="EMPTY snapshot must not contain durable data"
    ):
        TradingWorkspaceSnapshot(
            read_state=WorkspaceReadState.EMPTY,
            header=_header(),
            orders=(),
            basket=None,
            data_as_of_utc=None,
        )
    with pytest.raises(ValueError, match="STALE snapshot requires data_as_of_utc"):
        TradingWorkspaceSnapshot(
            read_state=WorkspaceReadState.STALE,
            header=replace(_header(), data_freshness=DataFreshness.STALE),
            orders=(),
            basket=None,
            data_as_of_utc=None,
        )
    with pytest.raises(ValueError, match="READY snapshot must not have stale data"):
        TradingWorkspaceSnapshot(
            read_state=WorkspaceReadState.READY,
            header=replace(_header(), data_freshness=DataFreshness.STALE),
            orders=(),
            basket=None,
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


def _order(created_at: datetime) -> OpenOrderSnapshot:
    return OpenOrderSnapshot(
        order_id="order-1",
        created_at_utc=created_at,
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        price=Decimal("66321.1200"),
        quantity=Decimal("0.00300000"),
        filled_quantity=Decimal("0.00100000"),
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


def _utc() -> datetime:
    return datetime(2026, 8, 1, 12, tzinfo=UTC)
