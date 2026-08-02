import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import UUID

import pytest

from tests.support.paper_session_setup import (
    configured_futures_session,
    configured_spot_session,
)
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionUnavailableError,
)
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase


def test_create_and_restart_round_trip_exact_spot_session(tmp_path: Path) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    session = configured_spot_session()

    first = store.create(session)
    restarted = SQLiteActivePaperSessions(SQLiteDatabase(database_path)).get_active()

    assert first == PaperSessionCreateOutcome(session=session, created=True)
    assert restarted == session


def test_create_and_restart_round_trip_exact_futures_session(tmp_path: Path) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    session = configured_futures_session(leverage=5)

    first = store.create(session)
    restarted = SQLiteActivePaperSessions(SQLiteDatabase(database_path)).get_active()

    assert first == PaperSessionCreateOutcome(session=session, created=True)
    assert restarted == session


def test_second_active_session_returns_existing_record(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    existing = configured_spot_session()
    store.create(existing)

    outcome = store.create(
        configured_futures_session(
            session_id=UUID("00000000-0000-0000-0000-000000000124")
        )
    )

    assert outcome == PaperSessionCreateOutcome(session=existing, created=False)


def test_get_active_returns_none_when_database_has_no_session(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()

    assert SQLiteActivePaperSessions(database).get_active() is None


@pytest.mark.parametrize(
    ("column", "unsupported_value"),
    [
        pytest.param("symbol", "ETHUSDT", id="symbol"),
        pytest.param("preset_version", "rsi-step-grid-v2", id="preset-version"),
    ],
)
def test_get_active_fails_closed_for_unsupported_durable_session_identity(
    tmp_path: Path,
    column: str,
    unsupported_value: str,
) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    store.create(configured_spot_session())
    with database.connect() as connection:
        connection.execute(
            f"UPDATE bot_sessions SET {column} = ?",
            (unsupported_value,),
        )

    with pytest.raises(
        PaperSessionUnavailableError,
        match="Active Paper Session read failed",
    ):
        store.get_active()


def test_migration_from_v2_preserves_trade_history_record(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    with database.connect() as connection:
        connection.execute("CREATE TABLE basket_results (basket_id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO basket_results VALUES ('basket-sentinel')")
        connection.execute("PRAGMA user_version = 2")

    database.migrate()

    with database.connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        basket_id = connection.execute(
            "SELECT basket_id FROM basket_results"
        ).fetchone()[0]
        bot_sessions_exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'bot_sessions'
            """
        ).fetchone()

    assert version == 4
    assert basket_id == "basket-sentinel"
    assert bot_sessions_exists is not None


class _CommitFailingConnection(sqlite3.Connection):
    def commit(self) -> None:
        raise sqlite3.OperationalError("injected commit failure")


class _CommitFailingDatabase(SQLiteDatabase):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._failure_path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._failure_path,
            factory=_CommitFailingConnection,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def test_commit_failure_rolls_back_active_session(tmp_path: Path) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    store = SQLiteActivePaperSessions(_CommitFailingDatabase(database_path))

    with pytest.raises(PaperSessionUnavailableError, match="write failed"):
        store.create(configured_spot_session())

    assert SQLiteActivePaperSessions(database).get_active() is None


def test_concurrent_create_keeps_exactly_one_active_session(tmp_path: Path) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    database = SQLiteDatabase(database_path)
    database.migrate()
    barrier = Barrier(2)
    sessions = (
        configured_spot_session(
            session_id=UUID("00000000-0000-0000-0000-000000000125")
        ),
        configured_futures_session(
            session_id=UUID("00000000-0000-0000-0000-000000000126")
        ),
    )

    def create(session: ConfiguredPaperSession) -> PaperSessionCreateOutcome:
        barrier.wait()
        store = SQLiteActivePaperSessions(SQLiteDatabase(database_path))
        return store.create(session)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = tuple(pool.map(create, sessions))

    active = SQLiteActivePaperSessions(database).get_active()
    with database.connect() as connection:
        active_count = connection.execute(
            "SELECT COUNT(*) FROM bot_sessions WHERE ended_at_utc IS NULL"
        ).fetchone()[0]

    assert sum(outcome.created for outcome in outcomes) == 1
    assert active is not None
    assert {outcome.session for outcome in outcomes} == {active}
    assert active_count == 1


def test_database_constraint_rejects_a_second_active_session(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    SQLiteActivePaperSessions(database).create(configured_spot_session())

    with database.connect() as connection:
        existing = connection.execute("SELECT * FROM bot_sessions").fetchone()
        assert existing is not None
        duplicate = (
            "00000000-0000-0000-0000-000000000127",
            *tuple(existing)[1:],
        )
        placeholders = ", ".join("?" for _ in duplicate)

        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            connection.execute(
                f"INSERT INTO bot_sessions VALUES ({placeholders})",
                duplicate,
            )
