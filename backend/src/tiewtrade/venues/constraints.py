"""สัญญาของแหล่งข้อจำกัดของเหรียญ (F-33)

จุดตรวจก่อนส่งออเดอร์ของ F-16 และ F-22 ต้องใช้ข้อจำกัดเหล่านี้
(`trading-safety.md` หัวข้อ 3) ตัวจุดตรวจเองอยู่นอกชั้นนี้ เพราะเป็นกฎของระบบ
ไม่ใช่ความสามารถของตลาด

การตรวจว่าคำสั่งผ่านข้อจำกัดหรือไม่อยู่ใน `tiewtrade.core.trading_limits`
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.symbols import Symbol, SymbolConstraints

#: ต้นทุนของการอ่านข้อจำกัด — ตัวเชื่อมของแต่ละตลาดประกาศค่าของตลาดนั้นเอง
DEFAULT_CONSTRAINTS_COST = CallCost(weight=1)


@runtime_checkable
class SymbolConstraintSource(Protocol):
    """แหล่งข้อจำกัดของคู่เทรดของตลาดหนึ่ง"""

    async def constraints(self, symbol: Symbol) -> SymbolConstraints:
        """ข้อจำกัดของคู่เทรดนั้น ตามที่ตลาดรายงาน

        **ต้องจองโควตากับตัวกั้นก่อนเรียกตลาดจริงทุกครั้ง** (Q-8)
        ไม่พบคู่เทรด → `VenueRejectedError` พร้อมเหตุผล `UNKNOWN_SYMBOL`
        """
        ...
