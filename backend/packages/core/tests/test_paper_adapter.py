from decimal import Decimal as D

import pytest

from tiewtrade_core.execution import (
    ExecutionAdapter,
    ExecutionReport,
    MarketSnapshot,
    PaperExecutionAdapter,
    ReportKind,
    TopOfBook,
    resting_fill_report,
)
from tiewtrade_core.market import LiquidityRole, OrderSide
from tiewtrade_core.orders import Order, OrderStatus, OrderType, OwnerType

BUY, SELL = OrderSide.BUY, OrderSide.SELL
MAKER, TAKER = LiquidityRole.MAKER, LiquidityRole.TAKER

SYMBOL = "BTCUSDT"
TICK = D("0.1")
S = D("0.0002")  # the 0.02% default of FR-ORD-07


def snapshot(bid: str, ask: str, last: str | None = None) -> MarketSnapshot:
    return MarketSnapshot(
        book=TopOfBook(best_bid=D(bid), best_ask=D(ask)),
        last_price=D(last if last is not None else bid),
        tick_size=TICK,
    )


def order(**changes: object) -> Order:
    fields: dict[str, object] = {
        "client_order_id": "tt1-p1-1",
        "symbol": SYMBOL,
        "side": BUY,
        "order_type": OrderType.MARKET,
        "quantity": D("0.5"),
        "owner_type": OwnerType.MANUAL,
    }
    fields.update(changes)
    return Order(**fields)  # type: ignore[arg-type]


class Reports:
    """Collects what the adapter emits, standing in for the engine."""

    def __init__(self) -> None:
        self.received: list[ExecutionReport] = []

    def __call__(self, report: ExecutionReport) -> None:
        self.received.append(report)

    @property
    def only(self) -> ExecutionReport:
        assert len(self.received) == 1, f"expected one report, got {self.received}"
        return self.received[0]


# The book most cases run against; the exact prices only matter where one is asserted.
MARKET = snapshot("60000.0", "60000.1")


def adapter(market: MarketSnapshot = MARKET) -> tuple[PaperExecutionAdapter, Reports]:
    sink = Reports()
    paper = PaperExecutionAdapter(sink, slippage_rate=S)
    paper.update_market(SYMBOL, market)
    return paper, sink


# --- the port ------------------------------------------------------------


def test_the_paper_adapter_satisfies_the_execution_adapter_port() -> None:
    """P-03/P-04: the core talks to the port, never to this class by name."""
    paper, _ = adapter()

    assert isinstance(paper, ExecutionAdapter)


def test_the_adapter_keeps_no_orders_of_its_own() -> None:
    """The engine owns open orders; a second copy here would be a second truth (C-20, §7.5).

    Stated as the exact set it may hold, so adding any store fails here whatever it is
    named — a substring scan would pass for a field called ``_resting``.
    """
    paper, _ = adapter()

    assert set(vars(paper)) == {"_sink", "_slippage_rate", "_markets"}


# --- submit: market orders (§4.1) ---------------------------------------


def test_a_market_buy_fills_at_once_as_taker() -> None:
    paper, sink = adapter(snapshot("60000.0", "60000.1"))

    paper.submit(order(side=BUY))

    report = sink.only
    assert report.kind is ReportKind.FILLED
    assert report.client_order_id == "tt1-p1-1"
    assert report.price == D("60012.2")  # 60000.1 * 1.0002, rounded up against the buyer
    assert report.liquidity is TAKER
    assert report.quantity == D("0.5")


def test_a_market_sell_reads_the_bid() -> None:
    paper, sink = adapter(snapshot("60000.1", "60000.2"))

    paper.submit(order(side=SELL))

    assert sink.only.price == D("59988.0")  # 60000.1 * 0.9998, rounded down against the seller


def test_a_fill_covers_only_what_is_left_of_a_partly_filled_order() -> None:
    """A partly filled order is advanced by price, never resubmitted."""
    partly = (
        order(order_type=OrderType.LIMIT, price=D("59000.0"))
        .accept()
        .apply_fill(D("0.2"), D(59000))
    )

    report = resting_fill_report(partly, D("58999.9"))

    assert report is not None
    assert report.quantity == D("0.3")


# --- submit: limit orders (§4.2) ----------------------------------------


def test_a_marketable_limit_fills_immediately_as_taker() -> None:
    paper, sink = adapter(snapshot("60000.0", "60000.1"))

    paper.submit(order(order_type=OrderType.LIMIT, price=D("60013.0")))

    report = sink.only
    assert report.kind is ReportKind.FILLED
    assert report.price == D("60012.2")
    assert report.liquidity is TAKER


