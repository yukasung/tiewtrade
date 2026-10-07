import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import (
    Candle,
    CandleFinality,
    CandleWindow,
    Timeframe,
    align_floor,
    expected_opens,
)
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import MarketDataSession, market_data_session
from tiewtrade.infra.market_data.claims import Claim, claim_next, update_claim
from tiewtrade.infra.market_data.storage import database_now, enqueue
from tiewtrade.services.market_data import ingestion
from tiewtrade.services.market_data.ingestion import _validate, run_round
from tiewtrade.venues import FakeVenue
from tiewtrade.venues.candles import CandlePage
from tiewtrade.venues.errors import VenueRateLimitedError, VenueUnavailableError
from tiewtrade.venues.symbols import Symbol


async def isolated_window(engine: AsyncEngine, slots: int = 3) -> CandleWindow:
    now = datetime.now(UTC)
    end = align_floor(now, Timeframe.M1)
    window = CandleWindow(end - timedelta(minutes=slots), end)
    async with market_data_session(engine) as session:
        await session.execute("DELETE FROM market_candle_demand")
        await session.execute("DELETE FROM market_candles")
        await session.execute(
            """INSERT INTO market_candle_demand
            (source,base,quote,timeframe,desired_start,desired_end,requested_at)
            VALUES ('primary_spot','BTC','USDT','1m',:start,:end,:now)""",
            {"start": window.start, "end": window.end, "now": now},
        )
    return window


async def only_btc_ready(engine: AsyncEngine) -> None:
    async with market_data_session(engine) as session:
        await session.execute("""UPDATE market_candle_demand SET next_attempt_at=
            CASE WHEN base='BTC' AND timeframe='1m' THEN clock_timestamp() ELSE
            clock_timestamp()+interval '1 hour' END""")


class GapSource(FakeVenue):
    def __init__(self, *, repair: bool) -> None:
        super().__init__()
        self.repair = repair
        self.windows: list[CandleWindow] = []

    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        self.windows.append(CandleWindow(start, end))
        page = await FullSource().fetch_candles(symbol, timeframe, start, end, limit)
        candles = page.candles
        if len(self.windows) == 1:
            candles = tuple(c for index, c in enumerate(candles) if index != 1)
        elif not self.repair:
            candles = ()
        return CandlePage(symbol, timeframe, page.window, candles, page.received_at)


