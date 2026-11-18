"""Failure-only diagnostics for one disposable chart browser fixture."""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from tiewtrade.services.market_data.ingestion import RoundSummary

Counts = dict[tuple[str, str], int]


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def series(counts: Counts) -> dict[str, int]:
    return {f"{base}/{tf}": count for (base, tf), count in sorted(counts.items())}


async def read_counts(engine: AsyncEngine) -> Counts:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT base,timeframe,count(*) FROM market_candles GROUP BY base,timeframe")
        )
        return {(base, tf): count for base, tf, count in rows}


class SeedObserver:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.rounds: list[dict[str, object]] = []
        self.waits: list[dict[str, object]] = []
        self.gaps: list[str] = []
        self.samples = 0
        self.initial: dict[str, int] | None = None
        self.started = stamp()

    async def sample(self, engine: AsyncEngine) -> None:
        try:
            async with engine.connect() as connection:
                while True:
                    async with connection.begin():
                        await connection.execute(text("SET TRANSACTION READ ONLY"))
                        rows = await connection.execute(
                            text("""
                            SELECT l.pid, l.locktype, (pg_blocking_pids(l.pid))[1:32]
                            FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid
                            WHERE NOT l.granted AND a.datname=current_database()
                            ORDER BY l.pid LIMIT 32
                        """)
                        )
                        self.samples += 1
                        for pid, kind, blockers in rows:
                            if len(self.waits) < 32:
                                self.waits.append(
                                    {
                                        "at": stamp(),
                                        "pid": pid,
                                        "lock": kind,
                                        "blockers": blockers,
                                    }
                                )
                    await asyncio.sleep(0.1)
        except Exception as exc:
            self.gaps.append(f"locks:{type(exc).__name__}")

    async def baseline(self, engine: AsyncEngine) -> None:
        try:
            async with asyncio.timeout(0.5):
                self.initial = series(await read_counts(engine))
        except Exception as exc:
            self.gaps.append(f"baseline:{type(exc).__name__}")

    def begin_round(self) -> None:
        self.rounds.append({"round": len(self.rounds) + 1, "start": stamp()})

    def result(self, summary: RoundSummary) -> None:
        self.rounds[-1].update(
            attempts=summary.attempts, stored=summary.stored, stale=summary.stale
        )

    def finish_round(self, counts: Counts) -> None:
        self.rounds[-1].update(end=stamp(), counts=series(counts))

    def publish(self, error: BaseException) -> None:
        try:
            self.path.write_text(
                json.dumps(
                    {
                        "error": type(error).__name__,
                        "start": self.started,
                        "end": stamp(),
                        "expected": {"BTC/1h": 1000, "ETH/1h": 1000},
                        "initial": self.initial,
                        "rounds": self.rounds,
                        "lock_samples": self.samples,
                        "lock_waits": self.waits,
                        "gaps": self.gaps if self.samples else [*self.gaps, "no_lock_samples"],
                    },
                    indent=2,
                )
                + "\n"
            )
        except OSError:
            sys.stderr.write("F12_SEED_EVIDENCE_UNAVAILABLE\n")
