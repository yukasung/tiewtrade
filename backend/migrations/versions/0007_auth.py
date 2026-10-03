"""ข้อมูลเข้าสู่ระบบ, session และตัวนับอัตราการเรียก (F-05)

Revision ID: 0007
Revises: 0006

**ทุกตารางที่เก็บข้อมูลผู้ใช้อยู่ใต้ RLS และไม่มีทางข้าม RLS เพิ่มใหม่**
(`database.md` หัวข้อ 3) สิ่งที่ต้องทำงาน "ก่อนรู้ว่าเป็นผู้ใช้คนไหน" ทำได้ด้วย
ตัวแปรประจำ transaction สองตัว ซึ่งเป็นกลไกเดียวกับ `tiewtrade.current_user_id`
ของ F-03:

- `tiewtrade.presented_token_hash` — **แฮชของโทเคน** ที่ผู้เรียกพามา
  ฐานข้อมูลไม่เคยเห็นโทเคนจริง
- `tiewtrade.presented_email` — อีเมลที่กรอกตอนเข้าสู่ระบบ

**ไม่ตั้งตัวแปร = อ่านศูนย์แถว** จึงเป็นการพลาดแบบปิดประตู

สิทธิ์แยกตามบทบาท (`requirements.md` Q-8):

- `tiewtrade_api` — แตะ `sessions` ได้เท่าที่ถือโทเคนอยู่ · **ออก session ใหม่ไม่ได้**
  · เปลี่ยนเจ้าของ แฮช เวลาเริ่ม หรือเพดานอายุรวมไม่ได้ · **แตะ `user_credentials`
  ไม่ได้เลย**
- `tiewtrade_auth` — บทบาทเดียวที่แตะข้อมูลเข้าสู่ระบบและออก session ได้
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

#: ชนิดเหตุการณ์ที่งานนี้เพิ่ม — ต้องตรงกับ `AuditAction` ในโค้ด (F-04 Q-1)
_NEW_ACTIONS = ("SESSION_STARTED", "SESSION_ENDED", "ALL_SESSIONS_ENDED", "PASSWORD_CHANGED")

# เงื่อนไขของคอลัมน์แกนต่อชนิดเหตุการณ์ — เขียนใหม่ทั้งก้อนเพราะ `CHECK` แทนที่กันไม่ได้
#
# ทุกเหตุการณ์ของงานนี้เป็นการกระทำที่ผู้ใช้ทำกับตัวเอง ฉะนั้นผู้กระทำและเป้าหมาย
# ต้องเป็นเจ้าของบันทึก และไม่มีอะไรให้บันทึกเพิ่มนอกจากจำนวน session ที่ถูกเพิกถอน
_SELF_ACTION = """
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'
"""

_SHAPE_WITH_SESSIONS = f"""
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_action_shape CHECK (
        CASE action
            WHEN 'USER_CREATED' THEN {_SELF_ACTION}
            WHEN 'SESSION_STARTED' THEN {_SELF_ACTION}
            WHEN 'SESSION_ENDED' THEN {_SELF_ACTION}
            WHEN 'PASSWORD_CHANGED' THEN {_SELF_ACTION}
            WHEN 'ALL_SESSIONS_ENDED' THEN
                details - 'ended' = '{{}}'::jsonb
                AND jsonb_typeof(details -> 'ended') = 'number'
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'
            ELSE false
        END
    )
"""

# ตอนถอยกลับ เงื่อนไขเดิมรับแต่ `USER_CREATED` ขณะที่ตารางอาจมีบันทึกของชนิดใหม่อยู่แล้ว
# และ **ตารางนี้ลบแถวไม่ได้** ตามกลไกของ F-04 จึงเพิ่มเงื่อนไขแบบ `NOT VALID`:
# บังคับกับแถวใหม่ตั้งแต่นี้ไป และไม่ตรวจแถวเก่าย้อนหลัง
#
# ทางเลือกอื่นคือให้การถอยกลับล้มเหลวเมื่อมีบันทึกของชนิดใหม่ ซึ่งจะทำให้ถอยกลับไม่ได้เลย
# บนฐานข้อมูลที่เคยใช้งานจริง — เลือกทางนี้เพราะการถอยกลับต้องทำได้จริง
# และการไม่ตรวจย้อนหลังไม่ได้ทำให้ข้อมูลเก่าเปลี่ยนความหมาย
_SHAPE_BEFORE = f"""
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_action_shape CHECK (
        CASE action
            WHEN 'USER_CREATED' THEN {_SELF_ACTION}
            ELSE false
        END
    ) NOT VALID
