"""โครงพื้นฐาน — domain ของเงินและหน่วย, กลไก RLS, กลไก append-only

Revision ID: 0001
Revises:

ที่มาของตัวเลขใน SQL (plan.md ข้อ 5)
-----------------------------------
`STORED_SCALE = 18` และ `MAX_ABS = 1E+20` ในไฟล์นี้เป็น **snapshot** ที่อ่านมาจาก
`tiewtrade.core.money.limits` ตอนจัดทำ revision นี้ ไม่ได้ import ตอนรัน migration
เพราะ revision ที่ merge แล้วคือประวัติของโครงสร้าง ถ้าให้มัน import ค่าคงที่ของ runtime
โครงสร้างในอดีตจะเปลี่ยนตามโค้ดวันนี้ แล้ว replay จะให้ผลไม่เหมือนเดิม

**เมื่อค่ากลางเปลี่ยน ต้องมี revision ใหม่** ห้ามแก้ไฟล์นี้ย้อนหลัง
เทสต์ตรวจว่า domain ที่ head ตรงกับ `Money` ทั้งสองทิศ (validation.md V-25)

ทำไม `NUMERIC` ไม่บังคับ scale
------------------------------
`NUMERIC(38,18)` ปัดค่าที่ทศนิยมเกินให้เองเงียบ ๆ ค่า `0.0000000000000000001`
จะกลายเป็น `0` ก่อนที่ `CHECK` จะได้เห็นค่าจริง ซึ่งเป็นการฝากการปัดให้ฐานข้อมูล
(F-02 RQ-9 ห้ามไว้) การใช้ `NUMERIC` เปล่าทำให้ค่าดิบถึง `CHECK` ครบ
แล้วฐานข้อมูลปฏิเสธเองได้แม้โค้ดพลาด (RQ-9.1)

`min_scale()` นับทศนิยมจริงโดยไม่นับศูนย์ท้าย ให้ผลตรงกับ `real_decimal_places()`
ของ F-02 — `1.0000000000000000000` ผ่าน แต่ `0.0000000000000000001` ไม่ผ่าน
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

#: บทบาททั้งหมดที่ใช้ตอนทำงานปกติ — ไม่รวม migrator
RUNTIME_ROLES = (
    "tiewtrade_api",
    "tiewtrade_engine",
    "tiewtrade_engine_scan",
    "tiewtrade_market_data",
)

#: ทุกบทบาท รวมเจ้าของโครงสร้าง
ALL_ROLES = ("tiewtrade_migrator", *RUNTIME_ROLES)

_ROLE_LIST = ", ".join(ALL_ROLES)
_RUNTIME_ROLE_SQL_ARRAY = ", ".join(f"'{role}'" for role in RUNTIME_ROLES)


def upgrade() -> None:
    # ── ความละเอียดของเงิน — snapshot จาก core.money.limits ──────────────
    op.execute(
        """
        CREATE DOMAIN tiewtrade_money_amount AS NUMERIC
            CONSTRAINT tiewtrade_money_amount_finite CHECK (
                VALUE <> 'NaN'::numeric
                AND VALUE > '-Infinity'::numeric
                AND VALUE < 'Infinity'::numeric
            )
            CONSTRAINT tiewtrade_money_amount_scale CHECK (
                min_scale(VALUE) <= 18
            )
            CONSTRAINT tiewtrade_money_amount_range CHECK (
                abs(VALUE) < 1E+20
            )
        """
    )

    # หน่วยเก็บคู่กับจำนวนเสมอ — กฎรูปแบบหน่วยจริงอยู่ที่ normalise_unit ของ F-02
    # ที่เดียว ที่นี่กันแค่ค่าว่าง ไม่เขียนกฎซ้ำและไม่ตั้งเพดานความยาวขึ้นเอง
    op.execute(
        """
        CREATE DOMAIN tiewtrade_unit_code AS TEXT
            CONSTRAINT tiewtrade_unit_code_not_blank CHECK (
                btrim(VALUE) <> ''
            )
        """
    )

    # ── กลไก RLS — ผู้ใช้ปัจจุบันของ transaction นี้ ─────────────────────
    # คืนค่าว่างเมื่อยังไม่ถูกตั้ง ไม่โยนข้อผิดพลาด เพราะ policy ต้องเทียบค่าได้
    # ผลคือไม่ตั้ง = เทียบไม่เป็นจริง = อ่านศูนย์แถวและเขียนถูกปฏิเสธ (Q-2 เงื่อนไข ค)
    op.execute(
        """
        CREATE FUNCTION tiewtrade_current_user_id() RETURNS uuid
            LANGUAGE sql
            STABLE
        AS $$
            SELECT nullif(current_setting('tiewtrade.current_user_id', true), '')::uuid
        $$
        """
    )

    # ── กลไกตารางที่แก้ย้อนหลังไม่ได้ ────────────────────────────────────
    op.execute(
        """
        CREATE FUNCTION tiewtrade_reject_mutation() RETURNS trigger
            LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'ตารางนี้แก้ย้อนหลังไม่ได้ (%)', TG_OP
                USING ERRCODE = 'TT001';
        END
        $$
        """
    )

    # เปิดกลไกทีละตาราง ตามขอบเขตที่เจ้าของระบุ (RQ-7) — ตารางทั่วไปไม่ถูกแตะ
    # ทำสองชั้นในตัวเดียว: ตัดสิทธิ์ และผูก trigger
    # TRUNCATE เป็นสิทธิ์และเหตุการณ์ trigger คนละตัวกับ DELETE จึงต้องระบุแยก
    op.execute(
        f"""
        CREATE FUNCTION tiewtrade_make_append_only(target regclass) RETURNS void
            LANGUAGE plpgsql
        AS $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY[{_RUNTIME_ROLE_SQL_ARRAY}]
            LOOP
                EXECUTE format(
                    'REVOKE UPDATE, DELETE, TRUNCATE ON %s FROM %I', target, role_name
                );
            END LOOP;

            EXECUTE format(
                'CREATE TRIGGER tiewtrade_append_only_row'
                ' BEFORE UPDATE OR DELETE ON %s'
                ' FOR EACH ROW EXECUTE FUNCTION tiewtrade_reject_mutation()',
                target
            );
            EXECUTE format(
                'CREATE TRIGGER tiewtrade_append_only_statement'
                ' BEFORE TRUNCATE ON %s'
                ' FOR EACH STATEMENT EXECUTE FUNCTION tiewtrade_reject_mutation()',
                target
            );
        END
        $$
        """
    )

    # รายชื่อตารางที่เปิดกลไกไว้ — อ่านจาก pg_trigger จริง ไม่ใช่ทะเบียนที่เขียนเอง
    # ทะเบียนที่เขียนเองจะไม่ตรงกับความจริงเมื่อมีคนลืมอัปเดต
    op.execute(
        """
        CREATE VIEW tiewtrade_append_only_tables AS
        SELECT c.oid::regclass::text AS table_name
        FROM pg_class AS c
        WHERE EXISTS (
                SELECT 1 FROM pg_trigger AS t
                WHERE t.tgrelid = c.oid
                  AND t.tgname = 'tiewtrade_append_only_row'
                  AND NOT t.tgisinternal
            )
          AND EXISTS (
                SELECT 1 FROM pg_trigger AS t
                WHERE t.tgrelid = c.oid
                  AND t.tgname = 'tiewtrade_append_only_statement'
                  AND NOT t.tgisinternal
            )
        """
    )

    # ── สิทธิ์: ค่าเริ่มต้นคือปฏิเสธ แล้วเปิดเท่าที่จำเป็น (RQ-5) ─────────
    op.execute("REVOKE ALL ON FUNCTION tiewtrade_current_user_id() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION tiewtrade_reject_mutation() FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION tiewtrade_make_append_only(regclass) FROM PUBLIC")

    op.execute(f"GRANT EXECUTE ON FUNCTION tiewtrade_current_user_id() TO {_ROLE_LIST}")
    op.execute(f"GRANT SELECT ON tiewtrade_append_only_tables TO {_ROLE_LIST}")

    # เปิดกลไก append-only ได้เฉพาะเจ้าของโครงสร้าง (RQ-5.1)
    op.execute(
        "GRANT EXECUTE ON FUNCTION tiewtrade_make_append_only(regclass) TO tiewtrade_migrator"
    )


def downgrade() -> None:
    op.execute("DROP VIEW tiewtrade_append_only_tables")
    op.execute("DROP FUNCTION tiewtrade_make_append_only(regclass)")
    op.execute("DROP FUNCTION tiewtrade_reject_mutation()")
    op.execute("DROP FUNCTION tiewtrade_current_user_id()")
    op.execute("DROP DOMAIN tiewtrade_unit_code")
    op.execute("DROP DOMAIN tiewtrade_money_amount")
