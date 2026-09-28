"""ค่าตั้งต้นที่เทสต์ของชั้น venue ใช้ร่วมกัน

อยู่ที่เดียวด้วยเหตุผลเดียวกับ `tests/core/money/conftest.py` — ถ้าแต่ละไฟล์เขียน
ค่าขอบของตัวเอง สองไฟล์จะค่อย ๆ ไม่ตรงกัน แล้วเทสต์จะพิสูจน์คนละเรื่องโดยไม่มีใครรู้
"""

from __future__ import annotations

from datetime import UTC, datetime

from tiewtrade.core.money import Money, Quantity
from tiewtrade.venues import Holding, Price, Symbol, SymbolConstraints, WalletHoldings

BTC_USDT = Symbol(base="BTC", quote="USDT")
ETH_USDT = Symbol(base="ETH", quote="USDT")

#: เวลาอ้างอิงของเทสต์ — คงที่ เพราะการทดสอบความเก่าของราคาต้องไม่ขึ้นกับนาฬิกาจริง
MARKET_TIME = datetime(2026, 9, 28, 10, 0, tzinfo=UTC)

PRICE = Price(
    symbol=BTC_USDT,
    amount=Money.of("70000", "USDT"),
    venue_time=MARKET_TIME,
    received_at=MARKET_TIME,
)

CONSTRAINTS = SymbolConstraints(
    symbol=BTC_USDT,
    minimum_quantity=Quantity.of("0.001", "BTC"),
    quantity_step=Quantity.of("0.0001", "BTC"),
    minimum_notional=Money.of("10", "USDT"),
)

HOLDINGS = WalletHoldings(
    received_at=MARKET_TIME,
    holdings=(Holding(available=Quantity.of("0.5", "BTC"), reserved=Quantity.of(0, "BTC")),),
)
