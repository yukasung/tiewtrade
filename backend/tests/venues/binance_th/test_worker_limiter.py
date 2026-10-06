"""Worker composition must preserve IP usage across keys and rounds (F-07 V-38.1)."""

from datetime import timedelta

import httpx
import pytest

from tiewtrade.infra.api_keys import HmacRequestSigner
from tiewtrade.services.engine import main
from tiewtrade.venues.errors import VenueRateLimitedError

from .conftest import FakeClock


def signer(name: str) -> HmacRequestSigner:
    return HmacRequestSigner(public_identifier=name, secret=b"synthetic-test-secret")


async def test_reported_ip_usage_is_shared_between_keys_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(main, "_now", clock)
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["X-MBX-APIKEY"])
        return httpx.Response(
            200,
            json={"balances": []},
            headers={"x-mbx-used-weight-1m": "6000"} if len(calls) == 1 else {},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        factory = main._wallet_factory(client)
        await factory(signer("first-key")).holdings()
        with pytest.raises(VenueRateLimitedError) as limited:
            await factory(signer("second-key")).holdings()
        assert limited.value.retry_after == timedelta(minutes=1)
        assert calls == ["first-key"]
        clock.advance(timedelta(minutes=1))
        await factory(signer("second-key")).holdings()
    assert calls == ["first-key", "second-key"]


async def test_request_weight_is_shared_without_response_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_now", FakeClock())
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["X-MBX-APIKEY"])
        return httpx.Response(200, json={"balances": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        factory = main._wallet_factory(client)
        # Account costs 20; 50 requests reach the documented 1,000/10s window.
        for index in range(50):
            await factory(signer(f"key-{index}")).holdings()
        with pytest.raises(VenueRateLimitedError):
            await factory(signer("key-51")).holdings()
    assert len(calls) == 50
