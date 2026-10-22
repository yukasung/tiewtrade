import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.indicators.parity_reference import (
    SPAN,
    Slot,
    canonical_digest,
    parity_slots,
    reference_points,
    scan,
)
from tests.infra.market_data.test_retention import insert_raw
from tiewtrade.core.indicators import IndicatorStatus, IndicatorStream
from tiewtrade.core.market_data import CandleWindow, Timeframe, align_floor, expected_opens
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import indicator_read_session, market_data_session
from tiewtrade.infra.indicators.codec import decode_checkpoint, encode_checkpoint
from tiewtrade.infra.indicators.source import begin_source_write
from tiewtrade.infra.market_data import indicator_reader


async def test_fetch_sizes_and_canonical_digest(
    api_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await insert_raw("1", age=timedelta(minutes=2))
    now = datetime.now(UTC)
    end = align_floor(now, Timeframe.M1)
    window = CandleWindow(end - timedelta(minutes=64), end)
    async with indicator_read_session(api_engine, uuid4()) as session:
        source = (
            (
                await session.execute(
                    "SELECT open_at,end_at,observed_at,fetch_started_at "
                    "FROM market_candles WHERE base='BTC'"
                )
            )
            .mappings()
            .one()
        )

        def stamp(moment: datetime) -> str:
            return moment.astimezone(UTC).isoformat(timespec="microseconds")

        records: list[list[object]] = [
            [
                1,
                "primary_spot",
                "BTC",
                "USDT",
                "1m",
                "indicators-v2",
                stamp(window.start),
                stamp(window.end),
            ]
        ]
        for moment in expected_opens(window, Timeframe.M1):
            records.append(
                [
                    stamp(moment),
                    stamp(source["end_at"]),
                    "1",
                    "2",
                    "1",
                    "1",
                    "0",
                    "UNCONFIRMED",
                    stamp(source["observed_at"]),
                    stamp(source["fetch_started_at"]),
                ]
                if moment == source["open_at"]
                else [stamp(moment), "MISSING"]
            )
        expected = hashlib.sha256(
            b"".join(
                json.dumps(record, separators=(",", ":")).encode() + b"\n" for record in records
            )
        ).hexdigest()
        results = []
        for size in (16, 64, 1000):

            def windows(
                value: CandleWindow,
                tf: Timeframe,
                _limit: int = 250,
                size: int = size,
            ) -> Iterator[CandleWindow]:
                cursor = value.start
                while cursor < value.end:
                    stop = min(cursor + size * tf.span, value.end)
                    yield CandleWindow(cursor, stop)
                    cursor = stop

            monkeypatch.setattr(indicator_reader, "bounded_windows", windows)
            result = await indicator_reader.read_indicators(
                session, "BTC", "USDT", Timeframe.M1, window, window, now, monotonic() + 30
            )
            assert result.revision == expected
            assert len(result.points) == 64
            results.append(result)
        assert results[0] == results[1] == results[2]


@pytest.mark.parametrize(("fetch_size", "batch_size"), [(7, 1), (64, 2), (1000, 16)])
async def test_checkpoint_replay_matches_database_full_scan(
    api_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    fetch_size: int,
    batch_size: int,
) -> None:
    now = datetime.now(UTC)
    end = align_floor(now, Timeframe.M1)
    window = CandleWindow(end - 1220 * SPAN, end)
    slots = parity_slots(window.start, 199, [((i % 41) - 20) * 10**17 + i for i in range(440)])
    expected_points = reference_points(slots)
    expected_digest = canonical_digest(slots, window)
    md_engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(md_engine) as writer:
            await begin_source_write(writer)
            for _, bar, fetched in slots:
                if bar is None:
                    continue
                await writer.execute(
                    """INSERT INTO market_candles
                    (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
                     finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                    VALUES ('primary_spot','BTC','USDT','1m',:opened,:end,
                    CAST(:price AS numeric),CAST(:high AS numeric),CAST(:low AS numeric),
                    CAST(:price AS numeric),CAST(:volume AS numeric),
                    :finality,:observed,:fetched,:checked,1)""",
                    {
                        "opened": bar.open_at,
                        "end": bar.end_at,
                        "price": bar.close.as_parts()["amount"],
                        "high": bar.high.as_parts()["amount"],
                        "low": bar.low.as_parts()["amount"],
                        "volume": bar.volume.as_parts()["quantity"],
                        "finality": bar.finality.value,
                        "observed": bar.observed_at,
                        "fetched": fetched,
                        "checked": now,
                    },
                )
    finally:
        await md_engine.dispose()

    def windows(value: CandleWindow, tf: Timeframe, _limit: int = 250) -> Iterator[CandleWindow]:
        cursor = value.start
        while cursor < value.end:
            stop = min(cursor + fetch_size * tf.span, value.end)
            yield CandleWindow(cursor, stop)
            cursor = stop

    monkeypatch.setattr(indicator_reader, "bounded_windows", windows)
    builder = IndicatorStream("BTC", "USDT", Timeframe.M1, now)
    identity = {"generation_id": "database-parity", "source": "primary_spot"}
    async with indicator_read_session(api_engine, uuid4()) as session:
        reference = await indicator_reader.read_indicators(
            session, "BTC", "USDT", Timeframe.M1, window, window, now, monotonic() + 30
        )
        assert reference.points == expected_points
        assert reference.revision == expected_digest
        assert reference.refresh_first == window.start + 1020 * SPAN
        assert not reference.refresh_more

        async def load(value: CandleWindow) -> tuple[Slot, ...]:
            loaded: list[Slot] = []
            for part in windows(value, Timeframe.M1):
                rows = {
                    row["open_at"]: row
                    for row in await indicator_reader.fetch_rows(
                        session, "BTC", "USDT", Timeframe.M1, part
                    )
                }
                for moment in expected_opens(part, Timeframe.M1):
                    raw = rows.get(moment)
                    stored = indicator_reader.decode_row(raw, builder.series) if raw else None
                    loaded.append(
                        (
                            moment,
                            stored.candle if stored else None,
                            stored.fetch_started_at if stored else None,
                        )
                    )
            return tuple(loaded)

        first = CandleWindow(window.start, window.start + 1000 * SPAN)
        first_slots = await load(first)
        assert scan(builder, first_slots, batch_size, fetch_size) == expected_points[:1000]
        assert len(builder.state.averages[2].pending) == 199
        checkpoint = encode_checkpoint(
            builder, **identity, calculation=window, next_open_at=first.end
        )
        replay = decode_checkpoint(
            json.loads(json.dumps(checkpoint)),
            **identity,
            base="BTC",
            quote="USDT",
            timeframe=Timeframe.M1,
            as_of=now,
            calculation=window,
            next_open_at=first.end,
        )
        last = CandleWindow(first.end, window.end)
        last_slots = await load(last)
        points = scan(replay, last_slots, batch_size, fetch_size)
        assert points == reference.points[1000:] == expected_points[1000:]
        assert all(value.status is IndicatorStatus.READY for value in points[0].values.values())
        assert canonical_digest((*first_slots, *last_slots), window) == expected_digest
