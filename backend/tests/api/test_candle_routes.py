import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.api.conftest import csrf_headers, register
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session


@pytest.fixture(autouse=True)
def clear_market() -> Iterator[None]:
    async def clear() -> None:
        engine = create_engine_for(DatabaseRole.MARKET_DATA)
        try:
            async with market_data_session(engine) as session:
                await session.execute("DELETE FROM market_candles")
                await session.execute("DELETE FROM market_candle_demand")
        finally:
            await engine.dispose()

    asyncio.get_event_loop().run_until_complete(clear())
    yield
    asyncio.get_event_loop().run_until_complete(clear())


def test_read_requires_authentication(client: TestClient) -> None:
    assert (
        client.get(
            "/market-data/candles", params={"base": "BTC", "quote": "USDT", "timeframe": "1m"}
        ).status_code
        == 401
    )


def test_chart_pages_require_authentication(client: TestClient) -> None:
    assert (
        client.get(
            "/market-data/candles/pages", params={"base": "BTC", "quote": "USDT", "timeframe": "1m"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"])
def test_chart_pages_cover_three_months_with_bounded_pages(
    client: TestClient, timeframe: str
) -> None:
    register(client)
    params = {"base": "BTC", "quote": "USDT", "timeframe": timeframe}
    result = client.get("/market-data/candles/pages", params=params)
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["earliest_known"] is True
    assert page["display_start"] < page["requested"]["end"]
    if page["older_before"]:
        older = client.get(
            "/market-data/candles/pages", params=params | {"before": page["older_before"]}
        )
        assert older.status_code == 200, older.text
        assert older.json()["requested"]["start"] < page["requested"]["start"]
        assert older.json()["requested"]["end"] > page["requested"]["start"]
    outside = client.get(
        "/market-data/candles/pages", params=params | {"before": "2000-01-01T00:00:00Z"}
    )
    assert outside.status_code == 422


def test_read_and_request_need_no_totp(client: TestClient) -> None:
    register(client)
    series = {"base": "ETH", "quote": "USDT", "timeframe": "5m"}
    result = client.get("/market-data/candles", params=series)
    assert result.status_code == 200, result.text
    assert result.json()["coverage"] == "INCOMPLETE"
    request = client.post(
        "/market-data/candles/requests", json=series, headers=csrf_headers(client)
    )
    assert request.status_code == 202, request.text


@pytest.mark.parametrize("timeframe", ["9m", "1W", "1mo"])
def test_invalid_timeframe_has_fixed_error(client: TestClient, timeframe: str) -> None:
    register(client)
    result = client.get(
        "/market-data/candles", params={"base": "BTC", "quote": "USDT", "timeframe": timeframe}
    )
    assert result.status_code == 422
    assert result.json() == {"detail": "INPUT_REJECTED"}


def test_request_requires_csrf(client: TestClient) -> None:
    register(client)
    result = client.post(
        "/market-data/candles/requests", json={"base": "BTC", "quote": "USDT", "timeframe": "1m"}
    )
    assert result.status_code == 403


def test_invalid_unit_returns_fixed_error(client: TestClient) -> None:
    register(client)
    result = client.get(
        "/market-data/candles", params={"base": "!", "quote": "USDT", "timeframe": "1m"}
    )
    assert result.status_code == 422
    assert result.json() == {"detail": "INPUT_REJECTED"}


@pytest.mark.parametrize("base", ["SOL", "XRP", "DOGE", "UNKNOWN"])
def test_unsupported_pair_is_rejected_without_creating_demand(
    client: TestClient, base: str
) -> None:
    register(client)
    series = {"base": base, "quote": "USDT", "timeframe": "1m"}
    read = client.get("/market-data/candles", params=series)
    request = client.post(
        "/market-data/candles/requests", json=series, headers=csrf_headers(client)
    )
    assert read.status_code == 422
    assert read.json() == {"detail": "UNSUPPORTED_SERIES"}
    assert request.status_code == 422
    assert request.json() == {"detail": "UNSUPPORTED_SERIES"}

    async def demand_count() -> int:
        engine = create_engine_for(DatabaseRole.MARKET_DATA)
        try:
            async with engine.connect() as connection:
                return int(
                    (
                        await connection.execute(text("SELECT count(*) FROM market_candle_demand"))
                    ).scalar_one()
                )
        finally:
            await engine.dispose()

    assert asyncio.get_event_loop().run_until_complete(demand_count()) == 0


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("9999-12-31T23:59:58-01:00", "9999-12-31T23:59:59-01:00"),
        ("0001-01-01T00:00:00+01:00", "0001-01-01T00:00:01+01:00"),
    ],
)
def test_utc_overflow_returns_fixed_input_error(
    client: TestClient, method: str, start: str, end: str
) -> None:
    register(client)
    bounds = {"base": "BTC", "quote": "USDT", "timeframe": "1m", "start": start, "end": end}
    if method == "GET":
        result = client.get("/market-data/candles", params=bounds)
    else:
        result = client.post(
            "/market-data/candles/requests", json=bounds, headers=csrf_headers(client)
        )
    assert result.status_code == 422
    assert result.json() == {"detail": "INPUT_REJECTED"}
