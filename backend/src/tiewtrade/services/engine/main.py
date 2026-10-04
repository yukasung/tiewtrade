"""จุดเริ่มของ `engine` — วนเรียกรอบตรวจ API key (F-07 `plan.md` ข้อ 7.1)

**ที่นี่มีแค่การวนกับการนอน** ตรรกะทั้งหมดอยู่ใน `verification.py` ซึ่งทดสอบได้
โดยไม่ต้องรอเวลาจริงและไม่ต้องมี loop (`architecture.md` หัวข้อ 2)

**ยังไม่มีตัวตั้งเวลาให้ process นี้รันบนเครื่องจริง** — การนำขึ้นเครื่องเป็นงาน
**F-31** เหมือนที่งานเก็บกวาดของ F-06 ฝากไว้ · วันนี้รันด้วยมือได้ และ Compose
ยังไม่มี service ของ engine
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime, timedelta
from typing import Final

import httpx

from tiewtrade.infra.crypto import KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.engine.verification import RoundSummary, run_round
from tiewtrade.venues import RequestSigner, WalletSource, live_wallet_source

_LOGGER = logging.getLogger(__name__)

#: ช่วงเวลาระหว่างรอบ — จังหวะของแต่ละแถวมาจาก `next_attempt_at` ของมันเอง
#: ค่านี้แค่บอกว่า process ตื่นมาดูบ่อยแค่ไหน
ROUND_INTERVAL: Final = timedelta(seconds=30)

#: เวลารอคำตอบจากตลาดหนึ่งคำขอ — **ต้องสั้นกว่าอายุการจองมาก** (`claims.CLAIM_LEASE`)
MARKET_TIMEOUT: Final = timedelta(seconds=10)


def _worker_name() -> str:
    """ชื่อที่ใช้จองแถว — ต้องต่างกันระหว่าง process ที่รันพร้อมกัน"""
    return f"{socket.gethostname()}:{os.getpid()}"


def _wallet_factory(client: httpx.AsyncClient) -> object:
    """ตัวสร้างกระเป๋าจากคำรับรองหนึ่งชุด — **ที่นี่ไม่รู้ว่าเป็นตลาดไหน**"""

    def build(signer: RequestSigner) -> WalletSource:
        return live_wallet_source(signer=signer, client=client, clock=_now, timeout=MARKET_TIMEOUT)

    return build


async def serve() -> None:
    """วนตรวจไปเรื่อย ๆ จนกว่าจะถูกสั่งหยุด

    **กุญแจอ่านตอนเริ่ม** — กุญแจไม่ครบแปลว่ากระบวนการไม่เริ่ม ไม่ใช่ล้มตอนเจอ
    แถวแรกที่ต้องเปิดผนึก (แบบแผนเดียวกับ F-06)
    """
    keys = KeySource.from_environment(KeyPurpose.VENUE_API_SECRET)
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan_engine = create_engine_for(DatabaseRole.ENGINE_SCAN)
    worker = _worker_name()

    async with httpx.AsyncClient() as client:
        _LOGGER.info("engine เริ่มทำงานในชื่อ %s", worker)
        while True:
            summary = await run_round(
                engine=engine,
                scan_engine=scan_engine,
                keys=keys,
                wallet_for=_wallet_factory(client),  # type: ignore[arg-type]
                worker=worker,
            )
            if summary != RoundSummary():
                _LOGGER.info("รอบตรวจ API key: %s", summary)
            await asyncio.sleep(ROUND_INTERVAL.total_seconds())


def _now() -> datetime:
    """นาฬิกาของ process นี้ — ส่งเข้าไปให้ชั้นที่ต้องใช้ ไม่ใช่ให้มันไปหาเอง"""
    return datetime.now(UTC)


def main() -> int:
    """รัน engine จนกว่าจะถูกขัดจังหวะ"""
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        _LOGGER.info("engine หยุดตามคำสั่ง")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
