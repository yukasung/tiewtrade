"""ดึงและแปลงรายการรหัสผ่านที่ห้ามใช้ — **คนสั่งเอง ไม่ใช่เทสต์** (F-05 plan.md ข้อ 5)

NIST SP 800-63B-4 กำหนดให้เทียบรหัสผ่านใหม่กับรายการที่พบบ่อยหรือที่เคยรั่ว
ไฟล์ผลลัพธ์เก็บลง repo เพื่อให้การตรวจ **ไม่ต้องเรียกบริการข้างนอกตอนทำงาน**
และให้ผลเหมือนเดิมทุกครั้ง

เรียกใช้:

```sh
uv run python scripts/refresh_password_blocklist.py              # ปักที่ commit ที่บันทึกไว้
uv run python scripts/refresh_password_blocklist.py --commit SHA # เปลี่ยนรุ่น
```

**ปักด้วย commit ไม่ใช่ "ล่าสุด"** เพราะรายการต้องทำซ้ำได้ และคนรีวิวต้องเห็นว่า
รุ่นไหนเปลี่ยนเป็นรุ่นไหน

**เก็บเป็นแฮช ไม่ใช่รหัสผ่านต้นฉบับ** เพื่อไม่ให้ repo กลายเป็นคลังรหัสผ่าน
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import httpx

from tiewtrade.core.passwords import MINIMUM_LENGTH

DESTINATION: Final = (
    Path(__file__).parents[1] / "src" / "tiewtrade" / "infra" / "auth" / "password_blocklist"
)

#: รายการต้นทาง — SecLists สัญญาอนุญาต MIT
REPOSITORY: Final = "danielmiessler/SecLists"
SOURCE_PATH: Final = "Passwords/Common-Credentials/100k-most-used-passwords-NCSC.txt"
LICENCE: Final = "MIT (SecLists)"

#: commit ที่ปักไว้ — อัปเดตด้วย `--commit` แล้วไฟล์กำกับจะเปลี่ยนตาม
PINNED_COMMIT: Final = "1a7bb9127eca9e6ff2fc0301c597fe6e16a0cb56"


def main() -> None:
    parsed = argparse.ArgumentParser(description=__doc__)
    parsed.add_argument("--commit", default=PINNED_COMMIT, help="commit ของ SecLists ที่จะดึง")
    commit = str(parsed.parse_args().commit)

    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{SOURCE_PATH}"
    print(f"ดึง {SOURCE_PATH} ที่ commit {commit[:12]}")  # noqa: T201
    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()

    source_entries, digests = _digests_of(response.text)

    DESTINATION.mkdir(parents=True, exist_ok=True)
    (DESTINATION / "hashes.txt").write_text("\n".join(sorted(digests)) + "\n", encoding="utf-8")
    (DESTINATION / "manifest.json").write_text(
        json.dumps(
            {
                "source_url": url,
                "source_commit": commit,
                "retrieved_on": datetime.now(UTC).date().isoformat(),
                "source_entries": source_entries,
                "kept_entries": len(digests),
                "licence": LICENCE,
                "minimum_length": MINIMUM_LENGTH,
                "note": (
                    "เก็บเฉพาะรายการที่ยาวตั้งแต่ขั้นต่ำของนโยบายขึ้นไป"
                    " เพราะรายการที่สั้นกว่านั้นถูกกฎความยาวปฏิเสธไปก่อนแล้ว"
                ),
            },
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(  # noqa: T201
        f"ต้นทาง {source_entries} รายการ · เก็บไว้ {len(digests)} รายการ"
        f" (ตัดที่สั้นกว่า {MINIMUM_LENGTH} ตัวอักษรออก)"
    )


def _digests_of(body: str) -> tuple[int, set[str]]:
    """แปลงรายการเป็นแฮช — ขั้นตอนต้องตรงกับ `blocklist.digest_of()` ทุกขั้น

    ตัดอักขระท้ายบรรทัด → normalise NFC → **ไม่แปลงตัวพิมพ์** (รหัสผ่านแยกตัวพิมพ์)
    → ตัดรายการที่สั้นกว่าขั้นต่ำ → ตัดรายการซ้ำ → แฮช
    """
    source_entries = 0
    digests: set[str] = set()
    for line in body.splitlines():
        entry = unicodedata.normalize("NFC", line.rstrip("\r"))
        if not entry:
            continue
        source_entries += 1
        if len(entry) < MINIMUM_LENGTH:
            continue
        digests.add(hashlib.sha256(entry.encode("utf-8")).hexdigest())
    return source_entries, digests


if __name__ == "__main__":
    main()
