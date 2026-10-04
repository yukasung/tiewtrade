"""ของที่ lifespan เตรียมไว้ให้คำขอใช้ — **ที่เดียว**

เดิมแต่ละโมดูลของเส้นทางเขียนตัวอ่าน `app.state` ของตัวเอง พอถึงโมดูลที่สาม
มันกลายเป็นสามชุดที่ต้องแก้ให้ตรงกันทุกครั้งที่ชื่อใน `app.state` เปลี่ยน —
`AGENTS.md` หัวข้อ "ใช้ของเดิมซ้ำ" สั่งให้ย้ายมาไว้ที่เดียวเมื่อถึงครั้งที่สาม

**ไม่มีค่าเริ่มต้น ไม่มีการสร้างของให้เอง** — ของที่ `lifespan` ไม่ได้เตรียมไว้
ถือว่าแอปตั้งค่าผิด และต้องดังทันที ไม่ใช่สร้าง engine ใหม่เงียบ ๆ ตอนมีคำขอเข้ามา
"""

from __future__ import annotations

from typing import Final

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.auth import key_of
from tiewtrade.infra.crypto import KeySource
from tiewtrade.infra.db import DatabaseRole

#: ชื่อที่ `lifespan` ใช้เก็บ engine ของแต่ละบทบาทใน `app.state`
_ENGINE_ATTRIBUTE: Final[dict[DatabaseRole, str]] = {
    DatabaseRole.API: "api_engine",
    DatabaseRole.AUTH: "auth_engine",
}

#: ที่มาของคำขอที่อ่านไม่ได้ — นับเป็นแหล่งเดียวกันทั้งหมด ไม่ใช่ข้ามการนับ
_UNKNOWN_CLIENT: Final[str] = "unknown"


def engine_for(request: Request, role: DatabaseRole) -> AsyncEngine:
    """engine ของบทบาทนั้น ตามที่ lifespan ของแอปสร้างไว้

    **เส้นทางที่แตะข้อมูลเข้าสู่ระบบต้องขอบทบาท `AUTH` เท่านั้น** การเลือกบทบาท
    จึงเขียนไว้ที่จุดเรียกให้เห็นชัด ไม่ซ่อนอยู่ในชื่อฟังก์ชันสองตัวที่ต่างกันทีละคำ
    """
    attribute = _ENGINE_ATTRIBUTE[role]
    engine = getattr(request.app.state, attribute, None)
    if not isinstance(engine, AsyncEngine):  # pragma: no cover - ตั้งค่าแอปผิด
        raise RuntimeError(f"แอปยังไม่ได้ตั้ง engine ของบทบาท {role.role_name}")
    return engine


def totp_keys(request: Request) -> KeySource:
    """กุญแจของ TOTP ที่ lifespan อ่านมาตอนเปิดแอป

    อ่านตอนเปิดแอปเพื่อให้ **กุญแจไม่ครบ = กระบวนการไม่เริ่ม** ไม่ใช่ล้มตอนมีผู้ใช้
    คนแรกมาเปิด TOTP (F-06 validation V-10)
    """
    keys = getattr(request.app.state, "totp_keys", None)
    if not isinstance(keys, KeySource):  # pragma: no cover - ตั้งค่าแอปผิด
        raise RuntimeError("แอปยังไม่ได้อ่านกุญแจของ TOTP")
    return keys


def venue_keys(request: Request) -> KeySource:
    """กุญแจของ API key ที่ lifespan อ่านมาตอนเปิดแอป (F-07 RQ-4)

    **คนละดอกกับกุญแจของ TOTP** — `tech-stack.md` หัวข้อ 8 ให้ `engine` เท่านั้น
    ที่เปิดผนึกความลับของตลาดได้ ฝั่งนี้จึงมีไว้ **ปิดผนึกอย่างเดียว**
    """
    keys = getattr(request.app.state, "venue_keys", None)
    if not isinstance(keys, KeySource):  # pragma: no cover - ตั้งค่าแอปผิด
        raise RuntimeError("แอปยังไม่ได้อ่านกุญแจของ API key")
    return keys


def client_key(request: Request) -> str:
    """แฮชของที่มาคำขอ — ใช้เป็นคีย์ของถังต่อ IP

    คำขอที่อ่านที่มาไม่ได้ **ยังถูกนับ** ภายใต้แหล่งเดียวกัน ไม่ใช่ถูกข้าม
    มิฉะนั้นการทำให้ที่มาอ่านไม่ได้จะกลายเป็นทางหลบการคุมอัตรา
    """
    client = request.client
    return key_of(client.host if client is not None else _UNKNOWN_CLIENT)
