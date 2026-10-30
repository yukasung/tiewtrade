"""A busy hint cannot block another owner, but claimed failures consume budget."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from tiewtrade.core.orders import SourceUnavailableError
from tiewtrade.infra.paper_orders.dispatch import OrderClaimLostError
from tiewtrade.infra.paper_orders.request_dispatch import RequestClaimLostError
from tiewtrade.services.engine import manual_order, paper_order


@pytest.mark.parametrize("phase", ["manual", "paper"])
@pytest.mark.parametrize(
    "outcome", ["success", "deferred", "lost", "claim_commit_failure", "default"]
)
async def test_ordered_fallback_skips_busy_hint_and_counts_claim_even_after_failure(
    monkeypatch: pytest.MonkeyPatch, phase: str, outcome: str
) -> None:
    module: Any = manual_order if phase == "manual" else paper_order
    hints = [
        SimpleNamespace(user_id=uuid4(), request_id=uuid4(), command_id=uuid4()) for _ in range(3)
    ]
    claims = [None, hints[1], hints[2]]
    session = SimpleNamespace(execute=AsyncMock())
    commit_failure = False

    @asynccontextmanager
    async def context(*args: Any, **kwargs: Any) -> Any:
        nonlocal commit_failure
        yield session
        if commit_failure:
            commit_failure = False
            raise RuntimeError("controlled lost claim commit reply")

    monkeypatch.setattr(module, "user_session", context)
    monkeypatch.setattr(module, "scan_session_bypassing_rls", context)
    if phase == "paper":
        monkeypatch.setattr(module, "presented_session", context)
        monkeypatch.setattr(module, "reconcile_removal_effects", AsyncMock())
        monkeypatch.setattr(module, "reconcile_maintenance_proofs", AsyncMock())
    names = (
        ("due_requests", "claim_request", "process_request", "defer_request_claim")
        if phase == "manual"
        else ("due_orders", "claim_order", "process_claimed_order", "defer_claim")
    )
    due = AsyncMock(return_value=hints)

    async def claim_hint(*args: Any, **kwargs: Any) -> Any:
        nonlocal commit_failure
        value = claims.pop(0)
        if value is not None and outcome == "claim_commit_failure":
            commit_failure = True
        return value

    claim = AsyncMock(side_effect=claim_hint)
    process = AsyncMock()
    defer = AsyncMock()
    if outcome == "deferred":
        process.side_effect = SourceUnavailableError("controlled dependency outage")
    elif outcome == "lost":
        error = RequestClaimLostError if phase == "manual" else OrderClaimLostError
        process.side_effect = error("controlled stale claim")
    for name, function in zip(names, (due, claim, process, defer), strict=True):
        monkeypatch.setattr(module, name, function)
    run = module.run_manual_order_round if phase == "manual" else module.run_paper_order_round
    kwargs = {} if outcome == "default" else {"claim_limit": 1}
    result = await run(engine=Mock(), scan_engine=Mock(), worker="bounded", policy=None, **kwargs)
    expected_claims = 3 if outcome == "default" else 2
    assert [call.args[1] for call in claim.await_args_list] == hints[:expected_claims]
    assert process.await_count == (
        0 if outcome == "claim_commit_failure" else 2 if outcome == "default" else 1
    )
    assert result.processed == (2 if outcome == "default" else int(outcome == "success"))
    assert result.deferred == int(outcome in ("deferred", "claim_commit_failure"))
    assert result.skipped == (2 if outcome == "lost" else 1)
    assert defer.await_count == int(outcome in ("deferred", "claim_commit_failure"))
    assert due.call_args.kwargs["limit"] == 20
