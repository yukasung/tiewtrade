"""ชั้นแยก venue — ส่วนต่อประสานกลางที่ตลาดทุกตลาดต้องทำตาม (F-33)

**โค้ดนอก package นี้ต้องไม่รู้ว่ากำลังคุยกับตลาดไหน** (`architecture.md` หัวข้อ 1)
ตัวเชื่อมของแต่ละตลาดอยู่ใน package ย่อยของที่นี่ — ตลาดเดียวของระบบคือ Binance TH
ซึ่งเป็นงาน F-35

งานนี้ส่งมอบสามสัญญา: ราคา, กระเป๋า, ข้อจำกัดของเหรียญ
**สัญญาส่งออเดอร์ยังไม่มี** เพราะชนิดออเดอร์ที่รองรับยังไม่ถูกตัดสิน (NC-08)
และ `AGENTS.md` กฎข้อ 2 ห้ามคิดข้อกำหนดการเทรดขึ้นเอง
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from tiewtrade.venues.candle_streams import CandleFeed
from tiewtrade.venues.candles import CandlePage, CandleSource
from tiewtrade.venues.constraints import DEFAULT_CONSTRAINTS_COST, SymbolConstraintSource
from tiewtrade.venues.errors import (
    RejectionReason,
    VenueCredentialRejectedError,
    VenueError,
    VenueOutcomeUnknownError,
    VenueProtocolError,
    VenueRateLimitedError,
    VenueRejectedError,
    VenueUnavailableError,
)
from tiewtrade.venues.fake import FakeCandleFeed, FakePriceFeed, FakeVenue
from tiewtrade.venues.limits import CallCost, NoRateLimit, RateLimitGuard
from tiewtrade.venues.price_streams import PriceFeed
from tiewtrade.venues.prices import DEFAULT_LATEST_PRICE_COST, Price, PriceSource
from tiewtrade.venues.signing import RequestSigner
from tiewtrade.venues.symbols import Symbol, SymbolConstraints
from tiewtrade.venues.wallets import (
    DEFAULT_HOLDINGS_COST,
    Holding,
    WalletHoldings,
    WalletSource,
)


def live_candle_feed(*, clock: Callable[[], datetime]) -> CandleFeed:
    from tiewtrade.venues.binance_th.candle_feed import BinanceThCandleFeed
    from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport

    return BinanceThCandleFeed(BinanceThStreamTransport(clock=clock))


def live_candle_source(
    *,
    client: object,
    clock: Callable[[], datetime],
    timeout: timedelta,
    guard: RateLimitGuard | None = None,
) -> CandleSource:
    """Compose one public source with shared conservative IP reservations."""
    from tiewtrade.venues.binance_th import BinanceThTransport, IpWeightLimiter
    from tiewtrade.venues.binance_th.candles import BinanceThCandles

    transport = BinanceThTransport(
        client=client,  # type: ignore[arg-type]
        guard=guard
        if guard is not None
        else IpWeightLimiter(clock=clock, reservation_weight_floor=10),
        clock=clock,
        timeout=timeout,
    )
    return BinanceThCandles(transport, clock=clock)


def live_price_feed(
    *,
    client: object,
    clock: Callable[[], datetime],
    timeout: timedelta,
    guard: RateLimitGuard | None = None,
) -> "PriceFeed":
    """Compose public recovery and stream, sharing the caller's IP guard."""
    from tiewtrade.venues.binance_th import BinanceThTransport, IpWeightLimiter
    from tiewtrade.venues.binance_th.price_feed import BinanceThPriceFeed
    from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport

    transport = BinanceThTransport(
        client=client,  # type: ignore[arg-type]
        guard=guard
        if guard is not None
        else IpWeightLimiter(clock=clock, reservation_weight_floor=10),
        clock=clock,
        timeout=timeout,
    )
    return BinanceThPriceFeed(transport, BinanceThStreamTransport(clock=clock))


def public_rate_limit_guard(*, clock: Callable[[], datetime]) -> RateLimitGuard:
    """A single public-data reservation guard for all sources in one process."""
    from tiewtrade.venues.binance_th import IpWeightLimiter

    return IpWeightLimiter(clock=clock, reservation_weight_floor=10)


def live_wallet_factory(
    *,
    client: object,
    clock: Callable[[], datetime],
    timeout: timedelta,
) -> Callable[[RequestSigner], WalletSource]:
    """ตัวสร้างกระเป๋าของ **ตลาดจริง** — แชร์ transport/โควตาตลอดอายุ factory

    **มีไว้เพื่อให้ service เรียกใช้ได้โดยไม่ต้องเอ่ยชื่อตลาด** (`architecture.md`
    หัวข้อ 1 — โค้ดนอก `venues` ต้องไม่รู้ว่ากำลังคุยกับตลาดไหน) ก่อนหน้านี้ไม่มีใคร
    ต้องประกอบของพวกนี้เลย เพราะ F-35 ยังไม่มีผู้เรียก · F-07 เป็นผู้เรียกรายแรก

    **import ตัวเชื่อมข้างในฟังก์ชันโดยเจตนา** — ที่นี่เป็น `__init__` ของชั้นกลาง
    การ import ตัวเชื่อมที่ระดับโมดูลจะทำให้ทุกคนที่แตะชั้นกลางลากตัวเชื่อมและไลบรารี
    เครือข่ายติดไปด้วย ทั้งที่ส่วนใหญ่ไม่ได้ใช้ · และยังเลี่ยงวงจร import ระหว่าง
    package แม่กับ package ย่อย

    **การเลือกตลาดอยู่ที่นี่ที่เดียว** วันที่มีตลาดที่สอง ฟังก์ชันนี้คือที่ที่เลือก
    ไม่ใช่ที่ service
    """
    from tiewtrade.venues.binance_th import BinanceThTransport, IpWeightLimiter
    from tiewtrade.venues.binance_th.wallets import BinanceThWallet

    transport = BinanceThTransport(
        client=client,  # type: ignore[arg-type]
        guard=IpWeightLimiter(clock=clock),
        clock=clock,
        timeout=timeout,
    )

    def build(signer: RequestSigner) -> WalletSource:
        return BinanceThWallet(transport, signer)

    return build


__all__ = [
    "DEFAULT_CONSTRAINTS_COST",
    "DEFAULT_HOLDINGS_COST",
    "DEFAULT_LATEST_PRICE_COST",
    "CallCost",
    "CandleFeed",
    "CandlePage",
    "CandleSource",
    "FakeCandleFeed",
    "FakePriceFeed",
    "FakeVenue",
    "Holding",
    "NoRateLimit",
    "Price",
    "PriceFeed",
    "PriceSource",
    "RateLimitGuard",
    "RejectionReason",
    "RequestSigner",
    "Symbol",
    "SymbolConstraintSource",
    "SymbolConstraints",
    "VenueCredentialRejectedError",
    "VenueError",
    "VenueOutcomeUnknownError",
    "VenueProtocolError",
    "VenueRateLimitedError",
    "VenueRejectedError",
    "VenueUnavailableError",
    "WalletHoldings",
    "WalletSource",
    "live_candle_feed",
    "live_candle_source",
    "live_price_feed",
    "live_wallet_factory",
    "public_rate_limit_guard",
]
