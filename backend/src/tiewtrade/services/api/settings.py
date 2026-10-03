"""ค่าตั้งของเส้นทางยืนยันตัวตน (F-05)

**ค่าเริ่มต้นของการเปิดให้สมัครคือปิด** (requirements.md Q-1) — `mission.md` หัวข้อ 2
ตัดสินไว้แล้วว่าผลิตภัณฑ์เปิดให้คนทั่วไปสมัครเอง งานนี้จึงสร้างความสามารถนั้น
ส่วนการ **เปิดใช้งาน** ยังติด NC-11 (กฎหมายไทย) จึงต้องเปิดด้วยการตั้งค่าโดยเจตนา
หลักเดียวกับ "Live ต้องไม่เปิดเองโดยปริยาย"
"""

from __future__ import annotations

import os
from typing import Final

#: ชื่อ cookie — `httpOnly` ตัวหนึ่งสำหรับ session และตัวที่อ่านได้สำหรับโทเคนกัน CSRF
SESSION_COOKIE: Final[str] = "tiewtrade_session"
CSRF_COOKIE: Final[str] = "tiewtrade_csrf"
CSRF_HEADER: Final[str] = "X-CSRF-Token"

_SIGNUP_VARIABLE: Final[str] = "TIEWTRADE_SIGNUP_OPEN"
_COOKIE_SECURE_VARIABLE: Final[str] = "TIEWTRADE_COOKIE_SECURE"


def signup_open() -> bool:
    """เปิดให้สมัครหรือไม่ — **ไม่ตั้งค่าคือปิด**"""
    return os.environ.get(_SIGNUP_VARIABLE, "") == "1"


def cookie_secure() -> bool:
    """ตั้งธง `Secure` บน cookie หรือไม่ — **ไม่ตั้งค่าคือตั้งธง**

    ปิดได้เฉพาะตอนพัฒนาและตอนรันเทสต์ที่ใช้ `http://` ซึ่งเบราว์เซอร์และไคลเอนต์
    จะไม่ส่ง cookie ที่มีธงนี้กลับมา — บนเครื่องจริงห้ามปิด
    """
    return os.environ.get(_COOKIE_SECURE_VARIABLE, "1") != "0"
