"""Shared native source loops for inline and isolated F18 fixture publication."""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_observations import SOURCE_HZ, SOURCE_PERIOD_SECONDS
from tests.infra.risk_limits.profile_resources import PoolEvidence
from tests.infra.risk_limits.profile_source_timing import SourceTimeline, source_cycle
from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import MarketTrade
from tiewtrade.core.orders import OrderType
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import (
    BookLease,
    ExecutionMetadata,
    publish_input,
)
from tiewtrade.infra.market_data.realtime_records import FeedLease
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    read_snapshot,
    renew_writer,
    set_connected,
    write_price,
)

FAILURE_CATEGORIES = frozenset(
    {
        "DatabaseTimeoutError",
        "DatabaseUnavailableError",
        "DatabaseRetryableError",
        "SourceUnavailableError",
        "ExecutionInputGapError",
        "SourceProofStateError",
        "TimeoutError",
        "AssertionError",
        "RuntimeError",
        "ValueError",
        "OTHER",
    }
)
FAILURE_STAGES = frozenset({"ACQUIRE", "BOOK", "PRICE", "PUBLISH"})


class SourcePublisher:
    def __init__(
        self, output: Path, emit: Callable[[dict[str, Any]], Awaitable[None] | None]
    ) -> None:
        self.output = output
        self.emit = emit
        self.failure: dict[str, str] | None = None
        self.event_timeout = 5.0
        self.price = "100"
        self.ask_quantity = Quantity.of(1000000, "BTC")
        self.finish_partial = False
        self.stop_market = asyncio.Event()
        self.source_timeline: SourceTimeline | None = None
        self.publisher_stats: dict[str, Any] = {"target_hz": SOURCE_HZ}
        self.price_identities: set[tuple[object, ...]] = set()
        self.last_frame = 0
        self.started = False
        self.suspend_prices_until = 0.0
        self._source_market: AsyncEngine | None = None
        self.source_pools: PoolEvidence | None = None

    @property
    def source_market(self) -> AsyncEngine:
        if self._source_market is None:
            self._source_market = create_engine_for(
                DatabaseRole.MARKET_DATA, pool_size=3, max_overflow=0
            )
            self.source_pools = PoolEvidence(self.output / "publisher.pools.json")
            self.source_pools.add(self._source_market, DatabaseRole.MARKET_DATA)
        return self._source_market

    def configure(self, values: dict[str, Any]) -> None:
        allowed = {
            "price",
            "ask_quantity",
            "finish_partial",
            "suspend_prices_until",
            "started",
            "trace_start",
        }
        if not values.keys() <= allowed:
            raise ValueError("F18_SOURCE_CONTROL_UNKNOWN")
        prepared: dict[str, Any] = {}
        for key, value in values.items():
            if key in {"started", "finish_partial"}:
                if not isinstance(value, bool):
                    raise ValueError("F18_SOURCE_CONTROL_BOOLEAN")
            elif key in {"trace_start", "suspend_prices_until"}:
                if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                    raise ValueError("F18_SOURCE_CONTROL_TIME")
            elif key == "ask_quantity":
                value = Quantity.of(value, "BTC")
            elif key == "price":
                Money.of(
                    value, "USDT"
                )  # reuse domain validation; store original exact representation
            prepared[key] = value
        if (
            "trace_start" in prepared
            and self.source_timeline is not None
            and self.source_timeline.started is not None
        ):
            raise ValueError("F18_SOURCE_TRACE_ALREADY_ACTIVE")
        for key, value in prepared.items():
            if key == "trace_start":
                if self.source_timeline is not None:
                    self.source_timeline.activate(value)
            else:
                setattr(self, key, value)

    async def close_source(self) -> None:
        if self.source_timeline is not None:
            self.source_timeline.close()
        if self._source_market is not None:
            await self._source_market.dispose()
        if self.source_pools is not None:
            self.source_pools.finish()

    async def send_event(self, event: dict[str, Any]) -> None:
        result = self.emit(event)
        if result is not None:
            async with asyncio.timeout(self.event_timeout):
                await result

    def record_failure(self, error: Exception, stage: str) -> None:
        if self.failure is not None:
            return
        category = type(error).__name__
        self.failure = {
            "category": category if category in FAILURE_CATEGORIES else "OTHER",
            "stage": stage if stage in FAILURE_STAGES else "PUBLISH",
        }
        (self.output / "publisher-failure.json").write_text(
            json.dumps(
                {
                    **self.failure,
                    "at": datetime.now(UTC).isoformat(),
                    "monotonic": monotonic(),
                }
            )
            + "\n"
        )

    async def publish(self) -> None:
        try:
            book, price = await f15.acquire_sources(self.source_market)
        except Exception as error:
            self.record_failure(error, "ACQUIRE")
            raise
        # R12: separate source clocks, with the same process, pool and budgets.
        tasks = (
            asyncio.create_task(self._publish_books(book, price)),
            asyncio.create_task(self._publish_prices(price)),
        )
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                try:
                    task.result()
                except Exception as error:
                    self.record_failure(error, "BOOK" if task is tasks[0] else "PRICE")
                    raise
            if not self.stop_market.is_set():
                raise RuntimeError("F18_SOURCE_PUBLISHER_STOPPED_UNEXPECTEDLY")
            # A normal stop must retain evidence for an in-flight committed price.
            # Canceling its recorder here leaves last_frame behind the actual tail.
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _publish_books(self, book: BookLease, price: FeedLease) -> None:
        tick = 0
        due = monotonic()
        while not self.stop_market.is_set():
            await asyncio.sleep(max(0, due - monotonic()))
            async with source_cycle(self.source_timeline, "BOOK", due):
                tick += 1
                ask_quantity = self.ask_quantity
                book, price = await f15.publish_market(
                    self.source_market,
                    book,
                    price,
                    rebase=tick == 1,
                    trade_id=tick,
                    update_price=False,
                    ask_quantity=ask_quantity,
                )
                async with market_data_session(self.source_market) as session:
                    committed = (
                        await session.execute(
                            "SELECT pg_xact_commit_timestamp(xmin) FROM market_execution_buffer "
                            "WHERE source=:source AND base=:base AND quote=:quote "
                            "AND input_id=:input",
                            {
                                "source": "primary_spot",
                                "base": "BTC",
                                "quote": "USDT",
                                "input": book.last_input_id,
                            },
                        )
                    ).scalar_one()
                await self.source_receipt("BOOK", "BTC/USDT", str(book.last_input_id), committed)
                if self.finish_partial:
                    # A partially filled GTC limit is resting: replenished depth alone
                    # cannot fill it. Keep publishing distinct fresh contra trades
                    # until FILLED is observed: recovery may discard stale inputs.
                    async with market_data_session(self.source_market) as session:
                        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                        book = await publish_input(
                            session,
                            book,
                            MarketTrade(
                                f15.PAIR,
                                book.last_input_id + 1,
                                book.generation,
                                now,
                                tick,
                                ExecutionSide.BUY,
                                Money.of(100, "USDT"),
                                Quantity.of("0.5", "BTC"),
                                True,
                            ),
                            ExecutionMetadata(
                                f15.constraints(OrderType.MARKET),
                                f15.constraints(OrderType.LIMIT),
                                now,
                                f15.SOURCE_DOCUMENT,
                            ),
                        )
                self.publisher_stats.update(
                    published=int(self.publisher_stats.get("published", 0)) + 1,
                    last_input_id=book.last_input_id,
                    last_ask_quantity=ask_quantity.as_parts()["quantity"],
                )
                await self.send_event({"kind": "stats", "values": dict(self.publisher_stats)})
            due += SOURCE_PERIOD_SECONDS

    async def _publish_prices(self, price: FeedLease) -> None:
        tick = 0
        due = monotonic()
        while not self.stop_market.is_set():
            await asyncio.sleep(max(0, due - monotonic()))
            if monotonic() < self.suspend_prices_until:
                due += SOURCE_PERIOD_SECONDS
                continue
            async with source_cycle(self.source_timeline, "PRICE", due):
                async with market_data_session(self.source_market) as session:
                    snapshot = await read_snapshot(session)
                    if price.lease_until <= snapshot.server_time:
                        acquired = await acquire_writer(session, uuid4())
                        assert acquired is not None
                        price = await set_connected(session, acquired, True)
                    else:
                        price = await renew_writer(session, price)
                    for base, amount in (("BTC", self.price), ("ETH", "2000")):
                        row = next(row for row in snapshot.rows if row.base == base)
                        now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
                        quote = QuoteObservation(
                            row.source,
                            base,
                            "USDT",
                            Money.of(amount, "USDT"),
                            1 if row.observation is None else row.observation.trade_id + 1,
                            now,
                            now,
                            ObservationKind.STREAM,
                        )
                        assert await write_price(
                            session,
                            price,
                            replace(
                                row,
                                observation=quote,
                                reconciled_generation=price.generation,
                                effective_readiness="READY",
                                reason=None,
                                unavailable_since=None,
                                order_ambiguous_at=None,
                            ),
                        )
                async with market_data_session(self.source_market) as session:
                    frames = await session.execute(
                        """SELECT id,payload,pg_xact_commit_timestamp(xmin) ready_at
                      FROM market_risk_price_frames WHERE id>:last ORDER BY id""",
                        {"last": self.last_frame},
                    )
                    for frame_row in frames:
                        if frame_row.ready_at is None:
                            raise RuntimeError("F18_COMMIT_TIMESTAMPS_REQUIRED")
                        for item in frame_row.payload["rows"]:
                            if item["amount"] is None:
                                continue
                            identity = (
                                item["source"],
                                item["base"],
                                item["quote"],
                                item["trade_id"],
                                item["received_at"],
                            )
                            if identity not in self.price_identities:
                                self.price_identities.add(identity)
                                await self.source_receipt(
                                    "PRICE",
                                    f"{item['base']}/{item['quote']}",
                                    json.dumps(identity),
                                    frame_row.ready_at,
                                )
                        await self.send_event(
                            {
                                "kind": "frame",
                                "cursor": frame_row.id,
                                "ready_at": frame_row.ready_at.isoformat(),
                                "measured": self.started,
                            }
                        )
                        self.last_frame = frame_row.id
                tick += 1
                self.publisher_stats["price_published"] = (
                    int(self.publisher_stats.get("price_published", 0)) + 1
                )
                await self.send_event({"kind": "stats", "values": dict(self.publisher_stats)})
            due += SOURCE_PERIOD_SECONDS

    async def source_receipt(
        self, kind: str, pair: str, identity: str, committed: datetime | None
    ) -> None:
        if committed is None:
            raise RuntimeError("F18_COMMIT_TIMESTAMPS_REQUIRED")
        if self.source_timeline is not None:
            self.source_timeline.receipt(kind, pair, identity, committed.isoformat())
        await self.send_event(
            {
                "kind": "receipt",
                "source": kind,
                "pair": pair,
                "identity": identity,
                "committed_at": committed.isoformat(),
            }
        )
