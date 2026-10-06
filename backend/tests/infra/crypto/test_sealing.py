"""การปิดผนึก secret — V-9, V-10 และ RQ-14

สิ่งที่ต้องพิสูจน์: **ค่าที่ถูกย้ายข้ามผู้ใช้หรือข้ามงานเปิดผนึกไม่ออก**
ไม่ใช่เปิดออกแล้วได้ของผิดคน (`validation.md` V-9)
"""

from __future__ import annotations

import base64
import os
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.infra.crypto import (
    KEY_BYTES,
    KeyConfigurationError,
    KeyPurpose,
    KeySource,
    Sealed,
    SealingError,
    seal,
    unseal,
)
from tiewtrade.infra.crypto.sealing import NONCE_BYTES, _bound

SECRET = b"12345678901234567890"


def encoded_key(filler: bytes) -> str:
    """กุญแจทดสอบในรูปที่ตัวแปรสภาพแวดล้อมรับ"""
    return base64.b64encode(filler * KEY_BYTES).decode("ascii")


def source_with(monkeypatch: pytest.MonkeyPatch, value: str) -> KeySource:
    """ตั้งตัวแปรของงาน TOTP แล้วอ่านกลับเป็น `KeySource`"""
    monkeypatch.setenv(KeyPurpose.TOTP_SECRET.environment_variable, value)
    return KeySource.from_environment(KeyPurpose.TOTP_SECRET)


@pytest.fixture
def source(monkeypatch: pytest.MonkeyPatch) -> KeySource:
    """กุญแจหนึ่งรุ่นสำหรับเทสต์ส่วนใหญ่"""
    return source_with(monkeypatch, f"1:{encoded_key(b'A')}")


def test_a_sealed_secret_comes_back_unchanged(source: KeySource) -> None:
    """รอบไปกลับได้ค่าเดิม และรุ่นของกุญแจเดินทางไปกับค่า"""
    owner = uuid4()

    sealed = seal(source, SECRET, owner=owner)

    assert sealed.key_version == "1"
    assert unseal(source, sealed, owner=owner) == SECRET


def test_the_sealed_form_does_not_contain_the_secret(source: KeySource) -> None:
    """RQ-2 — ค่าที่เก็บลงฐานข้อมูลต้องไม่มี secret อยู่ในนั้นตรง ๆ"""
    sealed = seal(source, SECRET, owner=uuid4())

    assert SECRET not in sealed.blob


def test_sealing_twice_gives_different_blobs(source: KeySource) -> None:
    """nonce สุ่มใหม่ทุกครั้ง — **ซ้ำแล้ว GCM เสียความปลอดภัยทันที**"""
    owner = uuid4()

    first = seal(source, SECRET, owner=owner)
    second = seal(source, SECRET, owner=owner)

    assert first.blob != second.blob


def test_another_owner_cannot_unseal_it(source: KeySource) -> None:
    """V-9 — ย้ายค่าไปแถวของผู้ใช้คนอื่นแล้วเปิดผนึกไม่ออก"""
    sealed = seal(source, SECRET, owner=uuid4())

    with pytest.raises(SealingError):
        unseal(source, sealed, owner=uuid4())


def test_the_bound_data_names_both_the_purpose_and_the_owner() -> None:
    """RQ-14 — สิ่งที่ค่าถูกผูกไว้กับต้องมีทั้งงานและเจ้าของ"""
    owner = uuid4()

    assert _bound(KeyPurpose.TOTP_SECRET, owner) == f"TOTP_SECRET|{owner}".encode()


