import threading
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from PySide6.QtCore import QCoreApplication, QThreadPool
from pytestqt.qtbot import QtBot

from tests.support.trade_history_records import basket_result, trade_fill
from tiewtrade.application.trade_history import (
    BasketHistoryPage,
    PageRequest,
    TradeHistoryFilter,
)
from tiewtrade.trading.trade_history import BasketResult, BasketStatus, TradeFill
from tiewtrade.ui.trade_history_presenter import TradeHistoryFilterValues
from tiewtrade.ui.trade_history_workflow import (
    ListBaskets,
    ListFills,
    TradeHistoryWorkflow,
)


def page_with(
    *items: BasketResult,
    page: int = 1,
    total_items: int | None = None,
) -> BasketHistoryPage:
    return BasketHistoryPage(
        items=tuple(items),
        page=page,
        page_size=50,
        total_items=len(items) if total_items is None else total_items,
        net_realized_pnl=sum(
            (
                item.net_realized_pnl
                for item in items
                if item.status is BasketStatus.CLOSED
            ),
            start=Decimal("0"),
        ),
    )


def workflow_with(
    *,
    list_baskets: ListBaskets,
    list_fills: ListFills,
) -> tuple[TradeHistoryWorkflow, QThreadPool]:
    pool = QThreadPool()
    pool.setMaxThreadCount(2)
    return (
        TradeHistoryWorkflow(
            list_baskets=list_baskets,
            list_fills=list_fills,
            thread_pool=pool,
        ),
        pool,
    )


def test_start_loads_first_page_and_auto_loads_first_basket_fills(
    qtbot: QtBot,
) -> None:
    basket = basket_result()
    fill = trade_fill()
    basket_calls: list[tuple[TradeHistoryFilter, PageRequest]] = []
    fill_calls: list[UUID] = []

    def list_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        basket_calls.append((filters, request))
        return page_with(basket)

    def list_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        fill_calls.append(basket_id)
        return (fill,)

    workflow, pool = workflow_with(
        list_baskets=list_baskets,
        list_fills=list_fills,
    )
    pages: list[BasketHistoryPage] = []
    fills: list[tuple[UUID, tuple[TradeFill, ...]]] = []
    workflow.baskets_ready.connect(pages.append)
    workflow.fills_ready.connect(
        lambda basket_id, values: fills.append((basket_id, values))
    )

    workflow.start()

    qtbot.waitUntil(lambda: len(fills) == 1)
    assert basket_calls == [(TradeHistoryFilter(), PageRequest(page=1, page_size=50))]
    assert pages[0].items == (basket,)
    assert fill_calls == [basket.basket_id]
    assert fills == [(basket.basket_id, (fill,))]
    assert pool.waitForDone(1_000)


def test_success_emits_semantic_results_before_matching_loading_false(
    qtbot: QtBot,
) -> None:
    basket = basket_result()
    events: list[str] = []
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(basket),
        list_fills=lambda basket_id: (),
    )
    workflow.baskets_loading.connect(
        lambda loading: events.append(f"baskets:{loading}")
    )
    workflow.baskets_ready.connect(lambda page: events.append("baskets:ready"))
    workflow.fills_loading.connect(lambda loading: events.append(f"fills:{loading}"))
    workflow.fills_empty.connect(lambda basket_id: events.append("fills:empty"))

    workflow.start()

    qtbot.waitUntil(lambda: events[-1:] == ["fills:False"])
    assert events.index("baskets:ready") < events.index("baskets:False")
    assert events.index("fills:empty") < events.index("fills:False")
    assert pool.waitForDone(1_000)


def test_empty_basket_page_does_not_query_fills(qtbot: QtBot) -> None:
    fill_calls: list[UUID] = []
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(),
        list_fills=lambda basket_id: fill_calls.append(basket_id) or (),
    )
    empty_events: list[None] = []
    workflow.baskets_empty.connect(lambda: empty_events.append(None))

    workflow.start()

    qtbot.waitUntil(lambda: empty_events == [None])
    assert fill_calls == []
    assert pool.waitForDone(1_000)


def test_apply_filters_resets_to_page_one_and_uses_exact_filter(
    qtbot: QtBot,
) -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []

    def list_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        calls.append((filters, request))
        return page_with()

    workflow, pool = workflow_with(
        list_baskets=list_baskets,
        list_fills=lambda basket_id: (),
    )
    values = TradeHistoryFilterValues(symbol="BTCUSDT", status="closed")
    workflow.apply_filters(values)

    qtbot.waitUntil(lambda: len(calls) == 1)
    assert calls[0] == (
        TradeHistoryFilter(symbol="BTCUSDT", status=BasketStatus.CLOSED),
        PageRequest(page=1, page_size=50),
    )
    assert pool.waitForDone(1_000)