@pytest.mark.parametrize("repair", [True, False])
async def test_interior_gap_is_repaired_or_exhausts_two_sweeps(repair: bool) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        window = await isolated_window(engine)
        # Seed other series once and keep them ineligible during the controlled job.
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        source = GapSource(repair=repair)
        await run_round(engine, source, "forward", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["phase"] == "REPAIR"
            assert row["repair_pass"] == 1
        await only_btc_ready(engine)
        await run_round(engine, source, "repair-one", datetime.now(UTC))
        if not repair:
            await only_btc_ready(engine)
            await run_round(engine, source, "repair-two", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["status"] == ("COMPLETE" if repair else "UNAVAILABLE")
            if not repair:
                assert row["failure_code"] == "GAP_REPAIR_EXHAUSTED"
                assert row["repair_pass"] == 2
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() == (
                3 if repair else 2
            )
        assert source.windows[1] == CandleWindow(
            window.start + timedelta(minutes=1), window.start + timedelta(minutes=2)
        )
        assert len(source.windows) == (2 if repair else 3)
    finally:
        await engine.dispose()


class FullSource(FakeVenue):
    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        window = CandleWindow(start, end)
        candles = tuple(
            Candle(
                symbol.base,
                symbol.quote,
                timeframe,
                moment,
                moment + timeframe.span,
                Money.of("2", symbol.quote),
                Money.of("2", symbol.quote),
                Money.of("2", symbol.quote),
                Money.of("2", symbol.quote),
                Quantity.of("1", symbol.base),
                CandleFinality.UNCONFIRMED,
                datetime.now(UTC),
            )
            for moment in expected_opens(window, timeframe)
        )
        return CandlePage(symbol, timeframe, window, candles, datetime.now(UTC))


class RemainingGapSource(FullSource):
    def __init__(self, missing_open: datetime) -> None:
        super().__init__()
        self.missing_open = missing_open
        self.requests: list[CandleWindow] = []

    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        self.requests.append(CandleWindow(start, end))
        page = await super().fetch_candles(symbol, timeframe, start, end, limit)
        return replace(
            page,
            candles=tuple(candle for candle in page.candles if candle.open_at != self.missing_open),
        )


@pytest.mark.parametrize("side", ["left", "right", "both"])
async def test_expansion_preserves_exhaustion_until_authorized_union_retry(side: str) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    api = create_engine_for(DatabaseRole.API)
    try:
        window = await isolated_window(engine)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        source = GapSource(repair=False)
        await only_btc_ready(engine)
        await run_round(engine, source, "forward", datetime.now(UTC))
        await only_btc_ready(engine)
        await run_round(engine, source, "repair-one", datetime.now(UTC))
        expanded = CandleWindow(
            window.start - timedelta(minutes=1) if side in {"left", "both"} else window.start,
            window.end + timedelta(minutes=1) if side in {"right", "both"} else window.end,
        )
        async with user_session(api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, expanded)
        await only_btc_ready(engine)
        await run_round(engine, source, "repair-two", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute(
                        "SELECT * FROM market_candle_demand WHERE base='BTC' AND timeframe='1m'"
                    )
                )
                .mappings()
                .one()
            )
            assert row["status"] == "UNAVAILABLE"
            assert row["failure_code"] == "GAP_REPAIR_EXHAUSTED"
            assert row["repair_pass"] == 2
            assert (row["leased_start"], row["leased_end"]) == (window.start, window.end)
            assert (row["desired_start"], row["desired_end"]) == (expanded.start, expanded.end)
            deadline = row["next_attempt_at"]
            assert deadline > await database_now(session) + timedelta(seconds=110)
        assert len(source.windows) == 3

        async with user_session(api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, expanded)
        assert (await run_round(engine, source, "early", datetime.now(UTC))).attempts == 0
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute(
                        "SELECT repair_pass,next_attempt_at FROM "
                        "market_candle_demand WHERE base='BTC' AND timeframe='1m'"
                    )
                )
                .mappings()
                .one()
            )
            assert row["repair_pass"] == 2 and row["next_attempt_at"] == deadline
            await session.execute("""UPDATE market_candle_demand SET
                next_attempt_at=clock_timestamp()-interval '1 second', requested_at=checked_at
                WHERE base='BTC' AND timeframe='1m'""")
        async with user_session(api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, expanded)
        missing_open = window.start + timedelta(minutes=1)
        retry = RemainingGapSource(missing_open)
        await run_round(engine, retry, "authorized-retry", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute(
                        "SELECT * FROM market_candle_demand WHERE base='BTC' AND timeframe='1m'"
                    )
                )
                .mappings()
                .one()
            )
            assert (row["leased_start"], row["leased_end"]) == (expanded.start, expanded.end)
            opens = set(
                (
                    await session.execute(
                        "SELECT open_at FROM market_candles WHERE base='BTC' AND timeframe='1m'"
                    )
                ).scalars()
            )
        assert missing_open not in opens
        if side in {"left", "both"}:
            assert expanded.start in opens
        if side in {"right", "both"}:
            assert window.end in opens
    finally:
        await engine.dispose()
        await api.dispose()


class LaterFailureSource(FullSource):
    def __init__(self, failing_start: datetime) -> None:
        super().__init__()
        self.failing_start = failing_start
        self.failures = 0
        self.requests: list[CandleWindow] = []

    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        self.requests.append(CandleWindow(start, end))
        if start == self.failing_start and self.failures < 2:
            self.failures += 1
            raise VenueUnavailableError()
        return await super().fetch_candles(symbol, timeframe, start, end, limit)


class OutOfOrderSource(FullSource):
    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        page = await super().fetch_candles(symbol, timeframe, start, end, limit)
        return CandlePage(
            symbol, timeframe, page.window, tuple(reversed(page.candles)), page.received_at
        )


