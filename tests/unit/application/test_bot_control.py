from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.bot_control import (
    BotControlAction,
    BotControlSnapshot,
    BotLifecycleResult,
    blocked_bot_control,
    configured_bot_control,
    transition_bot_control,
    workspace_with_runtime_state,
)
from tiewtrade.application.trading_workspace import (
    BasketSnapshot,
    BotRuntimeState,
    DataFreshness,
    OpenOrderSnapshot,
    WorkspaceHeaderSnapshot,
    WorkspaceReadState,
    empty_workspace_snapshot,
)
from tiewtrade.trading.session_config import MarketType, TradeMode

OBSERVED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)


def test_configured_control_exposes_summary_without_runtime_actions() -> None:
    snapshot = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=OBSERVED_AT,
        actions=frozenset(),
    )

    assert snapshot.state is BotRuntimeState.CONFIGURED
    assert snapshot.workspace.header is not None
    assert snapshot.workspace.header.runtime_state is BotRuntimeState.CONFIGURED
    assert snapshot.available_actions == frozenset()
    assert snapshot.entry_creation_allowed is False


def test_running_control_uses_workspace_facts_and_allows_only_stop() -> None:
    configured = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=OBSERVED_AT,
        actions=frozenset({BotControlAction.START}),
    )
    running_workspace = workspace_with_runtime_state(
        configured.workspace,
        BotRuntimeState.RUNNING,
        data_freshness=DataFreshness.FRESH,
    )

    starting = transition_bot_control(
        configured,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                configured.workspace,
                BotRuntimeState.STARTING,
            ),
        ),
        progress_message="Starting Paper Bot",
    )
    running = transition_bot_control(
        starting,
        result=BotLifecycleResult(workspace=running_workspace),
        actions=frozenset({BotControlAction.STOP}),
    )

    assert running.available_actions == frozenset({BotControlAction.STOP})
    assert running.entry_creation_allowed is True
    assert running.workspace is running_workspace
    assert running.session is configured.session


def test_stopping_and_stopped_disallow_actions_and_entries() -> None:
    running = _running_control()
    stopping = transition_bot_control(
        running,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                running.workspace,
                BotRuntimeState.STOPPING,
            )
        ),
        progress_message="Stopping Paper Bot",
    )
    stopped = transition_bot_control(
        stopping,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                stopping.workspace,
                BotRuntimeState.STOPPED,
            )
        ),
    )

    assert stopping.available_actions == frozenset()
    assert stopping.entry_creation_allowed is False
    assert stopped.available_actions == frozenset()
    assert stopped.entry_creation_allowed is False


def test_blocked_control_requires_sanitized_reason_and_only_allows_recovery() -> None:
    running = _running_control()

    for reason in (
        "Paper Bot could not be started",
        "Paper Bot could not be stopped",
        "Paper Bot recovery failed",
    ):
        blocked = blocked_bot_control(
            running,
            reason=reason,
            actions=frozenset({BotControlAction.RECOVER}),
        )

        assert blocked.state is BotRuntimeState.BLOCKED
        assert blocked.blocked_reason == reason
        assert blocked.available_actions == frozenset({BotControlAction.RECOVER})
        assert blocked.entry_creation_allowed is False


@pytest.mark.parametrize(
    "reason",
    [
        "RuntimeError: failed at /private/tmp",
        "ValueError: api_key=secret",
        "request_id=abc123 payload=order",
    ],
)
def test_blocked_control_rejects_raw_exception_credential_and_payload_reasons(
    reason: str,
) -> None:
    with pytest.raises(ValueError, match="blocked_reason"):
        blocked_bot_control(_running_control(), reason=reason)


