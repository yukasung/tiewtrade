from datetime import datetime, timedelta

RetryAfter = timedelta | datetime


class MarketDataSourceError(Exception):
    """Base failure exposed by a market-data source adapter."""


class MarketDataRetryableError(MarketDataSourceError):
    """A transient source failure eligible for bounded retry."""


class MarketDataFatalError(MarketDataSourceError):
    """A source failure that cannot succeed through retry."""


class MarketDataRateLimitError(MarketDataSourceError):
    """A source refusal that requires a provider-directed pause."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: RetryAfter | None,
    ) -> None:
        if isinstance(retry_after, datetime) and (
            retry_after.tzinfo is None or retry_after.utcoffset() != timedelta(0)
        ):
            raise ValueError("retry_after datetime must use UTC")
        super().__init__(message)
        self._retry_after = retry_after

    @property
    def retry_after(self) -> RetryAfter | None:
        return self._retry_after
