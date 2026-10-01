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

**คำศัพท์ที่ห้ามมาจากตัวเชื่อมเอง ไม่ใช่รายการที่เขียนไว้ที่นี่** แต่ละ package ตัวเชื่อม
ประกาศ `VENUE_VOCABULARY` ของตัวเอง ด่านอ่านด้วย AST แล้วรวมเป็นรายการที่ห้าม
การเพิ่มตลาดใหม่จึงขยายด่านให้เองโดยไม่ต้องมีใครจำ (F-35 plan.md ข้อ 7.2)

**ขอบเขตของด่านเครือข่าย: เฉพาะส่วนกลาง ไม่ครอบ package ของตัวเชื่อมจริง**
`architecture.md` หัวข้อ 1 วางตัวเชื่อมไว้ข้างใน `venues` และตัวเชื่อมต้องต่อเครือข่าย
เป็นงานหลัก ถ้าด่านครอบทั้ง package จะบล็อก F-35 ตั้งแต่บรรทัดแรก
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.purity import Violation

#: ชื่อที่ package ตัวเชื่อมแต่ละตัวต้องใช้ประกาศคำศัพท์ของตลาดตัวเอง
VOCABULARY_DECLARATION = "VENUE_VOCABULARY"

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


def adapter_packages(venues_root: Path) -> tuple[Path, ...]:
    """package ของตัวเชื่อมแต่ละตลาด — โฟลเดอร์ย่อยของ `venues/` ที่เป็น package"""
    return tuple(sorted(path.parent for path in venues_root.glob("*/__init__.py")))


def declared_venue_words(venues_root: Path) -> tuple[frozenset[str], list[Violation]]:
    """คำศัพท์ของตลาดที่ **ตัวเชื่อมประกาศเอง** รวมจากทุก package (F-35 plan.md ข้อ 7.2)

    อ่านด้วย AST ไม่ `import` เพราะด่านต้องอ่านโค้ดได้โดยไม่ต้องรันโค้ดนั้น

    **ตัวเชื่อมที่ไม่ประกาศคำศัพท์เลยถือว่าผิด** ตัวเชื่อมพาชื่อตลาดเข้ามาเป็นงานหลัก
    ถ้าไม่มีคำของตัวเองแปลว่ามีคนลืม แล้วด่านจะเงียบลงทีละตลาดโดยไม่มีอะไรเตือน
    """
    words: set[str] = set()
    violations: list[Violation] = []
    for package in adapter_packages(venues_root):
        init = package / "__init__.py"
        declared = _declared_vocabulary(init)
        if not declared:
            violations.append(
                Violation(
                    init,
                    0,
                    "missing-vocabulary",
                    f"package ตัวเชื่อมต้องประกาศ {VOCABULARY_DECLARATION} ที่ไม่ว่าง",
                )
            )
            continue
        words.update(declared)
    return frozenset(words), violations


def _declared_vocabulary(init: Path) -> frozenset[str]:
    """ค่าของ `VENUE_VOCABULARY` ในไฟล์หนึ่ง — ว่างเปล่าถ้าไม่มีหรืออ่านไม่ได้"""
    tree = ast.parse(init.read_text(encoding="utf-8"), filename=str(init))
    for node in ast.walk(tree):
        target = _assigned_name(node)
        if target != VOCABULARY_DECLARATION or not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and len(value.args) == 1
        ):
            value = value.args[0]
        try:
            literal = ast.literal_eval(value)
        except ValueError:
            return frozenset()
        if isinstance(literal, (set, frozenset, tuple, list)) and all(
            isinstance(word, str) and word for word in literal
        ):
            return frozenset(word.lower() for word in literal)
    return frozenset()


def _assigned_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.AnnAssign):
        return _identifier(node.target) or None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        return _identifier(node.targets[0]) or None
    return None