@pytest.mark.parametrize(
    ("state", "actions", "progress_message", "blocked_reason", "expected"),
    [
        (
            BotRuntimeState.CONFIGURED,
            frozenset({BotControlAction.STOP}),
            None,
            None,
            "CONFIGURED",
        ),
        (
            BotRuntimeState.STARTING,
            frozenset({BotControlAction.START}),
            "Starting Paper Bot",
            None,
            "STARTING",
        ),
        (
            BotRuntimeState.STOPPING,
            frozenset(),
            None,
            None,
            "progress_message",
        ),
        (
            BotRuntimeState.RUNNING,
            frozenset({BotControlAction.RECOVER}),
            None,
            None,
            "RUNNING",
        ),
        (
            BotRuntimeState.STOPPED,
            frozenset({BotControlAction.STOP}),
            None,
            None,
            "STOPPED",
        ),
        (
            BotRuntimeState.BLOCKED,
            frozenset({BotControlAction.RECOVER}),
            None,
            None,
            "blocked_reason",
        ),
        (
            BotRuntimeState.NO_SESSION,
            frozenset(),
            None,
            None,
            "NO_SESSION",
        ),
    ],
)
def test_control_rejects_invalid_action_and_state_combinations(
    state: BotRuntimeState,
    actions: frozenset[BotControlAction],
    progress_message: str | None,
    blocked_reason: str | None,
    expected: str,
) -> None:
    configured = configured_bot_control(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )
    if state is BotRuntimeState.NO_SESSION:
        assert configured.workspace.header is not None
        workspace = replace(
            configured.workspace,
            header=replace(
                configured.workspace.header,
                runtime_state=BotRuntimeState.NO_SESSION,
            ),
        )
    else:
        workspace = workspace_with_runtime_state(configured.workspace, state)

    with pytest.raises(ValueError, match=expected):
        BotControlSnapshot(
            state=state,
            session=configured.session,
            workspace=workspace,
            available_actions=actions,
            progress_message=progress_message,
            blocked_reason=blocked_reason,
        )


def test_control_rejects_workspace_header_state_mismatch() -> None:
    configured = configured_bot_control(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )

    with pytest.raises(ValueError, match="workspace header runtime state"):
        BotControlSnapshot(
            state=BotRuntimeState.RUNNING,
            session=configured.session,
            workspace=configured.workspace,
            available_actions=frozenset({BotControlAction.STOP}),
        )


@pytest.mark.parametrize(
    ("field", "change_header"),
    [
        ("symbol", lambda header: replace(header, symbol="ETHUSDT")),
        ("timeframe", lambda header: replace(header, timeframe="4h")),
        ("trade_mode", lambda header: replace(header, trade_mode=TradeMode.LIVE)),
        (
            "market_type",
            lambda header: replace(header, market_type=MarketType.FUTURES),
        ),
        (
            "preset_version",
            lambda header: replace(header, preset_version="rsi-step-grid-v2"),
        ),
    ],
)
def test_control_rejects_header_facts_owned_by_another_session(
    field: str,
    change_header: Callable[[WorkspaceHeaderSnapshot], WorkspaceHeaderSnapshot],
) -> None:
    configured = configured_bot_control(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )
    assert configured.workspace.header is not None
    mismatched_workspace = replace(
        configured.workspace,
        header=change_header(configured.workspace.header),
    )

    with pytest.raises(ValueError, match=f"workspace header {field}"):
        BotControlSnapshot(
            state=BotRuntimeState.CONFIGURED,
            session=configured.session,
            workspace=mismatched_workspace,
            available_actions=frozenset(),
        )


def test_lifecycle_result_allows_blocked_reason_only_for_blocked_workspace() -> None:
    configured = configured_bot_control(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )

    with pytest.raises(ValueError, match="blocked_reason"):
        BotLifecycleResult(
            workspace=configured.workspace,
            blocked_reason="Paper Bot could not be started",
        )


def test_transition_accepts_only_state_diagram_edges() -> None:
    configured = configured_bot_control(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )

    with pytest.raises(ValueError, match="Invalid Bot Control transition"):
        transition_bot_control(
            configured,
            result=BotLifecycleResult(
                workspace=workspace_with_runtime_state(
                    configured.workspace, BotRuntimeState.RUNNING
                )
            ),
        )


@pytest.mark.parametrize(
    "changed_workspace",
    [
        pytest.param(lambda workspace: replace(workspace, orders=()), id="orders"),
        pytest.param(lambda workspace: replace(workspace, basket=None), id="basket"),
        pytest.param(
            lambda workspace: replace(
                workspace,
                data_as_of_utc=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
            ),
            id="data-as-of",
        ),
        pytest.param(
            lambda workspace: replace(workspace, read_state=WorkspaceReadState.LOADING),
            id="read-state",
        ),
    ],
)
def test_transition_rejects_result_that_changes_workspace_continuity(
    changed_workspace: object,
) -> None:
    running = _running_control_with_workspace_facts()
    stopping_workspace = workspace_with_runtime_state(
        running.workspace, BotRuntimeState.STOPPING
    )
    assert callable(changed_workspace)

    with pytest.raises(ValueError, match="workspace continuity"):
        transition_bot_control(
            running,
            result=BotLifecycleResult(workspace=changed_workspace(stopping_workspace)),
            progress_message="Stopping Paper Bot",
        )


