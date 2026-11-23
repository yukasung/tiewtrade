"""Readiness classification only; no financial or transaction path is mocked."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tests.strategies.fixtures import money, snapshot
from tiewtrade.core.market_data import CandleFinality, Timeframe, advance
from tiewtrade.core.strategy_config import PaperTestConfig, RsiStepGridConfig
from tiewtrade.infra.bots.inputs import BotInputsUnavailableError, read_bot_indicators
from tiewtrade.infra.db.session import UserSession
from tiewtrade.strategies.paper_test.strategy import PaperTestStrategy
from tiewtrade.strategies.rsi_step_grid.strategy import RsiStepGridStrategy


@pytest.mark.parametrize("paper_test", [False, True])
@pytest.mark.parametrize("finality", [CandleFinality.UNCONFIRMED, CandleFinality.OPEN])
async def test_nonclosed_indicator_point_is_rejected_with_precise_reason(
    monkeypatch: pytest.MonkeyPatch, paper_test: bool, finality: CandleFinality
) -> None:
    value = snapshot()
    strategy = (
        PaperTestStrategy(PaperTestConfig(value.pair, Timeframe.M5, money("100")))
        if paper_test
        else RsiStepGridStrategy(RsiStepGridConfig(value.pair, Timeframe.M5, money("100"), 10))
    )
    session = AsyncMock(spec=UserSession)
    result = MagicMock()
    result.scalar_one.return_value = datetime.now(UTC)
    session.execute.return_value = result
    assert value.candle_input is not None
    opened = value.candle_input.candle.open_at
    point = SimpleNamespace(
        finality=finality,
        open_at=opened,
        values=dict(value.indicators),
        seed_open_at=advance(opened, Timeframe.M5, -249),
    )
    page = SimpleNamespace(
        generation={"id": uuid4(), "source_epoch": uuid4()},
        result=SimpleNamespace(points=(point,), revision="readiness-fixture"),
    )
    context = AsyncMock(return_value=value.candle_input)  # CLOSED fixture, no closure proof.
    monkeypatch.setattr("tiewtrade.infra.bots.inputs._candle_context", context)
    monkeypatch.setattr("tiewtrade.infra.bots.inputs.rollout_control", AsyncMock(return_value={}))
    monkeypatch.setattr(
        "tiewtrade.infra.bots.inputs.read_bot_indicator_page", AsyncMock(return_value=page)
    )
    reason = (
        "BOT_CANDLE_UNCONFIRMED"
        if finality is CandleFinality.UNCONFIRMED
        else "INDICATOR_NOT_READY"
    )
    with pytest.raises(BotInputsUnavailableError, match=f"^{reason}$"):
        await read_bot_indicators(session, strategy.descriptor, value)

    if finality is CandleFinality.UNCONFIRMED:
        context.assert_awaited_once()
    else:
        context.assert_not_awaited()
