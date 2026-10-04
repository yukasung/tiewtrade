"""ด่าน: โค้ดต้องไปถึง endpoint ที่ย้ายเงินออกจากบัญชีผู้ใช้ไม่ได้ (F-07 RQ-16)

**ทำไมต้องมีด่านนี้ทั้งที่ไม่มีใครตั้งใจเขียนโค้ดถอนเงิน** — NC-16 ยังเปิดอยู่:
เราไม่รู้ว่า API key ของตลาดนี้ถอนเงินได้หรือไม่ และผู้ใช้ไม่มีช่องให้ปิดสิทธิ์นั้น
สิ่งที่เรากันได้จริงจึงไม่ใช่ "สิทธิ์ของ key" แต่คือ **ความสามารถของโค้ดเราเอง**
(`trading-safety.md` หัวข้อ 2 · `requirements.md` RQ-16)

**ชั้นที่บังคับจริงคือชนิดข้อมูล** — ตัวส่งคำขอรับเฉพาะสมาชิกของ `Endpoint`
ฉะนั้นเส้นทางที่ไม่ได้ประกาศไว้ **สร้างขึ้นมาไม่ได้** ไฟล์นี้คือชั้นที่สองกับสาม:
ตรวจว่าไม่มีใครประกาศสมาชิกที่ย้ายเงิน และไม่มีสตริงของเส้นทางเหล่านั้นหลงเหลืออยู่

**ด่านค้นสตริงอย่างเดียวพิสูจน์อะไรไม่ได้** เส้นทางที่ประกอบจากตัวแปรจะผ่านมันไปได้
— เขียนไว้ตรงนี้เพื่อไม่ให้ใครอ่านด่านนี้แล้วเข้าใจว่ามันคือการป้องกันทั้งหมด
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

#: ชิ้นส่วนของเส้นทางที่ย้ายเงินออกจากบัญชีผู้ใช้ หรือย้ายระหว่างบัญชี
#:
#: เขียนเป็นชิ้นส่วน ไม่ใช่เส้นทางเต็ม เพราะตลาดเปลี่ยนรุ่นของ path ได้
#: (`/api/v1/...` เป็น `/api/v3/...`) แล้วรายการที่จำเส้นทางเต็มจะพลาดทันที
FORBIDDEN_PATH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "withdraw",
        "transfer",
        "sub-account",
        "subaccount",
        "universal",
    }
)


@dataclass(frozen=True, slots=True)
class Violation:
    """จุดที่ผิดหนึ่งจุด"""

    path: Path
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} [{self.rule}] {self.detail}"


def _offending_fragment(text: str) -> str | None:
    """ชิ้นส่วนต้องห้ามที่พบในข้อความที่อาจกลายเป็นเส้นทาง

    จับสองรูป:

    1. **ข้อความที่ขึ้นต้นด้วย `/`** และมีชิ้นส่วนต้องห้ามอยู่ข้างใน — เส้นทางที่เขียนตรง ๆ
    2. **ข้อความที่ *เท่ากับ* ชิ้นส่วนต้องห้ามพอดี** — ชิ้นส่วนที่รอประกอบเป็นเส้นทาง
       (`f"{prefix}/{action}"`) ซึ่งรูปแรกมองไม่เห็น

    **ไม่จับคำที่โผล่กลางข้อความธรรมดา** เช่นคำอธิบายภาษาไทยที่พูดถึงการโอนเงิน
    เพราะด่านที่ดังผิดบ่อยคือด่านที่คนเลิกเชื่อ ซึ่งแย่กว่าไม่มีด่าน

    **ยังมีช่องที่รูปนี้มองไม่เห็น** เช่นการต่อสตริงทีละตัวอักษร — เป็นเหตุผลที่
    ชั้นที่บังคับจริงคือชนิดข้อมูลของ `Endpoint` ไม่ใช่ด่านนี้
    """
    lowered = text.lower()
    if lowered in FORBIDDEN_PATH_FRAGMENTS:
        return lowered
    if not text.startswith("/"):
        return None
    for fragment in sorted(FORBIDDEN_PATH_FRAGMENTS):
        if fragment in lowered:
            return fragment
    return None


def check_no_money_paths(path: Path) -> list[Violation]:
    """ไฟล์นี้ต้องไม่มีสตริงของเส้นทางที่ย้ายเงิน"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        fragment = _offending_fragment(node.value)
        if fragment is not None:
            violations.append(
                Violation(
                    path,
                    node.lineno,
                    "money-moving-path",
                    f"เส้นทางที่ย้ายเงิน ({fragment!r}) ปรากฏในโค้ด",
                )
            )

    return violations


def check_tree(root: Path) -> list[Violation]:
    """ตรวจทุกไฟล์ `.py` ใต้โฟลเดอร์หนึ่ง"""
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        violations.extend(check_no_money_paths(path))
    return violations
