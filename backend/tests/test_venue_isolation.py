"""ชั้นแยก venue ต้องแยกจริงทั้งโปรเจกต์ — V-1, V-4, V-6

ด่านนี้รันกับโค้ดใน `src` เพราะเป็นโค้ดที่ทำงานจริง ส่วนไฟล์ใน `tests` พูดถึงชื่อตลาด
ได้ตามต้องการ — กรณีที่ต้องแดงของด่านเองก็ต้องเขียนชื่อตลาดลงไป
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from tests.venue_isolation import (
    adapter_packages,
    central_venue_modules,
    check_network_only_in,
    check_no_network,
    check_vocabulary,
    declared_venue_words,
    modules_not_reaching,
)

BACKEND_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = BACKEND_ROOT / "src" / "tiewtrade"
VENUES_ROOT = SOURCE_ROOT / "venues"
GATE_FIXTURES = BACKEND_ROOT / "tests" / "gates" / "fixtures"

#: ต้นไม้จำลองสองชุดที่ด่าน import-linter ใช้ — กรณีที่ต้องผ่านและกรณีที่ต้องแดง
GATE_TREES = ("imports_good", "imports_bad")

#: ชื่อ contract ใน `pyproject.toml` ที่ต้องมีรายชื่อโมดูลตรงกับโครงสร้างจริง
CENTRAL_CONTRACT = "ส่วนกลางของ venues ห้ามพึ่งไลบรารีเครือข่าย"
ADAPTER_CONTRACT = "การแปลข้อมูลของตัวเชื่อม Binance TH ห้ามรู้จักเครือข่าย"


def _venue_words() -> frozenset[str]:
    words, missing = declared_venue_words(VENUES_ROOT)
    assert missing == [], "มี package ตัวเชื่อมที่ไม่ประกาศคำศัพท์ของตัวเอง:\n" + "\n".join(
        str(violation) for violation in missing
    )
    return words


def _contract_modules(name: str) -> set[str]:
    config = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    contracts = config["tool"]["importlinter"]["contracts"]
    found = [contract for contract in contracts if contract["name"] == name]
    assert len(found) == 1, f"ไม่พบ contract ชื่อ {name!r} ใน pyproject.toml"
    return set(found[0]["source_modules"])


def _files_outside_venues() -> list[Path]:
    return [
        path
        for path in SOURCE_ROOT.rglob("*.py")
        if VENUES_ROOT not in path.parents and path != VENUES_ROOT
    ]


def test_no_venue_vocabulary_outside_the_venue_layer() -> None:
    """V-1 — คำศัพท์ของตลาดไม่โผล่นอก `venues`"""
    words = _venue_words()
    found = [
        violation for path in _files_outside_venues() for violation in check_vocabulary(path, words)
    ]
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


def test_every_adapter_package_declares_its_own_vocabulary() -> None:
    """V-46 — ตัวเชื่อมทุกตัวประกาศคำศัพท์ของตลาดตัวเอง และด่านใช้คำเหล่านั้นจริง

    F-35 plan.md ข้อ 7.2 — ถ้ารายการมาจากไฟล์เทสต์ การเพิ่มตลาดใหม่จะต้องมีคนจำ
    ว่าต้องไปเติมที่นั่น ซึ่งคือสิ่งที่ลืมได้
    """
    packages = adapter_packages(VENUES_ROOT)
    assert packages, "ไม่พบ package ตัวเชื่อมเลย ซึ่งแปลว่าด่านอ่านผิดที่"
    words = _venue_words()
    assert "binance" in words, "คำของตลาดที่ระบบใช้จริงต้องอยู่ในรายการที่ห้าม"


def test_network_contract_lists_every_central_module() -> None:
    """V-44 — รายชื่อโมดูลส่วนกลางใน `pyproject.toml` ตรงกับโครงสร้างจริง

    F-35 plan.md ข้อ 7.1 — เพิ่มไฟล์ใหม่ในส่วนกลางแล้วลืมเติมชื่อใน contract
    กฎจะไม่ครอบไฟล์นั้นโดยไม่มีอะไรเตือน เทสต์นี้คือสิ่งที่เตือน

    `__init__.py` ไม่อยู่ใน contract เพราะ import-linter เรียกชื่อมันแยกจาก package
    ไม่ได้ — ไฟล์นั้นถูกคุมด้วยด่าน AST (`check_no_network`) ซึ่งอ่านมันด้วย
    """
    expected = {
        f"tiewtrade.venues.{path.stem}"
        for path in central_venue_modules(VENUES_ROOT)
        if path.name != "__init__.py"
    }
    assert _contract_modules(CENTRAL_CONTRACT) == expected


def test_adapter_contract_lists_every_module_that_must_not_reach_the_network() -> None:
    """V-44 — รายชื่อโมดูลของตัวเชื่อมที่ห้ามถึงเครือข่ายก็มาจากโครงสร้างจริง

    กฎคือ "ทุกโมดูลที่ไม่ได้ผ่าน `transport`" ไม่ใช่รายชื่อที่ใครจำไว้
    """
    for package in adapter_packages(VENUES_ROOT):
        expected = {
            f"tiewtrade.venues.{package.name}.{path.stem}"
            for path in modules_not_reaching(package, "transport")
        }
        assert _contract_modules(ADAPTER_CONTRACT) == expected


def test_gate_fixtures_mirror_the_central_modules() -> None:
    """V-45 — ต้นไม้ของ fixture ทั้งสองชุดมีโมดูลครบเท่าส่วนกลางจริง

    contract ของ import-linter ระบุรายชื่อโมดูล ถ้า fixture ขาดโมดูลไหน
    contract จะอ้างถึงของที่ไม่มี แล้วด่านจะผ่านเพราะไม่มีอะไรให้ตรวจ ไม่ใช่เพราะถูกต้อง
    """
    expected = {path.name for path in central_venue_modules(VENUES_ROOT)}
    for tree in GATE_TREES:
        root = GATE_FIXTURES / tree / "src" / "tiewtrade" / "venues"
        assert {path.name for path in root.glob("*.py")} == expected, (
            f"fixture {tree} ไม่มีโมดูลครบเท่าส่วนกลางจริง"
        )


def test_gate_fixtures_have_every_module_the_contracts_name() -> None:
    """V-45 — ทุกโมดูลที่ contract เอ่ยชื่อต้องมีอยู่ใน fixture ทั้งสองชุด

    กฎที่อ้างถึงโมดูลที่ไม่มีในต้นไม้ที่ทดสอบคือกฎที่ไม่มีอะไรให้ตรวจ
    เพิ่ม contract ใหม่แล้วลืมสร้างไฟล์ใน fixture เทสต์นี้แดงแทนที่จะเงียบ
    """
    named = _contract_modules(CENTRAL_CONTRACT) | _contract_modules(ADAPTER_CONTRACT)
    for tree in GATE_TREES:
        root = GATE_FIXTURES / tree / "src"
        for module in sorted(named):
            path = root.joinpath(*module.split(".")).with_suffix(".py")
            assert path.exists(), f"fixture {tree} ไม่มี {module} ที่ contract เอ่ยชื่อไว้"


def test_each_adapter_reaches_the_network_through_one_file_only() -> None:
    """V-3 — `import httpx` อยู่ในไฟล์เดียวของตัวเชื่อม

    ทางออกเดียวคือเหตุผลที่ทำให้ "จองโควตา → เรียก → แปลผล" เลี่ยงไม่ได้
    """
    for package in adapter_packages(VENUES_ROOT):
        found = check_network_only_in(package, "transport")
        assert found == [], f"{package.name} มีทางออกสู่เครือข่ายมากกว่าหนึ่งทาง:\n" + "\n".join(
            str(violation) for violation in found
        )


def test_adapter_packages_depend_on_nothing_but_core_and_the_venue_layer() -> None:
    """V-6 — ตัวเชื่อมพึ่ง `infra`, `strategies` และ service ไม่ได้

    contract ของ import-linter ระบุ `tiewtrade.venues` ซึ่งครอบ package ย่อยอยู่แล้ว
    เทสต์นี้ยืนยันว่ามันครอบ **package ใหม่นี้จริง** ไม่ใช่เชื่อว่าครอบ
    """
    forbidden = ("tiewtrade.infra", "tiewtrade.strategies", "tiewtrade.services")
    for package in adapter_packages(VENUES_ROOT):
        for path in package.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for module in forbidden:
                assert module not in text, f"{path.name} พึ่ง {module}"
