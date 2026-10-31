"""Production/F18 worker scheduling agrees; the standalone F15 default stays20."""

import argparse
import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import event

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits import profile_workload as f18
from tiewtrade.services.engine import paper_order_main as runtime


async def test_production_interleaves_both_phases_and_closes_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engines = [SimpleNamespace(dispose=AsyncMock()), SimpleNamespace(dispose=AsyncMock())]
    calls = []
    monkeypatch.setattr(runtime, "create_engine_for", Mock(side_effect=engines))

    async def manual(**kwargs: Any) -> None:
        calls.append(("manual", kwargs["limit"], kwargs["claim_limit"]))

    async def paper(**kwargs: Any) -> None:
        assert kwargs["prefer_same_pair"] is runtime.PREFER_SAME_PAIR_ADMISSION
        assert kwargs["admission_first"] is False
        assert kwargs["source_resumption"] is runtime.SOURCE_RESUMPTION
        calls.append(("matching", kwargs["limit"], kwargs["claim_limit"]))
        raise asyncio.CancelledError

    monkeypatch.setattr(runtime, "run_manual_order_round", manual)
    monkeypatch.setattr(runtime, "run_paper_order_round", paper)
    with pytest.raises(asyncio.CancelledError):
        await runtime.serve()
    assert calls == [("manual", 20, 1), ("matching", 20, 1)]
    for engine in engines:
        engine.dispose.assert_awaited_once()


@pytest.mark.parametrize("limit", [None, 1])
async def test_harness_uses_explicit_limit_and_retains_f15_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: int | None
) -> None:
    stop = tmp_path / "stop"
    engine = SimpleNamespace(sync_engine=Mock(), dispose=AsyncMock())
    calls = []
    monkeypatch.setattr(f15, "create_engine_for", lambda role: engine)
    monkeypatch.setattr(event, "listens_for", lambda *args, **kwargs: lambda fn: fn)

    async def manual(**kwargs: Any) -> None:
        calls.append(("manual", kwargs["limit"], kwargs["claim_limit"]))

    async def paper(**kwargs: Any) -> None:
        calls.append(("matching", kwargs["limit"], kwargs["claim_limit"]))
        stop.touch()

    monkeypatch.setattr(f15, "run_manual_order_round", manual)
    monkeypatch.setattr(f15, "run_paper_order_round", paper)
    if limit is None:
        await f15.run_worker_process(
            "standalone", stop, tmp_path / "metrics.json", manual_intake=True
        )
    else:
        await f15.run_worker_process(
            "integrated",
            stop,
            tmp_path / "metrics.json",
            manual_intake=True,
            round_limit=20,
            claim_limit=limit,
        )
    assert calls == [("manual", 20, limit), ("matching", 20, limit)]
    assert engine.dispose.await_count == 2


async def test_f18_worker_passes_production_limit_to_reused_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = AsyncMock()
    monkeypatch.setattr(f15, "run_worker_process", run)
    await f18.worker(
        argparse.Namespace(
            worker="paper-0", metrics=tmp_path / "paper.json", stop=tmp_path / "stop"
        )
    )
    assert run.await_count == 1
    assert run.call_args.kwargs["round_limit"] == runtime.CANDIDATE_LIMIT == 20
    assert run.call_args.kwargs["claim_limit"] == runtime.CLAIM_LIMIT == 1
    assert run.call_args.kwargs["manual_intake"]
    assert run.call_args.kwargs["prefer_same_pair"] is runtime.PREFER_SAME_PAIR_ADMISSION
    assert run.call_args.kwargs["alternate_admission"] is runtime.ALTERNATE_ADMISSION_PRIORITY
    assert run.call_args.kwargs["source_resumption"] is runtime.SOURCE_RESUMPTION
