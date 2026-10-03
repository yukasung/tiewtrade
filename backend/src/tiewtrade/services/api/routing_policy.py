"""เส้นทางไหนเปิดสาธารณะ และเส้นทางไหนต่ออายุ session (F-05 plan.md ข้อ 2)

**ค่าเริ่มต้นคือปฏิเสธ** — เส้นทางที่ไม่อยู่ใน `PUBLIC_ROUTES` ต้องมี session
และ **ค่าเริ่มต้นคือไม่ต่ออายุ** — เส้นทางที่เป็นการกระทำของผู้ใช้ต้องประกาศตัวเอง
ใน `RENEWING_ROUTES` เท่านั้น

เขียนเป็นรายการที่เห็นได้ในรีวิว **และมีเทสต์ที่เดินทุกเส้นทางใน `app.routes`**
เพื่อให้การเพิ่ม endpoint ใหม่โดยไม่คิดเรื่องสิทธิ์ทำให้เทสต์แดง ไม่ใช่เงียบ
(validation V-16, V-17, V-21.1)
"""

from __future__ import annotations

from typing import Final

#: เส้นทางที่เรียกได้โดยไม่ต้องมี session — **สี่เส้นทางเท่านั้น**
PUBLIC_ROUTES: Final[frozenset[str]] = frozenset(
    {
        "/health",
        "/auth/csrf",
        "/auth/register",
        "/auth/login",
    }
)

#: เส้นทางที่นับว่าเป็น "การใช้งาน" จึงเลื่อนเวลาหมดอายุ
#:
#: **การ poll ราคาไม่อยู่ในรายการนี้** (Q-2) — เส้นทางอ่านข้อมูลที่หน้าเว็บเรียกเป็นรอบ ๆ
#: ต้องไม่ต่ออายุ มิฉะนั้นเปิดหน้าจอทิ้งไว้เท่ากับ session ไม่หมดอายุเลย
RENEWING_ROUTES: Final[frozenset[str]] = frozenset(
    {
        "/auth/logout",
        "/auth/logout-all",
        "/auth/password",
    }
)


def is_public(path: str) -> bool:
    """เส้นทางนี้เรียกได้โดยไม่ต้องมี session หรือไม่"""
    return path in PUBLIC_ROUTES


def renews_session(path: str) -> bool:
    """คำขอที่เส้นทางนี้รับ นับเป็นการใช้งานหรือไม่"""
    return path in RENEWING_ROUTES
