"""The real serve loop retains one limiter across verification rounds."""

import asyncio
from typing import Any, cast

import httpx
import pytest

from tests.venues.binance_th.conftest import FakeClock
from tiewtrade.infra.api_keys import HmacRequestSigner
from tiewtrade.infra.crypto import KeyConfigurationError, KeyPurpose
from tiewtrade.services.engine import main
from tiewtrade.services.engine.verification import RoundSummary, WalletFactory
from tiewtrade.venues.errors import VenueRateLimitedError


async def test_serve_keeps_ip_usage_between_rounds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[httpx.Request] = []
    rounds = 0
    original_client = httpx.AsyncClient

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"balances": []}, headers={"x-mbx-used-weight-1m": "6000"})

    class FinishedError(Exception):
        pass

    async def run_round(**kwargs: Any) -> RoundSummary:
        nonlocal rounds
        rounds += 1
        factory = cast(WalletFactory, kwargs["wallet_for"])
        credential = HmacRequestSigner(
            public_identifier=f"round-{rounds}", secret=b"synthetic-test-secret"
        )
        if rounds == 1:
            await factory(credential).holdings()
            return RoundSummary(verified=1)
        with pytest.raises(VenueRateLimitedError):
            await factory(credential).holdings()
        raise FinishedError

    async def sleep(_: float) -> None:
        pass

    monkeypatch.setattr(main, "_now", FakeClock())
    monkeypatch.setattr(main, "create_engine_for", lambda role: object())
    monkeypatch.setattr(main, "run_round", run_round)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda: original_client(transport=httpx.MockTransport(reply)),
    )
    with pytest.raises(FinishedError):
        await main.serve()
    assert rounds == 2
    assert len(calls) == 1


async def test_engine_refuses_to_start_without_venue_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-07 V-11: missing VENUE key fails before opening resources."""
    monkeypatch.delenv(KeyPurpose.VENUE_API_SECRET.environment_variable, raising=False)

    def unexpected_resource(*args: object, **kwargs: object) -> None:
        pytest.fail("engine opened resources before checking its key")

    monkeypatch.setattr(main, "create_engine_for", unexpected_resource)
    monkeypatch.setattr(httpx, "AsyncClient", unexpected_resource)
    with pytest.raises(KeyConfigurationError):
        await main.serve()
