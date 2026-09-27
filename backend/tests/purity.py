"""ตัวตรวจความบริสุทธิ์ของ core — อ่านโครงสร้างโค้ด ไม่ใช่ค้นข้อความ (P-7)

ทำไมต้องอ่านโครงสร้าง: การค้นข้อความพลาดได้ทั้งสองทาง — จับคำที่อยู่ในคอมเมนต์
หรือใน docstring ผิด ๆ และมองไม่เห็นการเรียกที่เขียนอ้อม

ทำไมต้องตรวจแยกจาก import-linter: การอ่านไฟล์ นาฬิกา ค่าสุ่ม และ socket
อยู่ใน standard library ทั้งหมด จึงผ่านกฎ import ของ import-linter ได้
สองเรื่องนี้แยกกัน (specs/standards/architecture.md หัวข้อ 1-2, RQ-7)

**ตัวตรวจต้องติดตาม alias ของ import** ไม่เช่นนั้น `from datetime import datetime as dt`
แล้วเรียก `dt.now()` จะหลุด (รีวิว 2026-09-27 ข้อ S-1)

**ตรวจไลบรารีภายนอกด้วยรายการที่อนุญาต ไม่ใช่รายการที่ห้าม** เพราะรายการที่ห้าม
ต้องตามเติมชื่อทุกครั้งที่เพิ่ม dependency แล้วจะลืม (รีวิว 2026-09-27 ข้อ S-3)
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

#: module ที่ core ห้าม import เลย แม้อยู่ใน standard library
FORBIDDEN_MODULES: dict[str, str] = {
    "random": "ค่าสุ่ม",
    "secrets": "ค่าสุ่ม",
    "socket": "เครือข่าย",
    "ssl": "เครือข่าย",
    "urllib": "เครือข่าย",
    "http": "เครือข่าย",
    "ftplib": "เครือข่าย",
    "smtplib": "เครือข่าย",
    "asyncio": "เครือข่ายและนาฬิกา",
    "pathlib": "การอ่านไฟล์",
    "io": "การอ่านไฟล์",
    "os": "ระบบปฏิบัติการ",
    "subprocess": "ระบบปฏิบัติการ",
    "sqlite3": "ฐานข้อมูล",
    "logging": "ผลข้างเคียง",
}

#: ชื่อเต็มของการเรียกที่ห้าม เทียบหลังคลี่ alias แล้ว
#: `datetime` กับ `time` import ได้เพราะใช้เป็นชนิดข้อมูลได้ แต่ห้ามเรียกเอาเวลาปัจจุบัน
FORBIDDEN_CALLS: dict[str, str] = {
    "open": "การอ่านไฟล์",
    "input": "ผลข้างเคียง",
    "print": "ผลข้างเคียง",
    "datetime.datetime.now": "นาฬิกา",
    "datetime.datetime.today": "นาฬิกา",
    "datetime.datetime.utcnow": "นาฬิกา",
    "datetime.date.today": "นาฬิกา",
    "time.time": "นาฬิกา",
    "time.time_ns": "นาฬิกา",
    "time.monotonic": "นาฬิกา",
    "time.monotonic_ns": "นาฬิกา",
    "time.perf_counter": "นาฬิกา",
    "time.sleep": "นาฬิกา",
}

#: ชื่อ package ของโค้ดในโปรเจกต์นี้ที่ core อาจ import ได้ (ตัวมันเอง)
LOCAL_PACKAGES: frozenset[str] = frozenset({"tiewtrade"})


@dataclass(frozen=True)
class Violation:
    """การละเมิดหนึ่งจุด"""

    path: Path
    line: int
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} [{self.kind}] {self.detail}"


def _dotted_name(node: ast.expr) -> str:
    """คืนชื่อแบบต่อจุดของ expression ที่เป็นชื่อหรือ attribute"""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


class _PurityVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[Violation] = []
        #: ชื่อที่ใช้ในไฟล์ -> ชื่อเต็มจริง เช่น {"dt": "datetime.datetime"}
        self.aliases: dict[str, str] = {}

    def _add(self, node: ast.AST, kind: str, detail: str) -> None:
        line = getattr(node, "lineno", 0)
        self.violations.append(Violation(self.path, line, kind, detail))

    def _check_module(self, node: ast.AST, module: str, statement: str) -> None:
        root = module.split(".")[0]
        if root in FORBIDDEN_MODULES:
            self._add(node, "forbidden-import", f"{statement} ({FORBIDDEN_MODULES[root]})")
            return
        # ไลบรารีภายนอกทั้งหมดถูกห้าม ตรวจด้วยรายการที่อนุญาต
        if root not in sys.stdlib_module_names and root not in LOCAL_PACKAGES:
            self._add(
                node,
                "external-import",
                f"{statement} — core ใช้ได้เฉพาะ standard library",
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(node, alias.name, f"import {alias.name}")
            bound = alias.asname or alias.name.split(".")[0]
            self.aliases[bound] = alias.name if alias.asname else alias.name.split(".")[0]
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            self.generic_visit(node)
            return
        self._check_module(node, node.module, f"from {node.module}")
        for alias in node.names:
            bound = alias.asname or alias.name
            self.aliases[bound] = f"{node.module}.{alias.name}"
        self.generic_visit(node)

    def _resolve(self, dotted: str) -> str:
        """คลี่ alias ของส่วนแรกออกเป็นชื่อเต็ม"""
        if not dotted:
            return dotted
        head, _, rest = dotted.partition(".")
        resolved_head = self.aliases.get(head, head)
        return f"{resolved_head}.{rest}" if rest else resolved_head

    def visit_Call(self, node: ast.Call) -> None:
        resolved = self._resolve(_dotted_name(node.func))
        if resolved in FORBIDDEN_CALLS:
            self._add(node, "forbidden-call", f"{resolved}() ({FORBIDDEN_CALLS[resolved]})")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "float":
            self._add(node, "float", "ใช้ชนิด float ซึ่งห้ามในโค้ดที่แตะเงิน")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, float):
            self._add(node, "float", f"ค่าคงที่ทศนิยมลอยตัว {node.value!r}")
        self.generic_visit(node)


def check_file(path: Path) -> list[Violation]:
    """ตรวจไฟล์เดียว"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = _PurityVisitor(path)
    visitor.visit(tree)
    return visitor.violations


def check_tree(root: Path) -> list[Violation]:
    """ตรวจทุกไฟล์ .py ใต้โฟลเดอร์ที่ให้มา"""
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        violations.extend(check_file(path))
    return violations
