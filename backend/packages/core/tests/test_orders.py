from decimal import Context, Inexact, Rounded, localcontext
from decimal import Decimal as D

import pytest

from tiewtrade_core.execution import ExecutionAdapter
from tiewtrade_core.market import OrderSide
from tiewtrade_core.orders import (
    MAX_LENGTH,
    Order,
    OrderIntent,
    OrderStatus,
    OrderType,
    OwnerType,
    TimeInForce,
    build_client_order_id,
    is_platform_client_order_id,
    order_from_intent,
)

BUY, SELL = OrderSide.BUY, OrderSide.SELL
PREFIX = "tt1"


def limit_intent(**changes: object) -> OrderIntent:
    fields: dict[str, object] = {
        "symbol": "BTCUSDT",
        "side": BUY,
        "order_type": OrderType.LIMIT,
        "quantity": D("0.5"),
        "price": D("60000.0"),
    }
    fields.update(changes)
    return OrderIntent(**fields)  # type: ignore[arg-type]


def order(**changes: object) -> Order:
    fields: dict[str, object] = {
        "client_order_id": "tt1-p1-1",
        "symbol": "BTCUSDT",
        "side": BUY,
        "order_type": OrderType.LIMIT,
        "quantity": D("0.5"),
        "owner_type": OwnerType.MANUAL,
        "price": D("60000.0"),
    }
    fields.update(changes)
    return Order(**fields)  # type: ignore[arg-type]


# --- Client Order ID (architecture §4.4) --------------------------------


def test_client_order_id_is_built_from_the_callers_parts() -> None:
    assert build_client_order_id(PREFIX, "p1", 1) == "tt1-p1-1"


def test_the_same_inputs_always_give_the_same_id() -> None:
    """The core invents no ids and reads no clock, so a retry rebuilds the same id (NFR-05)."""
    assert build_client_order_id(PREFIX, "abc", 42) == build_client_order_id(PREFIX, "abc", 42)


