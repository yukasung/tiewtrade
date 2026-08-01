from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

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
    BotRuntimeState,
    DataFreshness,
    WorkspaceReadState,
    empty_workspace_snapshot,
)

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
