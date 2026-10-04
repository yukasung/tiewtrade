"""เทสต์สัญญากับตลาดจริง — **ไม่อยู่ในเงื่อนไข merge** (F-35 plan.md ข้อ 6)

รันโดยงาน CI `venue-contract` ที่มีตารางรายวันและกดรันเองได้
เทสต์ปกติไม่รันไฟล์นี้ เพราะมีเครื่องหมาย `venue_contract` ที่ `pyproject.toml` ตัดออก

**คำขอทั้งหมดในไฟล์นี้เป็นการอ่าน endpoint สาธารณะ ไม่มี credential และไม่มีคำสั่ง
ซื้อขาย** (Q-5) และ **จองโควตาผ่าน `IpWeightLimiter` ทุกคำขอ ไม่ใช่ `NoRateLimit`** (Q-4)

สามสถานะ: ผ่าน · ข้ามเพราะเข้าถึงตลาดไม่ได้ · แดงเพราะสัญญาไม่ตรง
การแยกทำโดย `verdict.py` ซึ่งมีเทสต์ของตัวเองในชุดปกติ
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
import pytest

from tests.venue_contract.verdict import ContractReport, Verdict, verdict_for, weight_verdict
from tiewtrade.venues.binance_th import BinanceThConstraints, IpWeightLimiter
from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.mapping import price_from_trades
from tiewtrade.venues.binance_th.prices import LATEST_PRICE_COST
from tiewtrade.venues.binance_th.transport import BinanceThTransport
from tiewtrade.venues.errors import VenueError
from tiewtrade.venues.symbols import Symbol

pytestmark = pytest.mark.venue_contract

#: คู่เทรดที่ระบบใช้จริงและมีสภาพคล่อง — ใช้ตรวจสัญญา ไม่ใช่ตรวจราคา
BTC_THB: Final = Symbol(base="BTC", quote="THB")

#: หน้าต่างที่ตลาดรายงาน header น้ำหนักกลับมา
MINUTE: Final = timedelta(minutes=1)

#: จำนวนคำขอที่ใช้วัด weight — ต้องได้ผลต่างสามรอบจึงสรุปได้ (plan.md ข้อ 2.1)
WEIGHT_SAMPLES: Final = 4

#: ที่เก็บผลลัพธ์ที่งาน CI แนบไว้กับงาน (artifact)
OUTPUT_DIR: Final = Path(os.environ.get("VENUE_CONTRACT_OUTPUT", ".venue-contract"))


async def test_the_market_contract_still_holds() -> None:
    """สัญญาของตลาดยังเหมือนที่ตัวเชื่อมเข้าใจไว้หรือไม่"""
    report = ContractReport()
    captured: dict[str, object] = {}
    limiter = IpWeightLimiter(clock=_now)

    async with httpx.AsyncClient() as client:
        transport = BinanceThTransport(
            client=client, guard=limiter, clock=_now, timeout=timedelta(seconds=15)
        )
        await _check_price(transport, report, captured)
        await _check_constraints(transport, report, captured)
        await _check_weight(transport, report, captured)

    _publish(report, captured)

    if report.worst is Verdict.FAILED:
        pytest.fail(report.as_markdown())
    if report.worst is Verdict.SKIPPED:
        pytest.skip(report.as_markdown())


async def _check_price(
    transport: BinanceThTransport, report: ContractReport, captured: dict[str, object]
) -> None:
    """ราคาล่าสุดยังอ่านได้ และฟิลด์ที่เราต้องใช้ยังอยู่

    ตรวจฟิลด์ทีละตัวเองที่นี่ เพราะชนิดข้อผิดพลาดไม่พาชื่อฟิลด์มาด้วย (F-33 RQ-8)
    และผู้ดูแลต้องเห็นชื่อฟิลด์ที่หายในสรุป (plan.md ข้อ 6 ข้อ 2)

    **แปลคำตอบที่รับมาแล้ว ไม่ยิงคำขอที่สอง** คำขอที่สองที่อยู่นอกการดักจะทำให้
    งานล้มก่อนเขียนสรุปเมื่อตลาดช้าหรือจำกัดอัตรา ซึ่งเป็นสถานะ "ข้าม" ไม่ใช่ "แดง"
    """
    try:
        response = await transport.get(
            Endpoint.TRADES,
            cost=LATEST_PRICE_COST,
            params={"symbol": "BTCTHB", "limit": "1"},
        )
        captured["trades"] = response.payload

        # รายการว่างต้องไม่ถูกตรวจฟิลด์ เพราะ array ว่างคือคำตอบที่ถูกตามสัญญา
        # ของตลาด และ `price_from_trades` แปลเป็น `VenueUnavailableError`
        # ซึ่งตัวตัดสินจัดเป็น "ข้าม" ตาม V-15.3
        missing = _missing_fields(response.payload, ("price", "time"))
        if missing:
            report.record("ราคาล่าสุด", Verdict.FAILED, f"ฟิลด์ที่หายไป: {', '.join(missing)}")
            return

        price = price_from_trades(
            symbol=BTC_THB,
            payload=response.payload,
            received_at=response.received_at,
        )
    except VenueError as error:
        report.record("ราคาล่าสุด", verdict_for(error), type(error).__name__)
        return

    report.record("ราคาล่าสุด", Verdict.PASSED, f"อ่านราคาและเวลาของตลาดได้ ({price.symbol})")


async def _check_constraints(
    transport: BinanceThTransport, report: ContractReport, captured: dict[str, object]
) -> None:
    """ข้อจำกัดของคู่ที่ระบบใช้จริงยังอ่านได้ครบสามข้อ"""
    constraints = BinanceThConstraints(transport, ttl=timedelta(minutes=5), clock=_now)
    try:
        found = await constraints.constraints(BTC_THB)
    except VenueError as error:
        report.record("ข้อจำกัดของเหรียญ", verdict_for(error), type(error).__name__)
        return

    captured["constraints"] = {
        "minimum_quantity": found.minimum_quantity.as_parts(),
        "quantity_step": found.quantity_step.as_parts(),
        "minimum_notional": found.minimum_notional.as_parts(),
    }
    report.record("ข้อจำกัดของเหรียญ", Verdict.PASSED, "อ่าน LOT_SIZE และ MIN_NOTIONAL ได้ครบ")


async def _check_weight(
    transport: BinanceThTransport, report: ContractReport, captured: dict[str, object]
) -> None:
    """weight ที่เราประกาศตรงกับที่ตลาดนับหรือไม่

    เทียบ **ผลต่างของยอดสะสม** ระหว่างคำขอที่ต้นทุนเท่ากัน ไม่ใช่เทียบยอดสะสมตรง ๆ
    เพราะ header เป็นยอดของ IP ในหน้าต่างนั้น ไม่ใช่ต้นทุนของคำขอเดียว
    """
    readings: list[int | None] = []
    for _ in range(WEIGHT_SAMPLES):
        try:
            response = await transport.get(
                Endpoint.TRADES,
                cost=LATEST_PRICE_COST,
                params={"symbol": "BTCTHB", "limit": "1"},
            )
        except VenueError as error:
            report.record("weight ของการอ่านราคา", verdict_for(error), type(error).__name__)
            return
        readings.append(response.used_weight.get(MINUTE))

    captured["used_weight"] = readings
    verdict, note = weight_verdict(readings, declared=LATEST_PRICE_COST.weight)
    report.record("weight ของการอ่านราคา", verdict, note)


def _missing_fields(payload: object, required: tuple[str, ...]) -> list[str]:
    """ฟิลด์ที่ต้องมีแต่ไม่มีในรายการล่าสุดของคำตอบ

    **รายการว่างไม่ใช่ฟิลด์หาย** คู่เทรดที่ยังไม่มีใครเทรดคืน array ว่างได้ตามสัญญา
    ของตลาด ปล่อยให้การแปลเป็นผู้ตัดสิน ซึ่งจะได้ `VenueUnavailableError`
    แล้วตัวตัดสินจัดเป็น "ข้าม" ไม่ใช่ "แดง" (V-15.3)
    """
    if not isinstance(payload, list):
        return ["คำตอบไม่ใช่รายการซื้อขาย"]
    if not payload:
        return []
    latest = payload[-1]
    if not isinstance(latest, dict):
        return ["รายการซื้อขายไม่ใช่วัตถุ"]
    return [field for field in required if field not in latest]


def _publish(report: ContractReport, captured: dict[str, object]) -> None:
    """สามทางที่ผู้ดูแลเห็นผลโดยไม่ต้องอ่าน log (plan.md ข้อ 6 ข้อ 2)"""
    summary = report.as_markdown()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "summary.md").write_text(summary, encoding="utf-8")
    (OUTPUT_DIR / "responses.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with Path(step_summary).open("a", encoding="utf-8") as handle:
            handle.write(summary)


def _now() -> datetime:
    return datetime.now(UTC)