def test_reset_filters_queries_empty_filter_on_page_one(qtbot: QtBot) -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: (
            calls.append((filters, request)) or page_with()
        ),
        list_fills=lambda basket_id: (),
    )
    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    qtbot.waitUntil(lambda: len(calls) == 1)

    workflow.reset_filters()

    qtbot.waitUntil(lambda: len(calls) == 2)
    assert calls[-1] == (TradeHistoryFilter(), PageRequest(page=1, page_size=50))
    assert pool.waitForDone(1_000)


def test_invalid_filter_emits_validation_without_query() -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: (
            calls.append((filters, request)) or page_with()
        ),
        list_fills=lambda basket_id: (),
    )
    messages: list[str] = []
    workflow.filter_invalid.connect(messages.append)

    workflow.apply_filters(
        TradeHistoryFilterValues(
            from_date=date(2026, 1, 3),
            to_date=date(2026, 1, 2),
        )
    )

    assert messages == ["From Date must not be after To Date"]
    assert calls == []
    assert pool.waitForDone(1_000)


def test_filter_date_overflow_emits_validation_without_query() -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: (
            calls.append((filters, request)) or page_with()
        ),
        list_fills=lambda basket_id: (),
    )
    messages: list[str] = []
    workflow.filter_invalid.connect(messages.append)

    workflow.apply_filters(TradeHistoryFilterValues(to_date=date.max))

    assert messages == ["To Date is out of range"]
    assert calls == []
    assert pool.waitForDone(1_000)


def test_page_request_stays_within_known_bounds(qtbot: QtBot) -> None:
    calls: list[PageRequest] = []

    def list_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        calls.append(request)
        return page_with(basket_result(), page=request.page, total_items=51)

    workflow, pool = workflow_with(
        list_baskets=list_baskets, list_fills=lambda basket_id: ()
    )
    workflow.start()
    qtbot.waitUntil(lambda: len(calls) == 1)

    workflow.go_to_page(0)
    workflow.go_to_page(3)
    workflow.go_to_page(2)

    qtbot.waitUntil(lambda: len(calls) == 2)
    assert calls == [
        PageRequest(page=1, page_size=50),
        PageRequest(page=2, page_size=50),
    ]
    assert pool.waitForDone(1_000)


def test_basket_failure_is_sanitized_and_retry_reuses_latest_request(
    qtbot: QtBot,
) -> None:
    calls: list[tuple[TradeHistoryFilter, PageRequest]] = []

    def fail_then_succeed(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        calls.append((filters, request))
        if len(calls) == 1:
            raise RuntimeError("SQLite failed at /private/tmp/history.sqlite3")
        return page_with()

    workflow, pool = workflow_with(
        list_baskets=fail_then_succeed, list_fills=lambda basket_id: ()
    )
    messages: list[str] = []
    workflow.baskets_unavailable.connect(messages.append)
    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    qtbot.waitUntil(lambda: messages == ["Trade History unavailable"])

    workflow.retry_baskets()

    qtbot.waitUntil(lambda: len(calls) == 2)
    assert calls[1] == calls[0]
    assert "/private/tmp" not in messages[0]
    assert pool.waitForDone(1_000)


def test_basket_retry_can_queue_before_failed_task_finishes(qtbot: QtBot) -> None:
    calls = 0

    def fail_then_succeed(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("failed")
        return page_with()

    workflow, pool = workflow_with(
        list_baskets=fail_then_succeed, list_fills=lambda basket_id: ()
    )
    empty_events: list[None] = []
    workflow.baskets_unavailable.connect(workflow.retry_baskets)
    workflow.baskets_empty.connect(lambda: empty_events.append(None))

    workflow.start()

    qtbot.waitUntil(lambda: empty_events == [None])
    assert calls == 2
    assert pool.waitForDone(1_000)


def test_fill_failure_is_scoped_and_retry_requires_current_selection(
    qtbot: QtBot,
) -> None:
    basket = basket_result()
    calls: list[UUID] = []

    def fail_then_succeed(basket_id: UUID) -> tuple[TradeFill, ...]:
        calls.append(basket_id)
        if len(calls) == 1:
            raise RuntimeError("SQLite failed at /private/tmp/history.sqlite3")
        return ()

    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(basket),
        list_fills=fail_then_succeed,
    )
    messages: list[tuple[UUID, str]] = []
    empty: list[UUID] = []
    workflow.fills_unavailable.connect(
        lambda basket_id, message: messages.append((basket_id, message))
    )
    workflow.fills_empty.connect(empty.append)
    workflow.start()
    qtbot.waitUntil(lambda: messages == [(basket.basket_id, "Trade Fills unavailable")])

    workflow.retry_fills()

    qtbot.waitUntil(lambda: empty == [basket.basket_id])
    assert calls == [basket.basket_id, basket.basket_id]
    assert "/private/tmp" not in messages[0][1]
    assert pool.waitForDone(1_000)


def test_fill_retry_can_queue_before_failed_task_finishes(qtbot: QtBot) -> None:
    basket = basket_result()
    calls = 0

    def fail_then_succeed(basket_id: UUID) -> tuple[TradeFill, ...]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("failed")
        return ()

    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(basket),
        list_fills=fail_then_succeed,
    )
    empty_events: list[UUID] = []
    workflow.fills_unavailable.connect(
        lambda basket_id, message: workflow.retry_fills()
    )
    workflow.fills_empty.connect(empty_events.append)

    workflow.start()

    qtbot.waitUntil(lambda: empty_events == [basket.basket_id])
    assert calls == 2
    assert pool.waitForDone(1_000)


