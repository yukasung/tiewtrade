from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import create_autospec
from uuid import UUID, uuid5

import pytest

from tiewtrade.application.paper_spot_session import (
    PaperSpotFailureReason,
    PaperSpotSession,
    PaperSpotSessionError,
    PaperSpotSessionIdentity,
    PaperSpotSessionSnapshot,
    PaperSpotSessionState,
)
from tiewtrade.application.session_persistence import SessionPersistenceCoordinator
from tiewtrade.integrations.sqlite.paper_spot_history import PaperSpotSQLiteHistory
from tiewtrade.integrations.sqlite.persistent_paper_spot_session import (
    create_persistent_paper_spot_session,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.indicators import WilderIndicators
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import RsiStepGridStrategy
from tiewtrade.trading.entry_pair import EntryPairLifecycle
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.session_config import (
    MarketType,
    SessionConfig,
    TradeMode,
)
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules


def test_session_rejects_a_non_paper_spot_configuration() -> None:
    config = session_config(trade_mode=TradeMode.LIVE)

    with pytest.raises(ValueError, match="Paper Spot"):
        PaperSpotSession(
            config,
            MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
            SymbolRules(
                symbol="BTCUSDT",
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.001"),
                min_notional=Decimal("5"),
            ),
            RsiStepGridPreset.v1(),
        )


def test_session_exposes_immutable_persistence_identity() -> None:
    application = paper_session()

    assert application.identity == PaperSpotSessionIdentity(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )


def test_pending_intent_fills_at_the_next_completed_candle_open() -> None:
    session = session_config()
    application = PaperSpotSession(
        session,
        MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        RsiStepGridPreset.v1(),
    )
    pending = arm_entry_intent(application)
    fill_candle = candle(125, open_price="120", close_price="121")

    snapshot = application.process_completed_candle(
        fill_candle, received_at=fill_candle.close_time
    )

    assert pending.signal_candle.open_time < fill_candle.open_time
    assert snapshot.entry_fill is not None
    assert snapshot.entry_fill.intent_id == pending.intent_id
    assert snapshot.entry_fill.price == Decimal("120.30")
    assert snapshot.basket_id == uuid5(session.session_id, "basket:1")
    assert snapshot.basket_entry_count == 1
    assert snapshot.take_profit_price == Decimal("129.30")


def test_snapshot_has_no_basket_id_before_first_entry() -> None:
    application = paper_session()
    first_candle = candle(0, open_price="100", close_price="101")

    snapshot = application.process_completed_candle(
        first_candle,
        received_at=first_candle.close_time,
    )

    assert snapshot.accepted is True
    assert snapshot.basket_id is None


def test_warm_up_seeds_indicators_without_creating_trade_side_effects() -> None:
    application = paper_session()
    warm_up = indicator_ready_candles_with_entry_signal()
    next_candle = next_candle_after(warm_up[-1])

    application.warm_up_completed_candles(
        warm_up,
        received_at=warm_up[-1].close_time,
    )
    snapshot = application.process_completed_candle(
        next_candle,
        received_at=next_candle.close_time,
    )

    assert snapshot.entry_fill is None
    assert snapshot.closed_basket_count == 0
    assert snapshot.basket_entry_count == 0


def test_take_profit_skips_entry_fill_candle_and_closes_on_following_candle() -> None:
    application = paper_session()
    arm_entry_intent(application)
    entry_candle = candle(125, open_price="120", close_price="121", high="140")

    entry_snapshot = application.process_completed_candle(
        entry_candle, received_at=entry_candle.close_time
    )

    assert entry_snapshot.entry_fill is not None
    assert entry_snapshot.closed_basket is None
    assert entry_snapshot.take_profit_fill is None
    assert entry_snapshot.closed_basket_count == 0
    assert entry_snapshot.basket_entry_count == 1

    target_candle = candle(130, open_price="125", close_price="130", high="140")
    target_snapshot = application.process_completed_candle(
        target_candle, received_at=target_candle.close_time
    )

    assert target_snapshot.closed_basket is not None
    assert target_snapshot.basket_id == target_snapshot.closed_basket.basket_id
    assert target_snapshot.closed_basket.entry_count == 1
    assert target_snapshot.take_profit_fill is not None
    assert target_snapshot.take_profit_fill.filled_at == target_candle.close_time
    assert target_snapshot.closed_basket_count == 1
    assert target_snapshot.basket_entry_count == 0
    assert target_snapshot.take_profit_price is None


def test_minimum_notional_rejection_releases_strategy_to_create_a_new_intent() -> None:
    application = paper_session(min_notional=Decimal("200"))
    first_intent = arm_entry_intent(application)
    rejected_candle = candle(125, open_price="120", close_price="121")

    rejected = application.process_completed_candle(
        rejected_candle, received_at=rejected_candle.close_time
    )

    assert rejected.entry_fill is None
    assert rejected.pending_intent is not None
    assert rejected.pending_intent.intent_id != first_intent.intent_id
    assert rejected.pending_intent.signal_candle == rejected_candle


def test_entry_transition_is_atomic_when_lifecycle_rejects_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent),
        open_price="120",
        close_price="121",
    )
    first_fill = application.process_completed_candle(
        first_fill_candle,
        received_at=first_fill_candle.close_time,
    )
    assert first_fill.basket_entry_count == 1

    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    second_fill_candle = candle(
        minute_after(second_intent),
        open_price="100",
        close_price="101",
    )

    def reject_fill(self: EntryPairLifecycle, filled_at: datetime) -> None:
        raise ValueError("entry is blocked by pair lifecycle")

    monkeypatch.setattr(EntryPairLifecycle, "record_fill", reject_fill)

    with pytest.raises(PaperSpotSessionError, match="execution failed") as captured:
        application.process_completed_candle(
            second_fill_candle,
            received_at=second_fill_candle.close_time,
        )

    assert isinstance(captured.value.__cause__, ValueError)
    assert str(captured.value.__cause__) == "entry is blocked by pair lifecycle"
    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.failure_reason is PaperSpotFailureReason.EXECUTION_ERROR
    assert application.snapshot.pending_intent is None
    assert application.snapshot.basket_entry_count == 1
    assert application._lifecycle.entry_count == 1


