"""ถังคุมอัตราของเส้นทางที่บทบาท `api` รับผิดชอบ (F-07)

Revision ID: 0010
Revises: 0009

**ตารางใหม่ ไม่ใช่เปิด `auth_throttle` ให้บทบาทเพิ่ม** (เจ้าของอนุมัติ 2026-10-04 —
`plan.md` ข้อ 12.1) `auth_throttle` ให้สิทธิ์เฉพาะ `tiewtrade_auth` ซึ่งเป็นบทบาทเดียว
ที่แตะข้อมูลเข้าสู่ระบบ การเปิดให้บทบาทที่รับคำขอจากอินเทอร์เน็ตเขียนลงไปด้วย
แปลว่าบั๊กฝั่ง `api` ล้างโควตากันเดารหัสผ่านของ F-05 ได้ — เงียบ ๆ

**ตรรกะ token bucket ไม่ถูกคัดลอก** โค้ดเดิมใน `infra/auth/throttle.py` รับชื่อตาราง
เข้ามา แล้วทั้งสองที่เรียกตัวเดียวกัน · ที่แยกคือ **ที่เก็บกับสิทธิ์** ไม่ใช่ตรรกะ

**ไม่อยู่ใต้ RLS ด้วยเหตุผลเดียวกับ `auth_throttle`** — มันเป็นตัวนับ ไม่ใช่ข้อมูลผู้ใช้
และคีย์เป็นแฮช ขอบเขตความเสียหายถูกจำกัดด้วยสิทธิ์ที่ให้บทบาทเดียว

**ยังไม่มีงานเก็บกวาดแถวเก่า** เหมือน `auth_throttle` — เป็นงาน **F-31**
"""

from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

#: ชนิดถังของงานนี้ — **ทั้งคู่เป็น token bucket** และแยกกันเพราะมีต้นทุนต่างกัน
#:
#: การเพิ่ม key ยิงตลาดหนึ่งครั้งและกินที่เก็บความลับหนึ่งแถว ส่วนการกดลองใหม่
#: แค่ปลุกงานที่มีอยู่แล้ว — เกณฑ์ที่เหมาะจึงต่างกัน และต้องปรับแยกกันได้
_KINDS = ("API_KEY_ADD", "API_KEY_RETRY")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


_TABLE = f"""
CREATE TABLE api_throttle (
    bucket_kind text NOT NULL,
    bucket_key text NOT NULL,
    window_started_at timestamptz NOT NULL DEFAULT now(),
    failures integer NOT NULL DEFAULT 0,
    next_allowed_at timestamptz,
    tokens_left integer,
    refilled_at timestamptz,
    PRIMARY KEY (bucket_kind, bucket_key),
    CONSTRAINT api_throttle_kind CHECK (bucket_kind IN ({_quoted(_KINDS)})),
    CONSTRAINT api_throttle_key_shape CHECK (bucket_key ~ '^[0-9a-f]{{64}}$'),
    CONSTRAINT api_throttle_failures CHECK (failures >= 0),
    CONSTRAINT api_throttle_tokens CHECK (tokens_left IS NULL OR tokens_left >= 0),
    -- **ทุกถังของตารางนี้เป็น token bucket** ฉะนั้นสองช่องนี้ต้องมีค่าเสมอ
    -- รูปเดียวกับที่ `0008` บังคับกับ `auth_throttle` แต่ที่นั่นมีสองชนิดปนกัน
    CONSTRAINT api_throttle_bucket_shape CHECK (
        tokens_left IS NOT NULL AND refilled_at IS NOT NULL
    )
)
"""


def upgrade() -> None:
    op.execute(_TABLE)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON api_throttle TO tiewtrade_api")


def downgrade() -> None:
    op.execute("DROP TABLE api_throttle")
