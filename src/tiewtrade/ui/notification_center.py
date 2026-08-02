"""In-memory notification read model for safe Paper Trading UI feedback."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256

from tiewtrade.application.bot_control import BotLifecycleResult
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    DataFreshness,
)


class NotificationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationCategory(StrEnum):
    SAFETY = "safety"
    MARKET_DATA = "market_data"
    RECOVERY = "recovery"
    RUNTIME = "runtime"


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    fingerprint: str
    occurred_at_utc: datetime
    severity: NotificationSeverity
    category: NotificationCategory
    message: str
    acknowledged: bool = False

    def __post_init__(self) -> None:
        _require_utc(self.occurred_at_utc, "occurred_at_utc")
        if not isinstance(self.severity, NotificationSeverity):
            raise ValueError("severity must be a NotificationSeverity")
        if not isinstance(self.category, NotificationCategory):
            raise ValueError("category must be a NotificationCategory")
        if not isinstance(self.fingerprint, str) or not self.fingerprint:
            raise ValueError("fingerprint must not be empty")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("message must not be empty")
        if type(self.acknowledged) is not bool:
            raise ValueError("acknowledged must be a bool")


class NotificationStore:
    """Owns bounded, non-durable notification rows for one UI instance."""

    def __init__(self, *, max_records: int = 100) -> None:
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self._max_records = max_records
        self._records: tuple[NotificationRecord, ...] = ()
        self._last_runtime_state: BotRuntimeState | None = None

    @property
    def records(self) -> tuple[NotificationRecord, ...]:
        return self._records

    @property
    def unread_count(self) -> int:
        return sum(not record.acknowledged for record in self._records)

    @property
    def highest_unread_severity(self) -> NotificationSeverity | None:
        unread = (
            record.severity for record in self._records if not record.acknowledged
        )
        return max(unread, key=_severity_rank, default=None)

    def publish(
        self,
        result: BotLifecycleResult,
        *,
        occurred_at_utc: datetime,
    ) -> NotificationRecord | None:
        """Publish a notification derived only from a validated lifecycle result."""
        if not isinstance(result, BotLifecycleResult):
            raise ValueError("result must be a BotLifecycleResult")
        _require_utc(occurred_at_utc, "occurred_at_utc")
        notification = self._notification_for(result)
        header = result.workspace.header
        if header is not None:
            self._last_runtime_state = header.runtime_state
        if notification is None:
            return None
        if header is None:
            return None

        severity, category, message = notification
        fingerprint = _fingerprint(header.runtime_state, category, message)
        existing = next(
            (record for record in self._records if record.fingerprint == fingerprint),
            None,
        )
        if existing is not None:
            return existing

        record = NotificationRecord(
            fingerprint=fingerprint,
            occurred_at_utc=occurred_at_utc,
            severity=severity,
            category=category,
            message=message,
        )
        self._records = (record, *self._records[: self._max_records - 1])
        return record

    def acknowledge(self, fingerprint: str) -> bool:
        """Acknowledge one row without changing any durable trading state."""
        for index, record in enumerate(self._records):
            if record.fingerprint != fingerprint:
                continue
            if record.acknowledged:
                return False
            self._records = (
                *self._records[:index],
                replace(record, acknowledged=True),
                *self._records[index + 1 :],
            )
            return True
        return False

    def _notification_for(
        self, result: BotLifecycleResult
    ) -> tuple[NotificationSeverity, NotificationCategory, str] | None:
        header = result.workspace.header
        if header is None:
            return None
        if header.runtime_state is BotRuntimeState.BLOCKED:
            assert result.blocked_reason is not None
            return (
                NotificationSeverity.CRITICAL,
                NotificationCategory.SAFETY,
                result.blocked_reason,
            )
        if header.data_freshness is DataFreshness.STALE:
            return (
                NotificationSeverity.WARNING,
                NotificationCategory.MARKET_DATA,
                "Market data is stale; new entries are paused",
            )
        if self._last_runtime_state is BotRuntimeState.BLOCKED:
            return (
                NotificationSeverity.INFO,
                NotificationCategory.RECOVERY,
                "Paper Bot recovery completed safely",
            )
        if header.runtime_state is BotRuntimeState.RUNNING:
            return (
                NotificationSeverity.INFO,
                NotificationCategory.RUNTIME,
                "Paper Bot is running",
            )
        if header.runtime_state is BotRuntimeState.STOPPED:
            return (
                NotificationSeverity.INFO,
                NotificationCategory.RUNTIME,
                "Paper Bot is stopped",
            )
        return None


def _fingerprint(
    runtime_state: BotRuntimeState,
    category: NotificationCategory,
    message: str,
) -> str:
    safe_event = "\x1f".join((runtime_state.value, category.value, message))
    return sha256(safe_event.encode("utf-8")).hexdigest()


def _severity_rank(severity: NotificationSeverity) -> int:
    return {
        NotificationSeverity.INFO: 1,
        NotificationSeverity.WARNING: 2,
        NotificationSeverity.CRITICAL: 3,
    }[severity]


def _require_utc(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must use UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{name} must use UTC")
