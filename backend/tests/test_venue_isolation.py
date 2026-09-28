"""ชั้นแยก venue ต้องแยกจริงทั้งโปรเจกต์ — V-1, V-4, V-6

ด่านนี้รันกับโค้ดใน `src` เพราะเป็นโค้ดที่ทำงานจริง ส่วนไฟล์ใน `tests` พูดถึงชื่อตลาด
ได้ตามต้องการ — กรณีที่ต้องแดงของด่านเองก็ต้องเขียนชื่อตลาดลงไป
"""

from __future__ import annotations

from pathlib import Path

from tests.venue_isolation import central_venue_modules, check_no_network, check_vocabulary

BACKEND_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = BACKEND_ROOT / "src" / "tiewtrade"
VENUES_ROOT = SOURCE_ROOT / "venues"


def _files_outside_venues() -> list[Path]:
    return [
        path
        for path in SOURCE_ROOT.rglob("*.py")
        if VENUES_ROOT not in path.parents and path != VENUES_ROOT
    ]


def test_no_venue_vocabulary_outside_the_venue_layer() -> None:
    """V-1 — คำศัพท์ของตลาดไม่โผล่นอก `venues`"""
    found = [violation for path in _files_outside_venues() for violation in check_vocabulary(path)]
    assert found == [], "คำศัพท์ของตลาดรั่วออกนอกชั้น:\n" + "\n".join(str(v) for v in found)


def test_scanned_something() -> None:
    """ด่านที่ไม่เคยอ่านไฟล์ไหนจะเขียวตลอด — กันกรณีนั้น"""
    scanned = _files_outside_venues()
    assert len(scanned) > 10, f"ด่านอ่านแค่ {len(scanned)} ไฟล์ ซึ่งน้อยเกินกว่าจะเป็นจริง"


def test_central_venue_layer_does_not_know_about_networking() -> None:
    """V-4 — ส่วนกลางของ `venues` import เฉพาะสิ่งที่อยู่ในรายการที่อนุญาต

    รายชื่อไฟล์มาจากโครงสร้าง ไม่ใช่รายการที่เขียนไว้ — ไฟล์ใหม่ในส่วนกลาง
    จึงถูกตรวจทันทีโดยไม่ต้องมีใครจำว่าต้องไปเพิ่มชื่อที่ไหน
    """
    central = central_venue_modules(VENUES_ROOT)
    assert len(central) > 5, f"ส่วนกลางมีแค่ {len(central)} ไฟล์ ซึ่งน้อยเกินกว่าจะเป็นจริง"

    found = []
    for path in central:
        found.extend(check_no_network(path))
    assert found == [], "ส่วนกลางของ venues พึ่งของที่ไม่อยู่ในรายการที่อนุญาต:\n" + "\n".join(
        str(v) for v in found
    )
