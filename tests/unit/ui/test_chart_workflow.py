from datetime import UTC, datetime
from decimal import Decimal

from tests.support.paper_session_setup import configured_spot_session
from tests.support.trade_history_records import trade_fill
from tiewtrade.application.chart_data import (
    ChartRange,
    ChartReadState,
    ChartSnapshot,
)
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.trade_history import FillSide
from tiewtrade.ui.background_task import BackgroundTask
from tiewtrade.ui.chart_workflow import ChartWorkflow


class ImmediateThreadPool:
    def start(self, task: BackgroundTask) -> None:
        task.run()


class DeferredThreadPool:
    def __init__(self) -> None:
        self.tasks: list[BackgroundTask] = []

    def start(self, task: BackgroundTask) -> None:
        self.tasks.append(task)


class PartialCompletedCandle:
    symbol = "BTCUSDT"
    timeframe = "5m"
    open_time = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    close_time = datetime(2026, 1, 1, 0, 20, tzinfo=UTC)


def test_start_loads_application_owned_default_visible_range() -> None:
    session = configured_spot_session()
    requests: list[ChartRange] = []
    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, requests
        ),
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 1, 1, 10, 3, tzinfo=UTC),
    )

    workflow.start(session)

    assert requests == [
        ChartRange(
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
    ]


def test_latest_chart_request_wins() -> None:
    session = configured_spot_session()
    first_range = chart_range(0, 20)
    latest_range = chart_range(20, 40)
    calls: list[ChartRange] = []
    snapshots: list[ChartSnapshot] = []
    pool = DeferredThreadPool()
    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, calls
        ),
        thread_pool=pool,  # type: ignore[arg-type]
    )
    workflow.snapshot_changed.connect(snapshots.append)
    workflow.configure(session)

    workflow.load_range(first_range)
    workflow.load_range(latest_range)
    pool.tasks[0].run()
    pool.tasks[1].run()

    assert calls == [first_range, latest_range]
    assert [snapshot.chart_range for snapshot in snapshots] == [
        first_range,
        latest_range,
        latest_range,
    ]
    assert [snapshot.state for snapshot in snapshots] == [
        ChartReadState.LOADING,
        ChartReadState.LOADING,
        ChartReadState.READY,
    ]


def test_load_publishes_loading_snapshot_before_ready_snapshot() -> None:
    session = configured_spot_session()
    selected_range = chart_range(0, 20)
    snapshots: list[ChartSnapshot] = []
    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, []
        ),
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
    )
    workflow.snapshot_changed.connect(snapshots.append)
    workflow.configure(session)

    workflow.load_range(selected_range)

    assert [snapshot.state for snapshot in snapshots] == [
        ChartReadState.LOADING,
        ChartReadState.READY,
    ]
    assert all(snapshot.chart_range == selected_range for snapshot in snapshots)


def test_retry_reloads_last_safe_range_after_chart_failure() -> None:
    session = configured_spot_session()
    selected_range = chart_range(0, 20)
    attempts = 0
    snapshots: list[ChartSnapshot] = []

    async def fail_then_load(
        configured: ConfiguredPaperSession,
        requested: ChartRange,
    ) -> ChartSnapshot:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("public transport unavailable")
        return await load_snapshot(configured, requested, [])

    workflow = ChartWorkflow(
        load_chart=fail_then_load,
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
    )
    workflow.snapshot_changed.connect(snapshots.append)
    workflow.configure(session)
    workflow.load_range(selected_range)

    workflow.retry()

    assert attempts == 2
    assert snapshots[-1].state is ChartReadState.READY
    assert snapshots[-1].chart_range == selected_range


def test_chart_failure_is_unavailable_and_chart_scoped() -> None:
    session = configured_spot_session()
    first_range = chart_range(0, 20)

    unavailable: list[ChartSnapshot] = []
    failed = ChartWorkflow(
        load_chart=lambda configured, requested: fail_load(),
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
    )
    failed.snapshot_changed.connect(unavailable.append)
    failed.configure(session)
    failed.load_range(first_range)

    assert unavailable[-1].state is ChartReadState.UNAVAILABLE
    assert unavailable[-1].message == "Chart is unavailable"


