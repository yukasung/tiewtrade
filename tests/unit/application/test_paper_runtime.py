from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event, Thread
from typing import NoReturn, TypeVar
from uuid import UUID

import pytest

from tests.support.paper_session_setup import (
    configured_futures_session,
    configured_spot_session,
)
from tiewtrade.application.paper_runtime import PaperRuntimeController
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.application.trade_history import PageRequest, TradeHistoryFilter
from tiewtrade.application.trading_workspace import (
    BotRuntimeState,
    DataFreshness,
    TradingWorkspaceSnapshot,
    WorkspaceReadState,
)
from tiewtrade.integrations.binance.public_endpoints import BinancePublicEndpoints
from tiewtrade.integrations.sqlite.active_paper_sessions import (
    SQLiteActivePaperSessions,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_runtime_lifecycle import (
    PaperRuntimeLifecycleState,
    SQLitePaperRuntimeLifecycle,
)
from tiewtrade.integrations.sqlite.trade_history import (
    SQLiteTradeHistory,
    TradeHistoryUnavailableError,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeSnapshot,
    MarketDataRuntimeState,
)
from tiewtrade.market_data.source_errors import (
    MarketDataFailureKind,
    MarketDataFatalError,
)
from tiewtrade.trading.session_config import MarketType
from tiewtrade.trading.symbol_rules import SymbolRules
from tiewtrade.trading.trade_history import BasketStatus, TradeFill

_NOW = datetime(2026, 8, 2, 3, tzinfo=UTC)
_T = TypeVar("_T")


class ImmediateScheduler:
    def now(self) -> datetime:
        return _NOW

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(0)

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        return await awaitable


class ControllablePublicCandleSource:
    def __init__(
        self,
        *,
        warm_up: tuple[Candle, ...],
        live: tuple[Candle, ...],
    ) -> None:
        self._warm_up = warm_up
        self._live = live
        self._loop: asyncio.AbstractEventLoop | None = None
        self._release: asyncio.Event | None = None
        self.closed = Event()

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        assert count == len(self._warm_up)
        return self._warm_up

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        raise AssertionError("contiguous fake candles must not backfill")

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        return self._stream_completed()

    async def close(self) -> None:
        self.closed.set()

    def fail_stream(self) -> None:
        deadline = Event()
        while self._loop is None or self._release is None:
            if deadline.wait(0.001):
                raise AssertionError("unreachable")
        self._loop.call_soon_threadsafe(self._release.set)

    async def _stream_completed(self) -> AsyncIterator[Candle]:
        self._loop = asyncio.get_running_loop()
        self._release = asyncio.Event()
        for candle in self._live:
            yield candle
        await self._release.wait()
        raise MarketDataFatalError(
            "fake stream finished",
            kind=MarketDataFailureKind.TRANSPORT,
        )


class FailingSpotTradeHistory(SQLiteTradeHistory):
    def record_paper_spot_entry_fill(
        self,
        fill: TradeFill,
        *,
        symbol: str,
        timeframe: str,
        strategy_preset_version: str,
    ) -> bool:
        raise TradeHistoryUnavailableError(
            "sqlite failed at /private/tmp with api_key=secret"
        )


class FailingRuntimeLifecycle(SQLitePaperRuntimeLifecycle):
    def mark_running(
        self,
        session_id: UUID,
        observed_at_utc: datetime,
    ) -> None:
        raise RuntimeError("sqlite failed at /private/tmp with api_key=secret")


class RecordingRuntimeLifecycle(SQLitePaperRuntimeLifecycle):
    def __init__(self, database: SQLiteDatabase) -> None:
        super().__init__(database)
        self.running_marks = 0

    def mark_running(
        self,
        session_id: UUID,
        observed_at_utc: datetime,
    ) -> None:
        self.running_marks += 1
        super().mark_running(session_id, observed_at_utc)


class FatalWarmUpSource(ControllablePublicCandleSource):
    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        raise MarketDataFatalError(
            "warm-up failed with api_key=secret",
            kind=MarketDataFailureKind.PAYLOAD,
        )


@pytest.mark.parametrize("market_type", [MarketType.SPOT, MarketType.FUTURES])
def test_start_selects_concrete_paper_market_and_publishes_live_basket(
    tmp_path: Path,
    market_type: MarketType,
) -> None:
    session = _session(market_type)
    database = _database_with_session(tmp_path, session)
    source = _source()
    lifecycle = RecordingRuntimeLifecycle(database)
    selected: list[BinancePublicEndpoints] = []
    snapshots: list[TradingWorkspaceSnapshot] = []
    basket_ready = Event()

    def publish(snapshot: TradingWorkspaceSnapshot) -> None:
        snapshots.append(snapshot)
        if snapshot.basket is not None:
            basket_ready.set()

    controller = PaperRuntimeController(
        lifecycle=lifecycle,
        trade_history=SQLiteTradeHistory(database),
        symbol_rules=_symbol_rules(),
        source_factory=lambda endpoints: _select_source(
            endpoints, source=source, selected=selected
        ),
        scheduler=ImmediateScheduler(),
        snapshot_callback=publish,
    )

    result = controller.start(session)

    assert result.blocked_reason is None
    assert result.workspace.header is not None
    assert result.workspace.header.runtime_state is BotRuntimeState.RUNNING
    assert result.workspace.header.data_freshness is DataFreshness.FRESH
    assert basket_ready.wait(2)
    current = controller.current_workspace
    assert current.read_state is WorkspaceReadState.READY
    assert current.basket is not None
    assert current.basket.market_type == market_type.value
    assert current.basket.entry_count == 1
    assert current.basket.total_quantity > 0
    assert current.basket.current_price == _live_candles()[-1].close
    assert current.data_as_of_utc == _live_candles()[-1].close_time
    assert selected == [BinancePublicEndpoints.for_market_type(market_type)]
    marker = SQLitePaperRuntimeLifecycle(database).read(session.config.session_id)
    assert marker is not None
    assert marker.state is PaperRuntimeLifecycleState.RUNNING
    assert lifecycle.running_marks == 1
    history = SQLiteTradeHistory(database).list_baskets(
        _history_filter(market_type), _first_page()
    )
    assert len(history.items) == 1
    assert history.items[0].status is BasketStatus.OPEN
    assert MarketDataRuntimeState.LIVE in controller.observed_runtime_states

    source.fail_stream()
    assert source.closed.wait(2)


def test_persistence_failure_blocks_and_preserves_last_known_workspace(
    tmp_path: Path,
) -> None:
    session = configured_spot_session()
    database = _database_with_session(tmp_path, session)
    source = _source()
    pending_ready = Event()
    blocked_ready = Event()
    snapshots: list[TradingWorkspaceSnapshot] = []

    def publish(snapshot: TradingWorkspaceSnapshot) -> None:
        snapshots.append(snapshot)
        if snapshot.orders:
            pending_ready.set()
        if (
            snapshot.header is not None
            and snapshot.header.runtime_state is BotRuntimeState.BLOCKED
        ):
            blocked_ready.set()

    controller = PaperRuntimeController(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=FailingSpotTradeHistory(database),
        symbol_rules=_symbol_rules(),
        source_factory=lambda _endpoints: source,
        scheduler=ImmediateScheduler(),
        snapshot_callback=publish,
    )

    started = controller.start(session)

    assert started.workspace.header is not None
    assert started.workspace.header.runtime_state is BotRuntimeState.RUNNING
    assert started.blocked_reason is None
    assert pending_ready.wait(2)
    pending = next(snapshot for snapshot in snapshots if snapshot.orders)
    assert blocked_ready.wait(2)
    current = controller.current_workspace
    assert current.header is not None
    assert current.header.runtime_state is BotRuntimeState.BLOCKED
    assert current.read_state is WorkspaceReadState.STALE
    assert current.orders == pending.orders
    assert current.position_basket == pending.position_basket
    assert current.data_as_of_utc == pending.data_as_of_utc
    assert controller.current_result.blocked_reason == "Paper Bot could not be started"
    assert "api_key" not in (controller.current_result.blocked_reason or "")
    assert source.closed.wait(2)


def test_lifecycle_failure_blocks_and_closes_the_runtime_source(
    tmp_path: Path,
) -> None:
    session = configured_spot_session()
    database = _database_with_session(tmp_path, session)
    source = _source()
    controller = PaperRuntimeController(
        lifecycle=FailingRuntimeLifecycle(database),
        trade_history=SQLiteTradeHistory(database),
        symbol_rules=_symbol_rules(),
        source_factory=lambda _endpoints: source,
        scheduler=ImmediateScheduler(),
        snapshot_callback=lambda _snapshot: None,
    )

    result = controller.start(session)

    assert result.workspace.header is not None
    assert result.workspace.header.runtime_state is BotRuntimeState.BLOCKED
    assert result.blocked_reason == "Paper Bot could not be started"
    assert source.closed.wait(1)


def test_composition_failure_returns_blocked_instead_of_hanging(
    tmp_path: Path,
) -> None:
    session = configured_spot_session()
    database = _database_with_session(tmp_path, session)
    controller = PaperRuntimeController(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=SQLiteTradeHistory(database),
        symbol_rules=_symbol_rules(),
        source_factory=lambda _endpoints: _raise_composition_failure(),
        scheduler=ImmediateScheduler(),
        snapshot_callback=lambda _snapshot: None,
    )
    completed = Event()
    outcomes = []

    def start() -> None:
        outcomes.append(controller.start(session))
        completed.set()

    Thread(target=start, daemon=True).start()

    assert completed.wait(1)
    assert outcomes[0].workspace.header is not None
    assert outcomes[0].workspace.header.runtime_state is BotRuntimeState.BLOCKED
    assert outcomes[0].blocked_reason == "Paper Bot could not be started"


def test_snapshot_callback_failure_returns_blocked_and_stops_runtime(
    tmp_path: Path,
) -> None:
    session = configured_spot_session()
    database = _database_with_session(tmp_path, session)
    source = _source()
    controller = PaperRuntimeController(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=SQLiteTradeHistory(database),
        symbol_rules=_symbol_rules(),
        source_factory=lambda _endpoints: source,
        scheduler=ImmediateScheduler(),
        snapshot_callback=lambda _snapshot: _raise_callback_failure(),
    )

    result = controller.start(session)

    assert result.workspace.header is not None
    assert result.workspace.header.runtime_state is BotRuntimeState.BLOCKED
    assert result.blocked_reason == "Paper Bot could not be started"
    assert source.closed.wait(1)


def test_fatal_warm_up_failure_returns_sanitized_blocked(
    tmp_path: Path,
) -> None:
    session = configured_spot_session()
    database = _database_with_session(tmp_path, session)
    source = FatalWarmUpSource(warm_up=(), live=())
    controller = PaperRuntimeController(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=SQLiteTradeHistory(database),
        symbol_rules=_symbol_rules(),
        source_factory=lambda _endpoints: source,
        scheduler=ImmediateScheduler(),
        snapshot_callback=lambda _snapshot: None,
    )

    result = controller.start(session)

    assert result.workspace.header is not None
    assert result.workspace.header.runtime_state is BotRuntimeState.BLOCKED
    assert result.blocked_reason == "Paper Bot could not be started"
    assert "api_key" not in (result.blocked_reason or "")
    assert source.closed.wait(1)


@pytest.mark.parametrize(
    "state",
    [
        MarketDataRuntimeState.STALE,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.BACKFILLING,
        MarketDataRuntimeState.RATE_LIMITED,
    ],
)
def test_transient_runtime_state_projects_stale_until_live(
    tmp_path: Path,
    state: MarketDataRuntimeState,
) -> None:
    session = configured_spot_session()
    database = _database_with_session(tmp_path, session)
    source = _source()
    snapshots: list[TradingWorkspaceSnapshot] = []
    controller = PaperRuntimeController(
        lifecycle=SQLitePaperRuntimeLifecycle(database),
        trade_history=SQLiteTradeHistory(database),
        symbol_rules=_symbol_rules(),
        source_factory=lambda _endpoints: source,
        scheduler=ImmediateScheduler(),
        snapshot_callback=snapshots.append,
    )
    started = controller.start(session)
    assert started.workspace.header is not None
    assert started.workspace.header.runtime_state is BotRuntimeState.RUNNING

    controller._on_runtime_transition(  # noqa: SLF001
        session,
        _runtime_snapshot(state),
    )

    stale = controller.current_workspace
    assert stale.header is not None
    assert stale.header.runtime_state is BotRuntimeState.RUNNING
    assert stale.header.data_freshness is DataFreshness.STALE
    assert stale.read_state is WorkspaceReadState.STALE

    controller._on_runtime_transition(  # noqa: SLF001
        session,
        _runtime_snapshot(MarketDataRuntimeState.LIVE),
    )

    fresh = controller.current_workspace
    assert fresh.header is not None
    assert fresh.header.runtime_state is BotRuntimeState.RUNNING
    assert fresh.header.data_freshness is DataFreshness.FRESH
    assert fresh.read_state is WorkspaceReadState.READY
    source.fail_stream()
    assert source.closed.wait(2)


def _database_with_session(
    tmp_path: Path,
    session: ConfiguredPaperSession,
) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / f"{session.config.market_type.value}.sqlite3")
    database.migrate()
    assert SQLiteActivePaperSessions(database).create(session).created
    return database


