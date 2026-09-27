"""ปิดพาร์ทิชันใหม่ให้เองด้วยกลไก ไม่ใช่ด้วยการจำ

Revision ID: 0006
Revises: 0005

ฟังก์ชันสร้างพาร์ทิชันของ 0003 กันได้เฉพาะคนที่เรียกมัน คนที่สร้างพาร์ทิชันด้วยมือ
ยังหลุด ซึ่งอ่อนกว่ากฎอื่นในสเปกที่บังคับด้วยกลไกทั้งหมด
(เจ้าของอนุมัติเพิ่ม 2026-09-27 — plan.md ข้อ 1.1)

ไฟล์นี้มีสองอย่าง:

1. ตัวปิดพาร์ทิชันที่ **รันซ้ำได้** เพราะทั้งฟังก์ชันสร้างพาร์ทิชันและ event trigger
   จะเรียกมันในคำสั่งเดียวกัน
2. `tiewtrade_protect_all_partitions()` ที่ไล่ปิดพาร์ทิชันที่ยังไม่ถูกปิดทั้งฐานข้อมูล
   ใช้ทั้งใน event trigger และใช้ซ่อมฐานข้อมูลที่มีอยู่แล้ว

**`CREATE EVENT TRIGGER` ไม่อยู่ในไฟล์นี้** เพราะต้องใช้ superuser ซึ่งเป็นสิ่งที่
บทบาทที่รัน migration ต้องไม่มี (F-03 RQ-5.1) ตัว event trigger อยู่ใน
`backend/db/bootstrap/10-event-trigger.sql`

**ขอบเขต:** กันความผิดพลาดของคนทำงานปกติ **ไม่ใช่รับประกันป้องกัน superuser**
คนที่เป็น superuser ปิด event trigger ได้เหมือนที่ปิด trigger อื่นได้ (RQ-20)
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

RUNTIME_ROLES = (
    "tiewtrade_api",
    "tiewtrade_engine",
    "tiewtrade_engine_scan",
    "tiewtrade_market_data",
)
_RUNTIME_ROLE_SQL_ARRAY = ", ".join(f"'{role}'" for role in RUNTIME_ROLES)

# ── ตัวปิดพาร์ทิชัน รุ่นที่รันซ้ำได้ ────────────────────────────────────────
_PROTECT_PARTITION_IDEMPOTENT = f"""
CREATE OR REPLACE FUNCTION tiewtrade_protect_partition(target regclass) RETURNS void
    LANGUAGE plpgsql
AS $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[{_RUNTIME_ROLE_SQL_ARRAY}]
    LOOP
        EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %s FROM %I', target, role_name);
    END LOOP;

    -- รันซ้ำได้: ทั้งฟังก์ชันสร้างพาร์ทิชันและ event trigger เรียกตัวนี้ในคำสั่งเดียวกัน
    -- trigger ระดับแถวถูกโคลนมาจากตารางแม่แล้ว ที่ต้องสร้างเองคือ TRUNCATE
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgrelid = target
          AND tgname = 'tiewtrade_append_only_statement'
          AND NOT tgisinternal
    ) THEN
        EXECUTE format(
            'CREATE TRIGGER tiewtrade_append_only_statement'
            ' BEFORE TRUNCATE ON %s'
            ' FOR EACH STATEMENT EXECUTE FUNCTION tiewtrade_reject_mutation()',
            target
        );
    END IF;
END
$$
"""

# ── ตัวตั้ง policy รุ่นที่รันซ้ำได้ ─────────────────────────────────────────
# ต้องรันซ้ำได้เพราะ event trigger ตั้ง policy ให้พาร์ทิชันไปแล้วตอน CREATE TABLE
# แล้วฟังก์ชันสร้างพาร์ทิชันจะเรียกตัวนี้ต่อในคำสั่งเดียวกัน
_APPLY_OWNER_POLICY_IDEMPOTENT = """
CREATE OR REPLACE FUNCTION tiewtrade_apply_owner_policy(
    target regclass,
    owner_column text
) RETURNS void
    LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', target);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', target);

    IF EXISTS (
        SELECT 1 FROM pg_policy
        WHERE polrelid = target AND polname = 'tiewtrade_owner_only'
    ) THEN
        RETURN;
    END IF;

    EXECUTE format(
        'CREATE POLICY tiewtrade_owner_only ON %s'
        ' FOR ALL USING (%I = tiewtrade_current_user_id())'
        ' WITH CHECK (%I = tiewtrade_current_user_id())',
        target, owner_column, owner_column
    );
