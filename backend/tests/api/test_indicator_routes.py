import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import register


@pytest.mark.parametrize("elapsed,status", [(0, 200), (29.999, 200), (30, 504), (30.001, 504)])
def test_serialization_deadline_includes_exact_boundary(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, elapsed: float, status: int
) -> None:
    from time import monotonic
    from typing import cast

    from tiewtrade.services.api import indicator_routes as routes

    register(client)
    clock = [monotonic()]

    class Serialized:
        def model_dump_json(self) -> str:
            # Advance only the route clock during synchronous work: no await can
            # dispatch asyncio's cancellation callback before the route returns.
            clock[0] += elapsed
            return "{}"

    async def read(*args: object) -> routes.IndicatorHistoryView:
        return cast(routes.IndicatorHistoryView, Serialized())

    monkeypatch.setattr(routes, "_read", read)
    monkeypatch.setattr(routes, "monotonic", lambda: clock[0])
    response = client.get("/market-data/indicators")
    assert response.status_code == status
    assert response.json() == ({"detail": "INDICATOR_DEADLINE_EXCEEDED"} if status == 504 else {})
    from tiewtrade.services.api.app import app

    assert app.state.indicator_budget.busy is False


def test_indicator_auth_and_sanitized_validation(client: TestClient) -> None:
    assert client.get("/market-data/indicators").status_code == 401
    register(client)
    invalid = client.get(
        "/market-data/indicators", params={"timeframe": "9m", "cursor": "sentinel-secret"}
    )
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": "INPUT_REJECTED"}


def test_indicator_read_only_pagination_contract(client: TestClient) -> None:
    register(client)
    response = client.get(
        "/market-data/indicators",
        params={"base": "BTC", "quote": "USDT", "timeframe": "1m", "page_size": 2},
    )
    assert response.status_code == 200, response.text
    first = response.json()
    assert len(first["rows"]) == 2 and first["next_cursor"]
    assert response.headers["cache-control"] == "private, no-store"
    second = client.get("/market-data/indicators", params={"cursor": first["next_cursor"]})
    assert second.status_code == 200, second.text
    assert second.json()["dataset_revision"] == first["dataset_revision"]
    assert second.json()["rows"][0]["open_at"] > first["rows"][-1]["open_at"]
