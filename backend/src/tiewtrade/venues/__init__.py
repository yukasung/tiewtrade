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
from tiewtrade.venues.symbols import Symbol, SymbolConstraints
from tiewtrade.venues.wallets import (
    DEFAULT_HOLDINGS_COST,
    Holding,
    WalletHoldings,
    WalletSource,
)

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
]
