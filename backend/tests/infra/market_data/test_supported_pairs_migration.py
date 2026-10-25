"""Atomic rollback coverage for the destructive F-38 catalog migration."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.util import load_python_file
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _alembic


def _run(migration: Any, direction: str, connection: Connection) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        getattr(migration, direction)()


def _migration() -> Any:
    return load_python_file(
        Path(__file__).resolve().parents[3] / "migrations/versions",
        "0030_supported_pairs_reduction.py",
    )


async def test_catalog_downgrade_uses_source_maintenance_for_protected_candles(
    migrator_engine: AsyncEngine,
) -> None:
    _alembic("downgrade", "0030")
    migration = _migration()
    downgraded = False
    try:
        async with migrator_engine.begin() as connection:
            enabled: str = (
                await connection.execute(
                    text(
                        "SELECT evtenabled::text FROM pg_event_trigger "
                        "WHERE evtname='tiewtrade_indicator_trigger_ddl'"
                    )
                )
            ).scalar_one()
            assert enabled == "O"
            await connection.run_sync(lambda sync: _run(migration, "downgrade", sync))
        downgraded = True

        async with migrator_engine.connect() as connection:
            constraint: str = (
                await connection.execute(
                    text(
                        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conname='market_candles_check' "
                        "AND conrelid='market_candles'::regclass"
                    )
                )
            ).scalar_one()
            assert "SOL" in constraint
    finally:
        if downgraded:
            async with migrator_engine.begin() as connection:
                await connection.run_sync(lambda sync: _run(migration, "upgrade", sync))
        _alembic("upgrade", "head")


async def test_catalog_migration_failure_rolls_back_every_change(
    migrator_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _alembic("downgrade", "0030")
    migration = _migration()
    original_digests = cast(Callable[[], dict[str, tuple[int, str]]], migration._supported_digests)

    try:
        async with migrator_engine.begin() as connection:
            await connection.run_sync(lambda sync: _run(migration, "downgrade", sync))
            await connection.execute(
                text("""INSERT INTO market_latest_prices
                  (source,base,quote,amount,trade_id,trade_at,received_at,
                   observation_kind,reconciled_generation,revision,
                   effective_readiness,reason)
                  VALUES('primary_spot','SOL','USDT',1,1,clock_timestamp(),
                    clock_timestamp(),'SNAPSHOT',1,1,'READY','READY')""")
            )

        calls = 0

        def fail_after_changes() -> dict[str, tuple[int, str]]:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected failure")
            return original_digests()

        monkeypatch.setattr(migration, "_supported_digests", fail_after_changes)
        with pytest.raises(RuntimeError, match="injected failure"):
            async with migrator_engine.begin() as connection:
                await connection.run_sync(lambda sync: _run(migration, "upgrade", sync))

        async with migrator_engine.connect() as connection:
            assert (
                await connection.execute(
                    text("SELECT count(*) FROM market_latest_prices WHERE base='SOL'")
                )
            ).scalar_one() == 1
            assert (
                "SOL"
                in (
                    await connection.execute(
                        text("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                      WHERE conname='market_latest_prices_check'""")
                    )
                ).scalar_one()
            )
    finally:
        monkeypatch.setattr(migration, "_supported_digests", original_digests)
        async with migrator_engine.begin() as connection:
            constraint: str = (
                await connection.execute(
                    text("""SELECT pg_get_constraintdef(oid) FROM pg_constraint
                      WHERE conname='market_latest_prices_check'""")
                )
            ).scalar_one()
            if "SOL" in constraint:
                await connection.run_sync(lambda sync: _run(migration, "upgrade", sync))
        _alembic("upgrade", "head")

    async with migrator_engine.connect() as connection:
        assert (
            await connection.execute(
                text("SELECT count(*) FROM market_latest_prices WHERE base='SOL'")
            )
        ).scalar_one() == 0
