"""ขยายกลไก append-only ให้ครอบตารางที่แบ่งพาร์ทิชัน

Revision ID: 0003
Revises: 0002

F-03 สร้าง `tiewtrade_make_append_only()` ไว้ตอนที่ยังไม่มีตารางที่แบ่งพาร์ทิชัน
พอ F-04 ต้องใช้จึงพบสองช่องที่ยังไม่ถูกปิด:

1. **`TRUNCATE` ที่พาร์ทิชันโดยตรง** — trigger ระดับ statement ที่ผูกกับตารางแม่
   ไม่ถูกโคลนไปที่พาร์ทิชัน
2. **สิทธิ์ของพาร์ทิชัน** — พาร์ทิชันมี ACL ของตัวเอง ไม่ได้รับมาจากตารางแม่

ส่วน trigger **ระดับแถว** ที่สร้างบนตารางแม่ PostgreSQL โคลนไปให้พาร์ทิชันเองอยู่แล้ว
การสร้างซ้ำที่พาร์ทิชันจะชนชื่อกัน จึงต้องไม่สร้าง

**แก้ฟังก์ชันเดิม ไม่สร้างฟังก์ชันที่สอง** (plan.md ข้อ 1) เพราะถ้ามีสองตัว คนที่มาทีหลัง
ต้องรู้ว่าตารางของตัวเองเป็นแบบไหนแล้วเลือกให้ถูก ซึ่งเป็นการเลือกที่พลาดได้และ
ไม่มีอะไรเตือน (`AGENTS.md` — ตรรกะเดียวกันต้องอยู่ที่เดียว)
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

#: บทบาททั้งหมดที่ใช้ตอนทำงานปกติ — ต้องตรงกับ 0001
RUNTIME_ROLES = (
    "tiewtrade_api",
    "tiewtrade_engine",
    "tiewtrade_engine_scan",
    "tiewtrade_market_data",
)

_RUNTIME_ROLE_SQL_ARRAY = ", ".join(f"'{role}'" for role in RUNTIME_ROLES)

# ── ตัวปิดพาร์ทิชันหนึ่งตัว: ตัดสิทธิ์ + trigger ของ TRUNCATE ───────────────
_PROTECT_PARTITION = f"""
CREATE FUNCTION tiewtrade_protect_partition(target regclass) RETURNS void
    LANGUAGE plpgsql
AS $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[{_RUNTIME_ROLE_SQL_ARRAY}]
    LOOP
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %s FROM %I', target, role_name);
    END LOOP;

    -- trigger ระดับแถวถูกโคลนมาจากตารางแม่แล้ว สร้างซ้ำจะชนชื่อ
    -- ที่ต้องสร้างเองคือ TRUNCATE ซึ่งเป็นเหตุการณ์ระดับ statement และไม่ถูกโคลน
    EXECUTE format(
        'CREATE TRIGGER tiewtrade_append_only_statement'
        ' BEFORE TRUNCATE ON %s'
        ' FOR EACH STATEMENT EXECUTE FUNCTION tiewtrade_reject_mutation()',
        target
    );
END
$$
"""

# ── ฟังก์ชันเดิม รุ่นที่รู้จักตารางที่แบ่งพาร์ทิชัน ─────────────────────────
_MAKE_APPEND_ONLY_V2 = f"""
CREATE OR REPLACE FUNCTION tiewtrade_make_append_only(target regclass) RETURNS void
    LANGUAGE plpgsql
AS $$
DECLARE
    role_name text;
    partition_oid oid;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[{_RUNTIME_ROLE_SQL_ARRAY}]
    LOOP
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %s FROM %I', target, role_name);
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

    -- พาร์ทิชันที่มีอยู่แล้วต้องถูกปิดทีละตัว เพราะสิทธิ์และ trigger ของ TRUNCATE
    -- ไม่ตกทอดจากตารางแม่ (พาร์ทิชันที่สร้างภายหลังปิดโดย
    -- tiewtrade_create_monthly_partition / tiewtrade_create_default_partition)
    FOR partition_oid IN
        SELECT inhrelid FROM pg_inherits WHERE inhparent = target
    LOOP
        PERFORM tiewtrade_protect_partition(partition_oid::regclass);
    END LOOP;
END
$$
"""

# ── ฟังก์ชันเดิมรุ่นของ 0001 — ใช้ตอน downgrade ────────────────────────────
_MAKE_APPEND_ONLY_V1 = f"""
CREATE OR REPLACE FUNCTION tiewtrade_make_append_only(target regclass) RETURNS void
    LANGUAGE plpgsql
AS $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[{_RUNTIME_ROLE_SQL_ARRAY}]
    LOOP
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %s FROM %I', target, role_name);
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

