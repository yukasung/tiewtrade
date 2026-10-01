"""ข้อจำกัดของคู่เทรดจาก Binance TH — ทำตามสัญญา `SymbolConstraintSource` ของ F-33

`/exchangeInfo` คืนข้อจำกัดของ **ทุกคู่** ในคำขอเดียวและมี weight 10
การเรียกใหม่ทุกครั้งที่ต้องตรวจออเดอร์หนึ่งไม้จึงเป็นการเผาโควตาเปล่า — เก็บไว้ชั่วคราว
ตามอายุที่ผู้เรียกกำหนด (Q-3)

**กฎเมื่อข้อมูลหมดอายุแล้วอ่านใหม่ไม่สำเร็จ: คืนข้อผิดพลาด**
ห้ามคืนข้อมูลที่หมดอายุเงียบ ๆ เพราะข้อจำกัดที่เปลี่ยนไปแล้วทำให้จุดตรวจก่อนส่งออเดอร์
อนุมัติคำสั่งที่ตลาดจะปฏิเสธ หรือห้ามคำสั่งที่ควรผ่าน (Q-3 — เจ้าของตัดสิน)

**อ่านใหม่สำเร็จแล้วแทนข้อมูลชุดเดิมทั้งชุด** คู่ที่ตลาดถอดออกจึงหายไปจากระบบด้วย
ไม่ใช่ค้างอยู่เพราะไม่มีใครลบ (Q-3)

**เก็บคู่เทรดไว้ในรูปดิบ แล้วแปลงตอนมีคนถามถึงคู่นั้น** (NC-13 — เจ้าของตัดสิน
2026-10-01) เพราะตลาดรายงานตัวเลขที่ F-33 ไม่รับในบางคู่ที่เปิดเทรดจริง
ถ้าแปลงทั้งชุดตอนอ่าน คู่เดียวที่อ่านไม่ได้จะทำให้อ่านคู่อื่นไม่ได้ทั้งหมด
ส่วนคู่ที่อ่านไม่ได้ยัง **ดังเป็น `VenueProtocolError` ตอนที่มีคนถามถึงมัน**
ไม่ได้ถูกข้ามเงียบ ๆ และไม่ถูกแปลว่าตลาดไม่รู้จักคู่นั้น
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Final

from tiewtrade.venues.binance_th.mapping import (
    constraints_from_pair,
    market_symbol,
    pairs_from_exchange_info,
)
from tiewtrade.venues.binance_th.transport import BinanceThTransport
from tiewtrade.venues.errors import RejectionReason, VenueRejectedError
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.moments import require_aware
from tiewtrade.venues.symbols import Symbol, SymbolConstraints

EXCHANGE_INFO_ENDPOINT: Final = "/exchangeInfo"

#: weight ของ `/exchangeInfo` ตามเอกสารของตลาด
CONSTRAINTS_COST: Final = CallCost(weight=10)


class BinanceThConstraints:
    """แหล่งข้อจำกัดของ Binance TH พร้อมที่พักข้อมูลที่มีอายุ"""

    def __init__(
        self,
        transport: BinanceThTransport,
        *,
        ttl: timedelta,
        clock: Callable[[], datetime],
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("อายุของข้อมูลที่เก็บไว้ต้องมากกว่าศูนย์")
        self._transport = transport
        self._ttl = ttl
        self._clock = clock
        #: คู่เทรดในรูปที่ตลาดส่งมา เก็บตามชื่อที่ตลาดเรียกมันเอง
        self._known: dict[str, dict[str, object]] | None = None
        self._loaded_at: datetime | None = None
        # กันคำขออ่านใหม่พร้อมกันหลายอัน ซึ่งจะเสีย weight 10 ต่ออันโดยได้ข้อมูลชุดเดียวกัน
        self._lock = asyncio.Lock()

    async def constraints(self, symbol: Symbol) -> SymbolConstraints:
        """ข้อจำกัดของคู่เทรดนั้น ตามที่ตลาดรายงาน

        ไม่มีคู่นั้นในรายการของตลาด → `VenueRejectedError(UNKNOWN_SYMBOL)`
        """
        known = await self._fresh()
        found = known.get(market_symbol(symbol))
        if found is None:
            raise VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
        return constraints_from_pair(found)

    async def _fresh(self) -> dict[str, dict[str, object]]:
        async with self._lock:
            if self._known is None or self._expired():
                response = await self._transport.get(EXCHANGE_INFO_ENDPOINT, cost=CONSTRAINTS_COST)
                # อ่านให้ครบก่อนแล้วจึงแทนทั้งชุด — ถ้าอ่านซองจดหมายไม่ผ่าน
                # ข้อมูลชุดเดิมต้องไม่กลายเป็นชุดที่อ่านมาได้ครึ่ง ๆ
                parsed = pairs_from_exchange_info(response.payload)
                self._known = parsed
                self._loaded_at = response.received_at
            return self._known

    def _expired(self) -> bool:
        if self._loaded_at is None:
            return True
        now = self._clock()
        require_aware("เวลาที่ใช้ตรวจอายุของข้อจำกัด", now)
        return now - self._loaded_at >= self._ttl
