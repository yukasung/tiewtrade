"""ของกลางของเทสต์ทั้งชุด

**กุญแจปิดผนึกตั้งให้ทุกเทสต์** เพราะแอปอ่านกุญแจตอนเปิด (F-06 validation V-10)
ฉะนั้นเทสต์ใดที่เปิดแอปก็ต้องมีกุญแจ — ตั้งเหมือนตั้งค่าอื่น **ไม่ใช่ปิดการตรวจ**
เพราะการปิดจะทำให้ไม่ได้ทดสอบของจริง (เหตุผลเดียวกับที่เทสต์ของ F-05 ล้างสภาพ
ของตัวนับแทนการปิดกฎ)
"""

from __future__ import annotations

import base64
from typing import Final

import pytest

from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose

#: กุญแจของเทสต์ — **ค่าคงที่ที่ไม่มีความลับ** และใช้ได้เฉพาะในเทสต์
TEST_SEALING_KEY: Final[str] = "1:" + base64.b64encode(b"T" * KEY_BYTES).decode("ascii")


@pytest.fixture(autouse=True)
def _sealing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """ตั้งกุญแจปิดผนึกของ TOTP ให้ทุกเทสต์

    เทสต์ที่ต้องพิสูจน์ว่า **ไม่มีกุญแจแล้วแอปไม่เริ่ม** ลบค่านี้เองในเทสต์ของมัน
    """
    monkeypatch.setenv(KeyPurpose.TOTP_SECRET.environment_variable, TEST_SEALING_KEY)
