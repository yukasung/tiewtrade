"""จำกัดคอลัมน์แกนของบันทึกตามชนิดเหตุการณ์

Revision ID: 0005
Revises: 0004

0004 จำกัดเฉพาะ `details` แต่ **คอลัมน์แกนที่เป็นข้อความก็รับอะไรก็ได้**
`subject_id` และ `failure_code` จึงเป็นทางที่ค่าลับและข้อมูลระบุตัวตนเข้ามาได้
ซึ่งขัดกับ RQ-4 และ RQ-18 (พบจากรีวิว 2026-09-27)

ชั้นโค้ดมีข้อบังคับรายเหตุการณ์อยู่แล้ว ไฟล์นี้ปิดเส้นทางที่ **ไม่ผ่านตัวเขียน**
ตามหลักเดียวกับที่ใช้ทั้ง F-03 และ F-04: ฐานข้อมูลต้องปฏิเสธเองได้แม้โค้ดพลาด

**ทุกชนิดเหตุการณ์ที่เพิ่มภายหลังต้องเพิ่มเงื่อนไขของคอลัมน์แกนที่นี่ด้วย**
ไม่ใช่แค่รูปร่างของ `details` — และ `failure_code` ต้องประกาศทีละรหัส
(ตอนนี้ยังไม่มีรหัสไหนเลย จึงบังคับให้เป็นค่าว่าง)
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_OLD_CONSTRAINT = """
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_action_details CHECK (
        CASE action
            WHEN 'USER_CREATED' THEN details = '{}'::jsonb
            ELSE false
        END
    )
"""

# เงื่อนไขรวมของแต่ละชนิดเหตุการณ์: ทั้ง details และคอลัมน์แกน
#
# `USER_CREATED` — ผู้ใช้สร้างตัวเอง ฉะนั้นผู้กระทำและเป้าหมายต้องเป็นคนเดียวกับ
# เจ้าของบันทึก และไม่มีอะไรให้บันทึกเพิ่ม
_NEW_CONSTRAINT = """
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_action_shape CHECK (
        CASE action
            WHEN 'USER_CREATED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'
            ELSE false
        END
    )
"""

# ยังไม่มีรหัสความล้มเหลวที่ประกาศไว้ — ต้องเป็นค่าว่างจนกว่าจะมี migration ที่เพิ่มรหัส
_FAILURE_CODE_CONSTRAINT = """
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_failure_code CHECK (failure_code IS NULL)
"""


def upgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_details")
    op.execute(_NEW_CONSTRAINT)
    op.execute(_FAILURE_CODE_CONSTRAINT)


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_OLD_CONSTRAINT)
