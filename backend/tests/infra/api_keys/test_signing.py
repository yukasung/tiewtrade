"""ตัวลงลายเซ็น — V-36 และข้อที่ว่าความลับไม่หลุดออกจากตัวมันเอง

**ค่าที่ใช้เทียบมาจากนอก implementation ของเรา** (เวกเตอร์ที่เผยแพร่ของ HMAC-SHA256)
ไม่ใช่ค่าที่ได้จากการรันโค้ดของเราเองแล้วจดไว้ — การจดค่าจากโค้ดตัวเองคือการยืนยัน
ว่าโค้ดทำสิ่งที่โค้ดทำ ซึ่งไม่ได้พิสูจน์อะไร
"""

from __future__ import annotations

import pytest

from tiewtrade.infra.api_keys import HmacRequestSigner

#: เวกเตอร์ที่รู้คำตอบอยู่แล้วของ HMAC-SHA256 — กุญแจ `key` กับประโยคสุนัขจิ้งจอก
#: ค่านี้เผยแพร่อยู่ทั่วไปและคำนวณซ้ำได้ด้วยเครื่องมืออื่น เช่น `openssl dgst -sha256 -hmac`
KNOWN_KEY = b"key"
KNOWN_MESSAGE = "The quick brown fox jumps over the lazy dog"
KNOWN_SIGNATURE = "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8"


def test_the_signature_matches_a_value_computed_elsewhere() -> None:
    """V-36 — ลายเซ็นตรงกับค่าที่หามาจากนอกโค้ดของเรา"""
    signer = HmacRequestSigner(public_identifier="PUBLIC", secret=KNOWN_KEY)

    assert signer.sign(KNOWN_MESSAGE) == KNOWN_SIGNATURE


def test_signing_is_stable() -> None:
    """V-38 — ข้อความเดิมให้ลายเซ็นเดิมทุกครั้ง"""
    signer = HmacRequestSigner(public_identifier="PUBLIC", secret=KNOWN_KEY)

    assert signer.sign(KNOWN_MESSAGE) == signer.sign(KNOWN_MESSAGE)


def test_a_different_message_signs_differently() -> None:
    """เปลี่ยนข้อความแม้ตัวเดียวแล้วลายเซ็นต้องเปลี่ยน"""
    signer = HmacRequestSigner(public_identifier="PUBLIC", secret=KNOWN_KEY)

    assert signer.sign(KNOWN_MESSAGE) != signer.sign(KNOWN_MESSAGE + " ")


def test_nothing_in_the_signer_hands_the_secret_back() -> None:
    """RQ-9.2 — เขียน `repr()` ของมันลง log แล้วต้องไม่ได้ความลับหรือคำรับรอง"""
    signer = HmacRequestSigner(public_identifier="PUBLIC", secret=b"super-secret")

    printed = repr(signer)
    assert "super-secret" not in printed
    assert "PUBLIC" not in printed
    # และไม่มีช่องสาธารณะไหนคืนความลับ
    assert not any("secret" in name.lower() for name in dir(signer) if not name.startswith("_"))


@pytest.mark.parametrize(
    ("public_identifier", "secret"),
    [("", b"secret"), ("PUBLIC", b"")],
)
def test_an_incomplete_credential_is_refused(public_identifier: str, secret: bytes) -> None:
    """คำรับรองที่ไม่ครบต้องดังตอนสร้าง ไม่ใช่ตอนตลาดปฏิเสธ"""
    with pytest.raises(ValueError):
        HmacRequestSigner(public_identifier=public_identifier, secret=secret)
