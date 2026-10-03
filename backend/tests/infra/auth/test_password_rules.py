"""กฎของรหัสผ่าน — V-22 ถึง V-30.3

**แยกการรับรหัสผ่านใหม่ออกจากการตรวจรหัสผ่านที่มีอยู่** เพราะการรวมกันทำให้ผู้ใช้
ที่รหัสผ่านเดิมถูกเพิ่มเข้ารายการที่ห้ามภายหลัง เข้าสู่ระบบไม่ได้และเปลี่ยนรหัสผ่านก็ไม่ได้
ซึ่งในงานนี้ไม่มีทางกู้บัญชีเลย
"""

from __future__ import annotations

import json
import time
import unicodedata
from pathlib import Path

import pytest

from tiewtrade.core.passwords import (
    MAXIMUM_LENGTH,
    MINIMUM_LENGTH,
    PasswordPolicyError,
    acceptable_new_password,
    length_of,
    normalised,
)
from tiewtrade.infra.auth import (
    MANIFEST_FIELDS,
    blocked_digests,
    digest_of,
    hash_password,
    is_blocked,
    manifest,
    password_matches,
    spend_matching_time,
)
from tiewtrade.infra.auth.hashing import (
    HASH_LENGTH,
    MEMORY_COST_KIB,
    PARALLELISM,
    SALT_LENGTH,
    TIME_COST,
)


def test_a_password_one_character_short_is_refused() -> None:
    """V-22 — ขอบที่ 14 กับ 15 ตัวอักษร"""
    with pytest.raises(PasswordPolicyError):
        acceptable_new_password("ก" * (MINIMUM_LENGTH - 1))
    assert acceptable_new_password("ก" * MINIMUM_LENGTH)


def test_a_password_one_character_too_long_is_refused() -> None:
    """V-23 — ขอบที่ 1,024 กับ 1,025 ตัวอักษร"""
    assert acceptable_new_password("a" * MAXIMUM_LENGTH)
    with pytest.raises(PasswordPolicyError):
        acceptable_new_password("a" * (MAXIMUM_LENGTH + 1))


def test_length_counts_code_points_not_bytes() -> None:
    """V-24 — รหัสผ่านภาษาไทยและอิโมจิ 15 ตัวต้องผ่าน

    ถ้านับไบต์ รหัสผ่านภาษาไทย 15 ตัวจะนับได้ 45 ซึ่งผ่านเกณฑ์ทั้งที่สั้นกว่าที่กฎต้องการ
    และอิโมจิ 15 ตัวจะนับได้ 60
    """
    thai = "รหัสผ่านไทยสิบห้า"[:MINIMUM_LENGTH]
    assert length_of(thai) == MINIMUM_LENGTH
    assert len(thai.encode("utf-8")) > MINIMUM_LENGTH
    assert acceptable_new_password(thai)
    assert length_of("🔐" * MINIMUM_LENGTH) == MINIMUM_LENGTH


def test_the_same_password_in_two_unicode_forms_is_the_same_password() -> None:
    """V-25 — ตั้งด้วยรูปแยก (NFD) แล้วเข้าสู่ระบบด้วยรูปรวม (NFC) ต้องผ่าน และกลับกัน"""
    composed = "คาเฟ่̀ที่ยาวพอใช้งาน"
    decomposed = unicodedata.normalize("NFD", composed)
    assert decomposed != composed

    stored = hash_password(decomposed)
    assert password_matches(stored, composed)

    other = hash_password(composed)
    assert password_matches(other, decomposed)
    assert normalised(decomposed) == normalised(composed)


def test_a_lowercase_only_password_is_accepted() -> None:
    """V-26 — ไม่มีกฎบังคับชนิดอักขระ (มาตรฐานห้ามไว้ชัด)"""
    assert acceptable_new_password("ตัวพิมพ์เล็กล้วนแต่ยาวพอ")


def test_a_blocked_password_is_refused_and_the_list_really_has_entries() -> None:
    """V-27 — รหัสผ่านในรายการที่ห้ามถูกปฏิเสธ และรายการมีของจริง"""
    digests = blocked_digests()
    assert len(digests) > 0, "รายการที่ห้ามว่างเปล่า จึงไม่ได้ตรวจอะไรเลย"
    assert all(len(digest) == 64 for digest in digests)
    assert is_blocked("password123456789")


def test_a_password_that_is_not_in_the_list_passes() -> None:
    """คู่กันของข้อข้างบน — มิฉะนั้นเทสต์ก็แค่พิสูจน์ว่าทุกอย่างถูกห้าม"""
    assert not is_blocked("รหัสผ่านที่ไม่มีใครใช้ซ้ำแน่นอน")