def central_venue_modules(venues_root: Path) -> tuple[Path, ...]:
    """ไฟล์ของ **ส่วนกลาง** ของชั้น venue

    "ไฟล์ `.py` ที่อยู่ระดับบนสุดของ `venues/`" คือกฎของขอบเขตนี้ ไม่ใช่รายชื่อที่จำไว้
    — `glob` ที่ไม่ลงลึกจึงเป็นตัวกฎเอง package ของตัวเชื่อมจริงอยู่ในโฟลเดอร์ย่อย
    จึงถูกกันออกโดยโครงสร้าง ไม่ใช่โดยการที่ใครสักคนจำได้ว่าต้องไม่ใส่ชื่อมันลงรายการ
    """
    return tuple(sorted(venues_root.glob("*.py")))


#: ไลบรารีที่แตะเครือข่ายได้ — **รายการที่ห้าม** ไม่ใช่รายการที่อนุญาต
#:
#: ต่างจากด่านของส่วนกลางโดยเจตนา: ที่นั่นถามว่า "ไฟล์นี้บริสุทธิ์ไหม" จึงต้องใช้
#: รายการที่อนุญาต ส่วนที่นี่ถามว่า "เครือข่ายอยู่ไฟล์เดียวไหม" ตัวเชื่อมใช้ของใน
#: standard library ได้ตามต้องการ การใช้รายการที่อนุญาตที่นี่จะกลายเป็นรายการ
#: ที่ต้องตามเติมทุกครั้งที่ตัวเชื่อมใช้ของใหม่ และทิศทางอ้อมถูก import-linter คุมไว้แล้ว
NETWORK_LIBRARIES: frozenset[str] = frozenset(
    {"httpx", "socket", "urllib", "requests", "aiohttp", "websockets", "http", "ssl"}
)


def check_network_only_in(package_root: Path, gateway: str) -> list[Violation]:
    """ยืนยันว่ามีไฟล์เดียวใน package ที่รู้จักเครือข่าย (F-35 V-3)

    ตรวจ **ทุกไฟล์ของ package รวมโฟลเดอร์ย่อย** เพราะกฎคือ "ทางเดียวที่ออกไปข้างนอก"
    ถ้ามีสองทาง การจองโควตาก่อนเรียกจะเลี่ยงได้โดยไม่มีอะไรเตือน
    """
    violations: list[Violation] = []
    for path in sorted(package_root.rglob("*.py")):
        if path.name == f"{gateway}.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _reject_network(path, alias.name, node.lineno, violations)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                _reject_network(path, node.module, node.lineno, violations)
    return violations


def _reject_network(path: Path, module: str, line: int, violations: list[Violation]) -> None:
    if module.split(".")[0] in NETWORK_LIBRARIES:
        violations.append(
            Violation(path, line, "network-outside-gateway", f"{module!r} อยู่นอกไฟล์ทางออกเดียว")
        )


def modules_not_reaching(package_root: Path, gateway: str) -> tuple[Path, ...]:
    """ไฟล์ระดับบนสุดของ package ที่ **ไม่ได้** ผ่านโมดูลหนึ่ง (F-35 plan.md ข้อ 7.1)

    ใช้หาว่าโมดูลไหนของตัวเชื่อมต้องไม่รู้จักเครือข่ายเลย: ทุกไฟล์ที่ไม่ใช่
    `gateway` เองและไม่ `import` มัน `__init__.py` ไม่นับเพราะหน้าที่ของมันคือ
    ประกอบของทุกชิ้นมารวมกัน จึงต้องถึงเครือข่ายโดยปริยาย

    กฎนี้เป็นตัวกฎเอง ไม่ใช่รายชื่อที่จำไว้ — เพิ่มโมดูลใหม่ที่ไม่ผ่าน `gateway`
    แล้วลืมเติมใน contract ของ import-linter เทสต์จะแดงทันที
    """
    found: list[Path] = []
    for path in sorted(package_root.glob("*.py")):
        if path.name in ("__init__.py", f"{gateway}.py"):
            continue
        if not _imports_sibling(path, gateway):
            found.append(path)
    return tuple(found)


