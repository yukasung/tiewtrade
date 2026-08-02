from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from threading import Event, Lock
from uuid import UUID

from tiewtrade.application.bot_control import (
    BotControlSnapshot,
    BotLifecycleResult,
    workspace_with_runtime_state,
)
from tiewtrade.application.database_compatibility import DatabaseCompatibilityError
from tiewtrade.application.paper_runtime import PaperRuntimeController
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    CreatePaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)
from tiewtrade.application.trade_history import (
    BasketHistoryPage,
    PageRequest,
    TradeHistoryFilter,
)
from tiewtrade.application.trading_workspace import BotRuntimeState
from tiewtrade.decimal_context import configure_decimal_context
from tiewtrade.integrations.binance.public_market_data import BinancePublicMarketData
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import (
    SQLiteDatabase,
    UnsupportedDatabaseSchemaError,
)
from tiewtrade.integrations.sqlite.paper_runtime_lifecycle import (
    SQLitePaperRuntimeLifecycle,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.session_config import MarketType
from tiewtrade.trading.symbol_rules import SymbolRules
from tiewtrade.trading.trade_history import TradeFill
from tiewtrade.ui.bot_lifecycle_workflow import RuntimeSnapshotRelay
from tiewtrade.ui.desktop import run_desktop as run_desktop_ui

_RUNTIME_SHUTDOWN_TIMEOUT_SECONDS = 30.0


class _PaperRuntimeActions:
    def __init__(
        self,
        *,
        lifecycle: SQLitePaperRuntimeLifecycle,
        trade_history: SQLiteTradeHistory,
        runtime_snapshots: RuntimeSnapshotRelay,
        prepare_database: Callable[[], None],
    ) -> None:
        self._lifecycle = lifecycle
        self._trade_history = trade_history
        self._runtime_snapshots = runtime_snapshots
        self._prepare_database = prepare_database
        self._lock = Lock()
        self._controller: PaperRuntimeController | None = None
        self._session: ConfiguredPaperSession | None = None
        self._operation: str | None = None
        self._operation_finished = Event()
        self._operation_finished.set()
        self._shutdown_requested = False
        self._shutdown_stop_claimed = False

    def initialize(self, snapshot: BotControlSnapshot) -> BotLifecycleResult:
        self._prepare_database()
        self._begin_operation("initialize")
        controller: PaperRuntimeController | None = None
        try:
            controller = self._new_controller(snapshot.session)
            with self._lock:
                self._controller = controller
                self._session = snapshot.session
            result = controller.inspect_startup(snapshot.session)
        finally:
            self._finish_operation(
                "initialize",
                controller=controller,
                session=snapshot.session,
            )
        return _lifecycle_result_for_ui(snapshot, result)

    def start(self, snapshot: BotControlSnapshot) -> BotLifecycleResult:
        self._prepare_database()
        self._begin_operation("start")
        controller: PaperRuntimeController | None = None
        try:
            controller = self._new_controller(snapshot.session)
            with self._lock:
                self._controller = controller
                self._session = snapshot.session
            result = controller.start(snapshot.session)
        finally:
            self._finish_operation(
                "start",
                controller=controller,
                session=snapshot.session,
            )
        return _lifecycle_result_for_ui(snapshot, result)

    def stop(self, snapshot: BotControlSnapshot) -> BotLifecycleResult:
        self._begin_operation("stop")
        controller: PaperRuntimeController | None = None
        try:
            controller = self._current_controller(snapshot.session)
            result = controller.stop(snapshot.session)
        finally:
            self._finish_operation(
                "stop",
                controller=controller,
                session=snapshot.session,
            )
        return _lifecycle_result_for_ui(snapshot, result)

    def recover(self, snapshot: BotControlSnapshot) -> BotLifecycleResult:
        self._prepare_database()
        self._begin_operation("recover")
        controller: PaperRuntimeController | None = None
        try:
            with self._lock:
                controller = (
                    self._controller if self._session == snapshot.session else None
                )
            if controller is None:
                controller = self._new_controller(snapshot.session)
                with self._lock:
                    self._controller = controller
                    self._session = snapshot.session
            result = controller.recover(snapshot.session)
        finally:
            self._finish_operation(
                "recover",
                controller=controller,
                session=snapshot.session,
            )
        return _lifecycle_result_for_ui(snapshot, result)

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_requested = True
            if self._operation is not None:
                operation_finished = self._operation_finished
                controller = None
                session = None
            elif self._shutdown_stop_claimed:
                return
            else:
                self._shutdown_stop_claimed = True
                operation_finished = None
                controller = self._controller
                session = self._session
        if operation_finished is not None:
            operation_finished.wait(_RUNTIME_SHUTDOWN_TIMEOUT_SECONDS)
            return
        self._stop_controller_if_needed(controller, session)

    def _begin_operation(self, operation: str) -> None:
        with self._lock:
            if self._shutdown_requested:
                raise RuntimeError("Paper Runtime is shutting down")
            if self._operation is not None:
                raise RuntimeError("Paper Runtime operation is already in progress")
            self._operation = operation
            self._operation_finished.clear()

    def _finish_operation(
        self,
        operation: str,
        *,
        controller: PaperRuntimeController | None,
        session: ConfiguredPaperSession,
    ) -> None:
        with self._lock:
            shutdown_stop = (
                self._shutdown_requested
                and not self._shutdown_stop_claimed
                and operation != "stop"
            )
            if self._shutdown_requested and not self._shutdown_stop_claimed:
                self._shutdown_stop_claimed = True
        try:
            if shutdown_stop:
                self._stop_controller_if_needed(controller, session)
        finally:
            with self._lock:
                if self._operation == operation:
                    self._operation = None
                self._operation_finished.set()

    def _stop_controller_if_needed(
        self,
        controller: PaperRuntimeController | None,
        session: ConfiguredPaperSession | None,
    ) -> None:
        if controller is None or session is None:
            return
        try:
            result = controller.current_result
        except RuntimeError:
            return
        header = result.workspace.header
        if header is None or header.runtime_state not in {
            BotRuntimeState.RUNNING,
            BotRuntimeState.BLOCKED,
        }:
            return
        controller.stop(session)

    def _new_controller(
        self,
        session: ConfiguredPaperSession,
    ) -> PaperRuntimeController:
        publish = self._runtime_snapshots.new_generation()
        controller: PaperRuntimeController | None = None

        def publish_current_result(workspace: object) -> None:
            del workspace
            if controller is not None:
                publish(controller.current_result)

        controller = PaperRuntimeController(
            lifecycle=self._lifecycle,
            trade_history=self._trade_history,
            symbol_rules=_symbol_rules_for(session),
            source_factory=BinancePublicMarketData,
            snapshot_callback=publish_current_result,
        )
        return controller

    def _current_controller(
        self,
        session: ConfiguredPaperSession,
    ) -> PaperRuntimeController:
        with self._lock:
            controller = self._controller
            active_session = self._session
        if controller is None or active_session != session:
            raise RuntimeError("Paper Runtime is not active for this Session")
        return controller


def _lifecycle_result_for_ui(
    current: BotControlSnapshot,
    result: BotLifecycleResult,
) -> BotLifecycleResult:
    header = result.workspace.header
    if header is None:
        raise ValueError("Paper Runtime result requires a header")
    return BotLifecycleResult(
        workspace=workspace_with_runtime_state(
            current.workspace,
            header.runtime_state,
            data_freshness=(
                None
                if header.runtime_state is BotRuntimeState.BLOCKED
                else header.data_freshness
            ),
        ),
        blocked_reason=result.blocked_reason,
    )


def _symbol_rules_for(session: ConfiguredPaperSession) -> SymbolRules:
    return SymbolRules(
        symbol=session.market_data.symbol,
        tick_size=(
            Decimal("0.01")
            if session.config.market_type is MarketType.SPOT
            else Decimal("0.1")
        ),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )


def run_desktop(database_path: Path | None = None) -> int:
    configure_decimal_context()
    resolved_database_path = database_path or default_database_path()
    database = SQLiteDatabase(resolved_database_path)
    store = SQLiteActivePaperSessions(database)
    history = SQLiteTradeHistory(database)
    create_session = CreatePaperSession(create_active=store.create)
    database_preparation_lock = Lock()

    def prepare_database() -> None:
        with database_preparation_lock:
            resolved_database_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                database.migrate()
            except UnsupportedDatabaseSchemaError as error:
                raise DatabaseCompatibilityError from error

    def create_after_migration(
        values: PaperSessionSetupValues,
    ) -> PaperSessionCreateOutcome:
        prepare_database()
        return create_session.execute(values)

    def load_after_migration() -> ConfiguredPaperSession | None:
        prepare_database()
        return store.get_active()

    def list_baskets_after_migration(
        filters: TradeHistoryFilter,
        page: PageRequest,
    ) -> BasketHistoryPage:
        prepare_database()
        return history.list_baskets(filters, page)

    def list_fills_after_migration(basket_id: UUID) -> tuple[TradeFill, ...]:
        prepare_database()
        return history.list_fills(basket_id)

    runtime_snapshots = RuntimeSnapshotRelay()
    runtime_actions = _PaperRuntimeActions(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=history,
        runtime_snapshots=runtime_snapshots,
        prepare_database=prepare_database,
    )

    return run_desktop_ui(
        create_session=create_after_migration,
        load_active=load_after_migration,
        list_baskets=list_baskets_after_migration,
        list_fills=list_fills_after_migration,
        start_bot=runtime_actions.start,
        stop_bot=runtime_actions.stop,
        recover_bot=runtime_actions.recover,
        initialize_bot=runtime_actions.initialize,
        runtime_snapshots=runtime_snapshots,
        shutdown_runtime=runtime_actions.shutdown,
    )


def default_database_path() -> Path:
    directory = Path.home() / "Library" / "Application Support" / "TiewTrade"
    return directory / "tiewtrade.sqlite3"


if __name__ == "__main__":
    raise SystemExit(run_desktop())
