from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.bot_control import BotLifecycleResult
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    DataFreshness,
    configured_workspace_snapshot,
    stale_workspace_snapshot,
)
from tiewtrade.ui.notification_center import (
    NotificationCategory,
    NotificationSeverity,
    NotificationStore,
)

OBSERVED_AT = datetime(2026, 8, 2, 9, 30, tzinfo=UTC)


def _result(
    state: BotRuntimeState,
    *,
    freshness: DataFreshness = DataFreshness.FRESH,
    blocked_reason: str | None = None,
) -> BotLifecycleResult:
    workspace = configured_workspace_snapshot(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )
    assert workspace.header is not None
    workspace = replace(
        workspace,
        header=replace(
            workspace.header,
            runtime_state=state,
            data_freshness=DataFreshness.FRESH,
        ),
    )
    if freshness is DataFreshness.STALE:
        workspace = stale_workspace_snapshot(workspace)
    return BotLifecycleResult(
        workspace=workspace,
        blocked_reason=blocked_reason,
    )


def test_publish_maps_blocked_to_sanitized_critical_safety_notification() -> None:
    store = NotificationStore()

    record = store.publish(
        _result(
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot recovery required",
        ),
        occurred_at_utc=OBSERVED_AT,
    )

    assert record is not None
    assert record.occurred_at_utc == OBSERVED_AT
    assert record.severity is NotificationSeverity.CRITICAL
    assert record.category is NotificationCategory.SAFETY
    assert record.message == "Paper Bot recovery required"
    assert "sqlite" not in record.message.lower()
    assert store.unread_count == 1
    assert store.highest_unread_severity is NotificationSeverity.CRITICAL


def test_publish_maps_stale_workspace_to_warning_without_raw_message() -> None:
    store = NotificationStore()

    record = store.publish(
        _result(BotRuntimeState.RUNNING, freshness=DataFreshness.STALE),
        occurred_at_utc=OBSERVED_AT,
    )

    assert record is not None
    assert record.severity is NotificationSeverity.WARNING
    assert record.category is NotificationCategory.MARKET_DATA
    assert record.message == "Market data is stale; new entries are paused"


def test_publish_records_runtime_transitions_and_safe_recovery() -> None:
    store = NotificationStore()

    running = store.publish(
        _result(BotRuntimeState.RUNNING), occurred_at_utc=OBSERVED_AT
    )
    stopped = store.publish(
        _result(BotRuntimeState.STOPPED),
        occurred_at_utc=OBSERVED_AT + timedelta(minutes=1),
    )
    store.publish(
        _result(
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot recovery required",
        ),
        occurred_at_utc=OBSERVED_AT + timedelta(minutes=2),
    )
    recovered = store.publish(
        _result(BotRuntimeState.STOPPED),
        occurred_at_utc=OBSERVED_AT + timedelta(minutes=3),
    )

    assert running is not None
    assert (running.category, running.message) == (
        NotificationCategory.RUNTIME,
        "Paper Bot is running",
    )
    assert stopped is not None
    assert stopped.message == "Paper Bot is stopped"
    assert recovered is not None
    assert (recovered.category, recovered.message) == (
        NotificationCategory.RECOVERY,
        "Paper Bot recovery completed safely",
    )


def test_publish_deduplicates_safe_fingerprint_and_keeps_records_bounded() -> None:
    store = NotificationStore(max_records=2)
    blocked = _result(
        BotRuntimeState.BLOCKED,
        blocked_reason="Paper Bot recovery required",
    )

    first = store.publish(blocked, occurred_at_utc=OBSERVED_AT)
    duplicate = store.publish(
        blocked, occurred_at_utc=OBSERVED_AT + timedelta(minutes=1)
    )
    store.publish(
        _result(BotRuntimeState.RUNNING),
        occurred_at_utc=OBSERVED_AT + timedelta(minutes=2),
    )
    store.publish(
        _result(BotRuntimeState.STOPPED),
        occurred_at_utc=OBSERVED_AT + timedelta(minutes=3),
    )

    assert first is not None
    assert duplicate is first
    assert len(store.records) == 2
    assert tuple(record.message for record in store.records) == (
        "Paper Bot is stopped",
        "Paper Bot recovery completed safely",
    )


def test_acknowledge_is_idempotent_and_updates_unread_highest_severity() -> None:
    store = NotificationStore()
    warning = store.publish(
        _result(BotRuntimeState.RUNNING, freshness=DataFreshness.STALE),
        occurred_at_utc=OBSERVED_AT,
    )
    critical = store.publish(
        _result(
            BotRuntimeState.BLOCKED,
            blocked_reason="Paper Bot recovery required",
        ),
        occurred_at_utc=OBSERVED_AT + timedelta(minutes=1),
    )

    assert warning is not None
    assert critical is not None
    assert store.acknowledge(critical.fingerprint) is True
    assert store.acknowledge(critical.fingerprint) is False
    assert store.unread_count == 1
    assert store.highest_unread_severity is NotificationSeverity.WARNING


def test_publish_rejects_non_utc_timestamp() -> None:
    store = NotificationStore()

    with pytest.raises(ValueError, match="occurred_at_utc must use UTC"):
        store.publish(
            _result(BotRuntimeState.RUNNING),
            occurred_at_utc=OBSERVED_AT.astimezone(timezone(timedelta(hours=7))),
        )
