"""เครื่องมือร่วมของเทสต์ตัวเชื่อม Binance TH

**ปิด socket ทั้งกระบวนการสำหรับเทสต์ในโฟลเดอร์นี้** (V-7) เทสต์ปกติต้องไม่เรียก
ตลาดจริงแม้แต่ครั้งเดียว — ถ้าเผลอเขียนเทสต์ที่เรียกออกไป เทสต์นั้นจะพังทันที
ไม่ใช่ช้าลงหรือแดงเป็นครั้งคราวตามคุณภาพเน็ตของคนที่รัน

เทสต์สัญญาที่เรียกตลาดจริงอยู่ใน `tests/venue_contract/` ซึ่งอยู่นอกขอบเขตของการปิดนี้
"""

from __future__ import annotations

import json
import socket
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import httpx
import pytest

from tiewtrade.venues.binance_th import BinanceThTransport
from tiewtrade.venues.limits import CallCost, RateLimitGuard

RECORDED: Final = Path(__file__).parent / "recorded"
#: คำตอบที่แต่งจากรูปร่างจริงของ endpoint ที่ต้องลงลายเซ็น (F-07)
SHAPES: Final = Path(__file__).parent / "shapes"

#: เวลาอ้างอิงของเทสต์ — ค่าคงที่เพื่อให้ผลไม่ขึ้นกับว่ารันตอนไหน
START: Final = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """ห้ามต่อออกไปข้างนอกระหว่างเทสต์ในโฟลเดอร์นี้

    ปิดที่ **การเชื่อมต่อและการค้นชื่อโฮสต์** ไม่ใช่ปิดการสร้าง socket ทั้งหมด
    เพราะ event loop ของ asyncio สร้าง socket คู่ไว้ปลุกตัวเองอยู่ข้างใน
    ถ้าปิดกว้างกว่านี้ เทสต์จะพังเพราะ loop สร้างไม่ได้ ซึ่งไม่ได้พิสูจน์อะไรเลย
    """

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("เทสต์ปกติต้องไม่เรียกเครือข่ายออกไปจริง")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


class FakeClock:
    """นาฬิกาที่เทสต์เดินเองได้ — ตัวกั้นอัตราไม่เคยอ่านนาฬิกาจริง (V-29)"""

    def __init__(self, now: datetime = START) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, amount: timedelta) -> None:
        self.now += amount


class RecordingGuard:
    """ตัวกั้นที่จดลำดับการจอง — ใช้พิสูจน์ว่าจองก่อนเรียกจริง (V-27)"""

    def __init__(self) -> None:
        self.reserved: list[CallCost] = []

    async def reserve(self, cost: CallCost) -> None:
        self.reserved.append(cost)


def recorded(name: str) -> dict[str, object]:
    """คำตอบจริงที่บันทึกไว้หนึ่งไฟล์"""
    loaded = json.loads((RECORDED / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def recorded_body(name: str) -> str:
    body = recorded(name)["body"]
    assert isinstance(body, str)
    return body


def shaped_body(name: str) -> str:
    """คำตอบที่เราแต่งขึ้นจาก **รูปร่าง** ที่เรียกจริงแล้วเห็น (`shapes/README.md`)

    แยกจาก `recorded_body` เพราะสองอย่างนี้มีกฎคนละชุด: `recorded/` เป็นคำตอบจริง
    จาก endpoint สาธารณะและมีด่านของตัวเอง ส่วนที่นี่คือรูปร่างของ endpoint
    ที่ต้องลงลายเซ็น ซึ่งบันทึกคำตอบจริงไม่ได้เพราะมันคือยอดเงินของเจ้าของ
    """
    loaded = json.loads((SHAPES / f"{name}.json").read_text(encoding="utf-8"))
    body = loaded["body"]
    assert isinstance(body, str)
    return body


def transport_for(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    guard: RateLimitGuard | None = None,
    clock: Callable[[], datetime] | None = None,
    timeout: timedelta = timedelta(seconds=5),
) -> BinanceThTransport:
    """ตัวเชื่อมที่ตอบด้วย handler ที่เทสต์เขียน — ไม่มี socket เข้ามาเกี่ยวเลย"""
    return BinanceThTransport(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        guard=guard if guard is not None else RecordingGuard(),
        clock=clock if clock is not None else FakeClock(),
        timeout=timeout,
    )


def replying(
    body: str,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """handler ที่ตอบเหมือนกันทุกครั้ง"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body, headers=headers or {})

    return handler


def requests_to(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    """handler ที่จดคำขอทุกคำขอไว้ — ใช้นับจำนวนครั้งที่เรียก (V-26, V-35)"""
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return recording, seen
