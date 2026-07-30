from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import create_autospec
from uuid import UUID

import pytest

from tiewtrade.application.paper_futures_session import (
    PaperFuturesSession,
    PaperFuturesSessionIdentity,
    PaperFuturesSessionSnapshot,
    PaperFuturesSessionState,
)
from tiewtrade.application.session_persistence import (
    PersistenceState,
    SessionPersistenceBlockedError,
    SessionPersistenceCoordinator,
)
from tiewtrade.execution.paper_futures import (
    PaperFuturesEntryFill,
    PaperFuturesExitFill,
)
from tiewtrade.integrations.sqlite.paper_futures_history import (
    PaperFuturesSQLiteHistory,
)
from tiewtrade.integrations.sqlite.persistent_paper_futures_session import (
    create_persistent_paper_futures_session,
)
from tiewtrade.integrations.sqlite.trade_history import (
    TradeHistoryConflictError,
    TradeHistoryUnavailableError,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.basket import BasketCloseReason, ClosedBasket
from tiewtrade.trading.capital import FuturesCapitalPlan
from tiewtrade.trading.position import PositionSide

SESSION_ID = UUID("00000000-0000-0000-0000-000000000108")
BASKET_ID = UUID("00000000-0000-0000-0000-000000000109")
FILLED_AT = datetime(2026, 1, 1, 0, 5, tzinfo=UTC)


def completed_candle() -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("111"),
        low=Decimal("99"),
        close=Decimal("110"),
        volume=Decimal("10"),
    )


def capital_plan() -> FuturesCapitalPlan:
    return FuturesCapitalPlan(
        available_capital=Decimal("200000"),
        trading_capital=Decimal("100000"),
        collateral_buffer=Decimal("100000"),
        initial_margin_per_entry=Decimal("10000"),
        target_notional_per_entry=Decimal("30000"),
    )


def entry_fill() -> PaperFuturesEntryFill:
    return PaperFuturesEntryFill(
        order_id="entry:intent-1",
        fill_id=f"paper:{SESSION_ID}:entry:intent-1:fill",
        intent_id="intent-1",
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=FILLED_AT,
    )


def exit_fill(
    reason: BasketCloseReason = BasketCloseReason.TAKE_PROFIT,
) -> PaperFuturesExitFill:
    return PaperFuturesExitFill(
        order_id=f"{reason.value}:{BASKET_ID}",
        fill_id=f"paper:{SESSION_ID}:{reason.value}:{BASKET_ID}:fill",
        side=PositionSide.LONG,
        close_reason=reason,
        price=Decimal("110"),
        quantity=Decimal("2"),
        fee=Decimal("0.22"),
        filled_at=FILLED_AT,
    )