def test_a_marketable_limit_never_fills_worse_than_its_limit() -> None:
    paper, sink = adapter(snapshot("60000.0", "60000.1"))

    paper.submit(order(order_type=OrderType.LIMIT, price=D("60012.1")))

    assert sink.only.price == D("60012.1")


def test_a_limit_away_from_the_market_is_only_acknowledged() -> None:
    paper, sink = adapter()

    paper.submit(order(order_type=OrderType.LIMIT, price=D("59000.0")))

    report = sink.only
    assert report.kind is ReportKind.ACCEPTED
    assert report.quantity is None


@pytest.mark.parametrize("order_type", [OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET])
def test_a_conditional_order_rests_until_its_trigger_fires(order_type: OrderType) -> None:
    paper, sink = adapter()

    paper.submit(order(order_type=order_type, stop_price=D("58000.0")))

    assert sink.only.kind is ReportKind.ACCEPTED


# --- resting_fill_report: a free function, no adapter needed ------------


def test_a_resting_limit_fills_when_the_price_goes_through_it() -> None:
    resting = order(order_type=OrderType.LIMIT, price=D("59000.0")).accept()

    report = resting_fill_report(resting, D("58999.9"))

    assert report is not None
    assert report.kind is ReportKind.FILLED
    assert report.price == D("59000.0")  # a maker fills at its own price, with no slippage
    assert report.liquidity is MAKER


def test_touching_a_resting_limit_reports_nothing() -> None:
    """FR-ORD-08: the price must go through, not merely reach."""
    resting = order(order_type=OrderType.LIMIT, price=D("59000.0")).accept()

    assert resting_fill_report(resting, D("59000.0")) is None


@pytest.mark.parametrize(
    "order_type", [OrderType.MARKET, OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET]
)
def test_only_a_resting_limit_is_advanced_by_price(order_type: OrderType) -> None:
    """A fired stop fills as a market order and needs the position, so it is not done here."""
    stop = D("58000.0") if order_type.needs_stop_price else None
    resting = order(order_type=order_type, stop_price=stop).accept()

    assert resting_fill_report(resting, D("1")) is None


def test_only_an_open_order_can_be_re_priced() -> None:
    done = order().accept().apply_fill(D("0.5"), D(60000))

    with pytest.raises(ValueError, match="only an open order"):
        resting_fill_report(done, D(60000))


@pytest.mark.parametrize("last_price", ["0", "-1"])
def test_advancing_against_a_non_positive_price_is_refused(last_price: str) -> None:
    """The narrowed parameter lost MarketSnapshot's guard, so this boundary carries it.

    Without it a resting buy compares against a collapsed price and fills at its limit.
    """
    resting = order(order_type=OrderType.LIMIT, price=D("59000.0")).accept()

    with pytest.raises(ValueError, match="last price must be positive"):
        resting_fill_report(resting, D(last_price))


def test_advancing_an_order_needs_no_adapter_at_all() -> None:
    """The point of the split: driving the simulation is a pure function (FR-ORD-04)."""
    resting = order(order_type=OrderType.LIMIT, price=D("59000.0")).accept()

    assert resting_fill_report(resting, D("58999.9")) is not None


# --- cancel --------------------------------------------------------------


def test_cancelling_always_succeeds_under_paper() -> None:
    paper, sink = adapter()

    paper.cancel("tt1-p1-1")

    report = sink.only
    assert report.kind is ReportKind.CANCELED
    assert report.client_order_id == "tt1-p1-1"


# --- market data ---------------------------------------------------------


def test_submitting_without_market_data_is_refused() -> None:
    paper = PaperExecutionAdapter(Reports(), slippage_rate=S)

    with pytest.raises(ValueError, match="no market data"):
        paper.submit(order())


def test_the_newest_snapshot_wins() -> None:
    paper, sink = adapter(snapshot("60000.0", "60000.1"))
    paper.update_market(SYMBOL, snapshot("70000.0", "70000.1"))

    paper.submit(order())

    assert sink.only.price == D("70014.2")  # 70000.1 * 1.0002 = 70014.10002, rounded up a tick


@pytest.mark.parametrize(("last", "tick"), [("0", "0.1"), ("60000", "0")])
def test_a_nonsensical_snapshot_is_refused(last: str, tick: str) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        MarketSnapshot(
            book=TopOfBook(best_bid=D("60000.0"), best_ask=D("60000.1")),
            last_price=D(last),
            tick_size=D(tick),
        )


# --- the loop the engine runs -------------------------------------------


