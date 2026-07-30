from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.application.paper_futures_session import (
    PaperFuturesFailureReason,
    PaperFuturesSession,
    PaperFuturesSessionError,
    PaperFuturesSessionIdentity,
    PaperFuturesSessionState,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.basket import BasketCloseReason
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules


def test_session_requires_paper_futures_configuration_and_matching_preset() -> None:
    session = futures_session()

    with pytest.raises(ValueError, match="Paper Futures"):
        make_session(replace(session, trade_mode=TradeMode.LIVE))

    spot_session = SessionConfig(
        session_id=session.session_id,
        preset_version=session.preset_version,
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=session.available_capital,
        fee_rate=session.fee_rate,
        slippage_bps=session.slippage_bps,
        entry_policy=session.entry_policy,
        spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.8")),
    )
    with pytest.raises(ValueError, match="Paper Futures"):
        make_session(spot_session)

    with pytest.raises(ValueError, match="preset version"):
        make_session(replace(session, preset_version="wrong-version"))


def test_session_requires_futures_policy() -> None:
    session = futures_session()
    object.__setattr__(session, "futures_policy", None)

    with pytest.raises(ValueError, match="futures_policy"):
        make_session(session)


def test_session_exposes_immutable_persistence_identity() -> None:
    session = make_session()

    assert session.identity == PaperFuturesSessionIdentity(
        session_id=UUID("00000000-0000-0000-0000-000000000108"),
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
        leverage=5,
    )


def test_incomplete_candle_is_not_processed() -> None:
    session = make_session()
    incomplete = candle(0, open="100", close="101")

    snapshot = session.process_completed_candle(
        incomplete,
        received_at=incomplete.close_time - timedelta(seconds=1),
    )

    assert snapshot.accepted is False
    assert session._latest_mark_price is None


def test_entry_fill_can_liquidate_on_the_same_candle() -> None:
    session = make_session()
    pending = arm_entry_intent(session)
    liquidation_candle = next_candle(
        pending.signal_candle,
        open="120",
        high="121",
        low="10",
        close="20",
    )

    snapshot = session.process_completed_candle(
        liquidation_candle,
        received_at=liquidation_candle.close_time,
    )

    assert snapshot.entry_fill is not None
    assert snapshot.exit_fill is not None
    assert snapshot.exit_fill.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.state is PaperFuturesSessionState.LIQUIDATED
    assert snapshot.closed_basket is not None
    assert snapshot.closed_basket.close_reason is BasketCloseReason.LIQUIDATION


def test_liquidation_wins_when_same_candle_touches_take_profit() -> None:
    session, entry_candle = make_session_with_open_long_basket()
    ambiguous_candle = next_candle(
        entry_candle,
        open="120",
        high="200",
        low="10",
        close="120",
    )

    snapshot = session.process_completed_candle(
        ambiguous_candle,
        received_at=ambiguous_candle.close_time,
    )

    assert snapshot.exit_fill is not None
    assert snapshot.exit_fill.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.closed_basket is not None
    assert snapshot.closed_basket.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.state is PaperFuturesSessionState.LIQUIDATED


def test_session_does_not_call_executor_before_liquidation_crossing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, entry_candle = make_session_with_open_long_basket()
    session._liquidation_price = Decimal("80")
    safe_candle = next_candle(
        entry_candle,
        open="100",
        high="110",
        low="90",
        close="100",
    )

    def unexpected_liquidation_fill(*args: object, **kwargs: object) -> None:
        raise AssertionError("executor called before liquidation crossing")

    monkeypatch.setattr(
        session._executor,
        "fill_liquidation",
        unexpected_liquidation_fill,
    )

    snapshot = session.process_completed_candle(
        safe_candle,
        received_at=safe_candle.close_time,
    )

    assert snapshot.accepted
    assert snapshot.state is PaperFuturesSessionState.ACTIVE
    assert snapshot.exit_fill is None


def test_liquidated_session_rejects_future_candles_without_mutation() -> None:
    session, liquidation_candle = make_liquidated_session()
    before = session.snapshot
    following_candle = next_candle(
        liquidation_candle,
        open="20",
        high="21",
        low="19",
        close="20",
    )

    after = session.process_completed_candle(
        following_candle,
        received_at=following_candle.close_time,
    )

    assert not after.accepted
    assert after.state is before.state
    assert after.closed_basket == before.closed_basket
    assert after.basket_id == before.basket_id
    assert after.basket_entry_count == before.basket_entry_count
    assert after.account_equity == before.account_equity
    assert after.failure_reason is before.failure_reason


def test_unexpected_execution_error_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = make_session()
    pending = arm_entry_intent(session)
    entry_candle = next_candle(
        pending.signal_candle,
        open="120",
        high="121",
        low="119",
        close="120",
    )

    def raise_execution_error(*args: object, **kwargs: object) -> None:
        raise ValueError("broken execution invariant")

    monkeypatch.setattr(session._executor, "fill_entry", raise_execution_error)

    with pytest.raises(PaperFuturesSessionError, match="execution failed"):
        session.process_completed_candle(
            entry_candle,
            received_at=entry_candle.close_time,
        )

    assert session.snapshot.state is PaperFuturesSessionState.FAILED_CLOSED
    assert session.snapshot.failure_reason is PaperFuturesFailureReason.EXECUTION_ERROR
    assert session.snapshot.pending_intent is None
    assert session._strategy._pending_intent is None

    before = session.snapshot
    following_candle = next_candle(
        entry_candle,
        open="120",
        high="121",
        low="119",
        close="120",
    )
    after = session.process_completed_candle(
        following_candle,
        received_at=following_candle.close_time,
    )
    assert not after.accepted
    assert after.state is before.state
    assert after.basket_id == before.basket_id
    assert after.basket_entry_count == before.basket_entry_count
    assert after.account_equity == before.account_equity


def test_unexpected_margin_error_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = make_session()
    pending = arm_entry_intent(session)
    entry_candle = next_candle(
        pending.signal_candle,
        open="120",
        high="121",
        low="119",
        close="120",
    )

    def raise_margin_error(*args: object, **kwargs: object) -> None:
        raise ValueError("broken margin invariant")

    monkeypatch.setattr(session._margin, "liquidation_price", raise_margin_error)

    with pytest.raises(PaperFuturesSessionError, match="execution failed"):
        session.process_completed_candle(
            entry_candle,
            received_at=entry_candle.close_time,
        )

    assert session.snapshot.state is PaperFuturesSessionState.FAILED_CLOSED
    assert session.snapshot.failure_reason is PaperFuturesFailureReason.EXECUTION_ERROR
    assert session.snapshot.pending_intent is None
    assert session.snapshot.basket_id is None
    assert session.snapshot.basket_entry_count == 0
    assert session.snapshot.position_side is None
    assert session.snapshot.take_profit_price is None
    assert session.snapshot.liquidation_price is None
    assert session.snapshot.account_equity == Decimal("1000")
    assert session._basket is None
    assert session._lifecycle.entry_count == 0
    assert session._strategy._pending_intent is None


@pytest.mark.parametrize("failure_path", ["executor", "margin"])
def test_failure_cleanup_cannot_prevent_terminal_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    failure_path: str,
) -> None:
    session = make_session()
    pending = arm_entry_intent(session)
    entry_candle = next_candle(
        pending.signal_candle,
        open="120",
        high="121",
        low="119",
        close="120",
    )

    def raise_primary_error(*args: object, **kwargs: object) -> None:
        raise ValueError(f"broken {failure_path} invariant")

    def raise_cleanup_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("strategy cleanup failed")

    monkeypatch.setattr(session._strategy, "on_entry_rejected", raise_cleanup_error)
    if failure_path == "executor":
        monkeypatch.setattr(session._executor, "fill_entry", raise_primary_error)
    else:
        monkeypatch.setattr(
            session._margin,
            "liquidation_price",
            raise_primary_error,
        )

    captured: Exception | None = None
    try:
        session.process_completed_candle(
            entry_candle,
            received_at=entry_candle.close_time,
        )
    except Exception as error:
        captured = error

    actual = f"error={type(captured).__name__}, state={session.snapshot.state.value}"
    assert (
        isinstance(captured, PaperFuturesSessionError)
        and session.snapshot.state is PaperFuturesSessionState.FAILED_CLOSED
    ), actual
    assert session.snapshot.failure_reason is PaperFuturesFailureReason.EXECUTION_ERROR
    assert session.snapshot.pending_intent is None
    assert session._strategy._pending_intent is None


