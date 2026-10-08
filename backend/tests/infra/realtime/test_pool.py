import pytest
from sqlalchemy.pool import AsyncAdaptedQueuePool

from tiewtrade.infra.db import DatabaseRole, create_engine_for


async def test_bounded_realtime_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "TIEWTRADE_DATABASE_URL_API", "postgresql+asyncpg://example:example@localhost/example"
    )
    engine = create_engine_for(DatabaseRole.API, pool_size=3, max_overflow=0, pool_timeout=0.5)
    try:
        assert isinstance(engine.pool, AsyncAdaptedQueuePool)
        assert engine.pool.size() == 3
        assert engine.pool.timeout() == 0.5
    finally:
        await engine.dispose()


@pytest.mark.parametrize("kwargs", [{"pool_size": 0}, {"max_overflow": -1}, {"pool_timeout": 1}])
def test_pool_rejects_unbounded_options(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        create_engine_for(DatabaseRole.API, **kwargs)
