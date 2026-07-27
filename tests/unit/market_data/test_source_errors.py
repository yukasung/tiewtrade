from datetime import UTC, datetime, timedelta, timezone

import pytest

from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
)


def test_source_error_types_have_distinct_actions() -> None:
    assert not issubclass(MarketDataFatalError, MarketDataRetryableError)
    assert not issubclass(MarketDataRateLimitError, MarketDataRetryableError)


@pytest.mark.parametrize(
    "retry_after",
    [timedelta(seconds=30), datetime(2026, 1, 1, tzinfo=UTC), None],
)
def test_rate_limit_error_preserves_retry_directive(
    retry_after: timedelta | datetime | None,
) -> None:
    error = MarketDataRateLimitError("rate limited", retry_after=retry_after)

    assert error.retry_after == retry_after


def test_rate_limit_error_retry_directive_is_read_only() -> None:
    error = MarketDataRateLimitError(
        "rate limited",
        retry_after=timedelta(seconds=30),
    )

    with pytest.raises(AttributeError):
        setattr(error, "retry_after", timedelta(seconds=60))  # noqa: B010


def test_rate_limit_error_rejects_naive_http_date() -> None:
    with pytest.raises(ValueError, match="retry_after datetime must use UTC"):
        MarketDataRateLimitError(
            "rate limited",
            retry_after=datetime(2026, 1, 1),
        )


def test_rate_limit_error_rejects_non_utc_http_date() -> None:
    with pytest.raises(ValueError, match="retry_after datetime must use UTC"):
        MarketDataRateLimitError(
            "rate limited",
            retry_after=datetime(
                2026,
                1,
                1,
                tzinfo=timezone(timedelta(hours=7)),
            ),
        )