def test_checking_an_existing_password_ignores_length_and_the_blocklist() -> None:
    """V-27.1, V-27.2 — รหัสผ่านที่ตั้งไว้ก่อนกฎเปลี่ยนต้องยังเข้าสู่ระบบได้

    ถ้าการตรวจรหัสผ่านที่มีอยู่ใช้กฎของรหัสผ่านใหม่ด้วย ผู้ใช้จะถูกล็อกออกจากบัญชี
    ถาวรเมื่อรายการที่ห้ามอัปเดต — งานนี้ไม่มีทางกู้บัญชี
    """
    weak_and_blocked = "password123456789"
    assert is_blocked(weak_and_blocked)
    stored = hash_password(weak_and_blocked)
    assert password_matches(stored, weak_and_blocked)

    short = "สั้นมาก"
    assert password_matches(hash_password(short), short)


def test_the_blocklist_manifest_records_where_the_list_came_from() -> None:
    """V-28, V-28.1 — มีครบหกช่อง และรุ่นปักด้วย commit ไม่ใช่ "ล่าสุด" """
    recorded = manifest()
    for field in MANIFEST_FIELDS:
        assert field in recorded, f"ไฟล์กำกับขาดช่อง {field}"
    commit = recorded["source_commit"]
    assert isinstance(commit, str)
    assert len(commit) == 40, "รุ่นต้องเป็น commit เต็ม ไม่ใช่ชื่อ branch"
    assert str(recorded["source_url"]).find(commit) != -1, "URL ต้องปักที่ commit เดียวกัน"
    assert int(str(recorded["source_entries"])) > int(str(recorded["kept_entries"]))


def test_the_blocklist_stores_hashes_not_passwords() -> None:
    """V-29 — ไฟล์ต้องไม่กลายเป็นคลังรหัสผ่าน"""
    path = (
        Path(__file__).parents[2].parent
        / "src"
        / "tiewtrade"
        / "infra"
        / "auth"
        / "password_blocklist"
        / "hashes.txt"
    )
    body = path.read_text(encoding="utf-8")
    assert "password" not in body
    assert all(len(line) == 64 for line in body.split())


def test_the_digest_recipe_matches_the_script_that_builds_the_list() -> None:
    """V-28.2 — ขั้นตอนการแฮชต้องเหมือนกันทั้งสองฝั่ง มิฉะนั้นการตรวจไม่มีผล"""
    import hashlib

    password = "ค่าที่ใช้ทดสอบขั้นตอนการแฮช"
    expected = hashlib.sha256(unicodedata.normalize("NFC", password).encode("utf-8")).hexdigest()
    assert digest_of(password) == expected


def test_the_hashing_cost_is_the_one_that_was_approved() -> None:
    """V-30.1 — ค่าความแรงเป็นค่าที่อนุมัติไว้ และหนึ่งครั้งใช้เวลาอยู่ในช่วงที่ยอมรับ

    ขอบกว้างโดยเจตนา (10 มิลลิวินาที ถึง 1 วินาที) เพื่อไม่ให้แดงสุ่มบนเครื่องที่ช้า
    — เบาเกินไปคือไม่มีความหมาย หนักเกินไปคือการทำ DoS ใส่ตัวเอง
    """
    assert (TIME_COST, MEMORY_COST_KIB, PARALLELISM, HASH_LENGTH, SALT_LENGTH) == (
        3,
        65536,
        4,
        32,
        16,
    )
    started = time.perf_counter()
    hash_password("รหัสผ่านที่ใช้วัดเวลาแฮช")
    spent = time.perf_counter() - started
    assert 0.01 < spent < 1.0, f"แฮชหนึ่งครั้งใช้เวลา {spent:.3f} วินาที"


def test_the_dummy_hash_path_costs_about_the_same() -> None:
    """V-33.1 (ฝั่งโค้ด) — เส้นทางที่ไม่พบอีเมลต้องใช้เวลาจริง ไม่ใช่คืนทันที"""
    spend_matching_time()  # ครั้งแรกคิดแฮชหลอก
    started = time.perf_counter()
    spend_matching_time()
    spent = time.perf_counter() - started
    assert spent > 0.005, f"เส้นทางที่ไม่พบอีเมลใช้เวลาแค่ {spent:.4f} วินาที"


def test_two_hashes_of_the_same_password_differ_but_both_verify() -> None:
    """เกลือต้องต่างกันทุกครั้ง แต่ตรวจกลับได้ทั้งคู่"""
    password = "รหัสผ่านเดียวกันสองครั้ง"
    first, second = hash_password(password), hash_password(password)
    assert first != second
    assert password_matches(first, password)
    assert password_matches(second, password)


def test_a_wrong_password_does_not_match() -> None:
    """ด้านลบที่ขาดไม่ได้ — มิฉะนั้นเทสต์ข้างบนผ่านได้ด้วยฟังก์ชันที่คืนจริงตลอด"""
    assert not password_matches(hash_password("รหัสผ่านที่ถูกต้องยาวพอ"), "อย่างอื่น")


def test_the_manifest_is_valid_json_with_the_minimum_length_recorded() -> None:
    """ไฟล์กำกับต้องอ่านได้และบันทึกขั้นต่ำที่ใช้ตัดรายการไว้ด้วย"""
    path = (
        Path(__file__).parents[2].parent
        / "src"
        / "tiewtrade"
        / "infra"
        / "auth"
        / "password_blocklist"
        / "manifest.json"
    )
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["minimum_length"] == MINIMUM_LENGTH
