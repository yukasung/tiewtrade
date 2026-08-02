import asyncio
from collections.abc import AsyncIterator, Awaitable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event
from typing import NoReturn, TypeVar
from uuid import UUID

import pytest

from tests.support.paper_session_setup import configured_futures_session
from tiewtrade.application.paper_futures_session import (
    PaperFuturesSession,
    PaperFuturesSessionSnapshot,
    PaperFuturesSessionState,
)
from tiewtrade.application.paper_runtime import PaperRuntimeController
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.application.trade_history import PageRequest, TradeHistoryFilter
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    TradingWorkspaceSnapshot,
)
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_runtime_lifecycle import (
    PaperRuntimeLifecycleRecord,
    PaperRuntimeLifecycleState,
    SQLitePaperRuntimeLifecycle,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.source_errors import (
    MarketDataFailureKind,
    MarketDataFatalError,
)
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.basket import BasketCloseReason
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.symbol_rules import SymbolRules

_T = TypeVar("_T")
_RUNTIME_NOW = datetime(2026, 8, 2, 3, tzinfo=UTC)
_RECOVERED_AT = datetime(2026, 8, 2, 4, tzinfo=UTC)


class _ImmediateRuntimeScheduler:
    def now(self) -> datetime:
        return _RUNTIME_NOW

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(0)

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        return await awaitable


class _RuntimeFailureSource:
    def __init__(
        self,
        *,
        warm_up: tuple[Candle, ...],
        fail_warm_up: bool,
    ) -> None:
        self._warm_up = warm_up
        self._fail_warm_up = fail_warm_up
        self.closed = Event()

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        if self._fail_warm_up:
            raise MarketDataFatalError(
                "public source failed with api_key=secret at /private/tmp",
                kind=MarketDataFailureKind.PAYLOAD,
            )
        assert count == len(self._warm_up)
        return self._warm_up

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        raise AssertionError("failure acceptance path must not backfill")

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        return self._stream_completed()

    async def close(self) -> None:
        self.closed.set()

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        await asyncio.Event().wait()
        yield self._warm_up[-1]


class _FailingRunningLifecycle(SQLitePaperRuntimeLifecycle):
    def mark_running(
        self,
        session_id: UUID,
        observed_at_utc: datetime,
    ) -> None:
        raise RuntimeError("sqlite failed with api_key=secret at /private/tmp")


def test_interrupted_runtime_recovers_without_fabricating_strategy_state(
    tmp_path: Path,
) -> None:
    session = configured_futures_session(
        session_id=UUID("00000000-0000-0000-0000-000000000136")
    )
    database = _runtime_database(tmp_path, session)
    lifecycle = SQLitePaperRuntimeLifecycle(database)
    history = SQLiteTradeHistory(database)
    lifecycle.mark_running(session.config.session_id, _RUNTIME_NOW)
    published_states: list[BotRuntimeState] = []

    def publish(snapshot: TradingWorkspaceSnapshot) -> None:
        header = snapshot.header
        assert header is not None
        published_states.append(header.runtime_state)

    controller = PaperRuntimeController(
        lifecycle=lifecycle,
        trade_history=history,
        symbol_rules=_runtime_symbol_rules(),
        source_factory=lambda _endpoints: _unexpected_runtime_source(),
        snapshot_callback=publish,
        clock=lambda: _RECOVERED_AT,
    )

    startup = controller.inspect_startup(session)

    assert startup.workspace.header is not None
    assert startup.workspace.header.runtime_state is BotRuntimeState.BLOCKED
    assert startup.blocked_reason == "Paper Bot recovery required"
    assert startup.workspace.orders == ()
    assert startup.workspace.basket is None
    assert lifecycle.read(session.config.session_id) == PaperRuntimeLifecycleRecord(
        session_id=session.config.session_id,
        state=PaperRuntimeLifecycleState.RUNNING,
        observed_at_utc=_RUNTIME_NOW,
    )

    result = controller.recover(session)

    assert result.workspace.header is not None
    assert result.workspace.header.runtime_state is BotRuntimeState.STOPPED
    assert result.workspace.orders == ()
    assert result.workspace.basket is None
    assert published_states == [BotRuntimeState.BLOCKED, BotRuntimeState.STOPPED]
    assert lifecycle.read(session.config.session_id) == PaperRuntimeLifecycleRecord(
        session_id=session.config.session_id,
        state=PaperRuntimeLifecycleState.STOPPED,
        observed_at_utc=_RECOVERED_AT,
    )
    history_page = history.list_baskets(
        TradeHistoryFilter(market_type=MarketType.FUTURES),
        PageRequest(page=1, page_size=20),
    )
    assert history_page.items == ()


@pytest.mark.parametrize("failure", ["public_source", "sqlite_lifecycle"])
def test_runtime_start_failures_are_sanitized_and_fail_closed(
    tmp_path: Path,
    failure: str,
) -> None:
    session = configured_futures_session(
        session_id=UUID("00000000-0000-0000-0000-000000000137")
    )
    database = _runtime_database(tmp_path, session)
    source = _RuntimeFailureSource(
        warm_up=tuple(configured_entry_candles()[:15]),
        fail_warm_up=failure == "public_source",
    )
    lifecycle: SQLitePaperRuntimeLifecycle = (
        _FailingRunningLifecycle(database)
        if failure == "sqlite_lifecycle"
        else SQLitePaperRuntimeLifecycle(database)
    )
    controller = PaperRuntimeController(
        lifecycle=lifecycle,
        trade_history=SQLiteTradeHistory(database),
        symbol_rules=_runtime_symbol_rules(),
        source_factory=lambda _endpoints: source,
        snapshot_callback=lambda _snapshot: None,
        scheduler=_ImmediateRuntimeScheduler(),
        clock=lambda: _RUNTIME_NOW,
    )

    result = controller.start(session)

    assert result.workspace.header is not None
    assert result.workspace.header.runtime_state is BotRuntimeState.BLOCKED
    assert result.blocked_reason == "Paper Bot could not be started"
    assert "api_key" not in result.blocked_reason
    assert "/private/tmp" not in result.blocked_reason
    assert source.closed.wait(1)


def test_configured_paper_futures_entry_and_replay_are_deterministic() -> None:
    candles = configured_entry_candles()

    first = replay(candles)
    second = replay(candles)

    assert first == second
    entry_snapshot = next(snapshot for snapshot in first if snapshot.entry_fill)
    assert entry_snapshot.capital_plan.trading_capital == Decimal("100000.0")
    assert entry_snapshot.capital_plan.collateral_buffer == Decimal("100000.0")
    assert entry_snapshot.capital_plan.initial_margin_per_entry == Decimal("10000.0")
    assert entry_snapshot.capital_plan.target_notional_per_entry == Decimal("30000.0")
    assert entry_snapshot.entry_fill is not None
    assert entry_snapshot.entry_fill.side is PositionSide.LONG


def test_configured_adverse_candle_terminates_session_with_liquidation() -> None:
    snapshots = replay(configured_liquidation_candles())

    snapshot = snapshots[-1]

    assert all(item.state is PaperFuturesSessionState.ACTIVE for item in snapshots[:-1])
    assert snapshots[-2].state is PaperFuturesSessionState.ACTIVE
    assert snapshot.accepted
    assert snapshot.exit_fill is not None
    assert snapshot.exit_fill.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.closed_basket is not None
    assert snapshot.closed_basket.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.state is PaperFuturesSessionState.LIQUIDATED


def _runtime_database(
    tmp_path: Path,
    session: ConfiguredPaperSession,
) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    assert SQLiteActivePaperSessions(database).create(session).created
    return database


def _runtime_symbol_rules() -> SymbolRules:
    return SymbolRules(
        symbol="BTCUSDT",
        tick_size=Decimal("0.1"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )


def _unexpected_runtime_source() -> NoReturn:
    raise AssertionError("recovery must not start public market data")


def replay(candles: list[Candle]) -> list[PaperFuturesSessionSnapshot]:
    market_data = MarketDataConfig(symbol="BTCUSDT", timeframe="5m")
    session = PaperFuturesSession(
        SessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000108"),
            preset_version="rsi-step-grid-v1",
            market_type=MarketType.FUTURES,
            trade_mode=TradeMode.PAPER,
            available_capital=Decimal("200000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
            entry_policy=EntryPolicy(max_entries=10),
            spot_policy=None,
            futures_policy=FuturesTradingPolicy.v1(leverage=3),
        ),
        market_data,
        SymbolRules(
            symbol="BTCUSDT",
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        ),
        RsiStepGridPreset.v1(),
    )
    return [
        session.process_completed_candle(current, received_at=current.close_time)
        for current in candles
    ]


def configured_entry_candles() -> list[Candle]:
    candles: list[Candle] = []
    close = Decimal("100")
    for index in range(15):
        candles.append(configured_candle(index, close=close))
        close -= Decimal("1")
    for index in range(15, 40):
        close += Decimal("1")
        candles.append(configured_candle(index, close=close))
    return candles


def configured_liquidation_candles() -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 7, 2, tzinfo=UTC)
    candle_count = int((end - start) / timedelta(minutes=5))
    candles: list[Candle] = []
    close = Decimal("100")
    direction = Decimal("-1")
    phase_count = 0

    for index in range(candle_count):
        close += direction
        candles.append(configured_candle(index, close=close, wide_range=True))
        phase_count += 1
        if phase_count == 15:
            direction = -direction
            phase_count = 0

    last = candles[-1]
    candles.append(
        Candle(
            symbol="BTCUSDT",
            timeframe="5m",
            open_time=last.close_time,
            open=last.close,
            high=Decimal("500"),
            low=Decimal("1"),
            close=last.close,
            volume=Decimal("1"),
        )
    )
    return candles


def configured_candle(
    index: int,
    *,
    close: Decimal,
    wide_range: bool = False,
) -> Candle:
    open_price = close - Decimal("0.5")
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5),
        open=open_price,
        high=Decimal("500") if wide_range else max(open_price, close) + Decimal("1"),
        low=Decimal("50") if wide_range else min(open_price, close) - Decimal("1"),
        close=close,
        volume=Decimal("1"),
    )
