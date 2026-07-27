from pathlib import Path

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    CreatePaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.ui.desktop import run_desktop as run_desktop_ui


def run_desktop(database_path: Path | None = None) -> int:
    resolved_database_path = database_path or default_database_path()
    database = SQLiteDatabase(resolved_database_path)
    store = SQLiteActivePaperSessions(database)
    create_session = CreatePaperSession(create_active=store.create)

    def prepare_database() -> None:
        resolved_database_path.parent.mkdir(parents=True, exist_ok=True)
        database.migrate()

    def create_after_migration(
        values: PaperSessionSetupValues,
    ) -> PaperSessionCreateOutcome:
        prepare_database()
        return create_session.execute(values)

    def load_after_migration() -> ConfiguredPaperSession | None:
        prepare_database()
        return store.get_active()

    return run_desktop_ui(
        create_session=create_after_migration,
        load_active=load_after_migration,
    )


def default_database_path() -> Path:
    directory = Path.home() / "Library" / "Application Support" / "TiewTrade"
    return directory / "tiewtrade.sqlite3"


if __name__ == "__main__":
    raise SystemExit(run_desktop())