def test_rejected_entry_releases_strategy_to_rearm_pending_intent() -> None:
    session = make_session(min_notional=Decimal("50000"))
    pending = arm_entry_intent(session)
    rejected_candle = next_candle(
        pending.signal_candle,
        open="120",
        high="122",
        low="119",
        close="121",
    )

    snapshot = session.process_completed_candle(
        rejected_candle,
        received_at=rejected_candle.close_time,
    )

    assert snapshot.entry_fill is None
    assert snapshot.basket_id is None
    assert snapshot.pending_intent is not None
    assert snapshot.pending_intent.intent_id != pending.intent_id
    assert session._strategy._pending_intent == snapshot.pending_intent


def test_new_take_profit_cannot_fill_on_the_entry_candle() -> None:
    session = make_session()
    pending = arm_entry_intent(session)
    entry_candle = next_candle(
        pending.signal_candle,
        open="120",
        high="1000",
        low="100",
        close="121",
    )

    snapshot = session.process_completed_candle(
        entry_candle,
        received_at=entry_candle.close_time,
    )

    assert snapshot.entry_fill is not None
    assert snapshot.exit_fill is None
    assert snapshot.closed_basket is None
    assert snapshot.state is PaperFuturesSessionState.ACTIVE
    assert snapshot.basket_entry_count == 1
    assert snapshot.take_profit_price is not None


