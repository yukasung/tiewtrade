"""ชั้นแยก venue — ส่วนต่อประสานกลางที่ตลาดทุกตลาดต้องทำตาม (F-33)

**โค้ดนอก package นี้ต้องไม่รู้ว่ากำลังคุยกับตลาดไหน** (`architecture.md` หัวข้อ 1)
ตัวเชื่อมของแต่ละตลาดอยู่ใน package ย่อยของที่นี่ — ตลาดเดียวของระบบคือ Binance TH
ซึ่งเป็นงาน F-35

งานนี้ส่งมอบสามสัญญา: ราคา, กระเป๋า, ข้อจำกัดของเหรียญ
**สัญญาส่งออเดอร์ยังไม่มี** เพราะชนิดออเดอร์ที่รองรับยังไม่ถูกตัดสิน (NC-08)
และ `AGENTS.md` กฎข้อ 2 ห้ามคิดข้อกำหนดการเทรดขึ้นเอง
"""

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
from tiewtrade.venues.fake import FakeVenue
from tiewtrade.venues.limits import CallCost, NoRateLimit, RateLimitGuard
from tiewtrade.venues.prices import DEFAULT_LATEST_PRICE_COST, Price, PriceSource
from tiewtrade.venues.signing import RequestSigner
from tiewtrade.venues.symbols import Symbol, SymbolConstraints
from tiewtrade.venues.wallets import (
    DEFAULT_HOLDINGS_COST,
    Holding,
    WalletHoldings,
    WalletSource,
)


def live_wallet_source(
    *,
    signer: RequestSigner,
    client: object,
    clock: object,
    timeout: object,
) -> WalletSource:
    """กระเป๋าของ **ตลาดจริง** หนึ่งใบ — จุดเดียวที่ประกอบตัวเชื่อมเข้ากับคำรับรอง

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
        guard=IpWeightLimiter(clock=clock),  # type: ignore[arg-type]
        clock=clock,  # type: ignore[arg-type]
        timeout=timeout,  # type: ignore[arg-type]
    )
    return BinanceThWallet(transport, signer)


__all__ = [
    "DEFAULT_CONSTRAINTS_COST",
    "DEFAULT_HOLDINGS_COST",
    "DEFAULT_LATEST_PRICE_COST",
    "CallCost",
    "FakeVenue",
    "Holding",
    "NoRateLimit",
    "Price",
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
    "live_wallet_source",
]
