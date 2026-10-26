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
from uuid import UUID, uuid4

import httpx

from tiewtrade.infra.crypto import KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import presented_session
from tiewtrade.infra.platform import record_protocol_heartbeat
from tiewtrade.services.engine.catalog import activate_ready_symbols
from tiewtrade.services.engine.verification import RoundSummary, WalletFactory, run_round
from tiewtrade.venues import (
    live_execution_capability_source,
    live_wallet_factory,
    public_rate_limit_guard,
)

_LOGGER = logging.getLogger(__name__)

#: ช่วงเวลาระหว่างรอบ — จังหวะของแต่ละแถวมาจาก `next_attempt_at` ของมันเอง
#: ค่านี้แค่บอกว่า process ตื่นมาดูบ่อยแค่ไหน
ROUND_INTERVAL: Final = timedelta(seconds=30)

#: เวลารอคำตอบจากตลาดหนึ่งคำขอ — **ต้องสั้นกว่าอายุการจองมาก** (`claims.CLAIM_LEASE`)
MARKET_TIMEOUT: Final = timedelta(seconds=10)


def _worker_name() -> str:
    """ชื่อที่ใช้จองแถว — ต้องต่างกันระหว่าง process ที่รันพร้อมกัน"""
    return f"{socket.gethostname()}:{os.getpid()}"


def _wallet_factory(client: httpx.AsyncClient) -> WalletFactory:
    """สร้างตัวประกอบ wallet หนึ่งครั้งต่อ process โดยไม่เอ่ยชื่อตลาด."""
    return live_wallet_factory(client=client, clock=_now, timeout=MARKET_TIMEOUT)


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
        wallet_for = _wallet_factory(client)
        capability_source = live_execution_capability_source(
            client=client,
            clock=_now,
            timeout=MARKET_TIMEOUT,
            guard=public_rate_limit_guard(clock=_now),
        )
        generation_text = os.environ.get("TIEWTRADE_CATALOG_DEPLOYMENT_GENERATION")
        generation = None if not generation_text else UUID(generation_text)
        instance_id = uuid4()
        _LOGGER.info("engine เริ่มทำงานในชื่อ %s", worker)
        while True:
            if generation is not None:
                now = _now()
                async with presented_session(engine, role=DatabaseRole.ENGINE) as session:
                    await record_protocol_heartbeat(
                        session,
                        process_kind="ENGINE",
                        instance_id=instance_id,
                        protocol_version=1,
                        deployment_generation=generation,
                        lease_expires_at=now + ROUND_INTERVAL * 3,
                    )
            summary = await run_round(
                engine=engine,
                scan_engine=scan_engine,
                keys=keys,
                wallet_for=wallet_for,
                worker=worker,
            )
            if summary != RoundSummary():
                _LOGGER.info("รอบตรวจ API key: %s", summary)
            activated = await activate_ready_symbols(engine, capability_source, clock=_now)
            if activated:
                _LOGGER.info("activated supported symbols: %s", activated)
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
