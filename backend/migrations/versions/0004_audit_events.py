"""ตาราง audit_events — บันทึกทุกการกระทำที่แตะเงิน แก้ย้อนหลังไม่ได้

Revision ID: 0004
Revises: 0003

ข้อกำหนดอยู่ใน `specs/features/2026-09-27-audit-log/requirements.md`

`details` จำกัดด้วย **รายการที่อนุญาต ไม่ใช่รายการที่ห้าม** (plan.md ข้อ 2)
`CHECK` ตัวเดียวทำสองอย่าง: จำกัดชนิดเหตุการณ์ และจำกัดรูปร่างของ `details`
ของเหตุการณ์นั้น — `ELSE false` ทำให้ชนิดที่ยังไม่ได้ประกาศเขียนไม่ได้เลย

**ทุกชนิดเหตุการณ์ที่เพิ่มภายหลังต้องประกาศรูปร่างของ `details` ของตัวเองที่นี่**
ในงานเดียวกับที่เพิ่มชนิดนั้น ไม่ใช่ตามเก็บทีหลัง และ **ช่องข้อความอิสระห้ามโดยปริยาย**
ถ้าจำเป็นต้องมีจริง ต้องขออนุมัติเป็นรายช่อง (RQ-4, RQ-18)

**ไม่มี foreign key ไป `users`** (RQ-17) สองทางที่เป็นไปได้ล้วนผิด: ผูกแบบลบต่อกัน
จะลบบันทึกทิ้งเมื่อลบผู้ใช้ ซึ่ง `trading-safety.md` หัวข้อ 9 ห้าม ส่วนผูกแบบห้ามลบ
จะทำให้ลบผู้ใช้ไม่ได้เลย ซึ่งเป็นการตัดสิน NC-11 ล่วงหน้า
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

#: จำนวนเดือนที่สร้างพาร์ทิชันล่วงหน้า — พาร์ทิชันปลายทางรับส่วนที่เลยไป
MONTHS_AHEAD = 12

_TABLE = """
CREATE TABLE audit_events (
    id uuid NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    owner_user_id uuid NOT NULL,
    actor_kind text NOT NULL,
    actor_id uuid,
    action text NOT NULL,
    subject_kind text NOT NULL,
    subject_id text NOT NULL,
    mode text NOT NULL,
    outcome text NOT NULL,
    failure_code text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- คีย์หลักต้องมีคีย์ของพาร์ทิชันอยู่ด้วย ตามที่ PostgreSQL บังคับ
    CONSTRAINT audit_events_pkey PRIMARY KEY (recorded_at, id),

    CONSTRAINT audit_events_actor_kind CHECK (
        actor_kind IN ('USER', 'BOT', 'SYSTEM', 'PLATFORM')
    ),
    CONSTRAINT audit_events_mode CHECK (
        mode IN ('PAPER', 'LIVE', 'NOT_APPLICABLE')
    ),
    CONSTRAINT audit_events_outcome CHECK (
        outcome IN ('SUCCEEDED', 'FAILED', 'REJECTED')
    ),
    CONSTRAINT audit_events_details_is_object CHECK (
        jsonb_typeof(details) = 'object'
    ),

    -- ชนิดเหตุการณ์และรูปร่างของ details ของเหตุการณ์นั้น อยู่ในข้อเดียวกัน
    -- เพื่อไม่ให้มีทางประกาศชนิดใหม่โดยลืมประกาศรูปร่าง
    CONSTRAINT audit_events_action_details CHECK (
        CASE action
            WHEN 'USER_CREATED' THEN details = '{}'::jsonb
            ELSE false
        END
    )
) PARTITION BY RANGE (recorded_at)
"""

_COMMENT = """
COMMENT ON TABLE audit_events IS
    'บันทึกการกระทำที่แตะเงิน เพิ่มได้อย่างเดียว (F-04). '
    'ยังไม่กำหนดอายุข้อมูลและยังไม่ลบอะไรเลย ซึ่งเป็นข้อยกเว้นชั่วคราวจาก '
    'specs/standards/database.md หัวข้อ 7 สำหรับช่วงพัฒนา (F-04 RQ-21) — '
    'ต้องเคาะนโยบายเก็บข้อมูลก่อนเปิดให้ลูกค้าจริงใช้ ดูเงื่อนไขจุดปล่อยที่ 2 ใน specs/roadmap.md'
"""


def upgrade() -> None:
    op.execute(_TABLE)
    op.execute(_COMMENT)

    # ดัชนีเท่าที่ใช้จริง: ไล่ดูเหตุการณ์ของผู้ใช้หนึ่งคน และสืบสวนตามชนิดเหตุการณ์
    op.execute(
        "CREATE INDEX audit_events_owner_recorded_at"
        " ON audit_events (owner_user_id, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX audit_events_action_recorded_at ON audit_events (action, recorded_at DESC)"
    )

    # RLS ที่ตารางแม่ — พาร์ทิชันได้ของตัวเองจากตัวสร้างพาร์ทิชัน (0003)
    op.execute("SELECT tiewtrade_apply_owner_policy('audit_events'::regclass, 'owner_user_id')")

    # สิทธิ์: เขียนได้ อ่านได้ แต่ไม่มีใครแก้หรือลบได้ (RQ-8)
    # ไม่ให้เขียน recorded_at เพื่อให้เวลามาจากฐานข้อมูลเท่านั้น (RQ-6)
    op.execute(
        "GRANT INSERT (id, owner_user_id, actor_kind, actor_id, action,"
        " subject_kind, subject_id, mode, outcome, failure_code, details)"
        " ON audit_events TO tiewtrade_api, tiewtrade_engine"
    )
    op.execute("GRANT SELECT ON audit_events TO tiewtrade_api, tiewtrade_engine")
    # บทบาทกวาดรายการไม่ได้สิทธิ์อะไรเลยกับตารางนี้ — งานกวาดไม่ต้องอ่าน audit log
    # การให้สิทธิ์อ่านข้ามผู้ใช้กับบันทึกทั้งระบบคือการเปิดช่องที่ไม่มีใครขอ (plan.md ข้อ 4)

    op.execute("SELECT tiewtrade_make_append_only('audit_events'::regclass)")

    # พาร์ทิชันปลายทางมาก่อน เพื่อให้ไม่มีช่วงเวลาไหนที่เขียนแล้วล้มเหลว
    op.execute(
        "SELECT tiewtrade_create_default_partition('audit_events'::regclass, 'owner_user_id')"
    )
    for offset in range(MONTHS_AHEAD):
        op.execute(
            "SELECT tiewtrade_create_monthly_partition("
            "    'audit_events'::regclass,"
            f"   (date_trunc('month', now()) + interval '{offset} month')::date,"
            "    'owner_user_id')"
        )


def downgrade() -> None:
    # ลบตารางแม่ลบพาร์ทิชันทั้งหมดไปด้วย
    op.execute("DROP TABLE audit_events")
