"""ของกลางของเทสต์ชั้น API key — กุญแจของงานนี้และผู้ใช้ที่มีตัวตนจริง"""

from __future__ import annotations

import base64

import pytest

from tiewtrade.infra.crypto import KEY_BYTES, KeyPurpose, KeySource

#: กุญแจของเทสต์ — **ค่าคงที่ที่ไม่มีความลับ** และต่างจากกุญแจของ TOTP โดยตั้งใจ
#: เพื่อให้เทสต์ที่พิสูจน์ว่าสองงานใช้กุญแจคนละดอกมีของจริงให้เทียบ
TEST_VENUE_KEY = "1:" + base64.b64encode(b"V" * KEY_BYTES).decode("ascii")


@pytest.fixture(autouse=True)
def _venue_sealing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KeyPurpose.VENUE_API_SECRET.environment_variable, TEST_VENUE_KEY)


@pytest.fixture
def venue_keys(_venue_sealing_key: None) -> KeySource:
    return KeySource.from_environment(KeyPurpose.VENUE_API_SECRET)