def test_a_value_sealed_for_one_purpose_resists_another_binding(source: KeySource) -> None:
    """RQ-14 — **กุญแจดอกเดียวกันแต่คนละงาน เปิดผนึกไม่ออก**

    จำลองงานที่สองของ F-07 ด้วย associated data ของงานนั้น โดยใช้กุญแจดอกเดิม
    ซึ่งเป็นกรณีที่แย่ที่สุด: ถ้าไม่ผูกชื่องานไว้ ค่านี้จะเปิดออกได้

    **ขอบเขตของหลักฐานนี้** (บันทึกหลังตรวจคำรับรอง 2026-10-04): พิสูจน์ได้เฉพาะ
    การผูกกับชื่องาน · ส่วนที่ว่า **บทบาทที่อ่าน secret ของ TOTP ได้ ต้องอ่านคอลัมน์
    secret ของตลาดไม่ได้** ยังพิสูจน์ที่นี่ไม่ได้ เพราะคอลัมน์นั้นยังไม่มีอยู่จริง —
    **เป็นข้อที่ F-07 ต้องพิสูจน์ ไม่ใช่อ้างจากที่นี่**
    """
    owner = uuid4()
    sealed = seal(source, SECRET, owner=owner)
    nonce, ciphertext = sealed.blob[:NONCE_BYTES], sealed.blob[NONCE_BYTES:]
    key = source.current()[1]

    assert AESGCM(key).decrypt(nonce, ciphertext, _bound(KeyPurpose.TOTP_SECRET, owner)) == SECRET

    with pytest.raises(InvalidTag):
        AESGCM(key).decrypt(nonce, ciphertext, f"VENUE_CREDENTIAL|{owner}".encode())


def test_a_tampered_blob_is_refused(source: KeySource) -> None:
    """เปลี่ยนไบต์เดียวแล้วต้องเปิดไม่ออก — AEAD ตรวจความถูกต้องให้เอง"""
    sealed = seal(source, SECRET, owner=(owner := uuid4()))
    flipped = bytearray(sealed.blob)
    flipped[-1] ^= 0x01

    with pytest.raises(SealingError):
        unseal(source, Sealed(sealed.key_version, bytes(flipped)), owner=owner)


def test_a_truncated_blob_is_refused(source: KeySource) -> None:
    """ค่าที่สั้นกว่า nonce ต้องถูกปฏิเสธก่อนเรียกตัวถอด"""
    with pytest.raises(SealingError):
        unseal(source, Sealed("1", b"\x00" * 4), owner=uuid4())


def test_an_unknown_key_version_is_refused(source: KeySource) -> None:
    """รุ่นที่ไม่มีกุญแจต้องดัง **ไม่ใช่เดาว่าเป็นรุ่นปัจจุบัน**"""
    sealed = seal(source, SECRET, owner=(owner := uuid4()))

    with pytest.raises(KeyConfigurationError):
        unseal(source, Sealed("ไม่มีรุ่นนี้", sealed.blob), owner=owner)


def test_a_retired_key_still_unseals_old_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """การหมุนกุญแจต้องไม่ทำให้แถวเก่าอ่านไม่ออก — ซึ่งเท่ากับล็อกผู้ใช้ออกทั้งระบบ"""
    owner = uuid4()
    old = source_with(monkeypatch, f"1:{encoded_key(b'A')}")
    sealed_before = seal(old, SECRET, owner=owner)

    rotated = source_with(monkeypatch, f"2:{encoded_key(b'B')},1:{encoded_key(b'A')}")

    assert rotated.current_version == "2"
    assert seal(rotated, SECRET, owner=owner).key_version == "2"
    assert unseal(rotated, sealed_before, owner=owner) == SECRET


def test_a_missing_key_is_refused_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """V-10 — ไม่มีกุญแจต้องดังตอนสร้าง ไม่ใช่ตอนมีผู้ใช้คนแรกมาเปิด TOTP"""
    monkeypatch.delenv(KeyPurpose.TOTP_SECRET.environment_variable, raising=False)

    with pytest.raises(KeyConfigurationError):
        KeySource.from_environment(KeyPurpose.TOTP_SECRET)


@pytest.mark.parametrize(
    "value",
    [
        "ไม่มีตัวคั่น",
        ":ขาดรุ่น",
        "1:",
        "1:ไม่ใช่base64!!",
        "1:QUFB",
        "1:AAAA,1:BBBB",
    ],
)
def test_a_malformed_key_is_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """รูปแบบที่ผิดทุกแบบต้องดังตอนอ่าน — รวมกุญแจสั้นและรุ่นซ้ำ"""
    monkeypatch.setenv(KeyPurpose.TOTP_SECRET.environment_variable, value)

    with pytest.raises(KeyConfigurationError):
        KeySource.from_environment(KeyPurpose.TOTP_SECRET)


def test_an_error_message_never_carries_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """`security.md` หัวข้อ 4 — ข้อความข้อผิดพลาดไปจบที่ log ได้ จึงห้ามพากุญแจไป"""
    short = base64.b64encode(b"short-key-not-32-bytes").decode("ascii")
    monkeypatch.setenv(KeyPurpose.TOTP_SECRET.environment_variable, f"1:{short}")

    with pytest.raises(KeyConfigurationError) as raised:
        KeySource.from_environment(KeyPurpose.TOTP_SECRET)

    assert short not in str(raised.value)
    assert KeyPurpose.TOTP_SECRET.environment_variable in str(raised.value)


