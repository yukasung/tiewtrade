"""ตาข่ายชั้นที่สอง — กันค่าลับและข้อมูลระบุตัวตนที่หลุดเข้า `details`

**หลักประกันหลักคือรายการที่อนุญาตใน `events.py` ไม่ใช่ไฟล์นี้** (plan.md ข้อ 6)
ไฟล์นี้มีไว้จับกรณีที่รายละเอียดของเหตุการณ์ในอนาคตเปิดช่องไว้โดยไม่ควรเปิด
เช่นช่องที่รับ dict หรือรับข้อความอิสระที่เผลออนุมัติไป

ตรวจ **ที่ทางเขียน ไม่ใช่ที่ผู้เรียก** เพราะผู้เรียกจะมีหลายที่และจะลืม
"""

from __future__ import annotations

import re
from typing import Final

from tiewtrade.infra.db.errors import InfraError


class ForbiddenDetailError(InfraError):
    """รายละเอียดมีสิ่งที่ห้ามเก็บในบันทึก

    ข้อความของข้อผิดพลาดบอก **ชื่อคีย์เท่านั้น ไม่บอกค่า** เพราะค่าคือสิ่งที่ห้ามเก็บ
    การใส่ค่าลงในข้อความจะทำให้ค่านั้นไปอยู่ใน log แทน (RQ-4, `security.md` หัวข้อ 4)
    """

    code = "AUDIT_DETAIL_FORBIDDEN"


#: คำที่ห้ามปรากฏเป็นส่วนหนึ่งของชื่อคีย์ ทุกระดับความลึก
FORBIDDEN_KEY_PARTS: Final[frozenset[str]] = frozenset(
    {
        "secret",
        "password",
        "passwd",
        "token",
        "cookie",
        "apikey",
        "api_key",
        "credential",
        "email",
        "mail",
        "name",
        "phone",
        "tel",
        "address",
        "ip",
        "birth",
        "citizen",
        "passport",
    }
)

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def ensure_no_forbidden_content(details: object, path: str = "details") -> None:
    """ไล่ดูทุกระดับความลึก แล้วปฏิเสธคีย์ที่ห้ามและค่าที่เป็นอีเมล

    ค่าที่เป็นตัวเลขทศนิยมลอยตัวก็ถูกปฏิเสธ เพราะเงินต้องเก็บเป็นข้อความคู่กับหน่วย
    และ `float` ห้ามใช้ทุกที่ที่เกี่ยวกับเงิน (`AGENTS.md` กฎข้อ 6)
    """
    if isinstance(details, dict):
        for key, value in details.items():
            if not isinstance(key, str):
                raise ForbiddenDetailError(f"{path} มีคีย์ที่ไม่ใช่ข้อความ")
            _ensure_key_allowed(key, path)
            ensure_no_forbidden_content(value, f"{path}.{key}")
        return

    if isinstance(details, (list, tuple)):
        for index, value in enumerate(details):
            ensure_no_forbidden_content(value, f"{path}[{index}]")
        return

    if isinstance(details, float):
        raise ForbiddenDetailError(f"{path} เป็นทศนิยมลอยตัว ซึ่งห้ามใช้กับค่าที่เกี่ยวกับเงิน")

    if isinstance(details, str) and _EMAIL.search(details):
        raise ForbiddenDetailError(f"{path} มีค่าที่มีรูปแบบเป็นอีเมล")


def _ensure_key_allowed(key: str, path: str) -> None:
    flattened = key.lower().replace("-", "").replace("_", "")
    for part in FORBIDDEN_KEY_PARTS:
        if part.replace("_", "") in flattened:
            raise ForbiddenDetailError(f"{path}.{key} เป็นชื่อคีย์ที่ห้ามเก็บในบันทึก")