def test_completed_candle_ignores_other_session_and_updates_current_snapshot() -> None:
    session = configured_spot_session()
    selected_range = chart_range(0, 20)
    snapshots: list[ChartSnapshot] = []
    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, []
        ),
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
    )
    workflow.snapshot_changed.connect(snapshots.append)
    workflow.configure(session)
    workflow.load_range(selected_range)

    workflow.completed_candle(candle("15m", 15))
    assert len(snapshots) == 2

    workflow.completed_candle(candle("5m", 15))
    assert [item.open_time.minute for item in snapshots[-1].candles] == [0, 15]


def test_completed_candle_refreshes_shifted_latest_range_and_durable_fills() -> None:
    session = configured_spot_session()
    selected_range = chart_range(0, 20)
    refreshed: list[tuple[ChartSnapshot, Candle]] = []
    snapshots: list[ChartSnapshot] = []

    async def refresh_chart(
        configured: ConfiguredPaperSession,
        current: ChartSnapshot,
        completed: Candle,
    ) -> ChartSnapshot:
        assert configured is session
        refreshed.append((current, completed))
        shifted_range = ChartRange(
            datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 25, tzinfo=UTC),
        )
        return ChartSnapshot(
            session=session,
            chart_range=shifted_range,
            observed_at_utc=completed.close_time,
            candles=(completed,),
            fills=(
                trade_fill(
                    fill_id="runtime-buy",
                    side=FillSide.BUY,
                    session_id=session.config.session_id,
                    filled_at_utc=datetime(2026, 1, 1, 0, 21, tzinfo=UTC),
                ),
            ),
            state=ChartReadState.READY,
        )

    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, []
        ),
        refresh_chart=refresh_chart,
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
    )
    workflow.snapshot_changed.connect(snapshots.append)
    workflow.configure(session)
    workflow.load_range(selected_range)

    completed = candle("5m", 20)
    workflow.completed_candle(completed)

    assert refreshed == [(snapshots[1], completed)]
    assert snapshots[-1].chart_range.end == completed.close_time
    assert snapshots[-1].candles == (completed,)
    assert [marker.fill_id for marker in snapshots[-1].markers] == ["runtime-buy"]


def test_retry_uses_latest_runtime_refreshed_visible_range() -> None:
    session = configured_spot_session()
    initial_range = chart_range(0, 20)
    refreshed_range = chart_range(5, 25)
    load_requests: list[ChartRange] = []

    async def refresh_chart(
        configured: ConfiguredPaperSession,
        current: ChartSnapshot,
        completed: Candle,
    ) -> ChartSnapshot:
        del current
        return ChartSnapshot(
            session=configured,
            chart_range=refreshed_range,
            observed_at_utc=completed.close_time,
            candles=(completed,),
            fills=(),
            state=ChartReadState.READY,
        )

    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, load_requests
        ),
        refresh_chart=refresh_chart,
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
    )
    workflow.configure(session)
    workflow.load_range(initial_range)

    workflow.completed_candle(candle("5m", 20))
    workflow.retry()

    assert load_requests == [initial_range, refreshed_range]


def test_completed_candle_refresh_keeps_latest_event_while_worker_is_active() -> None:
    session = configured_spot_session()
    selected_range = chart_range(0, 20)
    pool = DeferredThreadPool()
    refreshed_minutes: list[int] = []
    snapshots: list[ChartSnapshot] = []

    async def refresh_chart(
        configured: ConfiguredPaperSession,
        current: ChartSnapshot,
        completed: Candle,
    ) -> ChartSnapshot:
        refreshed_minutes.append(completed.open_time.minute)
        duration = current.chart_range.end - current.chart_range.start
        next_range = ChartRange(completed.close_time - duration, completed.close_time)
        return ChartSnapshot(
            session=configured,
            chart_range=next_range,
            observed_at_utc=completed.close_time,
            candles=(completed,),
            fills=(),
            state=ChartReadState.READY,
        )

    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, []
        ),
        refresh_chart=refresh_chart,
        thread_pool=pool,  # type: ignore[arg-type]
    )
    workflow.snapshot_changed.connect(snapshots.append)
    workflow.configure(session)
    workflow.load_range(selected_range)
    pool.tasks[0].run()

    workflow.completed_candle(candle("5m", 20))
    workflow.completed_candle(candle("5m", 25))
    pool.tasks[1].run()
    pool.tasks[2].run()

    assert refreshed_minutes == [20, 25]
    assert snapshots[-1].candles[0].open_time.minute == 25
    assert snapshots[-1].chart_range.end.minute == 30