def test_an_order_travels_from_submission_to_filled() -> None:
    """The whole Paper path: submit, rest, price moves through, order reaches FILLED.

    This is the round trip P-03/P-04 promise — the same steps Live takes, with only the
    adapter differing.
    """
    paper, sink = adapter(snapshot("60000.0", "60000.1", last="60000.0"))
    resting = order(order_type=OrderType.LIMIT, price=D("59000.0"))

    paper.submit(resting)
    assert sink.only.kind is ReportKind.ACCEPTED
    resting = resting.accept()
    assert resting.status is OrderStatus.NEW

    fill = resting_fill_report(resting, D("58999.9"))
    assert fill is not None
    assert fill.kind is ReportKind.FILLED
    assert fill.quantity is not None
    assert fill.price is not None
    filled = resting.apply_fill(fill.quantity, fill.price)

    assert filled.status is OrderStatus.FILLED
    assert filled.average_fill_price == D("59000.0")
    assert filled.remaining_quantity == 0


# --- ExecutionReport (C-19) ---------------------------------------------


def test_a_fill_report_must_say_what_traded() -> None:
    with pytest.raises(ValueError, match="must carry quantity, price and liquidity"):
        ExecutionReport(client_order_id="tt1-p1-1", kind=ReportKind.FILLED)


@pytest.mark.parametrize("kind", [ReportKind.ACCEPTED, ReportKind.CANCELED, ReportKind.EXPIRED])
def test_a_report_without_a_trade_must_not_carry_trade_details(kind: ReportKind) -> None:
    with pytest.raises(ValueError, match="must not carry trade details"):
        ExecutionReport(
            client_order_id="tt1-p1-1",
            kind=kind,
            quantity=D("0.5"),
            price=D(60000),
            liquidity=TAKER,
        )


def test_a_rejection_must_say_why() -> None:
    with pytest.raises(ValueError, match="rejection must carry a reason"):
        ExecutionReport(client_order_id="tt1-p1-1", kind=ReportKind.REJECTED)

    assert (
        ExecutionReport(
            client_order_id="tt1-p1-1", kind=ReportKind.REJECTED, reason="no margin"
        ).reason
        == "no margin"
    )


@pytest.mark.parametrize(("quantity", "price"), [(D(0), D(60000)), (D("0.5"), D(0))])
def test_a_fill_report_needs_positive_numbers(quantity: D, price: D) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ExecutionReport(
            client_order_id="tt1-p1-1",
            kind=ReportKind.FILLED,
            quantity=quantity,
            price=price,
            liquidity=TAKER,
        )


def test_a_report_must_name_an_order() -> None:
    with pytest.raises(ValueError, match="client_order_id must not be empty"):
        ExecutionReport(client_order_id="", kind=ReportKind.ACCEPTED)


# --- the port's precondition (FR-ORD-03, C-22) --------------------------


@pytest.mark.parametrize(
    ("make", "status"),
    [
        (lambda o: o.accept(), "NEW"),
        (lambda o: o.accept().apply_fill(D("0.2"), D(60000)), "PARTIALLY_FILLED"),
        (lambda o: o.accept().cancel(), "CANCELED"),
        (lambda o: o.accept().expire(), "EXPIRED"),
        (lambda o: o.reject("no margin"), "REJECTED"),
        (lambda o: o.apply_fill(D("0.5"), D(60000)), "FILLED"),
    ],
)
def test_only_a_pending_new_order_can_be_submitted(make: object, status: str) -> None:
    """Whether an order should be sent at all is the Order Manager's call, not the adapter's.

    The adapter refuses anything else rather than deciding silently, because the two venues
    cannot infer the same thing from a record: under Paper the record is the venue, against
    Binance it is not (FR-ORD-03, FR-LIVE-07).
    """
    paper, sink = adapter()
    already = make(order())  # type: ignore[operator]

    with pytest.raises(
        ValueError, match=f"only a PENDING_NEW order can be submitted, not {status}"
    ):
        paper.submit(already)

    assert sink.received == []


def test_a_submission_always_produces_exactly_one_report() -> None:
    """No path returns silently, so a caller never reads meaning into an absent report."""
    for changes in (
        {},  # market: fills
        {"order_type": OrderType.LIMIT, "price": D("60013.0")},  # marketable: fills
        {"order_type": OrderType.LIMIT, "price": D("59000.0")},  # rests: acknowledged
        {"order_type": OrderType.STOP_MARKET, "stop_price": D("58000.0")},  # rests
    ):
        paper, sink = adapter()

        paper.submit(order(**changes))

        assert len(sink.received) == 1, changes
