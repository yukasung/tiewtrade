from collections.abc import Callable
from decimal import Decimal
from typing import TypeGuard
from uuid import UUID

from PySide6.QtCore import QObject, QThreadPool, Signal, Slot

from tiewtrade.application.trade_history import (
    BasketHistoryPage,
    PageRequest,
    TradeHistoryFilter,
)
from tiewtrade.trading.trade_history import BasketResult, TradeFill
from tiewtrade.ui.background_task import BackgroundTask
from tiewtrade.ui.trade_history_presenter import (
    TradeHistoryFilterValues,
    trade_history_filter,
)

ListBaskets = Callable[[TradeHistoryFilter, PageRequest], BasketHistoryPage]
ListFills = Callable[[UUID], tuple[TradeFill, ...]]

BasketRequest = tuple[TradeHistoryFilter, PageRequest]
PendingBasketRequest = tuple[int, BasketRequest]
PendingFillRequest = tuple[int, UUID]


class TradeHistoryWorkflow(QObject):
    baskets_loading = Signal(bool)
    baskets_ready = Signal(object)
    baskets_empty = Signal()
    baskets_unavailable = Signal(str)
    filter_invalid = Signal(str)
    fills_loading = Signal(bool)
    fills_ready = Signal(object, object)
    fills_empty = Signal(object)
    fills_unavailable = Signal(object, str)

    PAGE_SIZE = 50

    def __init__(
        self,
        *,
        list_baskets: ListBaskets,
        list_fills: ListFills,
        thread_pool: QThreadPool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._list_baskets = list_baskets
        self._list_fills = list_fills
        self._thread_pool = (
            thread_pool if thread_pool is not None else QThreadPool.globalInstance()
        )

        self._filters = TradeHistoryFilter()
        self._page = 1
        self._total_items: int | None = None
        self._selected_basket_id: UUID | None = None
        self._closed = False

        self._basket_generation = 0
        self._basket_task: BackgroundTask | None = None
        self._basket_task_generation: int | None = None
        self._basket_task_request: BasketRequest | None = None
        self._pending_basket_request: PendingBasketRequest | None = None
        self._latest_basket_request: BasketRequest | None = None
        self._failed_basket_request: BasketRequest | None = None
        self._baskets_are_loading = False

        self._fill_generation = 0
        self._fill_task: BackgroundTask | None = None
        self._fill_task_generation: int | None = None
        self._fill_task_basket_id: UUID | None = None
        self._pending_fill_request: PendingFillRequest | None = None
        self._latest_fill_request: UUID | None = None
        self._failed_fill_request: UUID | None = None
        self._fills_are_loading = False

    @Slot()
    def start(self) -> None:
        self._request_baskets(
            (self._filters, PageRequest(page=1, page_size=self.PAGE_SIZE))
        )

    def apply_filters(self, values: TradeHistoryFilterValues) -> None:
        if self._closed:
            return
        try:
            filters = trade_history_filter(values)
        except OverflowError:
            self.filter_invalid.emit("To Date is out of range")
            return
        except ValueError as error:
            self.filter_invalid.emit(str(error))
            return

        self._filters = filters
        self._page = 1
        self._total_items = None
        self._request_baskets((filters, PageRequest(page=1, page_size=self.PAGE_SIZE)))

    @Slot()
    def reset_filters(self) -> None:
        if self._closed:
            return
        self._filters = TradeHistoryFilter()
        self._page = 1
        self._total_items = None
        self._request_baskets(
            (self._filters, PageRequest(page=1, page_size=self.PAGE_SIZE))
        )

    def go_to_page(self, page: int) -> None:
        if self._closed or page < 1:
            return
        if self._total_items is not None and page > self._total_pages():
            return

        request = PageRequest(page=page, page_size=self.PAGE_SIZE)
        self._page = page
        self._request_baskets((self._filters, request))

    def select_basket(self, basket_id: UUID) -> None:
        if self._closed:
            return
        self._selected_basket_id = basket_id
        self._request_fills(basket_id)

    @Slot()
    def retry_baskets(self) -> None:
        if self._closed or self._failed_basket_request is None:
            return
        self._request_baskets(self._failed_basket_request)

    @Slot()
    def retry_fills(self) -> None:
        if (
            self._closed
            or self._failed_fill_request is None
            or self._failed_fill_request != self._selected_basket_id
        ):
            return
        self._request_fills(self._failed_fill_request)

    @Slot()
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._basket_generation += 1
        self._fill_generation += 1
        self._pending_basket_request = None
        self._pending_fill_request = None
        self._failed_basket_request = None
        self._failed_fill_request = None
        self._selected_basket_id = None

    def _request_baskets(self, request: BasketRequest) -> None:
        if self._closed:
            return
        if (
            self._basket_task is not None
            and request == self._latest_basket_request
            and self._failed_basket_request is None
        ):
            return

        active_task_can_satisfy_request = (
            self._basket_task is not None
            and request == self._basket_task_request
            and self._failed_basket_request is None
        )
        self._basket_generation += 1
        generation = self._basket_generation
        self._latest_basket_request = request
        self._failed_basket_request = None
        self._invalidate_fills()
        self._set_baskets_loading(True)

        if self._basket_task is not None:
            if active_task_can_satisfy_request:
                self._basket_task_generation = generation
                self._pending_basket_request = None
                return
            self._pending_basket_request = (generation, request)
            return
        self._start_basket_task(generation, request)

    def _start_basket_task(self, generation: int, request: BasketRequest) -> None:
        filters, page_request = request
        task = BackgroundTask(lambda: self._list_baskets(filters, page_request))
        task.signals.succeeded.connect(self._basket_task_succeeded)
        task.signals.failed.connect(self._basket_task_failed)
        task.signals.finished.connect(self._basket_task_finished)
        self._basket_task = task
        self._basket_task_generation = generation
        self._basket_task_request = request
        self._thread_pool.start(task)

    @Slot(object)
    def _basket_task_succeeded(self, result: object) -> None:
        if not self._basket_callbacks_are_current():
            return
        request = self._basket_task_request
        if request is None or not self._valid_basket_result(result, request):
            self._basket_query_failed()
            return

        self._failed_basket_request = None
        self._page = result.page
        self._total_items = result.total_items
        if not result.items:
            self.baskets_empty.emit()
            return

        self.baskets_ready.emit(result)
        first_basket_id = result.items[0].basket_id
        self._selected_basket_id = first_basket_id
        self._request_fills(first_basket_id)

    @Slot(object)
    def _basket_task_failed(self, error: object) -> None:
        del error
        if not self._basket_callbacks_are_current():
            return
        self._basket_query_failed()

    @Slot()
    def _basket_task_finished(self) -> None:
        task = self._basket_task
        generation = self._basket_task_generation
        if task is None or generation is None:
            return

        task.signals.succeeded.disconnect(self._basket_task_succeeded)
        task.signals.failed.disconnect(self._basket_task_failed)
        task.signals.finished.disconnect(self._basket_task_finished)
        self._basket_task = None
        self._basket_task_generation = None
        self._basket_task_request = None

        if self._closed:
            return
        pending = self._pending_basket_request
        self._pending_basket_request = None
        if pending is not None:
            pending_generation, pending_request = pending
            self._start_basket_task(pending_generation, pending_request)
            return
        if generation == self._basket_generation:
            self._set_baskets_loading(False)

    def _basket_query_failed(self) -> None:
        self._failed_basket_request = self._basket_task_request
        self._invalidate_fills()
        self.baskets_unavailable.emit("Trade History unavailable")

    def _basket_callbacks_are_current(self) -> bool:
        return (
            not self._closed
            and self._basket_task is not None
            and self._basket_task_generation == self._basket_generation
        )

    def _valid_basket_result(
        self, result: object, request: BasketRequest
    ) -> TypeGuard[BasketHistoryPage]:
        if not isinstance(result, BasketHistoryPage):
            return False
        page_request = request[1]
        return (
            isinstance(result.page, int)
            and result.page == page_request.page
            and isinstance(result.page_size, int)
            and result.page_size == page_request.page_size
            and isinstance(result.total_items, int)
            and result.total_items >= 0
            and isinstance(result.net_realized_pnl, Decimal)
            and result.net_realized_pnl.is_finite()
            and isinstance(result.items, tuple)
            and len(result.items) <= result.page_size
            and len(result.items) <= result.total_items
            and all(isinstance(item, BasketResult) for item in result.items)
        )

    def _request_fills(self, basket_id: UUID) -> None:
        if self._closed:
            return
        if (
            self._fill_task is not None
            and basket_id == self._latest_fill_request
            and self._failed_fill_request is None
        ):
            return

        active_task_can_satisfy_request = (
            self._fill_task is not None
            and basket_id == self._fill_task_basket_id
            and self._failed_fill_request is None
        )
        self._fill_generation += 1
        generation = self._fill_generation
        self._latest_fill_request = basket_id
        self._failed_fill_request = None
        self._set_fills_loading(True)

        if self._fill_task is not None:
            if active_task_can_satisfy_request:
                self._fill_task_generation = generation
                self._pending_fill_request = None
                return
            self._pending_fill_request = (generation, basket_id)
            return
        self._start_fill_task(generation, basket_id)

    def _start_fill_task(self, generation: int, basket_id: UUID) -> None:
        task = BackgroundTask(lambda: self._list_fills(basket_id))
        task.signals.succeeded.connect(self._fill_task_succeeded)
        task.signals.failed.connect(self._fill_task_failed)
        task.signals.finished.connect(self._fill_task_finished)
        self._fill_task = task
        self._fill_task_generation = generation
        self._fill_task_basket_id = basket_id
        self._thread_pool.start(task)

    @Slot(object)
    def _fill_task_succeeded(self, result: object) -> None:
        if not self._fill_callbacks_are_current():
            return
        basket_id = self._fill_task_basket_id
        if basket_id is None or not self._valid_fill_result(result, basket_id):
            self._fill_query_failed()
            return

        self._failed_fill_request = None
        if not result:
            self.fills_empty.emit(basket_id)
            return
        self.fills_ready.emit(basket_id, result)

    @Slot(object)
    def _fill_task_failed(self, error: object) -> None:
        del error
        if not self._fill_callbacks_are_current():
            return
        self._fill_query_failed()

    @Slot()
    def _fill_task_finished(self) -> None:
        task = self._fill_task
        generation = self._fill_task_generation
        if task is None or generation is None:
            return

        task.signals.succeeded.disconnect(self._fill_task_succeeded)
        task.signals.failed.disconnect(self._fill_task_failed)
        task.signals.finished.disconnect(self._fill_task_finished)
        self._fill_task = None
        self._fill_task_generation = None
        self._fill_task_basket_id = None

        if self._closed:
            return
        pending = self._pending_fill_request
        self._pending_fill_request = None
        if pending is not None:
            pending_generation, pending_basket_id = pending
            self._start_fill_task(pending_generation, pending_basket_id)
            return
        if generation == self._fill_generation:
            self._set_fills_loading(False)

    def _fill_query_failed(self) -> None:
        basket_id = self._fill_task_basket_id
        if basket_id is None:
            return
        self._failed_fill_request = basket_id
        self.fills_unavailable.emit(basket_id, "Trade Fills unavailable")

    def _fill_callbacks_are_current(self) -> bool:
        return (
            not self._closed
            and self._fill_task is not None
            and self._fill_task_generation == self._fill_generation
            and self._fill_task_basket_id == self._selected_basket_id
        )

    @staticmethod
    def _valid_fill_result(
        result: object, basket_id: UUID
    ) -> TypeGuard[tuple[TradeFill, ...]]:
        return (
            isinstance(result, tuple)
            and all(isinstance(fill, TradeFill) for fill in result)
            and all(fill.basket_id == basket_id for fill in result)
        )

    def _invalidate_fills(self) -> None:
        self._fill_generation += 1
        self._selected_basket_id = None
        self._pending_fill_request = None
        self._latest_fill_request = None
        self._failed_fill_request = None
        self._set_fills_loading(False)

    def _set_baskets_loading(self, loading: bool) -> None:
        if self._baskets_are_loading == loading:
            return
        self._baskets_are_loading = loading
        self.baskets_loading.emit(loading)

    def _set_fills_loading(self, loading: bool) -> None:
        if self._fills_are_loading == loading:
            return
        self._fills_are_loading = loading
        self.fills_loading.emit(loading)

    def _total_pages(self) -> int:
        assert self._total_items is not None
        return max(1, (self._total_items + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