@given(plaintext=st.binary(min_size=1, max_size=256))
def test_any_secret_survives_the_round_trip(plaintext: bytes) -> None:
    """คุณสมบัติ — ปิดผนึกแล้วเปิดผนึกได้ค่าเดิมสำหรับทุกค่า

    ตั้งตัวแปรด้วย `patch.dict` ไม่ใช่ `monkeypatch` เพราะ fixture แบบ function
    ไม่ถูกตั้งใหม่ต่อค่าที่ hypothesis สุ่ม ซึ่ง hypothesis เตือนไว้เอง
    """
    owner = uuid4()
    variable = KeyPurpose.TOTP_SECRET.environment_variable

    with patch.dict(os.environ, {variable: f"1:{encoded_key(b'A')}"}):
        source = KeySource.from_environment(KeyPurpose.TOTP_SECRET)

    assert unseal(source, seal(source, plaintext, owner=owner), owner=owner) == plaintext


def test_a_failed_unseal_never_shows_the_secret_in_the_traceback(source: KeySource) -> None:
    """V-6 — **canary ของ TOTP โดยเฉพาะ** — บังคับให้เปิดผนึกล้มแล้วค้น secret ทั้ง traceback

    canary ของ F-05 ครอบรหัสผ่านกับโทเคน และของ F-03 ครอบค่าที่ bind ลงฐานข้อมูล
    แต่ไม่มีอันไหนครอบ secret ของ TOTP · ข้อนี้สำคัญเพราะ traceback ของไลบรารี
    เข้ารหัสเป็นที่ที่ค่าดิบโผล่ได้ง่ายที่สุด
    """
    import base64 as b64
    import traceback

    owner = uuid4()
    secret = b"12345678901234567890"
    readable = (
        secret.hex(),
        b64.b32encode(secret).decode("ascii").rstrip("="),
        secret.decode("ascii"),
    )
    sealed = seal(source, secret, owner=owner)
    damaged = bytearray(sealed.blob)
    damaged[-1] ^= 0x01

    try:
        unseal(source, Sealed(sealed.key_version, bytes(damaged)), owner=owner)
    except SealingError:
        whole = traceback.format_exc()
    else:  # pragma: no cover - ต้องล้มเสมอ
        raise AssertionError("เปิดผนึกค่าที่ถูกแก้แล้วไม่ล้ม")

    for form in readable:
        assert form not in whole, f"พบ secret ในรูป {form[:8]}… ใน traceback"
    assert "AESGCM" not in whole, "traceback พาชื่อของไลบรารีเข้ารหัสออกไปด้วย"


@given(
    purpose=st.sampled_from(list(KeyPurpose)),
    plaintext=st.binary(min_size=1, max_size=256),
    owner=st.uuids(),
)
def test_both_purposes_preserve_generated_secrets_across_rotation_and_reject_foreign_context(
    purpose: KeyPurpose,
    plaintext: bytes,
    owner: UUID,
) -> None:
    """F-07 V-9/12: shared-key material proves binding for both purposes and different owners."""
    with patch.dict(
        os.environ, {p.environment_variable: f"1:{encoded_key(b'A')}" for p in KeyPurpose}
    ):
        original = KeySource.from_environment(purpose)
        foreign = KeySource.from_environment(next(p for p in KeyPurpose if p is not purpose))
    sealed = seal(original, plaintext, owner=owner)
    assert unseal(original, sealed, owner=owner) == plaintext
    with pytest.raises(SealingError):
        unseal(original, sealed, owner=UUID(int=owner.int ^ 1))
    with pytest.raises(SealingError):
        unseal(foreign, sealed, owner=owner)
    with patch.dict(
        os.environ, {purpose.environment_variable: f"2:{encoded_key(b'B')},1:{encoded_key(b'A')}"}
    ):
        rotated = KeySource.from_environment(purpose)
    assert unseal(rotated, sealed, owner=owner) == plaintext
    latest = seal(rotated, plaintext, owner=owner)
    assert latest.key_version == "2"
    assert unseal(rotated, latest, owner=owner) == plaintext