def test_normal_take_profit_closes_and_resets_basket_without_ending_session() -> None:
    session, first_entry_candle = make_session_with_open_long_basket()
    second_pending = arm_next_entry_intent(session, first_entry_candle)
    second_entry_price = second_pending.signal_candle.close
    second_entry_candle = next_candle(
        second_pending.signal_candle,
        open=str(second_entry_price),
        high=str(second_entry_price + Decimal("1")),
        low=str(second_entry_price - Decimal("1")),
        close=str(second_entry_price),
    )
    second_entry = session.process_completed_candle(
        second_entry_candle,
        received_at=second_entry_candle.close_time,
    )
    assert second_entry.entry_fill is not None
    assert second_entry.basket_entry_count == 2

    target_candle = next_candle(
        second_entry_candle,
        open="120",
        high="200",
        low="100",
        close="120",
    )

    closed = session.process_completed_candle(
        target_candle,
        received_at=target_candle.close_time,
    )

    assert closed.exit_fill is not None
    assert closed.exit_fill.close_reason is BasketCloseReason.TAKE_PROFIT
    assert closed.closed_basket is not None
    assert closed.closed_basket.close_reason is BasketCloseReason.TAKE_PROFIT
    assert closed.state is PaperFuturesSessionState.ACTIVE
    assert closed.basket_entry_count == 0
    assert closed.take_profit_price is None
    assert closed.liquidation_price is None

    new_pending = arm_next_entry_intent(session, target_candle)
    new_entry_price = new_pending.signal_candle.close
    new_entry_candle = next_candle(
        new_pending.signal_candle,
        open=str(new_entry_price),
        high=str(new_entry_price + Decimal("1")),
        low=str(new_entry_price - Decimal("1")),
        close=str(new_entry_price),
    )
    new_entry = session.process_completed_candle(
        new_entry_candle,
        received_at=new_entry_candle.close_time,
    )

    assert new_entry.entry_fill is not None
    assert new_entry.state is PaperFuturesSessionState.ACTIVE
    assert new_entry.basket_entry_count == 1
    assert new_entry.basket_id != closed.basket_id


def test_entry_updates_account_equity_and_liquidation_threshold() -> None:
    session, _ = make_session_with_open_long_basket()

    snapshot = session.snapshot

    assert snapshot.entry_fill is None
    assert snapshot.position_side is PositionSide.LONG
    assert snapshot.account_equity < snapshot.capital_plan.available_capital
    assert snapshot.liquidation_price is not None


def test_account_equity_marks_open_long_to_latest_accepted_close() -> None:
    session, entry_candle = make_session_with_open_long_basket()
    mark_candle = next_candle(
        entry_candle,
        open="120",
        high="121",
        low="100",
        close="110",
    )

    snapshot = session.process_completed_candle(
        mark_candle,
        received_at=mark_candle.close_time,
    )

    assert snapshot.accepted
    assert snapshot.exit_fill is None
    assert snapshot.state is PaperFuturesSessionState.ACTIVE
    assert snapshot.account_equity == Decimal("894.752")