def test_invalid_worker_results_fail_closed(qtbot: QtBot) -> None:
    basket = basket_result()
    basket_workflow, basket_pool = workflow_with(
        list_baskets=lambda filters, request: object(),  # type: ignore[return-value]
        list_fills=lambda basket_id: (),
    )
    basket_messages: list[str] = []
    basket_workflow.baskets_unavailable.connect(basket_messages.append)
    basket_workflow.start()
    qtbot.waitUntil(lambda: basket_messages == ["Trade History unavailable"])

    fill_workflow, fill_pool = workflow_with(
        list_baskets=lambda filters, request: page_with(basket),
        list_fills=lambda basket_id: (object(),),  # type: ignore[return-value]
    )
    fill_messages: list[tuple[UUID, str]] = []
    fill_workflow.fills_unavailable.connect(
        lambda basket_id, message: fill_messages.append((basket_id, message))
    )
    fill_workflow.start()
    qtbot.waitUntil(
        lambda: fill_messages == [(basket.basket_id, "Trade Fills unavailable")]
    )
    assert basket_pool.waitForDone(1_000)
    assert fill_pool.waitForDone(1_000)


@pytest.mark.parametrize(
    "malformed",
    [
        BasketHistoryPage(
            items=(),
            page=1,
            page_size=50,
            total_items="invalid",  # type: ignore[arg-type]
            net_realized_pnl=Decimal("0"),
        ),
        BasketHistoryPage(
            items=(basket_result(),),
            page=1,
            page_size=50,
            total_items=0,
            net_realized_pnl=Decimal("0"),
        ),
        BasketHistoryPage(
            items=(),
            page=1,
            page_size=50,
            total_items=0,
            net_realized_pnl=Decimal("NaN"),
        ),
    ],
)
def test_malformed_basket_page_fails_closed(
    qtbot: QtBot, malformed: BasketHistoryPage
) -> None:
    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: malformed,
        list_fills=lambda basket_id: (),
    )
    messages: list[str] = []
    workflow.baskets_unavailable.connect(messages.append)

    workflow.start()

    qtbot.waitUntil(lambda: messages == ["Trade History unavailable"])
    assert pool.waitForDone(1_000)