@pytest.mark.parametrize(
    ("prefix", "portfolio_ref", "sequence", "message"),
    [
        (PREFIX, "p1", -1, "sequence"),
        ("", "p1", 1, "prefix"),
        (PREFIX, "", 1, "portfolio_ref"),
        (PREFIX, "p-1", 1, "portfolio_ref"),  # the separator may not appear inside a part
        ("tt 1", "p1", 1, "prefix"),
    ],
)
def test_malformed_parts_are_rejected(
    prefix: str, portfolio_ref: str, sequence: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_client_order_id(prefix, portfolio_ref, sequence)


def test_an_id_longer_than_the_venue_allows_is_rejected() -> None:
    with pytest.raises(ValueError, match=f"exceeds {MAX_LENGTH}"):
        build_client_order_id(PREFIX, "p" * MAX_LENGTH, 1)


@pytest.mark.parametrize(
    ("client_order_id", "ours"),
    [
        ("tt1-p1-1", True),
        ("tt1-portfolio_9-1234", True),
        ("x-p1-1", False),  # another prefix
        ("tt1-p1", False),  # no sequence
        ("tt1-p1-abc", False),  # sequence is not a number
        ("tt1abcdef", False),  # same letters, wrong shape
        ("web_12345", False),  # a user's own order placed on Binance
        ("", False),
    ],
)
def test_external_orders_are_told_apart_by_shape(client_order_id: str, ours: bool) -> None:
    """D-14: an order without the platform's id shape was placed by the user on Binance."""
    assert is_platform_client_order_id(client_order_id, PREFIX) is ours


def test_a_built_id_is_always_recognised_as_ours() -> None:
    built = build_client_order_id(PREFIX, "p1", 7)

    assert is_platform_client_order_id(built, PREFIX)


# --- OrderIntent (FR-ORD-01) --------------------------------------------


def test_an_intent_carries_no_identity_or_status() -> None:
    """An intent is a request, not an order: it gets neither until Risk approves it."""
    intent = limit_intent()

    assert not hasattr(intent, "client_order_id")
    assert not hasattr(intent, "status")


@pytest.mark.parametrize(
    ("order_type", "price", "stop_price"),
    [
        (OrderType.MARKET, None, None),
        (OrderType.LIMIT, D("60000.0"), None),
        (OrderType.STOP_MARKET, None, D("58000.0")),
        (OrderType.TAKE_PROFIT_MARKET, None, D("62000.0")),
    ],
)
def test_each_order_type_accepts_exactly_the_prices_it_needs(
    order_type: OrderType, price: D | None, stop_price: D | None
) -> None:
    intent = OrderIntent(
        symbol="BTCUSDT",
        side=BUY,
        order_type=order_type,
        quantity=D("0.5"),
        price=price,
        stop_price=stop_price,
    )

    assert intent.order_type is order_type


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"order_type": OrderType.MARKET, "price": D("60000.0")}, "must not carry price"),
        ({"order_type": OrderType.LIMIT, "price": None}, "requires price"),
        ({"order_type": OrderType.LIMIT, "stop_price": D(1)}, "must not carry stop_price"),
        ({"quantity": D(0)}, "quantity must be positive"),
        ({"quantity": D(-1)}, "quantity must be positive"),
        ({"price": D(0)}, "price must be positive"),
        ({"symbol": ""}, "symbol must not be empty"),
    ],
)
def test_a_self_contradictory_intent_cannot_be_built(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        limit_intent(**changes)


def test_an_approved_intent_becomes_a_sendable_order() -> None:
    intent = limit_intent(time_in_force=TimeInForce.GTC, reduce_only=True)

    result = order_from_intent(intent, client_order_id="tt1-p1-3", owner_type=OwnerType.BOT)

    assert result.status is OrderStatus.PENDING_NEW
    assert result.client_order_id == "tt1-p1-3"
    assert result.owner_type is OwnerType.BOT
    assert (result.symbol, result.side, result.quantity) == ("BTCUSDT", BUY, D("0.5"))
    assert result.price == D("60000.0")
    assert result.time_in_force is TimeInForce.GTC
    assert result.reduce_only is True
    assert result.filled_quantity == 0
    assert result.average_fill_price is None


# --- Order lifecycle (FR-ORD-03) ----------------------------------------


def test_a_new_order_starts_pending_and_open() -> None:
    fresh = order()

    assert fresh.status is OrderStatus.PENDING_NEW
    assert fresh.is_open
    assert not fresh.status.is_terminal
    assert fresh.remaining_quantity == D("0.5")


def test_the_venue_acknowledging_moves_pending_to_new() -> None:
    accepted = order().accept(exchange_order_id="X-1")

    assert accepted.status is OrderStatus.NEW
    assert accepted.exchange_order_id == "X-1"


def test_paper_needs_no_exchange_order_id() -> None:
    assert order().accept().exchange_order_id is None


def test_a_transition_returns_a_new_order_and_leaves_the_old_one_alone() -> None:
    """Immutability is what lets an engine keep the previous value for the audit trail."""
    fresh = order()

    accepted = fresh.accept()

    assert fresh.status is OrderStatus.PENDING_NEW
    assert accepted is not fresh


def test_filling_the_whole_quantity_fills_the_order() -> None:
    filled = order().accept().apply_fill(D("0.5"), D("60000.0"))

    assert filled.status is OrderStatus.FILLED
    assert filled.filled_quantity == D("0.5")
    assert filled.average_fill_price == D("60000.0")
    assert filled.remaining_quantity == 0
    assert filled.status.is_terminal


def test_a_partial_fill_leaves_the_order_open() -> None:
    partial = order().accept().apply_fill(D("0.2"), D("60000.0"))

    assert partial.status is OrderStatus.PARTIALLY_FILLED
    assert partial.remaining_quantity == D("0.3")
    assert partial.is_open


def test_successive_fills_average_by_weight() -> None:
    """0.2 at 60000 then 0.3 at 61000 -> (12000 + 18300) / 0.5 = 60600."""
    result = order().accept().apply_fill(D("0.2"), D(60000)).apply_fill(D("0.3"), D(61000))

    assert result.status is OrderStatus.FILLED
    assert result.average_fill_price == D(60600)


def test_a_fill_cannot_exceed_what_is_left() -> None:
    partial = order().accept().apply_fill(D("0.4"), D(60000))

    with pytest.raises(ValueError, match="cannot exceed the remaining quantity"):
        partial.apply_fill(D("0.2"), D(60000))


@pytest.mark.parametrize(("quantity", "price"), [(D(0), D(60000)), (D("0.1"), D(0))])
def test_a_fill_needs_a_positive_quantity_and_price(quantity: D, price: D) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        order().accept().apply_fill(quantity, price)


def test_cancelling_keeps_what_had_already_filled() -> None:
    canceled = order().accept().apply_fill(D("0.2"), D(60000)).cancel()

    assert canceled.status is OrderStatus.CANCELED
    assert canceled.filled_quantity == D("0.2")
    assert canceled.status.is_terminal


def test_a_rejection_must_say_why() -> None:
    rejected = order().reject("insufficient margin")

    assert rejected.status is OrderStatus.REJECTED
    assert rejected.reject_reason == "insufficient margin"

    with pytest.raises(ValueError, match="must carry a reason"):
        order().reject("")


@pytest.mark.parametrize(
    "finish",
    [
        lambda o: o.cancel(),
        lambda o: o.reject("nope"),
        lambda o: o.expire(),
        lambda o: o.apply_fill(D("0.5"), D(60000)),
    ],
)
def test_a_finished_order_can_never_change_again(finish: object) -> None:
    done = finish(order().accept())  # type: ignore[operator]
    assert done.status.is_terminal

    for attempt in (lambda o: o.cancel(), lambda o: o.expire(), lambda o: o.accept()):
        with pytest.raises(ValueError, match="cannot move an order"):
            attempt(done)


def test_an_acknowledged_order_cannot_be_acknowledged_twice() -> None:
    with pytest.raises(ValueError, match="cannot move an order from NEW to NEW"):
        order().accept().accept()


def test_a_timeout_can_resolve_straight_to_a_fill_without_an_acknowledgement() -> None:
    """FR-LIVE-07: after a timeout the venue may report a fill for an order still PENDING_NEW."""
    filled = order().apply_fill(D("0.5"), D(60000))

    assert filled.status is OrderStatus.FILLED


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"client_order_id": ""}, "client_order_id must not be empty"),
        ({"quantity": D(0)}, "quantity must be positive"),
        ({"filled_quantity": D(1)}, "between zero and the order quantity"),
        ({"filled_quantity": D(-1)}, "between zero and the order quantity"),
        ({"average_fill_price": D(60000)}, "exactly when it has filled"),
        ({"filled_quantity": D("0.2")}, "exactly when it has filled"),
    ],
)
def test_an_inconsistent_order_cannot_be_built(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        order(**changes)


# --- ExecutionAdapter port (FR-ORD-04, P-03/P-04) -----------------------


def test_any_object_with_submit_and_cancel_satisfies_the_port() -> None:
    """The core talks to the port and never learns whether it is Paper or Live."""

    class Recorder:
        def __init__(self) -> None:
            self.submitted: list[str] = []
            self.canceled: list[str] = []

        def submit(self, order: Order) -> None:
            self.submitted.append(order.client_order_id)

        def cancel(self, client_order_id: str) -> None:
            self.canceled.append(client_order_id)

    adapter: ExecutionAdapter = Recorder()
    adapter.submit(order())
    adapter.cancel("tt1-p1-1")

    assert isinstance(adapter, ExecutionAdapter)
    assert adapter.submitted == ["tt1-p1-1"]  # type: ignore[attr-defined]
    assert adapter.canceled == ["tt1-p1-1"]  # type: ignore[attr-defined]


def test_an_object_missing_cancel_is_not_an_adapter() -> None:
    class SubmitOnly:
        def submit(self, order: Order) -> None: ...

    assert not isinstance(SubmitOnly(), ExecutionAdapter)


# --- Decimal context isolation ------------------------------------------


def test_reading_an_order_under_a_hostile_caller_context_is_exact() -> None:
    """Every Decimal read must run in the core context, not the caller's.

    A partially filled order whose remainder needs more digits than the caller allows
    would otherwise truncate silently, or raise on what looks like a plain attribute read.
    """
    partial = order(quantity=D("1.123456789")).accept().apply_fill(D("0.1"), D(60000))

    with localcontext(Context(prec=5, traps=[Inexact, Rounded])):
        assert partial.remaining_quantity == D("1.023456789")
        assert partial.filled_quantity == D("0.1")
        assert partial.is_open
        assert partial.status.is_open
        assert not partial.status.is_terminal