def test_warm_up_seeds_indicators_without_execution_side_effects() -> None:
    session = make_session()
    candles = signal_candles()

    session.warm_up_completed_candles(
        candles,
        received_at=candles[-1].close_time,
    )

    assert session.snapshot.accepted
    assert session.snapshot.pending_intent is None
    assert session.snapshot.entry_fill is None
    assert session.snapshot.basket_id is None
    assert session.snapshot.state is PaperFuturesSessionState.ACTIVE


def make_session(
    session: SessionConfig | None = None,
    *,
    min_notional: Decimal = Decimal("5"),
) -> PaperFuturesSession:
    return PaperFuturesSession(
        session or futures_session(),
        MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.1"),
            min_notional=min_notional,
        ),
        RsiStepGridPreset.v1(),
    )


def futures_session() -> SessionConfig:
    return SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000108"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.FUTURES,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("0"),
        entry_policy=EntryPolicy(max_entries=2),
        spot_policy=None,
        futures_policy=FuturesTradingPolicy.v1(leverage=5),
    )


def make_session_with_open_long_basket() -> tuple[PaperFuturesSession, Candle]:
    session = make_session()
    pending = arm_entry_intent(session)
    entry_candle = next_candle(
        pending.signal_candle,
        open="120",
        high="121",
        low="100",
        close="120",
    )
    snapshot = session.process_completed_candle(
        entry_candle,
        received_at=entry_candle.close_time,
    )
    assert snapshot.entry_fill is not None
    assert snapshot.liquidation_price is not None
    return session, entry_candle


def make_liquidated_session() -> tuple[PaperFuturesSession, Candle]:
    session, entry_candle = make_session_with_open_long_basket()
    liquidation_candle = next_candle(
        entry_candle,
        open="20",
        high="30",
        low="10",
        close="20",
    )
    snapshot = session.process_completed_candle(
        liquidation_candle,
        received_at=liquidation_candle.close_time,
    )
    assert snapshot.state is PaperFuturesSessionState.LIQUIDATED
    return session, liquidation_candle


def arm_entry_intent(session: PaperFuturesSession):
    for current in signal_candles():
        snapshot = session.process_completed_candle(
            current,
            received_at=current.close_time,
        )
        if snapshot.pending_intent is not None:
            return snapshot.pending_intent
    raise AssertionError("expected a pending Entry Intent")


def arm_next_entry_intent(session: PaperFuturesSession, previous: Candle):
    current = previous
    close = previous.close
    for _ in range(30):
        next_close = close - Decimal("1")
        current = next_candle(
            current,
            open=str(close),
            high=str(close + Decimal("1")),
            low=str(next_close - Decimal("1")),
            close=str(next_close),
        )
        session.process_completed_candle(current, received_at=current.close_time)
        close = next_close

    for _ in range(25):
        next_close = close + Decimal("1")
        current = next_candle(
            current,
            open=str(close),
            high=str(next_close + Decimal("1")),
            low=str(close - Decimal("1")),
            close=str(next_close),
        )
        snapshot = session.process_completed_candle(
            current,
            received_at=current.close_time,
        )
        if snapshot.pending_intent is not None:
            return snapshot.pending_intent
        close = next_close

    raise AssertionError("expected another pending Entry Intent")


def signal_candles() -> list[Candle]:
    candles: list[Candle] = []
    close = Decimal("100")
    for minute in range(0, 75, 5):
        candles.append(candle(minute, open=str(close + 1), close=str(close)))
        close -= Decimal("1")
    for minute in range(75, 200, 5):
        current = candle(minute, open=str(close), close=str(close + 1))
        candles.append(current)
        close += Decimal("1")
    return candles


def next_candle(
    previous: Candle,
    *,
    open: str,
    high: str,
    low: str,
    close: str,
) -> Candle:
    minute = int(
        (
            previous.open_time + timedelta(minutes=5) - datetime(2026, 1, 1, tzinfo=UTC)
        ).total_seconds()
        / 60
    )
    return candle(minute, open=open, high=high, low=low, close=close)


def candle(
    minute: int,
    *,
    open: str,
    close: str,
    high: str | None = None,
    low: str | None = None,
) -> Candle:
    open_price = Decimal(open)
    close_price = Decimal(close)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute),
        open=open_price,
        high=(
            max(open_price, close_price) + Decimal("1")
            if high is None
            else Decimal(high)
        ),
        low=(
            min(open_price, close_price) - Decimal("1") if low is None else Decimal(low)
        ),
        close=close_price,
        volume=Decimal("1"),
    )