END
$$
"""

# ── คัดลอก policy จากตารางแม่ด้วยข้อความของเงื่อนไขเดิม ────────────────────
# ไม่เดาชื่อคอลัมน์เจ้าของ เพราะการเดาจะพลาดเงียบ ๆ กับตารางที่ตั้งชื่อคอลัมน์ต่างไป
# รูปแบบ policy ที่ยังไม่รองรับต้อง **ล้มเหลว** เพื่อให้ DDL ถูกยกเลิกทั้งคำสั่ง
_CLONE_PARENT_POLICIES = """
CREATE FUNCTION tiewtrade_clone_parent_policies(child regclass) RETURNS void
    LANGUAGE plpgsql
AS $$
DECLARE
    parent oid;
    policy record;
BEGIN
    SELECT inhparent INTO parent FROM pg_inherits WHERE inhrelid = child;
    IF parent IS NULL THEN
        RETURN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE oid = parent AND relrowsecurity) THEN
        RETURN;
    END IF;

    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', child);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', child);

    FOR policy IN
        SELECT polname,
               polcmd,
               polpermissive,
               pg_get_expr(polqual, polrelid) AS using_expr,
               pg_get_expr(polwithcheck, polrelid) AS check_expr
        FROM pg_policy
        WHERE polrelid = parent
    LOOP
        IF EXISTS (
            SELECT 1 FROM pg_policy
            WHERE polrelid = child AND polname = policy.polname
        ) THEN
            CONTINUE;
        END IF;

        -- รองรับเฉพาะรูปแบบที่ระบบนี้ใช้จริง: policy แบบ FOR ALL ที่มีทั้ง USING
        -- และ WITH CHECK รูปแบบอื่นต้องล้มเหลว ไม่ใช่คัดลอกไปครึ่ง ๆ กลาง ๆ
        -- แล้วปล่อยให้พาร์ทิชันมีการป้องกันไม่ครบ
        IF policy.polcmd <> '*' OR policy.using_expr IS NULL OR policy.check_expr IS NULL THEN
            RAISE EXCEPTION
                'คัดลอก policy % ของ % ไปยังพาร์ทิชัน % ไม่ได้'
                ' เพราะยังไม่รองรับรูปแบบนี้ —'
                ' ให้สร้างพาร์ทิชันผ่าน tiewtrade_create_monthly_partition'
                ' หรือขยายตัวคัดลอกก่อน',
                policy.polname, parent::regclass, child
                USING ERRCODE = 'TT003';
        END IF;

        EXECUTE format(
            'CREATE POLICY %I ON %s FOR ALL USING (%s) WITH CHECK (%s)',
            policy.polname, child, policy.using_expr, policy.check_expr
        );
    END LOOP;
END
$$
"""

# ── ไล่ปิดพาร์ทิชันที่ยังไม่ถูกปิดทั้งฐานข้อมูล ──────────────────────────────
# ใช้ทั้งใน event trigger และใช้ซ่อมฐานข้อมูลที่มีอยู่แล้ว (plan.md ข้อ 1.1 เงื่อนไข ง)
_PROTECT_ALL_PARTITIONS = """
CREATE FUNCTION tiewtrade_protect_all_partitions() RETURNS integer
    LANGUAGE plpgsql
AS $$
DECLARE
    child oid;
    protected integer := 0;
