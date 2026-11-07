"""NC12 fixtures isolate mutable history, restore configuration and remove owned DBs."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market.conftest import InternalDatabaseFactory
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.users import create_user


@pytest.mark.parametrize("fails", [False, True])
async def test_independent_empty_databases_cleanup_and_restore_ambient_configuration(
    internal_database_factory: InternalDatabaseFactory,
    monkeypatch: pytest.MonkeyPatch,
    fails: bool,
) -> None:
    before = dict(os.environ)
    first = None
    failure = RuntimeError("controlled test failure")
    try:
        async with internal_database_factory() as urls:
            first = make_url(urls["TIEWTRADE_TEST_ADMIN_URL"]).database
            with monkeypatch.context() as patch:
                for key, value in urls.items():
                    patch.setenv(key, value)
                await internal.require_empty_database()
                api = create_engine_for(DatabaseRole.API)
                try:
                    await create_user(api, uuid4())
                finally:
                    await api.dispose()
                with pytest.raises(ValueError, match="newly created empty"):
                    await internal.require_empty_database()
                if fails:
                    raise failure
    except RuntimeError as error:
        assert fails and error is failure
    assert dict(os.environ) == before
    assert first is not None
    admin = create_async_engine(before["TIEWTRADE_TEST_ADMIN_URL"], hide_parameters=True)
    try:
        async with admin.connect() as connection:
            assert not await connection.scalar(
                text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"),
                {"name": first},
            )
    finally:
        await admin.dispose()
    async with internal_database_factory() as urls:
        assert make_url(urls["TIEWTRADE_TEST_ADMIN_URL"]).database != first
        with monkeypatch.context() as patch:
            for key, value in urls.items():
                patch.setenv(key, value)
            await internal.require_empty_database()
    assert dict(os.environ) == before