@pytest.mark.parametrize("protocol", [True, False])
async def test_malformed_and_permanent_failure_do_not_retry(protocol: bool) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        await isolated_window(engine, 2)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        source = OutOfOrderSource() if protocol else FakeVenue()
        result = await run_round(engine, source, "failed", datetime.now(UTC))
        assert result.attempts == 1
        await only_btc_ready(engine)
        result = await run_round(engine, source, "restart", datetime.now(UTC))
        assert result.attempts == 0
        async with market_data_session(engine) as session:
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() == 0
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["status"] == "FAILED"
            assert row["attemptcount"] == 1
    finally:
        await engine.dispose()


async def test_five_pages_have_independent_retry_units() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        window = await isolated_window(engine, 5000)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        source = LaterFailureSource(window.start + timedelta(minutes=3000))
        first = await run_round(engine, source, "first", datetime.now(UTC))
        assert first.attempts == 4
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["attemptcount"] == 1
            unit = row["fetch_unit_id"]
        await only_btc_ready(engine)
        await run_round(engine, source, "second", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["attemptcount"] == 2
            assert row["fetch_unit_id"] == unit
        await only_btc_ready(engine)
        third = await run_round(engine, source, "third", datetime.now(UTC))
        assert third.attempts == 2
        async with market_data_session(engine) as session:
            assert (
                await session.execute("SELECT count(*) FROM market_candles")
            ).scalar_one() == 5000
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["status"] == "COMPLETE"
            assert row["attemptcount"] == 0
    finally:
        await engine.dispose()


async def test_expanded_window_fetches_only_missing_stored_slots() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        window = await isolated_window(engine, 2)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        await run_round(engine, FullSource(), "initial", datetime.now(UTC))
        expanded_start = window.start - timedelta(minutes=1)
        async with market_data_session(engine) as session:
            await session.execute(
                """UPDATE market_candle_demand SET desired_start=:start
                WHERE base='BTC' AND timeframe='1m'""",
                {"start": expanded_start},
            )
        await only_btc_ready(engine)
        source = LaterFailureSource(datetime.now(UTC) + timedelta(days=1))
        await run_round(engine, source, "expanded", datetime.now(UTC))
        assert source.requests == [CandleWindow(expanded_start, window.start)]
    finally:
        await engine.dispose()


async def test_partial_observation_refreshes_without_changing_finality() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    api = create_engine_for(DatabaseRole.API)
    try:
        window = await isolated_window(engine, 1)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        await run_round(engine, FullSource(), "initial", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candles SET open=1,high=1,low=1,close=1,
                fetch_started_at=end_at-interval '1 second',
                last_checked_at=end_at-interval '1 second'""")
        async with user_session(api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        await only_btc_ready(engine)
        await run_round(engine, FullSource(), "refresh", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (await session.execute("SELECT * FROM market_candles")).mappings().one()
            assert str(row["close"]) == "2"
            assert row["finality"] == "UNCONFIRMED"
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["status"] == "COMPLETE"
            assert row["refresh_served_at"] == row["refresh_requested_at"]
    finally:
        await api.dispose()
        await engine.dispose()


class LateSource(FullSource):
    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__()
        self.engine = engine

    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        page = await super().fetch_candles(symbol, timeframe, start, end, limit)
        async with market_data_session(self.engine) as session:
            await session.execute("""UPDATE market_candle_demand SET
                lease_until=clock_timestamp()-interval '1 second'
                WHERE base='BTC' AND timeframe='1m'""")
            assert await claim_next(session, "replacement") is not None
        return page


class PartialRefreshSource(FullSource):
    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        page = await super().fetch_candles(symbol, timeframe, start, end, limit)
        return CandlePage(symbol, timeframe, page.window, page.candles[:1], page.received_at)


class RequestDuringRefreshSource(FullSource):
    def __init__(self, api: AsyncEngine, window: CandleWindow) -> None:
        super().__init__()
        self.api = api
        self.window = window
        self.calls = 0

    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        self.calls += 1
        async with user_session(self.api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, self.window)
        return await super().fetch_candles(symbol, timeframe, start, end, limit)


async def test_post_before_completion_keeps_pending_watermark_for_next_round() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    api = create_engine_for(DatabaseRole.API)
    try:
        await isolated_window(engine, 1)
        now = datetime.now(UTC)
        start = align_floor(now, Timeframe.M1)
        window = CandleWindow(start, start + timedelta(minutes=1))
        async with market_data_session(engine) as session:
            await session.execute(
                """UPDATE market_candle_demand SET desired_start=:start,
                desired_end=:end""",
                {"start": window.start, "end": window.end},
            )
        await run_round(engine, FakeVenue(), "seed", now)
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        await run_round(engine, FullSource(), "initial", now)
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candles SET
                fetch_started_at=clock_timestamp()-interval '32 seconds',
                last_checked_at=clock_timestamp()-interval '31 seconds'""")
        async with user_session(api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        await only_btc_ready(engine)
        source = RequestDuringRefreshSource(api, window)
        await run_round(engine, source, "active", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["status"] == "PENDING"
            assert row["refresh_requested_at"] > row["refresh_served_at"]
        await only_btc_ready(engine)
        await run_round(engine, source, "follow-up", datetime.now(UTC))
        assert source.calls == 1
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["status"] == "COMPLETE"
            assert row["refresh_requested_at"] == row["refresh_served_at"]
    finally:
        await api.dispose()
        await engine.dispose()


async def test_partial_refresh_preserves_unit_and_unreceived_timestamp() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    api = create_engine_for(DatabaseRole.API)
    try:
        window = await isolated_window(engine, 2)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        await run_round(engine, FullSource(), "initial", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candles SET open=1,high=1,low=1,close=1,
                fetch_started_at=end_at-interval '1 second',
                last_checked_at=end_at-interval '1 second'""")
            untouched = (
                await session.execute("""SELECT last_checked_at FROM market_candles
                ORDER BY open_at DESC LIMIT 1""")
            ).scalar_one()
        async with user_session(api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        source = PartialRefreshSource()
        unit = None
        for attempt in range(1, 4):
            await only_btc_ready(engine)
            await run_round(engine, source, f"refresh-{attempt}", datetime.now(UTC))
            async with market_data_session(engine) as session:
                row = (
                    (
                        await session.execute("""SELECT * FROM market_candle_demand
                    WHERE base='BTC' AND timeframe='1m'""")
                    )
                    .mappings()
                    .one()
                )
                assert row["attemptcount"] == attempt
                if unit is None:
                    unit = row["fetch_unit_id"]
                assert row["fetch_unit_id"] == unit
                assert row["refresh_cursor"] is None
                assert row["refresh_served_at"] is None
                assert row["status"] == ("FAILED" if attempt == 3 else "PENDING")
                assert (
                    await session.execute("""SELECT last_checked_at FROM market_candles
                    ORDER BY open_at DESC LIMIT 1""")
                ).scalar_one() == untouched
    finally:
        await api.dispose()
        await engine.dispose()


async def test_old_worker_late_response_cannot_write_rows_or_cursor() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        window = await isolated_window(engine, 1)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        summary = await run_round(engine, LateSource(engine), "old", datetime.now(UTC))
        assert summary.stale == 1
        async with market_data_session(engine) as session:
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() == 0
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["cursor"] == window.start
            assert row["worker"] == "replacement"
            assert row["attemptcount"] == 1
    finally:
        await engine.dispose()


async def test_identical_duplicate_observations_are_deduplicated() -> None:
    end = align_floor(datetime.now(UTC), Timeframe.M1)
    window = CandleWindow(end - timedelta(minutes=1), end)
    page = await FullSource().fetch_candles(
        Symbol("BTC", "USDT"), Timeframe.M1, window.start, window.end, 1000
    )
    duplicate = CandlePage(
        page.symbol, page.timeframe, page.window, page.candles + page.candles, page.received_at
    )
    validated = _validate(duplicate, Claim("BTC", "USDT", Timeframe.M1, uuid4(), 1), window)
    assert validated.candles == page.candles


async def test_page_and_cursor_rollback_together(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    original = update_claim

    async def fail_cursor(
        session: MarketDataSession, claim: Claim, *, release: bool = False, **changes: Any
    ) -> None:
        if "cursor" in changes:
            raise RuntimeError("simulated crash before cursor commit")
        await original(session, claim, release=release, **changes)

    try:
        window = await isolated_window(engine, 1)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        monkeypatch.setattr(ingestion, "update_claim", fail_cursor)
        with pytest.raises(RuntimeError, match="simulated crash"):
            await run_round(engine, FullSource(), "crashing", datetime.now(UTC))
        async with market_data_session(engine) as session:
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() == 0
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["cursor"] == window.start
            assert row["attemptcount"] == 1
            assert row["fetch_unit_id"] is not None
    finally:
        await engine.dispose()


async def test_crashed_third_reserved_attempt_is_not_refunded() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        window = await isolated_window(engine, 1)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute(
                """UPDATE market_candle_demand SET status='RUNNING',
                attemptcount=3,fetch_unit_id=:unit,fetch_start=:start,fetch_end=:end,
                cursor=:start,leased_start=:start,leased_end=:end,token=:token,worker='crashed',
                lease_until=clock_timestamp()-interval '1 second'
                WHERE base='BTC' AND timeframe='1m'""",
                {"unit": uuid4(), "token": uuid4(), "start": window.start, "end": window.end},
            )
        await only_btc_ready(engine)
        source = FullSource()
        result = await run_round(engine, source, "restart", datetime.now(UTC))
        assert result.attempts == 0
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["attemptcount"] == 3
            assert row["status"] == "FAILED"
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() == 0
    finally:
        await engine.dispose()


async def test_seed_uses_database_clock_despite_two_hour_caller_skew() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await session.execute("DELETE FROM market_candle_demand")
            now = await database_now(session)
        source = FakeVenue()
        await run_round(engine, source, "skewed", now + timedelta(hours=2))
        async with market_data_session(engine) as session:
            for row in (await session.execute("SELECT * FROM market_candle_demand")).mappings():
                timeframe = Timeframe(row["timeframe"])
                assert row["desired_end"] <= align_floor(now, timeframe) + timeframe.span
                assert row["requested_at"] < now + timedelta(seconds=10)
        assert all(
            call.end <= align_floor(now, call.timeframe) + call.timeframe.span
            for call in source.candle_calls
        )
    finally:
        await engine.dispose()


async def test_persisted_future_demand_is_clamped_before_fetch() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        await isolated_window(engine, 1)
        now = datetime.now(UTC)
        async with market_data_session(engine) as session:
            await session.execute(
                "UPDATE market_candle_demand SET desired_end=:future",
                {"future": now + timedelta(hours=2)},
            )
        source = FakeVenue()
        await run_round(engine, source, "persisted-skew", now)
        btc = next(
            call
            for call in source.candle_calls
            if call.symbol.base == "BTC" and call.timeframe is Timeframe.M1
        )
        assert btc.end <= align_floor(now, Timeframe.M1) + Timeframe.M1.span
    finally:
        await engine.dispose()


async def test_concurrent_rate_limit_failures_and_inflight_retry_preserve_source_wait() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        await isolated_window(engine, 1)
        async with market_data_session(engine) as session:
            await ingestion._seed_initial_demand(session)
            first = await claim_next(session, "first")
            second = await claim_next(session, "second")
            third = await claim_next(session, "third")
            assert first and second and third
            for claim in (first, second, third):
                await update_claim(session, claim, attemptcount=1)

        async def fail(claim: Claim, error: Exception) -> bool:
            async with market_data_session(engine) as session:
                return await ingestion._failure(session, claim, error)

        results = await asyncio.wait_for(
            asyncio.gather(
                fail(first, VenueRateLimitedError(timedelta(seconds=600))),
                fail(second, VenueRateLimitedError(timedelta(seconds=600))),
            ),
            10,
        )
        assert all(results)
        await fail(third, VenueUnavailableError())
        async with market_data_session(engine) as session:
            now = await database_now(session)
            earliest = (
                await session.execute("SELECT min(next_attempt_at) FROM market_candle_demand")
            ).scalar_one()
            assert earliest > now + timedelta(seconds=590)
    finally:
        await engine.dispose()


class OldObservationSource(FullSource):
    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        page = await super().fetch_candles(symbol, timeframe, start, end, limit)
        return replace(
            page,
            candles=tuple(
                replace(candle, observed_at=candle.observed_at - timedelta(days=1))
                for candle in page.candles
            ),
        )


async def test_ignored_old_full_refresh_page_does_not_advance_served_watermark() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    api = create_engine_for(DatabaseRole.API)
    try:
        window = await isolated_window(engine, 1)
        await run_round(engine, FakeVenue(), "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candle_demand SET status='PENDING',
                attemptcount=0,fetch_unit_id=NULL,fetch_start=NULL,fetch_end=NULL,
                cursor=NULL,leased_start=NULL,leased_end=NULL
                WHERE base='BTC' AND timeframe='1m'""")
        await only_btc_ready(engine)
        await run_round(engine, FullSource(), "initial", datetime.now(UTC))
        async with market_data_session(engine) as session:
            await session.execute("""UPDATE market_candles SET open=1,high=1,low=1,close=1,
                fetch_started_at=end_at-interval '1 second',
                last_checked_at=end_at-interval '1 second'""")
        async with user_session(api, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        await only_btc_ready(engine)
        await run_round(engine, OldObservationSource(), "old-refresh", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE base='BTC' AND timeframe='1m'""")
                )
                .mappings()
                .one()
            )
            assert row["refresh_served_at"] is None
            assert row["attemptcount"] == 1
            assert row["fetch_unit_id"] is not None
            unit = row["fetch_unit_id"]
            assert row["status"] == "PENDING"
        for attempt in (2, 3):
            await only_btc_ready(engine)
            await run_round(engine, OldObservationSource(), "old-refresh-retry", datetime.now(UTC))
            async with market_data_session(engine) as session:
                row = (
                    (
                        await session.execute("""SELECT * FROM market_candle_demand
                    WHERE base='BTC' AND timeframe='1m'""")
                    )
                    .mappings()
                    .one()
                )
                assert row["refresh_served_at"] is None
                assert row["fetch_unit_id"] == unit
                assert row["attemptcount"] == attempt
                assert row["status"] == ("FAILED" if attempt == 3 else "PENDING")
    finally:
        await api.dispose()
        await engine.dispose()


async def test_early_terminal_post_cannot_authorize_retry_after_eligibility() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        window = await isolated_window(engine, 1)
        async with market_data_session(engine) as session:
            now = await database_now(session)
            await session.execute(
                """UPDATE market_candle_demand SET status='FAILED',
                checked_at=:checked,requested_at=:request,next_attempt_at=:eligible,
                attemptcount=3,fetch_unit_id=:unit,fetch_start=:start,fetch_end=:end,
                cursor=:start,leased_start=:start,leased_end=:end""",
                {
                    "checked": now - timedelta(minutes=3),
                    "request": now - timedelta(minutes=2),
                    "eligible": now - timedelta(minutes=1),
                    "unit": uuid4(),
                    "start": window.start,
                    "end": window.end,
                },
            )
            assert await claim_next(session, "too-early-request") is None
            await session.execute("UPDATE market_candle_demand SET requested_at=clock_timestamp()")
            claim = await claim_next(session, "explicit-new-request")
            assert claim is not None
            row = (
                (await session.execute("SELECT attemptcount FROM market_candle_demand"))
                .mappings()
                .one()
            )
            assert row["attemptcount"] == 0
    finally:
        await engine.dispose()


class BlockedSource(FullSource):
    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        await asyncio.Event().wait()
        raise AssertionError("blocked source must be cancelled")


async def test_source_deadline_bounds_attempts_and_persists_timeout_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        await isolated_window(engine, 1)
        monkeypatch.setattr(ingestion, "MARKET_TIMEOUT", timedelta(0), raising=False)
        result = await asyncio.wait_for(
            run_round(engine, BlockedSource(), "deadline", datetime.now(UTC)), 1
        )
        assert result.attempts == 4
        async with market_data_session(engine) as session:
            rows = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE attemptcount=1""")
                )
                .mappings()
                .all()
            )
            assert len(rows) == 4
            now = await database_now(session)
            assert all(row["status"] == "PENDING" for row in rows)
            assert all(row["next_attempt_at"] > now + timedelta(seconds=20) for row in rows)
            assert all(row["fetch_unit_id"] is not None for row in rows)
    finally:
        await engine.dispose()


async def test_actual_rows_commit_and_complete_after_observations() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await session.execute("DELETE FROM market_candle_demand")
            await session.execute("DELETE FROM market_candles")
        source = FullSource()
        await run_round(engine, source, "seed", datetime.now(UTC))
        async with market_data_session(engine) as session:
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() > 0
            await session.execute("""UPDATE market_candle_demand SET next_attempt_at=
                CASE WHEN cursor=leased_end THEN clock_timestamp() ELSE
                clock_timestamp()+interval '1 hour' END""")
        await run_round(engine, source, "finish", datetime.now(UTC))
        async with market_data_session(engine) as session:
            assert (
                await session.execute("""SELECT count(*) FROM market_candle_demand
                WHERE status='COMPLETE'""")
            ).scalar_one() == 4
            assert (
                await session.execute("""SELECT count(*) FROM market_candles
                WHERE finality<>'UNCONFIRMED'""")
            ).scalar_one() == 0
    finally:
        await engine.dispose()


async def test_seed_is_idempotent_and_round_has_four_attempts() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await session.execute("DELETE FROM market_candle_demand")
        source = FakeVenue()
        result = await run_round(engine, source, "test", datetime.now(UTC))
        assert result.attempts == 4
        assert len(source.candle_calls) == 4
        assert len({(r.symbol, r.timeframe) for r in source.candle_calls}) == 4
        await run_round(engine, source, "test", datetime.now(UTC))
        async with market_data_session(engine) as session:
            assert (
                await session.execute("SELECT count(*) FROM market_candle_demand")
            ).scalar_one() == 30
    finally:
        await engine.dispose()


@pytest.mark.parametrize("retry_seconds", [None, 600])
async def test_rate_limit_defers_entire_source(retry_seconds: int | None) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await session.execute("DELETE FROM market_candle_demand")
        source = FakeVenue()
        source.queue_errors(
            [
                VenueRateLimitedError(
                    timedelta(seconds=retry_seconds) if retry_seconds is not None else None
                )
            ]
        )
        result = await run_round(engine, source, "limited", datetime.now(UTC))
        assert result.attempts == 1
        async with market_data_session(engine) as session:
            minimum = (retry_seconds or 120) - 10
            assert (
                await session.execute(
                    """SELECT count(*) FROM market_candle_demand
                WHERE next_attempt_at>clock_timestamp()+make_interval(secs=>:seconds)""",
                    {"seconds": minimum},
                )
            ).scalar_one() == 30
        restarted = await run_round(engine, source, "restarted", datetime.now(UTC))
        assert restarted.attempts == 0
    finally:
        await engine.dispose()


async def test_transient_attempt_count_survives_reclaim() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await session.execute("DELETE FROM market_candle_demand")
        source = FakeVenue()
        source.queue_errors([VenueUnavailableError()] * 12)
        await run_round(engine, source, "first", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute("""SELECT * FROM market_candle_demand
                WHERE attemptcount=1 ORDER BY base,timeframe LIMIT 1""")
                )
                .mappings()
                .one()
            )
            unit = row["fetch_unit_id"]
            await session.execute(
                """UPDATE market_candle_demand SET next_attempt_at=
                CASE WHEN fetch_unit_id=:unit THEN clock_timestamp() ELSE
                clock_timestamp()+interval '1 hour' END""",
                {"unit": unit},
            )
        await run_round(engine, source, "second", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute(
                        "SELECT * FROM market_candle_demand WHERE fetch_unit_id=:unit",
                        {"unit": unit},
                    )
                )
                .mappings()
                .one()
            )
            assert row["attemptcount"] == 2
            assert row["status"] == "PENDING"
            await session.execute(
                """UPDATE market_candle_demand SET
                next_attempt_at=clock_timestamp() WHERE fetch_unit_id=:unit""",
                {"unit": unit},
            )
        await run_round(engine, source, "third", datetime.now(UTC))
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute(
                        "SELECT * FROM market_candle_demand WHERE fetch_unit_id=:unit",
                        {"unit": unit},
                    )
                )
                .mappings()
                .one()
            )
            assert row["attemptcount"] == 3
            assert row["status"] == "FAILED"
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            assert row["next_attempt_at"] > now + timedelta(seconds=110)
    finally:
        await engine.dispose()
