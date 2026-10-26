from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.api.conftest import csrf_headers, register
from tests.api.test_totp_flow import code_now, enable_totp
from tiewtrade.infra.platform import (
    CatalogAction,
    CatalogCommand,
    ConstraintEvidence,
    PlatformRole,
)
from tiewtrade.services.api import catalog_routes
from tiewtrade.services.api.settings import TOTP_HEADER
from tiewtrade.venues import FakeVenue, Symbol, VenueUnavailableError
from tiewtrade.venues.binance_th.order_book_mapping import capability_from_pair
from tiewtrade.venues.order_books import ExecutionCapability


def test_trader_reads_only_public_catalog_shape(client: TestClient) -> None:
    register(client)

    response = client.get("/market-catalog")

    assert response.status_code == 200
    assert set(response.json()) == {"revision", "active_pairs"}
    assert response.json()["active_pairs"] == [["BTC", "USDT"], ["ETH", "USDT"]]


def test_trader_cannot_read_admin_catalog_or_impact(client: TestClient) -> None:
    register(client)

    catalog = client.get("/admin/supported-symbols")
    impact = client.get("/admin/supported-symbols/BTC/USDT/impact")

    assert catalog.status_code == 403
    assert catalog.json() == {"detail": "CATALOG_NOT_AUTHORIZED"}
    assert impact.status_code == 403
    assert impact.json() == {"detail": "CATALOG_NOT_AUTHORIZED"}


def test_catalog_mutation_requires_fresh_totp_before_endpoint(client: TestClient) -> None:
    register(client)

    response = client.post(
        "/admin/supported-symbols",
        json={
            "base": "SOL",
            "quote": "USDT",
            "expected_revision": 2,
            "reason_code": "ADMIN_LIQUIDITY_REVIEWED",
        },
        headers={**csrf_headers(client), "Idempotency-Key": "add-sol"},
    )

    assert response.status_code == 403


def _capability_payload() -> dict[str, object]:
    return {
        "symbol": "SOLUSDT",
        "baseAsset": "SOL",
        "quoteAsset": "USDT",
        "status": "TRADING",
        "orderTypes": ["MARKET", "LIMIT"],
        "filters": [
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.01",
                "maxPrice": "10000",
                "tickSize": "0.01",
            },
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.001",
                "maxQty": "1000",
                "stepSize": "0.001",
            },
            {
                "filterType": "MIN_NOTIONAL",
                "minNotional": "5",
                "applyToMarket": True,
                "avgPriceMins": 0,
            },
        ],
    }


def test_admin_add_normalizes_symbol_and_passes_exact_fake_venue_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client)
    secret, _ = enable_totp(client)
    symbol = Symbol("SOL", "USDT")
    initial = capability_from_pair(symbol, _capability_payload(), datetime.now(UTC))

    class FreshFakeVenue(FakeVenue):
        async def capability(self, requested: Symbol) -> ExecutionCapability:
            return replace(await super().capability(requested), observed_at=datetime.now(UTC))

    cast(FastAPI, client.app).state.catalog_capability_source = FreshFakeVenue(
        capabilities={symbol: initial}
    )
    captured: dict[str, object] = {}

    async def allowed(_session: object) -> PlatformRole:
        return PlatformRole.ADMIN

    async def stored(_session: object, **values: object) -> CatalogCommand:
        captured.update(values)
        now = datetime.now(UTC)
        return CatalogCommand(
            values["command_id"],  # type: ignore[arg-type]
            CatalogAction.ADD,
            str(values["base"]),
            str(values["quote"]),
            "PREPARING",
            3,
            now,
            None,
        )

    monkeypatch.setattr(catalog_routes, "role_for", allowed)
    monkeypatch.setattr(catalog_routes, "request_add", stored)
    response = client.post(
        "/admin/supported-symbols",
        json={
            "base": "sol",
            "quote": "usdt",
            "expected_revision": 2,
            "reason_code": "ADMIN_LIQUIDITY_REVIEWED",
        },
        headers={
            **csrf_headers(client),
            TOTP_HEADER: code_now(secret),
            "Idempotency-Key": "add-sol",
        },
    )

    assert response.status_code == 202, response.text
    assert response.json()["base"] == "SOL"
    assert response.json()["quote"] == "USDT"
    assert captured["expected_revision"] == 2
    evidence = cast(ConstraintEvidence, captured["evidence"])
    assert evidence.venue_symbol == "SOLUSDT"
    assert evidence.digest == initial.version


def test_admin_add_replay_does_not_depend_on_venue_availability(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(client)
    secret, _ = enable_totp(client)
    now = datetime.now(UTC)
    prior = CatalogCommand(
        UUID(int=37), CatalogAction.ADD, "SOL", "USDT", "REQUESTED", 3, now, None
    )

    async def allowed(_session: object) -> PlatformRole:
        return PlatformRole.ADMIN

    async def replayed(_session: object, **_values: object) -> CatalogCommand:
        return prior

    class UnavailableVenue(FakeVenue):
        async def capability(self, _requested: Symbol) -> ExecutionCapability:
            raise VenueUnavailableError()

    monkeypatch.setattr(catalog_routes, "role_for", allowed)
    monkeypatch.setattr(catalog_routes, "replay_command", replayed)
    cast(FastAPI, client.app).state.catalog_capability_source = UnavailableVenue()

    response = client.post(
        "/admin/supported-symbols",
        json={
            "base": "SOL",
            "quote": "USDT",
            "expected_revision": 2,
            "reason_code": "ADMIN_LIQUIDITY_REVIEWED",
        },
        headers={
            **csrf_headers(client),
            TOTP_HEADER: code_now(secret),
            "Idempotency-Key": "add-sol-replay",
        },
    )

    assert response.status_code == 202
    assert response.json()["command_id"] == str(prior.id)
