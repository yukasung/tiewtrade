"""ตัวตรวจว่าชั้นแยก venue ยังแยกจริง (F-33 RQ-12, RQ-14)

สองด่านที่ import-linter ทำแทนไม่ได้:

1. **คำศัพท์ของตลาดรั่วออกนอก `venues`** — การรั่วแบบนี้ไม่ใช่การ import
   แต่เป็นข้อความหรือชื่อที่เขียนไว้ในโค้ด
2. **ส่วนกลางของ `venues` รู้จักเครือข่าย** — ตรวจด้วยรายการที่อนุญาต ไม่ใช่รายการที่ห้าม
   เพราะรายการที่ห้ามต้องตามเติมชื่อทุกครั้งที่เพิ่ม dependency แล้วจะลืม
   (บทเรียนเดียวกับตัวตรวจความบริสุทธิ์ของ `core`)

**อ่านโครงสร้างโค้ด ไม่ค้นข้อความทั้งไฟล์** และ **ข้าม docstring** เพราะ docstring
อ้างถึงสเปกและชื่อตลาดเป็นเรื่องปกติและจำเป็น — การจับ docstring จะทำให้ต้องเลี่ยงคำ
ในเอกสารซึ่งทำให้เอกสารแย่ลงโดยไม่ได้ปลอดภัยขึ้น (บทเรียนจากตัวตรวจของ F-01)

**ขอบเขตของด่านเครือข่าย: เฉพาะส่วนกลาง ไม่ครอบ package ของตัวเชื่อมจริง**
`architecture.md` หัวข้อ 1 วางตัวเชื่อมไว้ข้างใน `venues` และตัวเชื่อมต้องต่อเครือข่าย
เป็นงานหลัก ถ้าด่านครอบทั้ง package จะบล็อก F-35 ตั้งแต่บรรทัดแรก
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.purity import Violation

#: คำที่เป็นของตลาดโดยเฉพาะ ห้ามปรากฏนอก `venues`
VENUE_WORDS: frozenset[str] = frozenset({"binance", "fapi", "sapi", "testnet"})

_VENUE_WORD_PATTERN = re.compile("|".join(sorted(VENUE_WORDS)))

#: ชื่อคู่เทรดแบบที่ตลาดเขียนติดกันเป็นคำเดียว เช่น `BTCUSDT`
#: ชั้นกลางใช้ `Symbol` ที่แยกสองส่วน จึงไม่มีเหตุผลให้รูปแบบนี้อยู่ในโค้ด
JOINED_PAIR = re.compile(r"^[A-Z]{2,6}(USDT|USDC|BUSD|THB|BTC|ETH)$")

#: ไลบรารีที่ส่วนกลางของ `venues` ใช้ได้ — รายการที่อนุญาต
ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "functools",
        "re",
        "typing",
        "tiewtrade",
    }
)


def central_venue_modules(venues_root: Path) -> tuple[Path, ...]:
    """ไฟล์ของ **ส่วนกลาง** ของชั้น venue

    "ไฟล์ `.py` ที่อยู่ระดับบนสุดของ `venues/`" คือกฎของขอบเขตนี้ ไม่ใช่รายชื่อที่จำไว้
    — `glob` ที่ไม่ลงลึกจึงเป็นตัวกฎเอง package ของตัวเชื่อมจริงอยู่ในโฟลเดอร์ย่อย
    จึงถูกกันออกโดยโครงสร้าง ไม่ใช่โดยการที่ใครสักคนจำได้ว่าต้องไม่ใส่ชื่อมันลงรายการ
    """
    return tuple(sorted(venues_root.glob("*.py")))


def _venue_words_in(text: str) -> list[str]:
    """คำของตลาดที่พบในข้อความหนึ่ง"""
    return _VENUE_WORD_PATTERN.findall(text.lower())


def check_vocabulary(path: Path) -> list[Violation]:
    """หาคำศัพท์ของตลาดในไฟล์หนึ่ง — ใช้กับไฟล์นอก `venues`

    เดินต้นไม้รอบเดียว โดยจำ docstring ที่เจอระหว่างทางไว้ข้าม
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []
    docstrings: set[int] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = _docstring_constant(node)
            if docstring is not None:
                docstrings.add(id(docstring))
            # ชื่อคลาสและชื่อฟังก์ชันก็เป็นที่ที่คำศัพท์ของตลาดโผล่ได้
            # เช่น `def binance_price()` ซึ่งไม่ใช่ทั้งข้อความและไม่ใช่การอ้างชื่อ
            if not isinstance(node, ast.Module):
                violations.extend(_name_violations(path, node.name, node.lineno))
            continue

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            for word in _venue_words_in(node.value):
                violations.append(
                    Violation(path, node.lineno, "venue-word", f"ข้อความมีคำว่า {word!r}")
                )
            if JOINED_PAIR.match(node.value):
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "joined-pair",
                        f"{node.value!r} เป็นชื่อคู่เทรดแบบของตลาด ใช้ Symbol แทน",
                    )
                )
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            # `from binance import Client` — ชื่อ module อยู่ที่นี่ ไม่ได้อยู่ใน alias
            violations.extend(_name_violations(path, node.module, node.lineno))
        elif isinstance(node, (ast.Name, ast.Attribute, ast.alias)):
            violations.extend(_name_violations(path, _identifier(node), getattr(node, "lineno", 0)))

    return violations


def _name_violations(path: Path, name: str, line: int) -> list[Violation]:
    """คำศัพท์ของตลาดที่ซ่อนอยู่ในชื่อหนึ่งชื่อ

    ตรวจทั้งคำของตลาดและชื่อคู่เทรดแบบติดกัน เพราะ `BTCUSDT = 1` เป็นชื่อตัวแปร
    ไม่ใช่ข้อความ จึงไม่ถูกจับโดยการตรวจค่าคงที่
    """
    found = [
        Violation(path, line, "venue-word", f"ชื่อ {name!r} มีคำว่า {word!r}")
        for word in _venue_words_in(name)
    ]
    if JOINED_PAIR.match(name):
        found.append(Violation(path, line, "joined-pair", f"ชื่อ {name!r} เป็นคู่เทรดแบบของตลาด"))
    return found


def _docstring_constant(node: ast.AST) -> ast.Constant | None:
    """โหนดข้อความที่เป็น docstring ของโหนดนี้ ถ้ามี"""
    body = getattr(node, "body", [])
    if not body:
        return None
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first.value
    return None


def _identifier(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.alias):
        return node.name
    return ""


def check_no_network(path: Path) -> list[Violation]:
    """ยืนยันว่าไฟล์นี้ import เฉพาะสิ่งที่อยู่ในรายการที่อนุญาต"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _check_module(alias.name, node.lineno, path, violations)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            _check_module(node.module, node.lineno, path, violations)

    return violations


def _check_module(module: str, line: int, path: Path, violations: list[Violation]) -> None:
    root = module.split(".")[0]
    if root not in ALLOWED_IMPORTS:
        violations.append(
            Violation(path, line, "not-allowed-import", f"{module!r} ไม่อยู่ในรายการที่อนุญาต")
        )
