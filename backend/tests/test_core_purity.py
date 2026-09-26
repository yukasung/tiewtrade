"""core ต้องบริสุทธิ์ (RQ-4, RQ-7)

ถ้าเทสต์นี้แดง **ให้แก้โค้ด ไม่ใช่แก้เทสต์**
(specs/standards/testing.md หัวข้อ 3)
"""

from pathlib import Path

from tests.purity import check_tree

CORE = Path(__file__).parents[1] / "src" / "core"


def test_core_is_pure() -> None:
    violations = check_tree(CORE)
    assert violations == [], "core ไม่บริสุทธิ์:\n" + "\n".join(str(v) for v in violations)
