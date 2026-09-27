"""ตาราง users — ผู้ใช้จริงรายแรกของกลไก RLS

Revision ID: 0002
Revises: 0001

ตารางนี้เล็กที่สุดเท่าที่กลไกต้องใช้ (Q-1) — ไม่มีอีเมล รหัสผ่าน หรือ TOTP
ซึ่งเป็นงาน F-05 ที่จะเพิ่มคอลัมน์ตาม RQ-19

`id` **เป็นคอลัมน์เจ้าของของตัวเอง** (Q-1.1 เจ้าของตัดสิน 2026-09-27)
ไม่มีคอลัมน์ `owner_id` ซ้ำ ข้อยกเว้นนี้บันทึกไว้ใน `standards/database.md` หัวข้อ 3

เวลาสร้างแก้ไม่ได้ด้วย **สิทธิ์ระดับคอลัมน์** (RQ-10.1) — บทบาทที่ใช้ตอนทำงานปกติ
ได้ `INSERT (id)` เท่านั้น ส่งค่า `created_at` มาเองจึงถูกปฏิเสธ ไม่ใช่ถูกเมิน
และไม่มีบทบาทไหนได้สิทธิ์ `UPDATE` คอลัมน์นั้น ค่าปริยายอย่างเดียวกันแค่กรณีไม่ส่งค่ามา
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    # RLS: ENABLE กันบทบาททั่วไป, FORCE ทำให้เจ้าของตารางอยู่ใต้ policy ด้วย
    # ไม่ให้มีข้อยกเว้นเงียบ ๆ สำหรับ migrator (plan.md ข้อ 3)
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")

    # USING กันอ่าน, WITH CHECK กันเขียนให้เป็นของผู้ใช้อื่น (Q-1.1 ข้อ 3)
    # ไม่ตั้งผู้ใช้ปัจจุบัน → เงื่อนไขไม่เป็นจริง → อ่านศูนย์แถวและเขียนถูกปฏิเสธ
    op.execute(
        """
        CREATE POLICY users_self_only ON users
            FOR ALL
            USING (id = tiewtrade_current_user_id())
            WITH CHECK (id = tiewtrade_current_user_id())
        """
    )

    # สิทธิ์รายคอลัมน์ — ไม่มีใครได้ UPDATE หรือ DELETE ในงานนี้
    op.execute("GRANT SELECT (id, created_at) ON users TO tiewtrade_api, tiewtrade_engine")
    op.execute("GRANT INSERT (id) ON users TO tiewtrade_api, tiewtrade_engine")

    # บทบาทกวาดรายการอ่านได้เท่าที่การกวาดต้องใช้ และเขียนไม่ได้เลย (Q-3 เงื่อนไข ก, ข)
    op.execute("GRANT SELECT (id, created_at) ON users TO tiewtrade_engine_scan")


def downgrade() -> None:
    op.execute("DROP TABLE users")
