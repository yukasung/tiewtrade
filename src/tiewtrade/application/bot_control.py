from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    DataFreshness,
    TradingWorkspaceSnapshot,
    WorkspaceReadState,
    configured_workspace_snapshot,
)


class BotControlAction(StrEnum):
    START = "start"
    STOP = "stop"
    RECOVER = "recover"


@dataclass(frozen=True, slots=True)
class BotLifecycleResult:
    workspace: TradingWorkspaceSnapshot
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.workspace, TradingWorkspaceSnapshot):
            raise ValueError("workspace must be a TradingWorkspaceSnapshot")
        is_blocked = (
            self.workspace.header is not None
            and self.workspace.header.runtime_state is BotRuntimeState.BLOCKED
        )
        if is_blocked:
            _require_sanitized_reason(self.blocked_reason, "blocked_reason")
        elif self.blocked_reason is not None:
            raise ValueError("blocked_reason is only allowed for BLOCKED workspace")


@dataclass(frozen=True, slots=True)
class BotControlSnapshot:
    state: BotRuntimeState
    session: ConfiguredPaperSession
    workspace: TradingWorkspaceSnapshot
    available_actions: frozenset[BotControlAction]
    progress_message: str | None = None
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, BotRuntimeState):
            raise ValueError("state must be a BotRuntimeState")
        if self.state is BotRuntimeState.NO_SESSION:
            raise ValueError("NO_SESSION cannot create a BotControlSnapshot")
        if not isinstance(self.session, ConfiguredPaperSession):
            raise ValueError("session must be a ConfiguredPaperSession")
        if not isinstance(self.workspace, TradingWorkspaceSnapshot):
            raise ValueError("workspace must be a TradingWorkspaceSnapshot")
        if self.workspace.header is None:
            raise ValueError("workspace requires a header")
        if self.workspace.header.runtime_state is not self.state:
            raise ValueError("workspace header runtime state must match state")
        self._validate_session_ownership()
        _require_actions(self.available_actions)
        self._validate_state_combination()

    @property
    def entry_creation_allowed(self) -> bool:
        header = self.workspace.header
        return (
            self.state is BotRuntimeState.RUNNING
            and self.workspace.read_state is WorkspaceReadState.READY
            and header is not None
            and header.data_freshness is DataFreshness.FRESH
        )

    def _validate_state_combination(self) -> None:
        if self.state is BotRuntimeState.CONFIGURED:
            _require_allowed_actions(
                self.available_actions,
                frozenset({BotControlAction.START}),
                self.state,
            )
            _require_absent(self.progress_message, "progress_message")
            _require_absent(self.blocked_reason, "blocked_reason")
        elif self.state in (BotRuntimeState.STARTING, BotRuntimeState.STOPPING):
            _require_allowed_actions(self.available_actions, frozenset(), self.state)
            _require_text(self.progress_message, "progress_message")
            _require_absent(self.blocked_reason, "blocked_reason")
        elif self.state is BotRuntimeState.RUNNING:
            _require_allowed_actions(
                self.available_actions,
                frozenset({BotControlAction.STOP}),
                self.state,
            )
            _require_absent(self.progress_message, "progress_message")
            _require_absent(self.blocked_reason, "blocked_reason")
        elif self.state is BotRuntimeState.STOPPED:
            _require_allowed_actions(self.available_actions, frozenset(), self.state)
            _require_absent(self.progress_message, "progress_message")
            _require_absent(self.blocked_reason, "blocked_reason")
        elif self.state is BotRuntimeState.BLOCKED:
            _require_allowed_actions(
                self.available_actions,
                frozenset({BotControlAction.RECOVER}),
                self.state,
            )
            _require_absent(self.progress_message, "progress_message")
            _require_sanitized_reason(self.blocked_reason, "blocked_reason")

    def _validate_session_ownership(self) -> None:
        header = self.workspace.header
        assert header is not None
        session_facts = {
            "symbol": self.session.market_data.symbol,
            "timeframe": self.session.market_data.timeframe,
            "trade_mode": self.session.config.trade_mode,
            "market_type": self.session.config.market_type,
            "preset_version": self.session.config.preset_version,
        }
        for field, expected in session_facts.items():
            if getattr(header, field) != expected:
                raise ValueError(f"workspace header {field} must match session")


def configured_bot_control(
    session: ConfiguredPaperSession,
    *,
    observed_at_utc: datetime,
    actions: frozenset[BotControlAction] = frozenset(),
) -> BotControlSnapshot:
    return BotControlSnapshot(
        state=BotRuntimeState.CONFIGURED,
        session=session,
        workspace=configured_workspace_snapshot(
            session, observed_at_utc=observed_at_utc
        ),
        available_actions=actions,
    )