def closed_basket(
    reason: BasketCloseReason = BasketCloseReason.TAKE_PROFIT,
) -> ClosedBasket:
    return ClosedBasket(
        basket_id=BASKET_ID,
        entry_count=1,
        average_entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        gross_realized_pnl=Decimal("20"),
        trading_fees=Decimal("0.42"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("19.58"),
        closed_at=FILLED_AT,
        position_side=PositionSide.LONG,
        close_reason=reason,
    )


def snapshot(
    *,
    entry: PaperFuturesEntryFill | None = None,
    exit: PaperFuturesExitFill | None = None,
    closed: ClosedBasket | None = None,
    state: PaperFuturesSessionState = PaperFuturesSessionState.ACTIVE,
) -> PaperFuturesSessionSnapshot:
    return PaperFuturesSessionSnapshot(
        accepted=True,
        state=state,
        pending_intent=None,
        entry_fill=entry,
        exit_fill=exit,
        closed_basket=closed,
        basket_id=BASKET_ID if entry is not None or closed is not None else None,
        basket_entry_count=1 if entry is not None else 0,
        position_side=PositionSide.LONG,
        take_profit_price=Decimal("105") if closed is None else None,
        liquidation_price=Decimal("50") if closed is None else None,
        account_equity=Decimal("200000"),
        capital_plan=capital_plan(),
        failure_reason=None,
    )


def session_identity() -> PaperFuturesSessionIdentity:
    return PaperFuturesSessionIdentity(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
        leverage=3,
    )


def persistent_session(
    session: PaperFuturesSession,
    history: PaperFuturesSQLiteHistory,
) -> SessionPersistenceCoordinator[PaperFuturesSessionSnapshot]:
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = session_identity()  # type: ignore[misc]
    return create_persistent_paper_futures_session(session, history)


def test_entry_is_durable_before_ready_snapshot_returns() -> None:
    session = create_autospec(PaperFuturesSession, instance=True)
    history = create_autospec(PaperFuturesSQLiteHistory, instance=True)
    core_snapshot = snapshot(entry=entry_fill())
    session.process_completed_candle.return_value = core_snapshot
    history.record_entry.return_value = True
    persistent = persistent_session(session, history)
    candle = completed_candle()

    result = persistent.process_completed_candle(
        candle,
        received_at=candle.close_time,
    )

    history.record_entry.assert_called_once_with(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )
    assert result.session == core_snapshot
    assert result.persistence_state is PersistenceState.READY


@pytest.mark.parametrize(
    ("reason", "state"),
    [
        (BasketCloseReason.TAKE_PROFIT, PaperFuturesSessionState.ACTIVE),
        (BasketCloseReason.LIQUIDATION, PaperFuturesSessionState.LIQUIDATED),
    ],
)
def test_exit_is_durable_before_ready_snapshot_returns(
    reason: BasketCloseReason,
    state: PaperFuturesSessionState,
) -> None:
    session = create_autospec(PaperFuturesSession, instance=True)
    history = create_autospec(PaperFuturesSQLiteHistory, instance=True)
    fill = exit_fill(reason)
    closed = closed_basket(reason)
    core_snapshot = snapshot(exit=fill, closed=closed, state=state)
    session.process_completed_candle.return_value = core_snapshot
    history.record_close.return_value = True
    persistent = persistent_session(session, history)
    candle = completed_candle()

    result = persistent.process_completed_candle(
        candle,
        received_at=candle.close_time,
    )

    history.record_close.assert_called_once_with(
        basket_id=BASKET_ID,
        fill=fill,
        closed=closed,
    )
    assert result.session == core_snapshot
    assert result.persistence_state is PersistenceState.READY


def test_same_candle_entry_and_liquidation_use_closed_entry_count() -> None:
    session = create_autospec(PaperFuturesSession, instance=True)
    history = create_autospec(PaperFuturesSQLiteHistory, instance=True)
    entry = entry_fill()
    exit = exit_fill(BasketCloseReason.LIQUIDATION)
    closed = closed_basket(BasketCloseReason.LIQUIDATION)
    core_snapshot = replace(
        snapshot(
            entry=entry,
            exit=exit,
            closed=closed,
            state=PaperFuturesSessionState.LIQUIDATED,
        ),
        basket_entry_count=0,
    )
    session.process_completed_candle.return_value = core_snapshot
    history.record_entry.return_value = True
    history.record_close.return_value = True
    persistent = persistent_session(session, history)
    candle = completed_candle()

    persistent.process_completed_candle(
        candle,
        received_at=candle.close_time,
    )

    history.record_entry.assert_called_once_with(
        basket_id=BASKET_ID,
        entry_number=closed.entry_count,
        fill=entry,
    )
    history.record_close.assert_called_once_with(
        basket_id=BASKET_ID,
        fill=exit,
        closed=closed,
    )


@pytest.mark.parametrize(
    "error",
    [
        TradeHistoryUnavailableError("forced failure"),
        TradeHistoryConflictError("conflicting Fill"),
    ],
)
def test_persistence_error_blocks_every_later_candle(error: Exception) -> None:
    session = create_autospec(PaperFuturesSession, instance=True)
    history = create_autospec(PaperFuturesSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = snapshot(entry=entry_fill())
    history.record_entry.side_effect = error
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(type(error), match=str(error)):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    with pytest.raises(SessionPersistenceBlockedError, match="blocked"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    session.process_completed_candle.assert_called_once()
    history.record_entry.assert_called_once()


def test_invalid_snapshot_invariant_fails_closed() -> None:
    session = create_autospec(PaperFuturesSession, instance=True)
    history = create_autospec(PaperFuturesSQLiteHistory, instance=True)
    invalid = replace(snapshot(entry=entry_fill()), basket_id=None)
    session.process_completed_candle.return_value = invalid
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="Basket ID"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )
    with pytest.raises(SessionPersistenceBlockedError, match="blocked"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    session.process_completed_candle.assert_called_once()
    history.record_entry.assert_not_called()


def test_exit_without_closed_basket_fails_closed() -> None:
    session = create_autospec(PaperFuturesSession, instance=True)
    history = create_autospec(PaperFuturesSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = snapshot(exit=exit_fill())
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="present together"):
        persistent.process_completed_candle(
            candle,
            received_at=candle.close_time,
        )

    history.record_close.assert_not_called()


def test_factory_rejects_mismatched_session_and_history_identity() -> None:
    session = create_autospec(PaperFuturesSession, instance=True)
    history = create_autospec(PaperFuturesSQLiteHistory, instance=True)
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = replace(  # type: ignore[misc]
        session_identity(),
        leverage=4,
    )

    with pytest.raises(ValueError, match="identity"):
        create_persistent_paper_futures_session(session, history)