def test_blocked_control_can_recover_to_configured_or_stopped() -> None:
    blocked = blocked_bot_control(
        _running_control(), reason="Paper Bot could not be started"
    )

    recovered = transition_bot_control(
        blocked,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                blocked.workspace, BotRuntimeState.CONFIGURED
            )
        ),
        actions=frozenset({BotControlAction.START}),
    )
    stopped = transition_bot_control(
        blocked,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                blocked.workspace, BotRuntimeState.STOPPED
            )
        ),
    )

    assert recovered.state is BotRuntimeState.CONFIGURED
    assert stopped.state is BotRuntimeState.STOPPED


def test_blocked_control_can_remain_blocked_through_application_transition() -> None:
    blocked = blocked_bot_control(
        _running_control_with_workspace_facts(),
        reason="Paper Bot could not be started",
    )
    result_workspace = workspace_with_runtime_state(
        blocked.workspace,
        BotRuntimeState.BLOCKED,
        data_freshness=DataFreshness.UNAVAILABLE,
    )

    still_blocked = transition_bot_control(
        blocked,
        result=BotLifecycleResult(
            workspace=result_workspace,
            blocked_reason="Paper Bot recovery failed",
        ),
        actions=frozenset({BotControlAction.RECOVER}),
    )

    assert still_blocked.workspace is result_workspace
    assert still_blocked.workspace.orders is blocked.workspace.orders
    assert still_blocked.workspace.basket is blocked.workspace.basket
    assert still_blocked.blocked_reason == "Paper Bot recovery failed"


def test_workspace_state_helper_preserves_workspace_facts() -> None:
    configured = configured_bot_control(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )

    changed = workspace_with_runtime_state(
        configured.workspace,
        BotRuntimeState.RUNNING,
        data_freshness=DataFreshness.FRESH,
    )

    assert changed.read_state is WorkspaceReadState.READY
    assert changed.orders is configured.workspace.orders
    assert changed.basket is configured.workspace.basket
    assert changed.data_as_of_utc is configured.workspace.data_as_of_utc
    assert changed.header is not configured.workspace.header
    assert changed.header is not None
    assert changed.header.runtime_state is BotRuntimeState.RUNNING
    assert changed.header.data_freshness is DataFreshness.FRESH


def test_control_snapshot_is_frozen() -> None:
    snapshot = configured_bot_control(
        configured_spot_session(), observed_at_utc=OBSERVED_AT
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.state = BotRuntimeState.RUNNING  # type: ignore[misc]
    with pytest.raises(ValueError, match="workspace requires a header"):
        workspace_with_runtime_state(
            empty_workspace_snapshot(), BotRuntimeState.RUNNING
        )


def _running_control() -> BotControlSnapshot:
    configured = configured_bot_control(
        configured_spot_session(),
        observed_at_utc=OBSERVED_AT,
        actions=frozenset({BotControlAction.START}),
    )
    starting = transition_bot_control(
        configured,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                configured.workspace, BotRuntimeState.STARTING
            )
        ),
        progress_message="Starting Paper Bot",
    )
    return transition_bot_control(
        starting,
        result=BotLifecycleResult(
            workspace=workspace_with_runtime_state(
                starting.workspace,
                BotRuntimeState.RUNNING,
                data_freshness=DataFreshness.FRESH,
            )
        ),
        actions=frozenset({BotControlAction.STOP}),
    )


def _running_control_with_workspace_facts() -> BotControlSnapshot:
    running = _running_control()
    workspace = replace(
        running.workspace,
        orders=(
            OpenOrderSnapshot(
                order_id="order-1",
                created_at_utc=OBSERVED_AT,
                symbol="BTCUSDT",
                side="SELL",
                order_type="LIMIT",
                price=Decimal("66000.123456789012345678"),
                quantity=Decimal("1"),
                filled_quantity=Decimal("0"),
                status="NEW",
            ),
        ),
        basket=BasketSnapshot(
            symbol="BTCUSDT",
            market_type="spot",
            entry_count=2,
            total_quantity=Decimal("1"),
            average_entry_price=Decimal("64000.123456789012345678"),
            current_price=Decimal("65000.123456789012345678"),
            take_profit_price=Decimal("66000.123456789012345678"),
            unrealized_pnl=Decimal("1000"),
            liquidation_price=None,
            lifecycle="open",
            updated_at_utc=OBSERVED_AT,
        ),
    )
    return replace(running, workspace=workspace)