def transition_bot_control(
    current: BotControlSnapshot,
    *,
    result: BotLifecycleResult,
    actions: frozenset[BotControlAction] = frozenset(),
    progress_message: str | None = None,
) -> BotControlSnapshot:
    if not isinstance(current, BotControlSnapshot):
        raise ValueError("current must be a BotControlSnapshot")
    if not isinstance(result, BotLifecycleResult):
        raise ValueError("result must be a BotLifecycleResult")
    header = result.workspace.header
    if header is None:
        raise ValueError("result workspace requires a header")
    state = header.runtime_state
    _require_workspace_continuity(current.workspace, result.workspace)
    if state not in _ALLOWED_TARGET_STATES[current.state]:
        raise ValueError(
            f"Invalid Bot Control transition: {current.state.value} -> {state.value}"
        )
    return BotControlSnapshot(
        state=state,
        session=current.session,
        workspace=result.workspace,
        available_actions=actions,
        progress_message=progress_message,
        blocked_reason=result.blocked_reason,
    )


def blocked_bot_control(
    current: BotControlSnapshot,
    *,
    reason: str,
    actions: frozenset[BotControlAction] = frozenset(),
) -> BotControlSnapshot:
    workspace = workspace_with_runtime_state(current.workspace, BotRuntimeState.BLOCKED)
    return transition_bot_control(
        current,
        result=BotLifecycleResult(workspace=workspace, blocked_reason=reason),
        actions=actions,
    )


def workspace_with_runtime_state(
    workspace: TradingWorkspaceSnapshot,
    state: BotRuntimeState,
    *,
    data_freshness: DataFreshness | None = None,
) -> TradingWorkspaceSnapshot:
    if not isinstance(workspace, TradingWorkspaceSnapshot):
        raise ValueError("workspace must be a TradingWorkspaceSnapshot")
    if workspace.header is None:
        raise ValueError("workspace requires a header")
    if not isinstance(state, BotRuntimeState) or state is BotRuntimeState.NO_SESSION:
        raise ValueError("state must be a BotRuntimeState other than NO_SESSION")
    header = replace(
        workspace.header,
        runtime_state=state,
        data_freshness=(
            workspace.header.data_freshness
            if data_freshness is None
            else data_freshness
        ),
    )
    return replace(workspace, header=header)


_ALLOWED_TARGET_STATES: dict[BotRuntimeState, frozenset[BotRuntimeState]] = {
    BotRuntimeState.CONFIGURED: frozenset(
        {BotRuntimeState.STARTING, BotRuntimeState.BLOCKED}
    ),
    BotRuntimeState.STARTING: frozenset(
        {BotRuntimeState.RUNNING, BotRuntimeState.BLOCKED}
    ),
    BotRuntimeState.RUNNING: frozenset(
        {BotRuntimeState.STOPPING, BotRuntimeState.BLOCKED}
    ),
    BotRuntimeState.STOPPING: frozenset(
        {BotRuntimeState.STOPPED, BotRuntimeState.BLOCKED}
    ),
    BotRuntimeState.STOPPED: frozenset(),
    BotRuntimeState.BLOCKED: frozenset(
        {
            BotRuntimeState.CONFIGURED,
            BotRuntimeState.STOPPED,
            BotRuntimeState.BLOCKED,
        }
    ),
}

_SAFE_BLOCKED_REASONS = frozenset(
    {
        "Paper Bot could not be started",
        "Paper Bot could not be stopped",
        "Paper Bot recovery failed",
        "Paper Bot recovery required",
    }
)


def _require_actions(actions: frozenset[BotControlAction]) -> None:
    if type(actions) is not frozenset or not all(
        isinstance(action, BotControlAction) for action in actions
    ):
        raise ValueError("available_actions must be a frozenset of BotControlAction")


def _require_allowed_actions(
    actions: frozenset[BotControlAction],
    allowed: frozenset[BotControlAction],
    state: BotRuntimeState,
) -> None:
    if not actions <= allowed:
        raise ValueError(f"{state.name} only permits its lifecycle action")


def _require_absent(value: str | None, name: str) -> None:
    if value is not None:
        raise ValueError(f"{name} is not allowed for this state")


def _require_text(value: str | None, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_sanitized_reason(value: str | None, name: str) -> None:
    _require_text(value, name)
    assert value is not None
    if value not in _SAFE_BLOCKED_REASONS:
        raise ValueError(f"{name} must be sanitized")


def _require_workspace_continuity(
    current: TradingWorkspaceSnapshot,
    result: TradingWorkspaceSnapshot,
) -> None:
    if (
        result.read_state is not current.read_state
        or result.open_orders != current.open_orders
        or result.position_basket != current.position_basket
        or result.data_as_of_utc != current.data_as_of_utc
    ):
        raise ValueError("result must preserve workspace continuity")