def test_late_entry_failure_does_not_commit_or_persist_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    persistent, history = persistent_spot_session(application)
    entry_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )

    def raise_indicator_error(*args: object, **kwargs: object) -> None:
        raise ValueError("indicator transition failed")

    monkeypatch.setattr(WilderIndicators, "update", raise_indicator_error)

    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        persistent.process_completed_candle(
            entry_candle,
            received_at=entry_candle.close_time,
        )

    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.basket_id is None
    assert application.snapshot.basket_entry_count == 0
    history.record_entry.assert_not_called()
    history.record_close.assert_not_called()


def test_late_close_failure_keeps_open_basket_and_does_not_persist_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    persistent, history = persistent_spot_session(application)
    entry_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )
    entry = persistent.process_completed_candle(
        entry_candle,
        received_at=entry_candle.close_time,
    )
    assert entry.session.basket_entry_count == 1

    def raise_indicator_error(*args: object, **kwargs: object) -> None:
        raise ValueError("indicator transition failed after close")

    monkeypatch.setattr(WilderIndicators, "update", raise_indicator_error)
    close_candle = candle(
        minute_after(pending) + 5,
        open_price="125",
        close_price="130",
        high="1000",
    )

    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        persistent.process_completed_candle(
            close_candle,
            received_at=close_candle.close_time,
        )

    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.basket_id == entry.session.basket_id
    assert application.snapshot.basket_entry_count == 1
    history.record_entry.assert_called_once()
    history.record_close.assert_not_called()


def test_strategy_callback_failure_does_not_commit_candidate_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent),
        open_price="120",
        close_price="121",
    )
    application.process_completed_candle(
        first_fill_candle,
        received_at=first_fill_candle.close_time,
    )
    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    original_strategy = application._strategy
    original_callback = RsiStepGridStrategy.on_entry_filled

    def mutate_then_raise(
        self: RsiStepGridStrategy,
        intent_id: str,
    ) -> None:
        original_callback(self, intent_id)
        raise ValueError("strategy transition failed")

    monkeypatch.setattr(RsiStepGridStrategy, "on_entry_filled", mutate_then_raise)
    second_fill_candle = candle(
        minute_after(second_intent),
        open_price="100",
        close_price="101",
    )

    with pytest.raises(PaperSpotSessionError) as captured:
        application.process_completed_candle(
            second_fill_candle,
            received_at=second_fill_candle.close_time,
        )

    assert str(captured.value.__cause__) == "strategy transition failed"
    assert application.snapshot.basket_entry_count == 1
    assert application._lifecycle.entry_count == 1
    assert original_strategy._pending_intent == second_intent
    assert application._strategy is not original_strategy


def test_failed_closed_session_rejects_later_candles_and_warm_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    failed_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )

    def raise_execution_error(*args: object, **kwargs: object) -> None:
        raise ValueError("broken execution invariant")

    monkeypatch.setattr(application._executor, "fill_entry", raise_execution_error)
    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        application.process_completed_candle(
            failed_candle,
            received_at=failed_candle.close_time,
        )

    before = application.snapshot
    following = candle(
        minute_after(pending) + 5,
        open_price="121",
        close_price="122",
    )
    after = application.process_completed_candle(
        following,
        received_at=following.close_time,
    )

    assert after.accepted is False
    assert after.state is before.state
    assert after.basket_id == before.basket_id
    assert after.basket_entry_count == before.basket_entry_count
    with pytest.raises(PaperSpotSessionError, match="not active"):
        application.warm_up_completed_candles(
            [following],
            received_at=following.close_time,
        )


