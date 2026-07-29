from decimal import Decimal
from uuid import UUID

from tiewtrade.application.trade_history import (
    BasketHistoryPage,
    PageRequest,
    TradeHistoryFilter,
)
from tiewtrade.trading.trade_history import TradeFill


def empty_basket_page(
    filters: TradeHistoryFilter,
    request: PageRequest,
) -> BasketHistoryPage:
    del filters
    return BasketHistoryPage(
        items=(),
        page=request.page,
        page_size=request.page_size,
        total_items=0,
        net_realized_pnl=Decimal("0"),
    )


def empty_fills(basket_id: UUID) -> tuple[TradeFill, ...]:
    del basket_id
    return ()
