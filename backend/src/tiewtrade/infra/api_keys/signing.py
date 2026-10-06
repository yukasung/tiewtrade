"""ตัวลงลายเซ็นที่ **ถือ secret** — อยู่ใน `infra` ไม่ใช่ใน `venues` (F-07 `plan.md` ข้อ 6.1)

ตัวที่ลงลายเซ็นได้คือตัวที่ถือความลับ ฉะนั้นถ้ามันอยู่ใน `venues` ก็เท่ากับ `venues`
เห็นค่าดิบ ซึ่งขัดกับคำตัดสิน Q-2 ที่เจ้าของอนุมัติ · `venues` รู้แค่ว่า **ข้อความไหน
ต้องถูกลงลายเซ็น** และ **ชื่อ header ของตลาด** ส่วนความลับไม่เคยข้ามเส้นเข้าไป

**ค่าที่ถืออยู่ไม่มีทางอ่านกลับ** — ไม่มี property ไม่มี `__repr__` ที่พาค่าออกมา
และการเขียน `repr()` ของมันลง log จึงไม่ได้อะไรเลย
"""

from __future__ import annotations

import hashlib
import hmac


class HmacRequestSigner:
    """ลงลายเซ็นด้วย HMAC-SHA256 ตามที่ตลาดกำหนด

    รับ secret เป็น `bytes` ที่ `engine` เพิ่งเปิดผนึกมา และ **ไม่เก็บสำเนาอื่นใด**
    """

    __slots__ = ("_public_identifier", "_secret")

    def __init__(self, *, public_identifier: str, secret: bytes) -> None:
        if not public_identifier:
            raise ValueError("ต้องมีส่วนที่เปิดเผยได้ของคำรับรอง")
        if not secret:
            raise ValueError("ต้องมีความลับสำหรับลงลายเซ็น")
        self._public_identifier = public_identifier
        self._secret = secret

    @property
    def public_identifier(self) -> str:
        """ส่วนที่เปิดเผยได้ — ตลาดใช้บอกว่าเป็นใคร"""
        return self._public_identifier

    def sign(self, payload: str) -> str:
        """ลายเซ็นของข้อความนี้ในรูปเลขฐานสิบหก"""
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()

    def __repr__(self) -> str:
        """**ไม่พาความลับและไม่พาคำรับรองออกมา** — ค่าทั้งคู่ห้ามลง log (RQ-9.2)"""
        return f"{type(self).__name__}(ซ่อนไว้)"
