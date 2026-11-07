import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.infra.execution_market.profile_restore import database_url
from tests.infra.positions.conftest import legacy_wallet as legacy_wallet
from tests.infra.positions.conftest import owner as owner
from tests.infra.positions.conftest import production_wallet as production_wallet
from tiewtrade.infra.paper_wallet.records import PaperWalletSnapshot

BACKEND_ROOT = Path(__file__).resolve().parents[3]
INTERNAL_DATABASE_PREFIX = "tiewtrade_internal20_test_"
CHECKPOINT_DATABASE_PREFIX = "tiewtrade_set4_iso_"


class InternalDatabaseFactory(Protocol):
    def __call__(
        self, *, prefix: str = INTERNAL_DATABASE_PREFIX
    ) -> AbstractAsyncContextManager[dict[str, str]]: ...


async def _bootstrap_internal_database(admin_url: str) -> None:
    name = make_url(admin_url).database
    bootstrap = create_async_engine(admin_url, hide_parameters=True)
    try:
        async with bootstrap.begin() as connection:
            raw = await connection.get_raw_connection()
            assert raw.driver_connection is not None
            for script in sorted((BACKEND_ROOT / "db/bootstrap").glob("*.sql")):
                # Reuse bootstrap SQL; resolve psql directives for this generated DB.
                sql = "\n".join(
                    line
                    for line in script.read_text().splitlines()
                    if not line.startswith("\\set ")
                ).replace(':"DBNAME"', f'"{name}"')
                await raw.driver_connection.execute(sql)
    finally:
        await bootstrap.dispose()


@asynccontextmanager
async def _internal_scratch_database(
    admin_url: str, *, template: str | None = None, prefix: str = INTERNAL_DATABASE_PREFIX
) -> AsyncIterator[str]:
    # Identifiers are generated here, never taken from the ambient source DB name.
    if prefix not in {INTERNAL_DATABASE_PREFIX, CHECKPOINT_DATABASE_PREFIX}:
        raise ValueError("approved isolated test database prefix required")
    name = prefix + uuid4().hex
    admin = create_async_engine(
        make_url(admin_url).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        hide_parameters=True,
    )
    created = False
    try:
        async with admin.connect() as connection:
            sql = f"CREATE DATABASE {name} OWNER tiewtrade_migrator"
            if template is not None:
                sql += f" TEMPLATE {template}"
            await connection.exec_driver_sql(sql)
            created = True
        # Cloning copies schema/data, but not database ACLs or log settings.
        # Both the template and its clones use the same existing bootstrap.
        await _bootstrap_internal_database(database_url(admin_url, name))
        yield name
    finally:
        try:
            if created:
                async with admin.connect() as connection:
                    await connection.exec_driver_sql(f"DROP DATABASE {name}")
        finally:
            await admin.dispose()


@pytest_asyncio.fixture(scope="session")
async def _internal_database_template() -> AsyncIterator[dict[str, str]]:
    """Build a clean schema once; never clone or reset the shared test database."""
    urls = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("TIEWTRADE_DATABASE_URL_") or key == "TIEWTRADE_TEST_ADMIN_URL"
    }
    admin_url = urls["TIEWTRADE_TEST_ADMIN_URL"]
    admin_identity = make_url(admin_url)
    if admin_identity.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("internal test fixtures require local PostgreSQL")
    identities = [make_url(value) for value in urls.values()]
    if any(
        (identity.host, identity.port) != (admin_identity.host, admin_identity.port)
        for identity in identities
    ):
        raise ValueError("internal test fixture roles must use the same PostgreSQL server")
    async with _internal_scratch_database(admin_url) as name:
        target_urls = {key: database_url(value, name) for key, value in urls.items()}
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            "head",
            cwd=BACKEND_ROOT,
            env={**os.environ, **target_urls},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await process.communicate()
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode != 0:
            raise RuntimeError("internal test template migration failed")
        yield target_urls


@pytest.fixture
def internal_database_factory(
    _internal_database_template: dict[str, str],
) -> InternalDatabaseFactory:
    @asynccontextmanager
    async def create(*, prefix: str = INTERNAL_DATABASE_PREFIX) -> AsyncIterator[dict[str, str]]:
        admin_url = _internal_database_template["TIEWTRADE_TEST_ADMIN_URL"]
        async with _internal_scratch_database(
            admin_url, template=make_url(admin_url).database, prefix=prefix
        ) as name:
            urls = {
                key: database_url(value, name) for key, value in _internal_database_template.items()
            }
            yield urls

    return create


@pytest_asyncio.fixture
async def internal_database(
    internal_database_factory: InternalDatabaseFactory, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    """Runs before dependent role-engine fixtures and restores ambient URLs afterwards."""
    async with internal_database_factory() as urls:
        with monkeypatch.context() as patch:
            for key, value in urls.items():
                patch.setenv(key, value)
            yield


@pytest.fixture
def wallet(production_wallet: PaperWalletSnapshot) -> PaperWalletSnapshot:
    """Use production-created, F-15-managed wallets for execution-market tests."""
    return production_wallet