# ── ตัวสร้างพาร์ทิชัน — ทำสามอย่างให้เสร็จในตัว ────────────────────────────
# RLS, policy และ append-only อยู่ในฟังก์ชันเดียว จึงลืมทีละอย่างไม่ได้
#
# RLS ต้องตั้งที่พาร์ทิชันด้วย เพราะ query ที่ระบุชื่อพาร์ทิชันโดยตรงใช้ policy
# ของพาร์ทิชันนั้น ไม่ใช่ของตารางแม่ (plan.md ข้อ 4)
_CREATE_MONTHLY_PARTITION = """
CREATE FUNCTION tiewtrade_create_monthly_partition(
    parent regclass,
    month_start date,
    owner_column text
) RETURNS regclass
    LANGUAGE plpgsql
AS $$
DECLARE
    partition_name text;
    created regclass;
BEGIN
    partition_name := format('%s_%s', parent::text, to_char(month_start, 'YYYY_MM'));

    BEGIN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF %s FOR VALUES FROM (%L) TO (%L)',
            partition_name, parent, month_start, month_start + interval '1 month'
        );
    EXCEPTION
        WHEN check_violation OR invalid_object_definition OR object_not_in_prerequisite_state THEN
            -- เกิดเมื่อมีแถวของเดือนนี้อยู่ในพาร์ทิชันปลายทางแล้ว
            -- ย้ายแถวออกไม่ได้เพราะกลไก append-only ห้าม และเราจะไม่เปิดช่องนั้น
            -- (plan.md ข้อ 3) จึงต้องดังพร้อมบอกสาเหตุ ไม่ใช่ข้ามไปเงียบ ๆ
            RAISE EXCEPTION
                'สร้างพาร์ทิชัน % ไม่ได้ เพราะมีแถวของเดือนนั้นอยู่ในพาร์ทิชันปลายทางแล้ว'
                ' ข้อมูลยังอยู่ครบและอ่านผ่านตารางแม่ได้ตามปกติ'
                ' แถวเดิมย้ายไม่ได้เพราะบันทึกแก้ย้อนหลังไม่ได้ —'
                ' ป้องกันด้วยการสร้างพาร์ทิชันล่วงหน้าให้พอ', partition_name
                USING ERRCODE = 'TT002';
    END;

    created := partition_name::regclass;
    PERFORM tiewtrade_protect_partition(created);
    PERFORM tiewtrade_apply_owner_policy(created, owner_column);
    RETURN created;
END
$$
"""

_CREATE_DEFAULT_PARTITION = """
CREATE FUNCTION tiewtrade_create_default_partition(
    parent regclass,
    owner_column text
) RETURNS regclass
    LANGUAGE plpgsql
AS $$
DECLARE
    partition_name text;
    created regclass;
BEGIN
    partition_name := format('%s_default', parent::text);
    EXECUTE format('CREATE TABLE %I PARTITION OF %s DEFAULT', partition_name, parent);

    created := partition_name::regclass;
    PERFORM tiewtrade_protect_partition(created);
    PERFORM tiewtrade_apply_owner_policy(created, owner_column);
    RETURN created;
END
$$
"""

# ── policy ของเจ้าของแถว ใช้ได้กับทั้งตารางแม่และพาร์ทิชัน ─────────────────
_APPLY_OWNER_POLICY = """
CREATE FUNCTION tiewtrade_apply_owner_policy(
    target regclass,
    owner_column text
) RETURNS void
    LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', target);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', target);
    EXECUTE format(
        'CREATE POLICY tiewtrade_owner_only ON %s'
        ' FOR ALL USING (%I = tiewtrade_current_user_id())'
        ' WITH CHECK (%I = tiewtrade_current_user_id())',
        target, owner_column, owner_column
    );
END
$$
"""


def upgrade() -> None:
    op.execute(_PROTECT_PARTITION)
    op.execute(_APPLY_OWNER_POLICY)
    op.execute(_MAKE_APPEND_ONLY_V2)
    op.execute(_CREATE_MONTHLY_PARTITION)
    op.execute(_CREATE_DEFAULT_PARTITION)

    # ค่าเริ่มต้นคือปฏิเสธ แล้วเปิดเท่าที่จำเป็น — ทั้งสี่ตัวเป็นงานของเจ้าของโครงสร้าง
    for signature in (
        "tiewtrade_protect_partition(regclass)",
        "tiewtrade_apply_owner_policy(regclass, text)",
        "tiewtrade_create_monthly_partition(regclass, date, text)",
        "tiewtrade_create_default_partition(regclass, text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO tiewtrade_migrator")


def downgrade() -> None:
    op.execute("DROP FUNCTION tiewtrade_create_default_partition(regclass, text)")
    op.execute("DROP FUNCTION tiewtrade_create_monthly_partition(regclass, date, text)")
    op.execute("DROP FUNCTION tiewtrade_apply_owner_policy(regclass, text)")
    op.execute(_MAKE_APPEND_ONLY_V1)
    op.execute("DROP FUNCTION tiewtrade_protect_partition(regclass)")
