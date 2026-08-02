from datetime import UTC, datetime
from decimal import Decimal

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.chart_data import (
    ChartRange,
    ChartReadState,
    ChartSnapshot,
)
from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
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
    assert [snapshot.chart_range for snapshot in snapshots] == [latest_range]


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
    assert len(snapshots) == 1

    workflow.completed_candle(candle("5m", 15))
    assert [item.open_time.minute for item in snapshots[-1].candles] == [0, 15]


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
