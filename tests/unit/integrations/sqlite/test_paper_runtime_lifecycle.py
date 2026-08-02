import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_runtime_lifecycle import (
    PaperRuntimeLifecycleRecord,
    PaperRuntimeLifecycleState,
    PaperRuntimeLifecycleUnavailableError,
    SQLitePaperRuntimeLifecycle,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000123")
RUNNING_AT = datetime(2026, 8, 2, 4, 15, tzinfo=UTC)
STOPPED_AT = datetime(2026, 8, 2, 4, 45, tzinfo=UTC)


def test_read_returns_none_when_active_session_has_no_lifecycle_marker(
    tmp_path: Path,
) -> None:
    database = _created_active_session_database(tmp_path)

    assert SQLitePaperRuntimeLifecycle(database).read(SESSION_ID) is None


def test_running_and_stopped_markers_persist_exact_utc_facts_across_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    database = _created_active_session_database(tmp_path)
    lifecycle = SQLitePaperRuntimeLifecycle(database)

    lifecycle.mark_running(SESSION_ID, RUNNING_AT)

    assert SQLitePaperRuntimeLifecycle(SQLiteDatabase(database_path)).read(
        SESSION_ID
    ) == PaperRuntimeLifecycleRecord(
        session_id=SESSION_ID,
        state=PaperRuntimeLifecycleState.RUNNING,
        observed_at_utc=RUNNING_AT,
    )

    lifecycle.mark_stopped(SESSION_ID, STOPPED_AT)

    assert SQLitePaperRuntimeLifecycle(SQLiteDatabase(database_path)).read(
        SESSION_ID
    ) == PaperRuntimeLifecycleRecord(
        session_id=SESSION_ID,
        state=PaperRuntimeLifecycleState.STOPPED,
        observed_at_utc=STOPPED_AT,
    )


def test_mark_running_rejects_unknown_session_without_creating_marker(
    tmp_path: Path,
) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    lifecycle = SQLitePaperRuntimeLifecycle(database)
    unknown_session_id = UUID("00000000-0000-0000-0000-000000000999")

    with pytest.raises(
        PaperRuntimeLifecycleUnavailableError,
        match="Paper Runtime Lifecycle write failed",
    ):
        lifecycle.mark_running(unknown_session_id, RUNNING_AT)

    assert lifecycle.read(unknown_session_id) is None


class _UnavailableDatabase(SQLiteDatabase):
    def connect(self) -> sqlite3.Connection:
        raise sqlite3.OperationalError("sensitive sqlite detail")


def test_read_sanitizes_sqlite_failure(tmp_path: Path) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    lifecycle = SQLitePaperRuntimeLifecycle(_UnavailableDatabase(database_path))

    with pytest.raises(
        PaperRuntimeLifecycleUnavailableError,
        match="Paper Runtime Lifecycle read failed",
    ) as caught:
        lifecycle.read(SESSION_ID)

    assert "sensitive sqlite detail" not in str(caught.value)


def test_migration_from_v3_creates_lifecycle_marker_table(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    with database.connect() as connection:
        connection.execute("CREATE TABLE bot_sessions (session_id TEXT PRIMARY KEY)")
        connection.execute("PRAGMA user_version = 3")

    database.migrate()

    with database.connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(paper_runtime_lifecycle)")
        }

    assert version == 5
    assert columns == {"session_id", "state", "observed_at_utc"}


def _created_active_session_database(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    SQLiteActivePaperSessions(database).create(configured_spot_session())
    return database
