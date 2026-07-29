from pathlib import Path
from threading import Lock
from uuid import UUID

from tiewtrade.application.database_compatibility import DatabaseCompatibilityError
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
from tiewtrade.decimal_context import configure_decimal_context
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import (
    SQLiteDatabase,
    UnsupportedDatabaseSchemaError,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.trade_history import TradeFill
from tiewtrade.ui.desktop import run_desktop as run_desktop_ui


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

    return run_desktop_ui(
        create_session=create_after_migration,
        load_active=load_after_migration,
        list_baskets=list_baskets_after_migration,
        list_fills=list_fills_after_migration,
    )


def default_database_path() -> Path:
    directory = Path.home() / "Library" / "Application Support" / "TiewTrade"
    return directory / "tiewtrade.sqlite3"


if __name__ == "__main__":
    raise SystemExit(run_desktop())
