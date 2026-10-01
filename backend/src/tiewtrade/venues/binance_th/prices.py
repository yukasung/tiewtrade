"""ราคาล่าสุดจาก Binance TH — ทำตามสัญญา `PriceSource` ของ F-33 (plan.md ข้อ 4)

ใช้ `/trades?limit=1` ตามที่เจ้าของเห็นชอบ (Q-7) เพราะรายการซื้อขายล่าสุด
**พาเวลาของตัวมันเองมาด้วย** ส่วน `/ticker/price` ไม่มีเวลา จึงใช้ตัดสินความเก่าไม่ได้
"""

from __future__ import annotations

from typing import Final

from tiewtrade.venues.binance_th.mapping import market_symbol, price_from_trades
from tiewtrade.venues.binance_th.transport import BinanceThTransport
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.prices import Price
from tiewtrade.venues.symbols import Symbol

TRADES_ENDPOINT: Final = "/trades"

#: weight ของ `/trades` ตามเอกสารของตลาด — ไม่ใช่ค่าที่เราคิดขึ้นเอง
LATEST_PRICE_COST: Final = CallCost(weight=1)


class BinanceThPrices:
    """แหล่งราคาของ Binance TH"""

    def __init__(self, transport: BinanceThTransport) -> None:
        self._transport = transport

    async def latest_price(self, symbol: Symbol) -> Price:
        """ราคาล่าสุดของคู่เทรดนั้น

        ไม่พบคู่เทรด → `VenueRejectedError(UNKNOWN_SYMBOL)` จากรหัสของตลาด
        ยังไม่มีใครเทรดคู่นั้น → `VenueUnavailableError` (plan.md ข้อ 4.1)
        """
        response = await self._transport.get(
            TRADES_ENDPOINT,
            cost=LATEST_PRICE_COST,
            params={"symbol": market_symbol(symbol), "limit": "1"},
        )
        return price_from_trades(
            symbol=symbol,
            payload=response.payload,
            received_at=response.received_at,
        )