def test_only_latest_filter_request_runs_after_active_request(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    calls: list[str | None] = []

    def delayed(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        calls.append(filters.symbol)
        if len(calls) == 1:
            started.set()
            assert release.wait(timeout=2)
        return page_with()

    workflow, pool = workflow_with(
        list_baskets=delayed, list_fills=lambda basket_id: ()
    )
    workflow.start()
    qtbot.waitUntil(started.is_set)

    workflow.apply_filters(TradeHistoryFilterValues(symbol="OLD"))
    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    release.set()

    qtbot.waitUntil(lambda: len(calls) == 2)
    assert calls == [None, "BTCUSDT"]
    assert pool.waitForDone(1_000)


def test_active_basket_request_is_reused_when_it_becomes_latest_again(
    qtbot: QtBot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    basket = basket_result()
    calls: list[str | None] = []

    def delayed(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        calls.append(filters.symbol)
        started.set()
        assert release.wait(timeout=2)
        return page_with(basket)

    workflow, pool = workflow_with(
        list_baskets=delayed, list_fills=lambda basket_id: ()
    )
    pages: list[BasketHistoryPage] = []
    workflow.baskets_ready.connect(pages.append)
    workflow.start()
    qtbot.waitUntil(started.is_set)

    workflow.apply_filters(TradeHistoryFilterValues(symbol="OLD"))
    workflow.reset_filters()
    release.set()

    qtbot.waitUntil(lambda: pages == [page_with(basket)])
    assert calls == [None]
    assert pool.waitForDone(1_000)


def test_new_filter_supersedes_running_basket_request(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    old_basket = basket_result(symbol="OLD")
    new_basket = basket_result(
        basket_id=UUID("00000000-0000-0000-0000-000000000199"),
        symbol="BTCUSDT",
    )
    calls = 0

    def delayed(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            assert release.wait(timeout=2)
            return page_with(old_basket)
        return page_with(new_basket)

    workflow, pool = workflow_with(
        list_baskets=delayed, list_fills=lambda basket_id: ()
    )
    pages: list[BasketHistoryPage] = []
    workflow.baskets_ready.connect(pages.append)
    workflow.start()
    qtbot.waitUntil(started.is_set)
    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    release.set()

    qtbot.waitUntil(lambda: len(pages) == 1)
    assert pages[0].items == (new_basket,)
    assert pool.waitForDone(1_000)


def test_new_selection_supersedes_running_fill_request(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    first = basket_result()
    second = basket_result(basket_id=UUID("00000000-0000-0000-0000-000000000299"))
    first_fill = trade_fill()
    second_fill = trade_fill(basket_id=second.basket_id, fill_id="fill-2")

    def delayed_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        if basket_id == first.basket_id:
            started.set()
            assert release.wait(timeout=2)
            return (first_fill,)
        return (second_fill,)

    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(first, second),
        list_fills=delayed_fills,
    )
    results: list[tuple[UUID, tuple[TradeFill, ...]]] = []
    workflow.fills_ready.connect(
        lambda basket_id, fills: results.append((basket_id, fills))
    )
    workflow.start()
    qtbot.waitUntil(started.is_set)
    workflow.select_basket(second.basket_id)
    release.set()

    qtbot.waitUntil(lambda: len(results) == 1)
    assert results == [(second.basket_id, (second_fill,))]
    assert pool.waitForDone(1_000)


def test_only_latest_fill_selection_runs_after_active_request(qtbot: QtBot) -> None:
    started = threading.Event()
    release = threading.Event()
    first = basket_result()
    second_id = UUID("00000000-0000-0000-0000-000000000299")
    latest_id = UUID("00000000-0000-0000-0000-000000000399")
    calls: list[UUID] = []

    def delayed_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        calls.append(basket_id)
        if len(calls) == 1:
            started.set()
            assert release.wait(timeout=2)
        return ()

    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(first),
        list_fills=delayed_fills,
    )
    workflow.start()
    qtbot.waitUntil(started.is_set)

    workflow.select_basket(second_id)
    workflow.select_basket(latest_id)
    release.set()

    qtbot.waitUntil(lambda: len(calls) == 2)
    assert calls == [first.basket_id, latest_id]
    assert pool.waitForDone(1_000)


def test_active_fill_request_is_reused_when_it_becomes_latest_again(
    qtbot: QtBot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    first = basket_result()
    second_id = UUID("00000000-0000-0000-0000-000000000299")
    fill = trade_fill()
    calls: list[UUID] = []

    def delayed_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        calls.append(basket_id)
        started.set()
        assert release.wait(timeout=2)
        return (fill,)

    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(first),
        list_fills=delayed_fills,
    )
    results: list[tuple[UUID, tuple[TradeFill, ...]]] = []
    workflow.fills_ready.connect(
        lambda basket_id, fills: results.append((basket_id, fills))
    )
    workflow.start()
    qtbot.waitUntil(started.is_set)

    workflow.select_basket(second_id)
    workflow.select_basket(first.basket_id)
    release.set()

    qtbot.waitUntil(lambda: results == [(first.basket_id, (fill,))])
    assert calls == [first.basket_id]
    assert pool.waitForDone(1_000)


def test_basket_request_invalidates_running_fill_result(qtbot: QtBot) -> None:
    fill_started = threading.Event()
    fill_release = threading.Event()
    basket = basket_result()
    basket_calls = 0

    def list_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        nonlocal basket_calls
        basket_calls += 1
        return page_with(basket) if basket_calls == 1 else page_with()

    def delayed_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        fill_started.set()
        assert fill_release.wait(timeout=2)
        return (trade_fill(),)

    workflow, pool = workflow_with(
        list_baskets=list_baskets,
        list_fills=delayed_fills,
    )
    fill_results: list[tuple[UUID, tuple[TradeFill, ...]]] = []
    basket_empty: list[None] = []
    workflow.fills_ready.connect(
        lambda basket_id, fills: fill_results.append((basket_id, fills))
    )
    workflow.baskets_empty.connect(lambda: basket_empty.append(None))
    workflow.start()
    qtbot.waitUntil(fill_started.is_set)

    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    qtbot.waitUntil(lambda: basket_empty == [None])
    fill_release.set()

    assert pool.waitForDone(1_000)
    QCoreApplication.processEvents()
    assert fill_results == []


def test_duplicate_active_requests_do_not_enqueue_more_work(qtbot: QtBot) -> None:
    basket_started = threading.Event()
    basket_release = threading.Event()
    fill_started = threading.Event()
    fill_release = threading.Event()
    basket = basket_result()
    basket_calls = 0
    fill_calls = 0

    def delayed_baskets(
        filters: TradeHistoryFilter, request: PageRequest
    ) -> BasketHistoryPage:
        nonlocal basket_calls
        basket_calls += 1
        basket_started.set()
        assert basket_release.wait(timeout=2)
        return page_with(basket)

    def delayed_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        nonlocal fill_calls
        fill_calls += 1
        fill_started.set()
        assert fill_release.wait(timeout=2)
        return ()

    workflow, pool = workflow_with(
        list_baskets=delayed_baskets,
        list_fills=delayed_fills,
    )
    workflow.start()
    qtbot.waitUntil(basket_started.is_set)
    workflow.start()
    basket_release.set()
    qtbot.waitUntil(fill_started.is_set)
    workflow.select_basket(basket.basket_id)
    fill_release.set()

    assert pool.waitForDone(1_000)
    QCoreApplication.processEvents()
    assert basket_calls == 1
    assert fill_calls == 1


def test_close_suppresses_late_results_and_finished_cleans_tasks(
    qtbot: QtBot,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def delayed(filters: TradeHistoryFilter, request: PageRequest) -> BasketHistoryPage:
        started.set()
        assert release.wait(timeout=2)
        return page_with(basket_result())

    workflow, pool = workflow_with(
        list_baskets=delayed, list_fills=lambda basket_id: ()
    )
    pages: list[BasketHistoryPage] = []
    workflow.baskets_ready.connect(pages.append)
    workflow.start()
    qtbot.waitUntil(started.is_set)
    retained_task = workflow._basket_task
    assert retained_task is not None

    workflow.close()
    workflow.start()
    workflow.apply_filters(TradeHistoryFilterValues(symbol="BTCUSDT"))
    release.set()

    assert pool.waitForDone(1_000)
    qtbot.waitUntil(lambda: workflow._basket_task is None)
    callback_count = len(pages)
    retained_task.signals.succeeded.emit(page_with(basket_result()))
    QCoreApplication.processEvents()

    assert pages == []
    assert callback_count == 0
    assert workflow._basket_task is None
    assert workflow._fill_task is None


def test_close_cleans_active_fill_task_and_disconnects_callbacks(
    qtbot: QtBot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    basket = basket_result()
    fill = trade_fill()

    def delayed_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
        started.set()
        assert release.wait(timeout=2)
        return (fill,)

    workflow, pool = workflow_with(
        list_baskets=lambda filters, request: page_with(basket),
        list_fills=delayed_fills,
    )
    results: list[tuple[UUID, tuple[TradeFill, ...]]] = []
    workflow.fills_ready.connect(
        lambda basket_id, fills: results.append((basket_id, fills))
    )
    workflow.start()
    qtbot.waitUntil(started.is_set)
    retained_task = workflow._fill_task
    assert retained_task is not None

    workflow.close()
    release.set()

    assert pool.waitForDone(1_000)
    qtbot.waitUntil(lambda: workflow._fill_task is None)
    retained_task.signals.succeeded.emit((fill,))
    QCoreApplication.processEvents()

    assert results == []
