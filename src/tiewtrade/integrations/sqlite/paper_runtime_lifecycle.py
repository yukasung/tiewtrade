import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from tiewtrade.integrations.sqlite.database import SQLiteDatabase


class PaperRuntimeLifecycleState(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"


class PaperRuntimeLifecycleUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PaperRuntimeLifecycleRecord:
    session_id: UUID
    state: PaperRuntimeLifecycleState
    observed_at_utc: datetime

    def __post_init__(self) -> None:
        if (
            self.observed_at_utc.tzinfo is None
            or self.observed_at_utc.utcoffset() != timedelta(0)
        ):
            raise ValueError("observed_at_utc must use UTC")


class SQLitePaperRuntimeLifecycle:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def read(self, session_id: UUID) -> PaperRuntimeLifecycleRecord | None:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            row = connection.execute(
                """
                SELECT session_id, state, observed_at_utc
                FROM paper_runtime_lifecycle
                WHERE session_id = ?
                """,
                (str(session_id),),
            ).fetchone()
            return None if row is None else _record_from_row(row)
        except (sqlite3.Error, ValueError) as error:
            raise PaperRuntimeLifecycleUnavailableError(
                "Paper Runtime Lifecycle read failed"
            ) from error
        finally:
            _close_if_open(connection)

    def mark_running(self, session_id: UUID, observed_at_utc: datetime) -> None:
        self._mark(session_id, PaperRuntimeLifecycleState.RUNNING, observed_at_utc)

    def mark_stopped(self, session_id: UUID, observed_at_utc: datetime) -> None:
        self._mark(session_id, PaperRuntimeLifecycleState.STOPPED, observed_at_utc)

    def _mark(
        self,
        session_id: UUID,
        state: PaperRuntimeLifecycleState,
        observed_at_utc: datetime,
    ) -> None:
        record = PaperRuntimeLifecycleRecord(
            session_id=session_id,
            state=state,
            observed_at_utc=observed_at_utc,
        )
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            connection.execute("BEGIN IMMEDIATE")
            active_session = connection.execute(
                """
                SELECT 1 FROM bot_sessions
                WHERE session_id = ? AND ended_at_utc IS NULL
                """,
                (str(record.session_id),),
            ).fetchone()
            if active_session is None:
                raise sqlite3.IntegrityError("active session is required")
            connection.execute(
                """
                INSERT INTO paper_runtime_lifecycle (
                    session_id, state, observed_at_utc
                ) VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state = excluded.state,
                    observed_at_utc = excluded.observed_at_utc
                """,
                (
                    str(record.session_id),
                    record.state.value,
                    record.observed_at_utc.isoformat(),
                ),
            )
            connection.commit()
        except sqlite3.Error as error:
            _rollback_if_open(connection)
            raise PaperRuntimeLifecycleUnavailableError(
                "Paper Runtime Lifecycle write failed"
            ) from error
        except BaseException:
            _rollback_if_open(connection)
            raise
        finally:
            _close_if_open(connection)


def _record_from_row(row: sqlite3.Row) -> PaperRuntimeLifecycleRecord:
    return PaperRuntimeLifecycleRecord(
        session_id=UUID(row["session_id"]),
        state=PaperRuntimeLifecycleState(row["state"]),
        observed_at_utc=datetime.fromisoformat(row["observed_at_utc"]),
    )


def _rollback_if_open(connection: sqlite3.Connection | None) -> None:
    if connection is not None:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass


def _close_if_open(connection: sqlite3.Connection | None) -> None:
    if connection is not None:
        try:
            connection.close()
        except sqlite3.Error:
            pass
