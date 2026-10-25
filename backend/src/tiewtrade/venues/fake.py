"""ตัวแทนปลอมของตลาด — มีไว้พิสูจน์สัญญา (F-33 Q-1, Q-9, RQ-16)

**ไม่ใช่ตัวจำลองของ Paper Trading** การจำลองการจับคู่ออเดอร์และบัญชี Paper
เป็นงาน **F-15** ซึ่งจะทำตามสัญญาชุดเดียวกันนี้ ตัวนี้ไม่จับคู่อะไร ไม่มีบัญชี
และ **ไม่เปลี่ยนยอดในกระเป๋าเอง** — ยอดที่อ่านได้คือยอดที่ผู้เรียกตั้งไว้เท่านั้น

ทำตามสัญญา **ครบ รวมกรณีผิดพลาดทุกชนิดในหกชนิด** (RQ-16) เพราะตัวปลอมที่ทำแต่
ทางที่สำเร็จจะทำให้เทสต์ของงานหลังไม่เคยเจอกรณีพลาด ซึ่งเป็นกรณีที่กฎความปลอดภัย
เกือบทั้งหมดพูดถึง

บังคับข้อผิดพลาดด้วย **คิว** ไม่ใช่สวิตช์ "ให้พังตลอด" เพราะเทสต์ส่วนใหญ่ต้องการลำดับ
เช่น พลาดครั้งแรกแล้วสำเร็จครั้งที่สอง

**ไม่อ่านนาฬิกาเอง** เวลาที่ติดมากับราคาและยอดกระเป๋าเป็นค่าที่ผู้เรียกกำหนด
เพื่อให้เทสต์ความเก่าของราคาทำได้โดยไม่ต้องรอเวลาจริง
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Iterable, Mapping
from datetime import datetime, timedelta

from tiewtrade.core.market_data import CandleSeries, Timeframe
from tiewtrade.core.realtime_prices import QuoteObservation
from tiewtrade.venues.candle_streams import CandleFeedEvent
from tiewtrade.venues.candles import (
    DEFAULT_CANDLES_COST,
    CandlePage,
    CandleRequest,
    validate_request,
)
from tiewtrade.venues.constraints import DEFAULT_CONSTRAINTS_COST
from tiewtrade.venues.errors import (
    RejectionReason,
    VenueError,
    VenueRejectedError,
    VenueUnavailableError,
)
from tiewtrade.venues.limits import CallCost, NoRateLimit, RateLimitGuard
from tiewtrade.venues.order_books import ExecutionCapability
from tiewtrade.venues.price_streams import FeedEvent
from tiewtrade.venues.prices import DEFAULT_LATEST_PRICE_COST, Price
from tiewtrade.venues.symbols import Symbol, SymbolConstraints
from tiewtrade.venues.wallets import DEFAULT_HOLDINGS_COST, WalletHoldings


class FakeVenue:
    """ตลาดปลอมที่ทำตามทั้งสามสัญญาของ F-33"""

    max_request_span: timedelta | None = None

    async def close(self) -> None:
        return None

    def max_request_slots(self, timeframe: Timeframe) -> int | None:
        if not isinstance(timeframe, Timeframe):
            raise ValueError("unsupported timeframe")
        return None

    def __init__(
        self,
        *,
        prices: Mapping[Symbol, Price] | None = None,
        holdings: WalletHoldings | None = None,
        constraints: Mapping[Symbol, SymbolConstraints] | None = None,
        capabilities: Mapping[Symbol, ExecutionCapability] | None = None,
        guard: RateLimitGuard | None = None,
        latest_price_cost: CallCost = DEFAULT_LATEST_PRICE_COST,
        holdings_cost: CallCost = DEFAULT_HOLDINGS_COST,
        constraints_cost: CallCost = DEFAULT_CONSTRAINTS_COST,
    ) -> None:
        self._prices = dict(prices or {})
        self._holdings = holdings
        self._constraints = dict(constraints or {})
        self._capabilities = dict(capabilities or {})
        self._guard = guard if guard is not None else NoRateLimit()
        self._latest_price_cost = latest_price_cost
        self._holdings_cost = holdings_cost
        self._constraints_cost = constraints_cost
        self._queued_errors: deque[VenueError] = deque()
        self._candle_pages: deque[CandlePage] = deque()
        self.candle_calls: list[CandleRequest] = []

    def queue_candle_pages(self, pages: Iterable[CandlePage]) -> None:
        self._candle_pages.extend(pages)

    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        validate_request(timeframe, start, end, limit)
        self.candle_calls.append(CandleRequest(symbol, timeframe, start, end, limit))
        await self._before_call(DEFAULT_CANDLES_COST)
        if not self._candle_pages:
            raise VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
        return self._candle_pages.popleft()

    def queue_errors(self, errors: Iterable[VenueError]) -> None:
        """เตรียมข้อผิดพลาดให้เกิดตามลำดับที่ใส่ไว้

        การเรียกครั้งถัดไปจะโยนตัวแรกในคิว ครั้งต่อไปโยนตัวถัดไป และเมื่อคิวหมด
        ก็ทำงานตามปกติ — ลำดับคือสิ่งที่เทสต์ของกฎความปลอดภัยต้องใช้
        """
        self._queued_errors.extend(errors)

    async def latest_price(self, symbol: Symbol) -> Price:
        """ราคาล่าสุดที่ผู้เรียกตั้งไว้"""
        await self._before_call(self._latest_price_cost)
        price = self._prices.get(symbol)
        if price is None:
            raise VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
        return price

    async def holdings(self) -> WalletHoldings:
        """ยอดในกระเป๋าที่ผู้เรียกตั้งไว้ — **ไม่เคยเปลี่ยนเอง**"""
        await self._before_call(self._holdings_cost)
        if self._holdings is None:
            raise VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
        return self._holdings

    async def constraints(self, symbol: Symbol) -> SymbolConstraints:
        """ข้อจำกัดของคู่เทรดที่ผู้เรียกตั้งไว้"""
        await self._before_call(self._constraints_cost)
        constraints = self._constraints.get(symbol)
        if constraints is None:
            raise VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
        return constraints

    async def capability(self, symbol: Symbol) -> ExecutionCapability:
        """Exact public execution capability supplied by a catalog test fixture."""
        await self._before_call(self._constraints_cost)
        capability = self._capabilities.get(symbol)
        if capability is None:
            raise VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
        return capability

    async def _before_call(self, cost: CallCost) -> None:
        """จองโควตาก่อน แล้วค่อยดูว่ามีข้อผิดพลาดที่ถูกสั่งไว้หรือไม่

        ลำดับนี้สำคัญ: ตัวจริงต้องจองก่อนแตะเครือข่าย ฉะนั้นตัวปลอมก็ต้องจองก่อน
        แม้การเรียกนั้นจะถูกสั่งให้ล้มเหลว ไม่เช่นนั้นเทสต์เรื่องโควตาจะพิสูจน์
        พฤติกรรมที่ไม่เหมือนของจริง
        """
        await self._guard.reserve(cost)
        if self._queued_errors:
            raise self._queued_errors.popleft()


class FakePriceFeed:
    """Finite scripted feed with exact recovery observations and no clock/network."""

    def __init__(
        self, *, snapshots: dict[Symbol, QuoteObservation], events: tuple[FeedEvent, ...] = ()
    ) -> None:
        self._snapshots = dict(snapshots)
        self._events = events

    async def snapshot(self, symbol: Symbol) -> QuoteObservation:
        quote = self._snapshots.get(symbol)
        if quote is None:
            raise VenueUnavailableError()
        return quote

    async def events(self, symbols: tuple[Symbol, ...]) -> AsyncIterator[FeedEvent]:
        for event in self._events:
            yield event


class FakeCandleFeed:
    """Finite scripted candle events; no financial calculation or external I/O."""

    def __init__(self, events: tuple[CandleFeedEvent, ...] = ()) -> None:
        self._events = events

    async def events(
        self, series: tuple[CandleSeries, ...]
    ) -> AsyncGenerator[CandleFeedEvent, None]:
        for event in self._events:
            yield event
