from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import create_autospec
from uuid import UUID

import pytest

from tiewtrade.application.paper_spot_session import (
    PaperSpotSession,
    PaperSpotSessionIdentity,
    PaperSpotSessionSnapshot,
    PaperSpotSessionState,
)
from tiewtrade.execution.paper_spot import PaperSpotEntryFill, PaperSpotExitFill
from tiewtrade.integrations.sqlite.paper_spot_history import PaperSpotSQLiteHistory
from tiewtrade.integrations.sqlite.persistent_paper_spot_session import (
    PersistenceState,
    PersistentPaperSpotSQLiteSession,
    SessionPersistenceBlockedError,
)
from tiewtrade.integrations.sqlite.trade_history import (
    TradeHistoryConflictError,
    TradeHistoryUnavailableError,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.basket import ClosedBasket

SESSION_ID = UUID("00000000-0000-0000-0000-000000000101")
BASKET_ID = UUID("00000000-0000-0000-0000-000000000102")
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


def entry_fill() -> PaperSpotEntryFill:
    return PaperSpotEntryFill(
        intent_id="intent-1",
        order_id="entry:intent-1",
        fill_id=f"paper:{SESSION_ID}:entry:intent-1:fill",
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=FILLED_AT,
    )


def exit_fill() -> PaperSpotExitFill:
    return PaperSpotExitFill(
        order_id=f"take-profit:{BASKET_ID}",
        fill_id=f"paper:{SESSION_ID}:take-profit:{BASKET_ID}:fill",
        price=Decimal("110"),
        quantity=Decimal("2"),
        fee=Decimal("0.22"),
        filled_at=FILLED_AT,
    )


def closed_basket() -> ClosedBasket:
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
    )


def entry_snapshot() -> PaperSpotSessionSnapshot:
    return PaperSpotSessionSnapshot(
        accepted=True,
        state=PaperSpotSessionState.ACTIVE,
        failure_reason=None,
        pending_intent=None,
        entry_fill=entry_fill(),
        take_profit_fill=None,
        closed_basket=None,
        closed_basket_count=0,
        basket_id=BASKET_ID,
        basket_entry_count=1,
        take_profit_price=Decimal("105"),
    )


def close_snapshot() -> PaperSpotSessionSnapshot:
    return PaperSpotSessionSnapshot(
        accepted=True,
        state=PaperSpotSessionState.ACTIVE,
        failure_reason=None,
        pending_intent=None,
        entry_fill=None,
        take_profit_fill=exit_fill(),
        closed_basket=closed_basket(),
        closed_basket_count=1,
        basket_id=BASKET_ID,
        basket_entry_count=0,
        take_profit_price=None,
    )


def session_identity() -> PaperSpotSessionIdentity:
    return PaperSpotSessionIdentity(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )


def persistent_session(
    session: PaperSpotSession,
    history: PaperSpotSQLiteHistory,
) -> PersistentPaperSpotSQLiteSession:
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = session_identity()  # type: ignore[misc]
    return PersistentPaperSpotSQLiteSession(session, history)


def test_constructor_rejects_mismatched_session_and_history_identity() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = replace(  # type: ignore[misc]
        session_identity(),
        timeframe="15m",
    )

    with pytest.raises(ValueError, match="identity"):
        PersistentPaperSpotSQLiteSession(session, history)


def test_successful_entry_is_durable_before_ready_snapshot_returns() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = entry_snapshot()
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
    assert result.session == entry_snapshot()
    assert result.persistence_state is PersistenceState.READY


def test_successful_close_is_durable_before_ready_snapshot_returns() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = close_snapshot()
    history.record_close.return_value = True
    persistent = persistent_session(session, history)
    candle = completed_candle()

    result = persistent.process_completed_candle(
        candle,
        received_at=candle.close_time,
    )

    history.record_close.assert_called_once_with(
        basket_id=BASKET_ID,
        fill=exit_fill(),
        closed=closed_basket(),
    )
    assert result.session == close_snapshot()
    assert result.persistence_state is PersistenceState.READY


def test_take_profit_fill_without_closed_basket_blocks_persistence() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = replace(
        entry_snapshot(),
        entry_fill=None,
        take_profit_fill=exit_fill(),
        closed_basket=None,
    )
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="present together"):
        persistent.process_completed_candle(candle, received_at=candle.close_time)

    history.record_close.assert_not_called()


def test_closed_basket_with_mismatched_snapshot_basket_id_blocks_persistence() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = replace(
        close_snapshot(),
        basket_id=UUID("00000000-0000-0000-0000-000000000199"),
    )
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="matching Basket ID"):
        persistent.process_completed_candle(candle, received_at=candle.close_time)

    history.record_close.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        TradeHistoryUnavailableError("forced failure"),
        TradeHistoryConflictError("conflicting Fill"),
    ],
)
def test_persistence_error_blocks_every_later_candle(error: Exception) -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = entry_snapshot()
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