BEGIN
    FOR child IN
        SELECT i.inhrelid
        FROM pg_inherits AS i
        WHERE EXISTS (
                -- ตารางแม่ที่เปิดกลไกไว้ ดูจาก trigger ระดับแถวที่กลไกสร้าง
                SELECT 1 FROM pg_trigger AS t
                WHERE t.tgrelid = i.inhparent
                  AND t.tgname = 'tiewtrade_append_only_row'
                  AND NOT t.tgisinternal
            )
          AND NOT EXISTS (
                SELECT 1 FROM pg_trigger AS t
                WHERE t.tgrelid = i.inhrelid
                  AND t.tgname = 'tiewtrade_append_only_statement'
                  AND NOT t.tgisinternal
            )
    LOOP
        PERFORM tiewtrade_protect_partition(child::regclass);
        PERFORM tiewtrade_clone_parent_policies(child::regclass);
        protected := protected + 1;
    END LOOP;

    RETURN protected;
END
$$
"""

# ── ตัวที่ event trigger เรียก ─────────────────────────────────────────────
# ตรวจก่อนว่ากลไกถูกติดตั้งแล้ว เพื่อให้ฐานข้อมูลที่ยังไม่รัน migration
# ไม่ล้มเหลวตอน migration แรกสร้างตาราง
# `CREATE OR REPLACE` เพราะ bootstrap สร้างตัวชั่วคราวที่ไม่ทำอะไรไว้ก่อนแล้ว
# เพื่อให้ event trigger ติดตั้งได้ก่อน migration (ดู db/bootstrap/10-event-trigger.sql)
_EVENT_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION tiewtrade_protect_partitions_on_ddl() RETURNS event_trigger
    LANGUAGE plpgsql
AS $$
BEGIN
    IF to_regprocedure('tiewtrade_protect_all_partitions()') IS NULL THEN
        RETURN;
    END IF;
    PERFORM tiewtrade_protect_all_partitions();
END
$$
"""


def upgrade() -> None:
    op.execute(_PROTECT_PARTITION_IDEMPOTENT)
    op.execute(_APPLY_OWNER_POLICY_IDEMPOTENT)
    op.execute(_CLONE_PARENT_POLICIES)
    op.execute(_PROTECT_ALL_PARTITIONS)
    op.execute(_EVENT_TRIGGER_FUNCTION)

    for signature in (
        "tiewtrade_clone_parent_policies(regclass)",
        "tiewtrade_protect_all_partitions()",
        "tiewtrade_protect_partitions_on_ddl()",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO tiewtrade_migrator")

    # ฐานข้อมูลที่สร้างพาร์ทิชันไว้ก่อนมีกลไกนี้ ต้องถูกซ่อมตอน migrate
    op.execute("SELECT tiewtrade_protect_all_partitions()")


def downgrade() -> None:
    # **ห้าม DROP ตัวที่ event trigger เรียก** เพราะ event trigger อยู่ใน bootstrap
    # ไม่ได้อยู่ใน migration ถ้าลบฟังก์ชันทิ้ง คำสั่ง CREATE TABLE ทุกคำสั่งหลังจากนั้น
    # จะล้มเหลวเพราะ event trigger เรียกของที่ไม่มีอยู่ — คืนเป็นตัวที่ไม่ทำอะไรแทน
    op.execute(_EVENT_TRIGGER_FUNCTION)
    op.execute("DROP FUNCTION tiewtrade_protect_all_partitions()")
    op.execute("DROP FUNCTION tiewtrade_clone_parent_policies(regclass)")
    # คืนตัวตั้ง policy เป็นรุ่นของ 0003 ซึ่งไม่ได้เขียนให้รันซ้ำ
    op.execute(
        """
        CREATE OR REPLACE FUNCTION tiewtrade_apply_owner_policy(
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
    )
    # คืนตัวปิดพาร์ทิชันเป็นรุ่นของ 0003 ซึ่งไม่ได้เขียนให้รันซ้ำ
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION tiewtrade_protect_partition(target regclass) RETURNS void
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
                'CREATE TRIGGER tiewtrade_append_only_statement'
                ' BEFORE TRUNCATE ON %s'
                ' FOR EACH STATEMENT EXECUTE FUNCTION tiewtrade_reject_mutation()',
                target
            );
        END
        $$
        """
    )
