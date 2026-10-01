"""เก็บคำตอบจริงจาก Binance TH ลงไฟล์ — **คนสั่งเอง ไม่ใช่เทสต์** (F-35 plan.md ข้อ 5)

เจ้าของอนุมัติให้เก็บจากเครื่องนี้ได้ **เฉพาะ endpoint สาธารณะที่จำเป็นกับงาน
ไม่มี credential และไม่ส่งคำสั่งซื้อขาย** (Q-5)

สคริปต์นี้จึงทำได้แค่ `GET` ของ endpoint สาธารณะ กับกรณีที่ตลาดปฏิเสธคำขอที่อ่าน
อย่างเดียว — **ไม่พยายามทำให้ตลาดตอบ 429** (Q-5) กรณีนั้นทดสอบด้วยข้อมูลที่เขียนขึ้นเอง

เรียกใช้:

```sh
uv run python scripts/record_binance_th.py
```

**จองโควตาผ่าน `IpWeightLimiter` ก่อนทุกคำขอ ไม่ใช่ `NoRateLimit`** (Q-4)
และบันทึก header น้ำหนักที่ตลาดส่งกลับมาด้วย เพื่อให้เทสต์เทียบกับ weight ที่เราประกาศได้

**บันทึกคำตอบดิบตามที่ตลาดส่งมา ไม่ผ่านการแปลของเรา** เพราะไฟล์ที่บันทึกไว้มีหน้าที่
เป็นหลักฐานว่าตลาดตอบอะไร ถ้ามันผ่านการแปลของเราก่อน เทสต์จะเทียบโค้ดกับตัวเอง
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx

from tiewtrade.venues.binance_th import BASE_URL, IpWeightLimiter
from tiewtrade.venues.binance_th.constraints import CONSTRAINTS_COST, EXCHANGE_INFO_ENDPOINT
from tiewtrade.venues.binance_th.prices import LATEST_PRICE_COST, TRADES_ENDPOINT
from tiewtrade.venues.binance_th.transport import used_weight_of
from tiewtrade.venues.limits import CallCost

RECORDED: Final = Path(__file__).parents[1] / "tests" / "venues" / "binance_th" / "recorded"

#: header ที่บันทึกได้ — **รายการที่อนุญาต** ไม่ใช่รายการที่ห้าม
#: header อื่นพารหัสของตัวกลางและคุกกี้มาด้วย ซึ่งไม่ใช่สัญญาของตลาดและไม่ควรลง repo
RECORDED_HEADERS: Final = ("x-mbx-used-weight-1m", "x-mbx-used-weight-10s", "retry-after")

#: คู่เทรดที่เก็บไว้จาก `/exchangeInfo` — ของจริงมีห้าร้อยกว่าคู่ ประมาณ 380 KB
#: **ตัดจำนวนคู่ ไม่แก้รูปร่าง** เพราะสิ่งที่เทสต์ต้องใช้คือรูปร่างของข้อมูล
#: ความครบของรายการคู่เทรดเป็นหน้าที่ของเทสต์สัญญารายวันที่เรียกตลาดจริง
#:
#: เลือกสามคู่ที่มีเหตุผลต่างกัน: คู่ที่ระบบใช้จริง, คู่ที่ชื่อติดกันแล้วตัดได้หลายแบบ
#: (`ETHBTC` ตัดเป็น ETH+BTC หรือ E+THBTC ก็ได้), และคู่ที่ชื่อสินทรัพย์เริ่มด้วยตัวเลข
KEPT_SYMBOLS: Final = ("BTCTHB", "ETHBTC", "0GUSDT")

TIME_ENDPOINT: Final = "/time"
TIME_COST: Final = CallCost(weight=1)

#: ชื่อไฟล์ → (endpoint, ต้นทุน, พารามิเตอร์)
#: สองรายการท้ายคือกรณีที่ตลาดต้องปฏิเสธ — ทั้งคู่เป็นคำขออ่านอย่างเดียว
PLAN: Final = (
    ("server_time", TIME_ENDPOINT, TIME_COST, {}),
    ("exchange_info", EXCHANGE_INFO_ENDPOINT, CONSTRAINTS_COST, {}),
    ("trades_btc_thb", TRADES_ENDPOINT, LATEST_PRICE_COST, {"symbol": "BTCTHB", "limit": "1"}),
    (
        "rejected_unknown_symbol",
        TRADES_ENDPOINT,
        LATEST_PRICE_COST,
        {"symbol": "ZZZZNOTAPAIR", "limit": "1"},
    ),
    (
        "rejected_bad_limit",
        TRADES_ENDPOINT,
        LATEST_PRICE_COST,
        {"symbol": "BTCTHB", "limit": "ไม่ใช่ตัวเลข"},
    ),
)


async def main() -> None:
    limiter = IpWeightLimiter(clock=_now)
    async with httpx.AsyncClient() as client:
        for name, endpoint, cost, params in PLAN:
            await limiter.reserve(cost)
            response = await client.get(f"{BASE_URL}{endpoint}", params=params, timeout=10.0)
            headers = _allowed_headers(response.headers)
            _feed_back(limiter, headers)
            body = _trimmed(response.text) if endpoint == EXCHANGE_INFO_ENDPOINT else response.text
            _write(name, endpoint, params, response.status_code, headers, body)


def _write(
    name: str,
    endpoint: str,
    params: dict[str, str],
    status: int,
    headers: dict[str, str],
    body: str,
) -> None:
    destination = RECORDED / f"{name}.json"
    destination.write_text(
        json.dumps(
            {
                "endpoint": endpoint,
                "params": params,
                "status": status,
                "headers": headers,
                "body": body,
            },
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"เขียน {destination.name} สถานะ {status} ({len(body)} ตัวอักษร)")  # noqa: T201


def _feed_back(limiter: IpWeightLimiter, headers: dict[str, str]) -> None:
    """ยอดที่ตลาดนับเอง — ค่าที่สูงกว่าของเราต้องเชื่อตลาด (plan.md ข้อ 2.1)

    อ่าน header ด้วยตัวอ่านของตัวเชื่อม ไม่ประกอบชื่อ header เอง เพราะรูปแบบชื่อ
    เป็นของตลาดและต้องอยู่ที่เดียว
    """
    at = _now()
    for span, used in used_weight_of(headers).items():
        limiter.observe_used_weight(span=span, used=used, at=at)


def _allowed_headers(headers: httpx.Headers) -> dict[str, str]:
    return {name: headers[name] for name in RECORDED_HEADERS if name in headers}


def _trimmed(body: str) -> str:
    """ตัดให้เหลือไม่กี่คู่เทรด โดยไม่แตะรูปร่างของข้อมูล

    คู่ที่เลือกไว้ต้องมีอยู่จริงทุกคู่ — ขาดคู่ไหนให้ดังทันที เพราะไฟล์ที่บันทึกแบบขาด ๆ
    จะทำให้เทสต์ข้ามกรณีที่ตั้งใจทดสอบไปเงียบ ๆ
    """
    payload = json.loads(body)
    kept = [pair for pair in payload["symbols"] if pair["symbol"] in KEPT_SYMBOLS]
    missing = set(KEPT_SYMBOLS) - {pair["symbol"] for pair in kept}
    if missing:
        raise SystemExit(f"ตลาดไม่มีคู่เทรดที่ตั้งใจเก็บ: {sorted(missing)}")
    payload["symbols"] = kept
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _now() -> datetime:
    return datetime.now(UTC)


if __name__ == "__main__":
    asyncio.run(main())
