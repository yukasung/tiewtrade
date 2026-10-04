"""กระเป๋าของ Binance TH — ส่วนที่ F-35 เลื่อนไว้เพราะยังไม่มีกุญแจของผู้ใช้ (F-07)

**ตัวนี้ไม่เคยเห็น secret** มันถือ "ตัวลงลายเซ็น" ที่ `engine` สร้างให้ และตัวนั้น
มีแค่สองอย่างคือส่วนที่เปิดเผยได้กับการลงลายเซ็น (`venues/signing.py`)

**หนึ่งตัวผูกกับหนึ่งกระเป๋าตอนสร้าง** ตามสัญญาของ F-33 จึงไม่มีพารามิเตอร์ชี้กระเป๋า
ในเมธอด — ซึ่งตรงกับกฎ "หนึ่งกระเป๋า หนึ่งผู้เขียน" (`architecture.md` หัวข้อ 4)

**งานนี้ใช้มันเป็นหลักฐานว่า key ใช้งานได้จริง** (Q-2 ที่เจ้าของตัดสิน) ไม่ใช่เพื่อ
แสดงยอด — การแสดงยอดเป็นงานของ F-08 แต่สัญญาเดียวกันรับใช้ทั้งสองอย่าง
"""

from __future__ import annotations

from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.mapping import holdings_from_account
from tiewtrade.venues.binance_th.transport import BinanceThTransport
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.signing import RequestSigner
from tiewtrade.venues.wallets import WalletHoldings

#: ต้นทุนของการอ่านข้อมูลบัญชีตามเอกสารของตลาด
HOLDINGS_COST = CallCost(weight=20)


class BinanceThWallet:
    """กระเป๋าหนึ่งใบ — ทำตามสัญญา `WalletSource` ของ F-33"""

    def __init__(self, transport: BinanceThTransport, signer: RequestSigner) -> None:
        self._transport = transport
        self._signer = signer

    async def holdings(self) -> WalletHoldings:
        """ยอดทั้งกระเป๋า ณ เวลาที่อ่านมา

        คำรับรองใช้ไม่ได้ → `VenueCredentialRejectedError` ซึ่งมาจากการแปลรหัส
        ของตลาดใน `failures.py` ไม่ใช่การเดาจากข้อความ
        """
        response = await self._transport.signed_get(
            Endpoint.ACCOUNT,
            signer=self._signer,
            cost=HOLDINGS_COST,
        )
        return holdings_from_account(
            payload=response.payload,
            received_at=response.received_at,
        )