def test_completed_candle_gap_advances_and_keeps_following_runtime_updates() -> None:
    session = configured_spot_session()
    selected_range = chart_range(0, 20)
    refreshed_minutes: list[int] = []
    snapshots: list[ChartSnapshot] = []

    async def refresh_chart(
        configured: ConfiguredPaperSession,
        current: ChartSnapshot,
        completed: Candle,
    ) -> ChartSnapshot:
        refreshed_minutes.append(completed.open_time.minute)
        duration = current.chart_range.end - current.chart_range.start
        next_range = ChartRange(completed.close_time - duration, completed.close_time)
        return ChartSnapshot(
            session=configured,
            chart_range=next_range,
            observed_at_utc=completed.close_time,
            candles=(completed,),
            fills=(),
            state=ChartReadState.READY,
        )

    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, []
        ),
        refresh_chart=refresh_chart,
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
    )
    workflow.snapshot_changed.connect(snapshots.append)
    workflow.configure(session)
    workflow.load_range(selected_range)

    workflow.completed_candle(candle("5m", 25))
    workflow.completed_candle(candle("5m", 30))

    assert refreshed_minutes == [25, 30]
    assert snapshots[-1].chart_range == chart_range(15, 35)
    assert snapshots[-1].candles == (candle("5m", 30),)


def test_partial_completed_candle_fact_cannot_reach_refresh_boundary() -> None:
    session = configured_spot_session()
    selected_range = chart_range(0, 20)
    refreshed: list[object] = []

    async def refresh_chart(
        configured: ConfiguredPaperSession,
        current: ChartSnapshot,
        completed: Candle,
    ) -> ChartSnapshot:
        del configured
        refreshed.append(completed)
        return current

    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, []
        ),
        refresh_chart=refresh_chart,
        thread_pool=ImmediateThreadPool(),  # type: ignore[arg-type]
    )
    workflow.configure(session)
    workflow.load_range(selected_range)

    workflow.completed_candle(PartialCompletedCandle())

    assert refreshed == []


def test_load_queued_during_refresh_is_drained_and_latest_request_wins() -> None:
    session = configured_spot_session()
    initial_range = chart_range(0, 20)
    queued_range = chart_range(20, 40)
    latest_range = chart_range(40, 55)
    calls: list[ChartRange] = []
    pool = DeferredThreadPool()

    async def refresh_chart(
        configured: ConfiguredPaperSession,
        current: ChartSnapshot,
        completed: Candle,
    ) -> ChartSnapshot:
        del configured, completed
        return current

    workflow = ChartWorkflow(
        load_chart=lambda configured, requested: load_snapshot(
            configured, requested, calls
        ),
        refresh_chart=refresh_chart,
        thread_pool=pool,  # type: ignore[arg-type]
    )
    workflow.configure(session)
    workflow.load_range(initial_range)
    pool.tasks[0].run()

    workflow.completed_candle(candle("5m", 20))
    workflow.load_range(queued_range)
    workflow.load_range(latest_range)
    pool.tasks[1].run()
    pool.tasks[2].run()

    assert calls == [initial_range, latest_range]


async def load_snapshot(
    session: ConfiguredPaperSession,
    chart_range: ChartRange,
    calls: list[ChartRange],
) -> ChartSnapshot:
    calls.append(chart_range)
    return ChartSnapshot(
        session=session,
        chart_range=chart_range,
        observed_at_utc=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        candles=(candle("5m", chart_range.start.minute),),
        fills=(),
        state=ChartReadState.READY,
    )


async def fail_load() -> ChartSnapshot:
    raise RuntimeError("transport details must not reach the chart")


def chart_range(start_minute: int, end_minute: int) -> ChartRange:
    return ChartRange(
        datetime(2026, 1, 1, 0, start_minute, tzinfo=UTC),
        datetime(2026, 1, 1, 0, end_minute, tzinfo=UTC),
    )


def candle(timeframe: str, minute: int) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe=timeframe,
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("106"),
        low=Decimal("99"),
        close=Decimal("103"),
        volume=Decimal("1"),
    )
