"""เขียนสัญญา API (OpenAPI) ลงไฟล์ เพื่อให้หน้าบ้านสร้างชนิดข้อมูลจากไฟล์นี้

CI จะสร้างใหม่แล้วเทียบกับไฟล์ที่ commit ไว้ ถ้าต่างกันถือว่าแดง (P-5)
ทำให้ชนิดข้อมูลสองฝั่งหลุดกันไม่ได้โดยไม่มีใครรู้
"""

import json
import sys
from pathlib import Path

from tiewtrade.services.api.app import app

DEFAULT_OUTPUT = Path(__file__).parents[4] / "openapi.json"


def main(output: Path = DEFAULT_OUTPUT) -> int:
    schema = app.openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    output.write_text(text, encoding="utf-8")
    sys.stdout.write(f"เขียนสัญญา API ลง {output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