def _imports_sibling(path: Path, module: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.split(".")[-1] == module:
                return True
        elif isinstance(node, ast.Import) and any(
            alias.name.split(".")[-1] == module for alias in node.names
        ):
            return True
    return False


def _venue_words_in(text: str, words: frozenset[str]) -> list[str]:
    """คำของตลาดที่พบในข้อความหนึ่ง"""
    return re.findall("|".join(sorted(re.escape(word) for word in words)), text.lower())


def check_vocabulary(path: Path, words: frozenset[str]) -> list[Violation]:
    """หาคำศัพท์ของตลาดในไฟล์หนึ่ง — ใช้กับไฟล์นอก `venues`

    เดินต้นไม้รอบเดียว โดยจำ docstring ที่เจอระหว่างทางไว้ข้าม

    `words` มาจาก `declared_venue_words` ไม่ใช่รายการที่เขียนไว้ในไฟล์นี้
    เพราะคำของตลาดเป็นของตัวเชื่อม ไม่ใช่ของด่าน
    """
    if not words:
        raise ValueError("ด่านคำศัพท์ที่ไม่มีคำให้หาคือด่านที่เขียวตลอด")
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
                violations.extend(_name_violations(path, node.name, node.lineno, words))
            continue

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            for word in _venue_words_in(node.value, words):
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
            violations.extend(_name_violations(path, node.module, node.lineno, words))
        elif isinstance(node, (ast.Name, ast.Attribute, ast.alias)):
            violations.extend(
                _name_violations(path, _identifier(node), getattr(node, "lineno", 0), words)
            )

    return violations


def _name_violations(path: Path, name: str, line: int, words: frozenset[str]) -> list[Violation]:
    """คำศัพท์ของตลาดที่ซ่อนอยู่ในชื่อหนึ่งชื่อ

    ตรวจทั้งคำของตลาดและชื่อคู่เทรดแบบติดกัน เพราะ `BTCUSDT = 1` เป็นชื่อตัวแปร
    ไม่ใช่ข้อความ จึงไม่ถูกจับโดยการตรวจค่าคงที่
    """
    found = [
        Violation(path, line, "venue-word", f"ชื่อ {name!r} มีคำว่า {word!r}")
        for word in _venue_words_in(name, words)
    ]
    if JOINED_PAIR.match(name):
        found.append(Violation(path, line, "joined-pair", f"ชื่อ {name!r} เป็นคู่เทรดแบบของตลาด"))
    return found


def code_strings(path: Path) -> list[str]:
    """ข้อความที่โค้ดใช้จริงในไฟล์หนึ่ง — **ไม่รวม docstring**

    อยู่ที่นี่เพราะมีสามที่ที่ต้องถามคำถามเดียวกัน: ด่านคำศัพท์, เทสต์ที่ยืนยันว่า
    ตัวเชื่อมไม่มีทางสำรองของราคา และเทสต์ที่ยืนยันว่าสคริปต์เรียกแต่ endpoint
    ที่อนุมัติ — และทุกที่ต้องข้าม docstring เหมือนกัน เพราะเอกสารพูดถึงสิ่งที่
    **ไม่ทำ** เป็นเรื่องปกติและจำเป็น
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = {
        id(_docstring_constant(node))
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def identifiers(path: Path) -> set[str]:
    """ชื่อทุกชื่อที่โค้ดในไฟล์นั้นอ้างถึง — ไม่รวมข้อความและ docstring

    ใช้ถามว่า "โค้ดนี้ใช้ของชิ้นนั้นจริงไหม" ซึ่งต่างจากการค้นข้อความทั้งไฟล์
    ที่จะเจอชื่อในเอกสารที่อธิบายว่าทำไม **ไม่** ใช้ของชิ้นนั้น
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute, ast.alias)):
            found.update(_identifier(node).split("."))
    return found - {""}


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
