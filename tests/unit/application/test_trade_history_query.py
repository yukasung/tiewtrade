from datetime import UTC, datetime

import pytest

from tiewtrade.application.trade_history import PageRequest, TradeHistoryFilter


@pytest.mark.parametrize("field", ["opened_from_utc", "opened_before_utc"])
def test_trade_history_filter_requires_utc_bounds(field: str) -> None:
    with pytest.raises(ValueError, match="UTC"):
        TradeHistoryFilter(**{field: datetime(2026, 1, 1)})


def test_trade_history_filter_rejects_empty_market_identity() -> None:
    with pytest.raises(ValueError, match="symbol"):
        TradeHistoryFilter(symbol="")

    with pytest.raises(ValueError, match="timeframe"):
        TradeHistoryFilter(timeframe="")


def test_trade_history_filter_requires_ordered_time_bounds() -> None:
    boundary = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="before"):
        TradeHistoryFilter(
            opened_from_utc=boundary,
            opened_before_utc=boundary,
        )


@pytest.mark.parametrize(
    ("page", "page_size", "field"),
    [(0, 10, "page"), (1, 0, "page_size")],
)
def test_page_request_requires_positive_values(
    page: int,
    page_size: int,
    field: str,
) -> None:
    with pytest.raises(ValueError, match=field):
        PageRequest(page=page, page_size=page_size)


def test_page_request_calculates_offset() -> None:
    request = PageRequest(page=3, page_size=25)

    assert request.offset == 50