def test_closed_two_entry_basket_resets_lifecycle_for_a_new_basket() -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent), open_price="120", close_price="121"
    )
    application.process_completed_candle(
        first_fill_candle, received_at=first_fill_candle.close_time
    )

    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    second_fill_candle = candle(
        minute_after(second_intent), open_price="100", close_price="101"
    )
    second_fill = application.process_completed_candle(
        second_fill_candle, received_at=second_fill_candle.close_time
    )
    assert second_fill.basket_entry_count == 2

    close_candle = candle(
        minute_after(second_intent) + 5,
        open_price="100",
        close_price="101",
        high="1000",
    )
    closed = application.process_completed_candle(
        close_candle, received_at=close_candle.close_time
    )
    assert closed.closed_basket is not None
    assert closed.closed_basket.entry_count == 2
    assert closed.take_profit_fill is not None
    assert closed.closed_basket_count == 1

    new_intent = arm_entry_intent(
        application,
        start_minute=minute_after(second_intent) + 10,
        downtrend_candles=60,
    )
    new_fill_candle = candle(
        minute_after(new_intent), open_price="120", close_price="121"
    )
    new_fill = application.process_completed_candle(
        new_fill_candle, received_at=new_fill_candle.close_time
    )

    assert new_fill.entry_fill is not None
    assert new_fill.basket_entry_count == 1
    assert new_fill.take_profit_fill is None
    assert new_fill.closed_basket is None
    assert new_fill.closed_basket_count == 1

    second_close_candle = candle(
        minute_after(new_intent) + 5,
        open_price="100",
        close_price="101",
        high="1000",
    )
    second_closed = application.process_completed_candle(
        second_close_candle, received_at=second_close_candle.close_time
    )

    assert second_closed.closed_basket is not None
    assert second_closed.take_profit_fill is not None
    assert second_closed.closed_basket_count == 2


def paper_session(*, min_notional: Decimal = Decimal("5")) -> PaperSpotSession:
    return PaperSpotSession(
        session_config(),
        MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=min_notional,
        ),
        RsiStepGridPreset.v1(),
    )


def persistent_spot_session(
    application: PaperSpotSession,
) -> tuple[
    SessionPersistenceCoordinator[PaperSpotSessionSnapshot], PaperSpotSQLiteHistory
]:
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    history.session_identity = application.identity  # type: ignore[misc]
    return create_persistent_paper_spot_session(application, history), history


def arm_entry_intent(
    application: PaperSpotSession,
    *,
    start_minute: int = 0,
    downtrend_candles: int = 15,
):
    close = Decimal("100")
    downtrend_end = start_minute + (downtrend_candles * 5)
    for minute in range(start_minute, downtrend_end, 5):
        candle_value = candle(minute, open_price=str(close + 1), close_price=str(close))
        application.process_completed_candle(
            candle_value, received_at=candle_value.close_time
        )
        close -= Decimal("1")

    for minute in range(downtrend_end, downtrend_end + 125, 5):
        candle_value = candle(minute, open_price=str(close), close_price=str(close + 1))
        snapshot = application.process_completed_candle(
            candle_value, received_at=candle_value.close_time
        )
        if snapshot.pending_intent is not None:
            return snapshot.pending_intent
        close += Decimal("1")

    raise AssertionError("expected a pending entry intent")


def candle(
    minute: int,
    *,
    open_price: str,
    close_price: str,
    high: str | None = None,
) -> Candle:
    open_decimal = Decimal(open_price)
    close_decimal = Decimal(close_price)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
        open=open_decimal,
        high=(
            max(open_decimal, close_decimal) + Decimal("1")
            if high is None
            else Decimal(high)
        ),
        low=min(open_decimal, close_decimal) - Decimal("1"),
        close=close_decimal,
        volume=Decimal("1"),
    )


def indicator_ready_candles_with_entry_signal() -> list[Candle]:
    candles: list[Candle] = []
    close = Decimal("100")

    for minute in range(0, 75, 5):
        candles.append(
            candle(minute, open_price=str(close + 1), close_price=str(close))
        )
        close -= Decimal("1")

    for minute in range(75, 125, 5):
        candles.append(
            candle(minute, open_price=str(close), close_price=str(close + 1))
        )
        close += Decimal("1")

    return candles


def next_candle_after(previous: Candle) -> Candle:
    next_open_time = previous.open_time + timedelta(minutes=5)
    return Candle(
        symbol=previous.symbol,
        timeframe=previous.timeframe,
        open_time=next_open_time,
        open=previous.close,
        high=previous.close + Decimal("2"),
        low=previous.close - Decimal("1"),
        close=previous.close + Decimal("1"),
        volume=Decimal("1"),
    )


def minute_after(intent) -> int:
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    return int((intent.signal_candle.open_time - origin).total_seconds() / 60) + 5


def session_config(**overrides: object) -> SessionConfig:
    values: dict[str, object] = {
        "session_id": UUID("00000000-0000-0000-0000-000000000079"),
        "preset_version": "rsi-step-grid-v1",
        "market_type": MarketType.SPOT,
        "trade_mode": TradeMode.PAPER,
        "available_capital": Decimal("1000"),
        "fee_rate": Decimal("0.001"),
        "slippage_bps": Decimal("25"),
        "entry_policy": EntryPolicy(max_entries=4),
        "spot_policy": SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
    }
    values.update(overrides)
    return SessionConfig(**values)  # type: ignore[arg-type]
