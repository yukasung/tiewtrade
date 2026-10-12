"""Test-only consumer of the approved V-17 HTTP protocol, not application UI."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol

import httpx


class Client(Protocol):
    def get(self, url: str, *, params: dict[str, Any], timeout: float) -> httpx.Response: ...
    def post(
        self, url: str, *, json: dict[str, Any], headers: dict[str, str], timeout: float
    ) -> httpx.Response: ...


@dataclass
class RefreshResult:
    status: str
    pages: list[dict[str, Any]]
    polls: int = 0


async def refresh_once(
    client: Client,
    initial: dict[str, Any],
    first_params: dict[str, Any],
    headers: dict[str, str],
    advance: Callable[[float], Awaitable[None]],
    *,
    requested: bool,
    clock: Callable[[], float] = monotonic,
) -> RefreshResult:
    """One explicit refresh action; fake time replaces waiting, never HTTP results."""
    result = RefreshResult("UNCHANGED", [initial])
    refresh = initial["refresh"]
    if not requested or not refresh["required"] or refresh["target"] is None:
        return result
    target = refresh["target"]
    result.status = "STOPPED"
    deadline = clock() + 60

    def remaining() -> float:
        seconds = deadline - clock()
        if seconds <= 0:
            raise TimeoutError
        return seconds

    try:
        response = client.post(
            "/market-data/candles/requests", json=target, headers=headers, timeout=remaining()
        )
        remaining()  # A late response never authorizes another request or success.
        if response.status_code not in (200, 202):
            return result
        if response.status_code == 202:
            for _ in range(6):
                await advance(min(10, remaining()))
                timeout = remaining()
                result.polls += 1
                response = client.get("/market-data/candles", params=target, timeout=timeout)
                remaining()
                if response.status_code != 200:
                    return result
                state = response.json()
                if state["status"] in ("FAILED", "UNAVAILABLE") or state["failure_code"]:
                    return result
                if not state["refresh_pending"]:
                    break
            else:
                result.status = "PENDING"
                return result
        # Neither 200 nor COMPLETE proves indicator readiness. Discard old pages
        # and use the actual indicator first-page response, with one 409 restart.
        result.pages.clear()
        for _ in range(2):
            response = client.get(
                "/market-data/indicators", params=first_params, timeout=remaining()
            )
            remaining()
            if response.status_code != 409:
                break
        if response.status_code != 200:
            return result
        body = response.json()
        result.pages.append(body)
        result.status = "REFRESH_REQUIRED" if body["refresh"]["required"] else "READY"
        return result
    except (httpx.RequestError, TimeoutError):
        # An unknown POST outcome never causes another POST in this action.
        return result
