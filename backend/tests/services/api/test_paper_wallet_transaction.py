from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request, Response

from tiewtrade.infra.paper_wallet import (
    PaperCommand,
    PaperCommandState,
    PaperWalletAction,
    PaperWalletIntegrityError,
)
from tiewtrade.services.api import paper_wallet_routes
from tiewtrade.services.api.request_identity import Authenticated


async def test_rejection_commits_before_http_response_and_uses_dedicated_throttle_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    admission_engine = object()
    throttle_engine = object()

    @asynccontextmanager
    async def transaction(*args: object, **kwargs: object) -> AsyncIterator[object]:
        del args, kwargs
        try:
            yield object()
        except BaseException:
            events.append("rollback")
            raise
        else:
            events.append("commit")

    async def spend(engine: object, *args: object, **kwargs: object) -> None:
        del args, kwargs
        assert engine is throttle_engine
        events.append("token")

    async def reject(*args: object, **kwargs: object) -> PaperCommand:
        del args, kwargs
        events.append("result-and-audit")
        return PaperCommand(uuid4(), PaperCommandState.REJECTED, "INITIAL_CAPITAL_TOO_SMALL")

    monkeypatch.setattr(paper_wallet_routes, "engine_for", lambda *args: admission_engine)
    monkeypatch.setattr(
        paper_wallet_routes, "paper_mutation_engine", lambda request: throttle_engine
    )
    monkeypatch.setattr(paper_wallet_routes, "user_session", transaction)
    monkeypatch.setattr(paper_wallet_routes, "inspect_submission", _return_none)
    monkeypatch.setattr(paper_wallet_routes, "spend_token", spend)
    monkeypatch.setattr(paper_wallet_routes, "admit_command", reject)

    with pytest.raises(HTTPException) as caught:
        await paper_wallet_routes._submit(
            request=cast(Request, SimpleNamespace()),
            who=cast(Authenticated, SimpleNamespace(user_id=uuid4())),
            action=PaperWalletAction.CREATE,
            capital="1000",
            expected_episode_id=None,
            idempotency_key=uuid4(),
            response=Response(),
        )

    assert caught.value.status_code == 422
    assert events == ["token", "result-and-audit", "commit"]


async def _return_none(*args: object, **kwargs: object) -> None:
    del args, kwargs
    return None


async def test_inconsistent_wallet_is_reported_as_safe_dependency_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def transaction(*args: object, **kwargs: object) -> AsyncIterator[object]:
        del args, kwargs
        yield object()

    async def inconsistent(session: object) -> None:
        del session
        raise PaperWalletIntegrityError("internal detail")

    monkeypatch.setattr(paper_wallet_routes, "engine_for", lambda *args: object())
    monkeypatch.setattr(paper_wallet_routes, "repeatable_user_session", transaction)
    monkeypatch.setattr(paper_wallet_routes, "get_wallet", inconsistent)

    with pytest.raises(HTTPException) as caught:
        await paper_wallet_routes.read_paper_wallet(
            cast(Request, SimpleNamespace()),
            cast(Authenticated, SimpleNamespace(user_id=uuid4())),
        )

    assert caught.value.status_code == 503
    assert caught.value.detail == "PAPER_WALLET_DEPENDENCY_UNAVAILABLE"
