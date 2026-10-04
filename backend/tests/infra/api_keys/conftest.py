"""ของกลางของเทสต์ชั้น API key — กุญแจของงานนี้และผู้ใช้ที่มีตัวตนจริง"""

from __future__ import annotations

import pytest

from tiewtrade.infra.crypto import KeyPurpose, KeySource


#: กุญแจของเทสต์ — **ค่าคงที่ที่ไม่มีความลับ** และต่างจากกุญแจของ TOTP โดยตั้งใจ
#: เพื่อให้เทสต์ที่พิสูจน์ว่าสองงานใช้กุญแจคนละดอกมีของจริงให้เทียบ
@pytest.fixture
def venue_keys() -> KeySource:
    return KeySource.from_environment(KeyPurpose.VENUE_API_SECRET)
