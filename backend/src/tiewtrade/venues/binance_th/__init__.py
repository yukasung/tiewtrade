"""ตัวเชื่อม Binance TH — Spot เท่านั้น (F-35)

ตลาดเดียวของระบบ `mission.md` หัวข้อ 2 — **ยังไม่มี Futures** (NC-12)

F-35 ทำเฉพาะ **endpoint สาธารณะ**: ราคาและข้อจำกัดของเหรียญ · **F-07 เพิ่มกระเป๋า**
ซึ่งเป็น endpoint ที่ต้องลงลายเซ็น และใช้เป็นหลักฐานว่า API key ของผู้ใช้ใช้งานได้จริง
**ยังไม่มีการส่งคำสั่งซื้อขาย** (F-16)

**package นี้ไม่เคยเห็น secret ของผู้ใช้** — มันรับ "ตัวลงลายเซ็น" ตามสัญญา
`venues/signing.py` ซึ่งถือความลับไว้ข้างในตัวเอง ส่วนตัวที่ทำตามสัญญานั้นอยู่ใน
`infra/api_keys` (F-07 Q-2 ที่เจ้าของตัดสิน)

**เส้นทางที่เรียกได้เป็นรายการปิดใน `endpoints.py`** — เส้นทางที่ย้ายเงินออกจาก
บัญชีผู้ใช้สร้างขึ้นมาไม่ได้เลย ไม่ใช่แค่ไม่มีใครเขียน (F-07 RQ-16)

**package นี้เป็นที่เดียวในระบบที่พูดชื่อตลาดได้** ด่านคำศัพท์อ่าน `VENUE_VOCABULARY`
ข้างล่างไปใช้เป็นรายการคำที่ห้ามโผล่นอกชั้น `venues`
"""

from __future__ import annotations

from typing import Final

from tiewtrade.venues.binance_th.constraints import BinanceThConstraints
from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.prices import BinanceThPrices
from tiewtrade.venues.binance_th.rate_limit import IpWeightLimiter
from tiewtrade.venues.binance_th.transport import BASE_URL, BinanceThTransport
from tiewtrade.venues.binance_th.wallets import BinanceThWallet

#: คำที่เป็นของตลาดนี้โดยเฉพาะ — **ห้ามปรากฏนอกชั้น `venues`**
#:
#: ประกาศไว้ข้างโค้ดที่พาคำเหล่านี้เข้ามา ไม่ใช่ในไฟล์เทสต์ที่อยู่ไกลออกไป
#: ด่านอ่านรายการนี้ด้วย AST จากทุก package ตัวเชื่อม แล้วรวมเป็นรายการที่ห้าม
#: การเพิ่มตลาดใหม่จึงขยายด่านให้เองโดยไม่ต้องมีใครจำ (plan.md ข้อ 7.2)
#:
#: `mbx` มาจาก header `X-MBX-USED-WEIGHT-*` ที่ตลาดส่งกลับมา
VENUE_VOCABULARY: Final[frozenset[str]] = frozenset({"binance", "fapi", "sapi", "testnet", "mbx"})

#: เปิดเท่าที่ผู้เรียกใช้จริง — ต้นทุนของแต่ละ endpoint, ตารางแปลข้อผิดพลาด
#: และชนิดช่วยเหลืออื่นอยู่ในโมดูลของตัวเอง ใครต้องใช้ก็ import จากที่นั่นตรง ๆ
#: ชื่อที่ส่งออกไว้เผื่อคือชื่อที่ต้องรักษาความเข้ากันได้ทั้งที่ยังไม่มีใครเรียก
__all__ = [
    "BASE_URL",
    "VENUE_VOCABULARY",
    "BinanceThConstraints",
    "BinanceThPrices",
    "BinanceThTransport",
    "BinanceThWallet",
    "Endpoint",
    "IpWeightLimiter",
]
