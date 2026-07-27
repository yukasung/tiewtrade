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
    database = SQLiteDatabase(database_path or default_database_path())
    store = SQLiteActivePaperSessions(database)
    create_session = CreatePaperSession(create_active=store.create)

    def create_after_migration(
        values: PaperSessionSetupValues,
    ) -> PaperSessionCreateOutcome:
        database.migrate()
        return create_session.execute(values)

    def load_after_migration() -> ConfiguredPaperSession | None:
        database.migrate()
        return store.get_active()

    return run_desktop_ui(
        create_session=create_after_migration,
        load_active=load_after_migration,
    )


def default_database_path() -> Path:
    directory = Path.home() / "Library" / "Application Support" / "TiewTrade"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "tiewtrade.sqlite3"


if __name__ == "__main__":
    raise SystemExit(run_desktop())