"""


def upgrade() -> None:
    # ── ตัวแปรที่ policy อ่านได้ก่อนรู้ว่าเป็นผู้ใช้คนไหน ────────────────────
    op.execute(
        """
        CREATE FUNCTION tiewtrade_presented_token_hash() RETURNS text
            LANGUAGE sql
            STABLE
        AS $$
            SELECT nullif(current_setting('tiewtrade.presented_token_hash', true), '')
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION tiewtrade_presented_email() RETURNS text
            LANGUAGE sql
            STABLE
        AS $$
            SELECT nullif(current_setting('tiewtrade.presented_email', true), '')
        $$
        """
    )
    for function in ("tiewtrade_presented_token_hash()", "tiewtrade_presented_email()"):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION tiewtrade_presented_token_hash()"
        " TO tiewtrade_api, tiewtrade_auth"
    )
    op.execute("GRANT EXECUTE ON FUNCTION tiewtrade_presented_email() TO tiewtrade_auth")

    # `0001` ให้สิทธิ์เฉพาะบทบาทที่มีอยู่ตอนนั้น — ขาดข้อนี้ policy ทุกตัวที่เรียก
    # ฟังก์ชันนี้จะล้มด้วย "permission denied for function"
    op.execute("GRANT EXECUTE ON FUNCTION tiewtrade_current_user_id() TO tiewtrade_auth")

    # ── ข้อมูลเข้าสู่ระบบ ────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE user_credentials (
            user_id uuid PRIMARY KEY REFERENCES users (id),
            email text NOT NULL UNIQUE,
            password_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT user_credentials_email_length CHECK (
                char_length(email) BETWEEN 3 AND 254
            ),
            CONSTRAINT user_credentials_email_lowercase CHECK (email = lower(email))
        )
        """
    )
    op.execute("ALTER TABLE user_credentials ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_credentials FORCE ROW LEVEL SECURITY")

    # อ่านตอนเข้าสู่ระบบ: ได้ทีละอีเมลที่ระบุ — `SELECT` ครั้งเดียว dump ทั้งตารางไม่ได้
    op.execute(
        """
        CREATE POLICY user_credentials_by_email ON user_credentials
            FOR SELECT
            TO tiewtrade_auth
            USING (email = tiewtrade_presented_email())
        """
    )
    # หลังรู้ตัวตนแล้ว: แถวของตัวเองเท่านั้น (ใช้ตอนสมัครและตอนเปลี่ยนรหัสผ่าน)
    op.execute(
        """
        CREATE POLICY user_credentials_self ON user_credentials
            FOR ALL
            TO tiewtrade_auth
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )
    # ไม่ให้ `email` อยู่ในชุดที่แก้ได้ เพราะงานนี้ไม่เปลี่ยนอีเมล (Q-5)
    # และเวลามาจากฐานข้อมูล จึงไม่ให้เขียน `created_at`
    op.execute("GRANT SELECT ON user_credentials TO tiewtrade_auth")
    op.execute("GRANT INSERT (user_id, email, password_hash) ON user_credentials TO tiewtrade_auth")
    op.execute("GRANT UPDATE (password_hash, updated_at) ON user_credentials TO tiewtrade_auth")

    # ── session ──────────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE sessions (
            token_hash text PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users (id),
            started_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            idle_expires_at timestamptz NOT NULL,
            absolute_expires_at timestamptz NOT NULL,
            CONSTRAINT sessions_token_hash_shape CHECK (token_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT sessions_idle_within_absolute CHECK (
                idle_expires_at <= absolute_expires_at
            )
        )
        """
    )
    op.execute("CREATE INDEX sessions_by_user ON sessions (user_id)")
    op.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sessions FORCE ROW LEVEL SECURITY")

    # ผู้ถือโทเคนเห็นได้แถวเดียว — **ห้ามมี SELECT policy ที่อ้างตารางนี้เอง**
    # เพราะทำให้ PostgreSQL แจ้ง "infinite recursion detected in policy"
    op.execute(
        """
        CREATE POLICY sessions_presented ON sessions
            FOR SELECT
            TO tiewtrade_api
            USING (token_hash = tiewtrade_presented_token_hash())
        """
    )
    # ต่ออายุได้เฉพาะแถวที่ยังไม่หมดอายุ และเลื่อนเกินเพดานรวมไม่ได้
    op.execute(
        """
        CREATE POLICY sessions_renew ON sessions
            FOR UPDATE
            TO tiewtrade_api
            USING (
                token_hash = tiewtrade_presented_token_hash()
                AND now() < idle_expires_at
                AND now() < absolute_expires_at
            )
            WITH CHECK (idle_expires_at <= absolute_expires_at)
        """
    )
    op.execute(
        """
        CREATE POLICY sessions_end_one ON sessions
            FOR DELETE
            TO tiewtrade_api
            USING (token_hash = tiewtrade_presented_token_hash())
        """
    )
    # ออกจากระบบทุกเครื่อง — ผูกกับ **การถือโทเคนที่ยังใช้ได้** ไม่ใช่กับค่าผู้ใช้
    # ปัจจุบันที่แอปตั้งเอง · คำสั่งต้องเป็น `DELETE FROM sessions` ที่ไม่อ้างคอลัมน์
    # มิฉะนั้น PostgreSQL จะนำ SELECT policy มาใช้ด้วยแล้วลบได้แถวเดียว
    op.execute(
        """
        CREATE POLICY sessions_end_all ON sessions
            FOR DELETE
            TO tiewtrade_api
            USING (
                user_id = (
                    SELECT s.user_id
                    FROM sessions AS s
                    WHERE s.token_hash = tiewtrade_presented_token_hash()
                      AND now() < s.idle_expires_at
                      AND now() < s.absolute_expires_at
                )
            )
        """
    )
    # บทบาทยืนยันตัวตน: แถวของผู้ใช้ที่ระบุตัวแล้ว — ใช้ออก session และเพิกถอน
    # ตอนเปลี่ยนรหัสผ่าน (ซึ่งต้องเก็บเครื่องปัจจุบันไว้ จึงต้องอ้างคอลัมน์ได้)
    op.execute(
        """
        CREATE POLICY sessions_auth_owner ON sessions
            FOR ALL
            TO tiewtrade_auth
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )

    op.execute("GRANT SELECT, DELETE ON sessions TO tiewtrade_api, tiewtrade_auth")
    # เวลาเริ่มและเวลาใช้งานล่าสุดมาจากฐานข้อมูล จึงไม่อยู่ในชุดที่เขียนได้ตอน INSERT
    op.execute(
        "GRANT INSERT (token_hash, user_id, idle_expires_at, absolute_expires_at)"
        " ON sessions TO tiewtrade_auth"
    )
    # ต่ออายุได้สองคอลัมน์ — **ไม่มี `user_id`, `token_hash`, `started_at`
    # และ `absolute_expires_at`** จึงเปลี่ยนเจ้าของหรือยืดเพดานไม่ได้
    op.execute("GRANT UPDATE (last_seen_at, idle_expires_at) ON sessions TO tiewtrade_api")

    # ── ตัวนับอัตราการเรียก ──────────────────────────────────────────────
    #
    # **ไม่อยู่ใต้ RLS** — เจ้าของอนุมัติข้อยกเว้นนี้ (2026-10-02) ด้วยเหตุผลสองข้อ
    # ที่แก้ตามรีวิว 2026-10-03:
    #
    # 1. **หน้าที่ของตารางคือตัวนับร่วมของช่วงก่อนยืนยันตัวตน** — ต้องนับอีเมลที่
    #    ยังไม่มีบัญชี และ IP ที่คนหลายคนใช้ร่วมกัน การบังคับให้ทุกแถวมีเจ้าของใน
    #    `users` จึงขัดกับหน้าที่ของมันเอง ไม่ใช่แค่ไม่สะดวก
    # 2. **ขอบเขตความเสียหายถูกจำกัดด้วยสิทธิ์** — มีเพียงบทบาท `tiewtrade_auth`
    #    ที่แตะตารางนี้ได้ บทบาทที่รับคำขอทั่วไปไม่มีสิทธิ์ใด ๆ
    #
    # **"ไม่มีคอลัมน์เจ้าของ" ไม่ใช่เหตุผล** — มันเป็นผลของการออกแบบ ไม่ใช่หลักฐานว่า
    # ตารางนี้ไม่มีข้อมูลที่เกี่ยวกับผู้ใช้ และการแฮชก็ไม่ใช่การปกปิด เพราะเดาอีเมล
    # แล้วแฮชเทียบได้ (ดู `key_of()` ซึ่งเขียนข้อนี้กำกับไว้)
    #
    # **ยังไม่มีการลบแถวเก่าโดยอัตโนมัติ** — `claim()` รีเซ็ตตัวนับเมื่อหน้าต่างเวลา
    # ผ่านไปแล้วและมีการเรียกใช้อีกครั้ง ส่วนการลบแถวเกิดเฉพาะตอนเข้าสู่ระบบสำเร็จ
    # ของถังบัญชี ฉะนั้นแถวของ IP ที่ไม่กลับมาอีกจะค้างอยู่ — ต้องมีงานเก็บกวาด
    # ก่อนปล่อยผู้ใช้จริง (บันทึกใน `roadmap.md`)
    op.execute(
        """
        CREATE TABLE auth_throttle (
            bucket_kind text NOT NULL,
            bucket_key text NOT NULL,
            window_started_at timestamptz NOT NULL DEFAULT now(),
            failures integer NOT NULL DEFAULT 0,
            next_allowed_at timestamptz,
            PRIMARY KEY (bucket_kind, bucket_key),
            CONSTRAINT auth_throttle_kind CHECK (
                bucket_kind IN ('ACCOUNT', 'IP', 'SIGNUP_IP')
            ),
            CONSTRAINT auth_throttle_key_shape CHECK (bucket_key ~ '^[0-9a-f]{64}$'),
            CONSTRAINT auth_throttle_failures CHECK (failures >= 0)
        )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON auth_throttle TO tiewtrade_auth")

    # ── สิทธิ์ที่ migration เดิมให้เฉพาะบทบาทที่มีอยู่ตอนนั้น ──────────────
    op.execute("GRANT SELECT (id, created_at) ON users TO tiewtrade_auth")
    op.execute("GRANT INSERT (id) ON users TO tiewtrade_auth")
    op.execute(
        "GRANT INSERT (id, owner_user_id, actor_kind, actor_id, action,"
        " subject_kind, subject_id, mode, outcome, failure_code, details)"
        " ON audit_events TO tiewtrade_auth"
    )
    op.execute("GRANT SELECT ON audit_events TO tiewtrade_auth")

    # กฎ "เพิ่มได้อย่างเดียว" ของ `0001` ใช้รายชื่อบทบาทที่เขียนไว้ตอนนั้น
    # **ห้ามแก้ migration ที่รันไปแล้ว** จึงถอนสิทธิ์ให้บทบาทใหม่ที่นี่
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM tiewtrade_auth")

    # ── ชนิดเหตุการณ์ใหม่สี่ชนิด ─────────────────────────────────────────
    #
    # ชนิดที่อนุญาตถูกบังคับด้วย `CASE ... ELSE false` ใน `audit_events_action_shape`
    # อยู่แล้ว — ไม่มีรายการชนิดแยกอีกที่ จึงเขียนเงื่อนไขก้อนนั้นใหม่ทั้งก้อน
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_SHAPE_WITH_SESSIONS)


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_SHAPE_BEFORE)
    op.execute("REVOKE ALL ON audit_events FROM tiewtrade_auth")
    op.execute("REVOKE ALL ON users FROM tiewtrade_auth")
    op.execute("DROP TABLE auth_throttle")
    op.execute("DROP TABLE sessions")
    op.execute("DROP TABLE user_credentials")
    op.execute("REVOKE ALL ON FUNCTION tiewtrade_current_user_id() FROM tiewtrade_auth")
    op.execute("DROP FUNCTION tiewtrade_presented_email()")
    op.execute("DROP FUNCTION tiewtrade_presented_token_hash()")
