"""R25 evidence from actual test-harness pools; no changes to trading transactions."""

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool

from tests.infra.execution_market import profile_workload as f15
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.engine import risk_limit_main as risk_runtime


class PoolEvidence:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.entries: list[dict[str, Any]] = []
        self.listeners: list[tuple[Any, str, Any]] = []

    def add(self, engine: AsyncEngine, role: DatabaseRole) -> None:
        pool = engine.pool
        if not isinstance(pool, QueuePool):
            raise ValueError("bounded queue pool required")
        active: set[int] = set()
        entry: dict[str, Any] = {
            "role": role.name,
            "pool_size": pool.size(),
            "max_overflow": pool._max_overflow,
            "checked_out": 0,
            "peak_checked_out": 0,
        }
        if entry["pool_size"] <= 0 or entry["max_overflow"] < 0:
            raise ValueError("bounded pool inventory required")
        self.entries.append(entry)

        def checkout(connection: Any, record: Any, proxy: Any) -> None:
            active.add(id(record))
            entry["checked_out"] = len(active)
            entry["peak_checked_out"] = max(entry["peak_checked_out"], len(active))

        def checkin(connection: Any, record: Any) -> None:
            active.discard(id(record))
            entry["checked_out"] = len(active)

        for name, callback in (("checkout", checkout), ("checkin", checkin)):
            event.listen(pool, name, callback)
            self.listeners.append((pool, name, callback))
        self.save(finalized=False)

    def save(self, *, finalized: bool) -> None:
        self.path.write_text(json.dumps({"pools": self.entries, "finalized": finalized}))

    def finish(self) -> None:
        self.save(finalized=True)
        for pool, name, callback in self.listeners:
            event.remove(pool, name, callback)
        self.listeners.clear()


def pool_configuration(document: dict[str, Any]) -> list[tuple[str, int, int]]:
    return sorted((p["role"], p["pool_size"], p["max_overflow"]) for p in document["pools"])


async def connection_budget(
    engine: AsyncEngine, paths: list[Path], *, expected_counts: list[int]
) -> dict[str, Any]:
    if not paths or len(set(paths)) != len(paths) or len(paths) != len(expected_counts):
        raise ValueError("complete process inventory required")
    inventory = {}
    capacity = 0
    for path, expected in zip(paths, expected_counts, strict=True):
        document = json.loads(path.read_text())
        configuration = pool_configuration(document)
        if len(configuration) != expected:
            raise ValueError("incomplete pool inventory")
        inventory[path.name] = configuration
        capacity += sum(size + overflow for _, size, overflow in configuration)
    async with engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text("""SELECT current_setting('max_connections')::int AS maximum,
                  current_setting('superuser_reserved_connections')::int AS superuser_reserved,
                  coalesce(nullif(current_setting('reserved_connections',true),''),'0')::int
                    AS reserved,
                  (SELECT count(*) FROM pg_stat_activity
                    WHERE datname IS NOT NULL AND usename IS NOT NULL
                    AND datname<>current_database()) AS other_clients""")
                )
            )
            .mappings()
            .one()
        )
    available = row["maximum"] - row["superuser_reserved"] - row["reserved"] - row["other_clients"]
    if available < 1:
        raise ValueError("no database connection headroom")
    return {
        "inventory": inventory,
        "declared_capacity": capacity,
        "server": dict(row),
        "limit": min(capacity, available),
    }


def returned_pools(paths: list[Path], budget: dict[str, Any]) -> bool:
    initial = budget["inventory"]
    if not paths or not set(initial).issubset({p.name for p in paths}):
        return False
    for path in paths:
        document = json.loads(path.read_text())
        # Restarts retain the same logical worker and must retain its frozen pool configuration.
        baseline = (
            path.name if path.name in initial else path.name.rsplit("-", 1)[0] + "-0.pools.json"
        )
        if baseline not in initial or pool_configuration(document) != [
            tuple(x) for x in initial[baseline]
        ]:
            return False
        if not document["finalized"] or any(p["checked_out"] != 0 for p in document["pools"]):
            return False
    return True


async def cleanup_connections(*, observer_pids: tuple[int, ...] = ()) -> dict[str, Any]:
    engine = create_engine_for(DatabaseRole.MIGRATOR, pool_size=1, max_overflow=0)
    started = asyncio.get_running_loop().time()
    rows: Any = []
    try:
        async with asyncio.timeout(5):
            while True:
                async with engine.connect() as connection:
                    rows = (
                        (
                            await connection.execute(
                                text("""SELECT pid,state FROM pg_stat_activity
                              WHERE datname=current_database() AND usename IS NOT NULL
                              AND pid<>pg_backend_pid()
                              AND NOT(pid=ANY(CAST(:observers AS int[])))"""),
                                {"observers": list(observer_pids)},
                            )
                        )
                        .mappings()
                        .all()
                    )
                if not rows:
                    return {
                        "passed": True,
                        "remaining": [],
                        "seconds": asyncio.get_running_loop().time() - started,
                    }
                await asyncio.sleep(0.05)
    except TimeoutError:
        return {"passed": False, "remaining": [dict(row) for row in rows], "seconds": 5}
    finally:
        await engine.dispose()


@contextmanager
def worker_pool_evidence(metrics: Path) -> Iterator[None]:
    tracker = PoolEvidence(metrics.with_suffix(".pools.json"))
    original = create_engine_for

    def tracked(role: DatabaseRole, **options: Any) -> AsyncEngine:
        engine = original(role, **options)
        tracker.add(engine, role)
        return engine

    paper_namespace, risk_namespace = vars(f15), vars(risk_runtime)
    original_paper = paper_namespace["create_engine_for"]
    original_risk = risk_namespace["create_engine_for"]
    paper_namespace["create_engine_for"] = tracked
    risk_namespace["create_engine_for"] = tracked
    try:
        yield
    finally:
        paper_namespace["create_engine_for"] = original_paper
        risk_namespace["create_engine_for"] = original_risk
        tracker.finish()