def _select_source(
    endpoints: BinancePublicEndpoints,
    *,
    source: ControllablePublicCandleSource,
    selected: list[BinancePublicEndpoints],
) -> ControllablePublicCandleSource:
    selected.append(endpoints)
    return source


def _raise_composition_failure() -> NoReturn:
    raise RuntimeError("transport payload with api_key=secret")


def _raise_callback_failure() -> None:
    raise RuntimeError("UI callback failed with api_key=secret")


def _source() -> ControllablePublicCandleSource:
    return ControllablePublicCandleSource(
        warm_up=_warm_up_candles(),
        live=_live_candles(),
    )


def _session(market_type: MarketType) -> ConfiguredPaperSession:
    if market_type is MarketType.SPOT:
        return configured_spot_session()
    return configured_futures_session()


def _symbol_rules() -> SymbolRules:
    return SymbolRules(
        symbol="BTCUSDT",
        tick_size=Decimal("0.1"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )


def _warm_up_candles() -> tuple[Candle, ...]:
    close = Decimal("100")
    candles: list[Candle] = []
    for index in range(15):
        candles.append(_candle(index, close=close))
        close -= Decimal("1")
    return tuple(candles)


def _live_candles() -> tuple[Candle, ...]:
    close = Decimal("86")
    candles: list[Candle] = []
    for index in range(15, 26):
        close += Decimal("1")
        candles.append(_candle(index, close=close))
    return tuple(candles)


def _candle(index: int, *, close: Decimal) -> Candle:
    opened = close - Decimal("0.5")
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 8, 2, tzinfo=UTC) + timedelta(minutes=index * 5),
        open=opened,
        high=close + Decimal("1"),
        low=opened - Decimal("1"),
        close=close,
        volume=Decimal("1"),
    )


def _runtime_snapshot(state: MarketDataRuntimeState) -> MarketDataRuntimeSnapshot:
    reason = (
        MarketDataRuntimeReason.WARM_UP_COMPLETED
        if state is MarketDataRuntimeState.LIVE
        else MarketDataRuntimeReason.DATA_STALE
    )
    return MarketDataRuntimeSnapshot(
        state=state,
        reason=reason,
        transitioned_at=_NOW,
        last_accepted_open_time=_live_candles()[-1].open_time,
    )


def _history_filter(market_type: MarketType) -> TradeHistoryFilter:
    return TradeHistoryFilter(market_type=market_type)


def _first_page() -> PageRequest:
    return PageRequest(page=1, page_size=20)
