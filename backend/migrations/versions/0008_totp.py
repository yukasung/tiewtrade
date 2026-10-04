"""TOTP, รหัสสำรอง, ขั้นที่สองของการเข้าสู่ระบบ และสิทธิ์กู้บัญชี (F-06)

Revision ID: 0008
Revises: 0007

**ห้าตารางใหม่ และ `tiewtrade_api` ไม่มีสิทธิ์ใด ๆ บนทั้งห้า** — ทุกอย่างที่แตะ
ปัจจัยยืนยันตัวตนอยู่บนบทบาท `tiewtrade_auth` เท่านั้น เหมือนที่ `0007` ทำกับ
`user_credentials` (`requirements.md` RQ-10 · `plan.md` หัวข้อ 6)

**สองตารางสำหรับ secret ไม่ใช่ตารางเดียว** (`plan.md` หัวข้อ 1.6):

- `user_totp` — **มีแถว = เปิดใช้แล้ว** ไม่มีคอลัมน์สถานะ จึงไม่มีสถานะกำกวม
- `user_totp_pending` — secret ที่ยังไม่พิสูจน์ เขียนทับได้ **ไม่มีผลกับการยืนยันตัวตน**

ถ้ามี secret ช่องเดียว การเปลี่ยนเครื่องจะต้องเขียนทับก่อนผู้ใช้ยืนยัน ซึ่งเท่ากับ
เปิดใช้ปัจจัยที่ยังไม่พิสูจน์ หรือปิด TOTP ชั่วคราวโดยที่ผู้ใช้ไม่ได้สั่ง — ทั้งสองอย่าง
ทำให้ผู้ใช้ล็อกตัวเองออกได้

**`login_challenges` ไม่มีสิทธิ์ `UPDATE` ให้ใครเลย** จึงต่ออายุไม่ได้ และ "ผ่านแล้ว"
แสดงด้วยการลบแถวพร้อมออก session ใน transaction เดียว ไม่ใช่ด้วยการตั้งธง

**`recovery_grants` ตรวจอายุของ session จริง** ไม่พึ่ง `ON DELETE CASCADE` อย่างเดียว
เพราะ `CASCADE` ทำงานตอน **ลบ** แถว ไม่ใช่ตอน session **หมดอายุ** และ F-05 ไม่ลบ
แถวที่หมดอายุทิ้ง (`plan.md` หัวข้อ 6.5)

**ถังของ TOTP ใช้ token bucket** จึงเพิ่มสองคอลัมน์ที่ว่างได้ใน `auth_throttle`
และบังคับด้วย `CHECK` ว่าถังชนิดไหนต้องมีค่าและชนิดไหนต้องว่าง — ชนิดที่ไม่ได้
ประกาศเขียนลงไปไม่ได้เลย ตามแบบแผนของ F-04 (`plan.md` หัวข้อ 1.9)
"""

from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

#: ชนิดเหตุการณ์ที่งานนี้เพิ่ม — ต้องตรงกับ `AuditAction` ในโค้ด (F-04 Q-1)
_NEW_ACTIONS = (
    "TOTP_ENABLED",
    "TOTP_DISABLED",
    "TOTP_SECRET_REPLACED",
    "RECOVERY_CODES_ISSUED",
    "RECOVERY_CODE_USED",
)

#: ชนิดถังที่งานนี้เพิ่ม — **ทั้งสามเป็น token bucket** (`plan.md` หัวข้อ 1.9)
_TOKEN_BUCKETS = ("TOTP_ACCOUNT", "TOTP_IP", "RECOVERY_ACCOUNT")

#: ชนิดถังเดิมของ F-05 — หน้าต่างคงที่ ไม่มีโควตาคงเหลือ
_WINDOW_BUCKETS = ("ACCOUNT", "IP", "SIGNUP_IP")

_SELF_ACTION = """
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'
"""


def _self_action_counting(field: str) -> str:
    """เงื่อนไขของเหตุการณ์ที่ผู้ใช้ทำกับตัวเองและมีตัวเลขหนึ่งช่อง

    รูปเดียวกับ `ALL_SESSIONS_ENDED` ของ `0007` — เขียนเป็นฟังก์ชันเพราะงานนี้
    มีสองชนิดที่ใช้รูปนี้ และสองก้อนที่ต้องแก้ให้ตรงกันทุกครั้งคือสองก้อนที่จะต่างกันเอง
    """
    return f"""
                details - '{field}' = '{{}}'::jsonb
                AND jsonb_typeof(details -> '{field}') = 'number'
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'
"""


_SHAPE_WITH_TOTP = f"""
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_action_shape CHECK (
        CASE action
            WHEN 'USER_CREATED' THEN {_SELF_ACTION}
            WHEN 'SESSION_STARTED' THEN {_SELF_ACTION}
            WHEN 'SESSION_ENDED' THEN {_SELF_ACTION}
            WHEN 'PASSWORD_CHANGED' THEN {_SELF_ACTION}
            WHEN 'TOTP_ENABLED' THEN {_SELF_ACTION}
            WHEN 'TOTP_DISABLED' THEN {_SELF_ACTION}
            WHEN 'TOTP_SECRET_REPLACED' THEN {_SELF_ACTION}
            WHEN 'ALL_SESSIONS_ENDED' THEN {_self_action_counting("ended")}
            WHEN 'RECOVERY_CODES_ISSUED' THEN {_self_action_counting("issued")}
            WHEN 'RECOVERY_CODE_USED' THEN {_self_action_counting("remaining")}
            ELSE false
        END
    )
"""

# เหตุผลของ `NOT VALID` เหมือน `0007`: ตารางนี้ลบแถวไม่ได้ และการถอยกลับต้องทำได้จริง
# บนฐานข้อมูลที่เคยมีบันทึกของชนิดใหม่อยู่แล้ว
_SHAPE_BEFORE_TOTP = f"""
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_action_shape CHECK (
        CASE action
            WHEN 'USER_CREATED' THEN {_SELF_ACTION}
            WHEN 'SESSION_STARTED' THEN {_SELF_ACTION}
            WHEN 'SESSION_ENDED' THEN {_SELF_ACTION}
            WHEN 'PASSWORD_CHANGED' THEN {_SELF_ACTION}
            WHEN 'ALL_SESSIONS_ENDED' THEN {_self_action_counting("ended")}
            ELSE false
        END
    ) NOT VALID
"""


def _quoted(values: tuple[str, ...]) -> str:
    """รายการค่าในรูปที่ใส่ใน `IN (...)` ได้"""
    return ", ".join(f"'{value}'" for value in values)


_BUCKET_SHAPE = f"""
ALTER TABLE auth_throttle
    ADD CONSTRAINT auth_throttle_kind CHECK (
        bucket_kind IN ({_quoted(_WINDOW_BUCKETS + _TOKEN_BUCKETS)})
    ),
    ADD CONSTRAINT auth_throttle_bucket_shape CHECK (
        CASE
            WHEN bucket_kind IN ({_quoted(_TOKEN_BUCKETS)})
                THEN tokens_left IS NOT NULL AND refilled_at IS NOT NULL
            ELSE tokens_left IS NULL AND refilled_at IS NULL
        END
    )
"""

_BUCKET_SHAPE_BEFORE = f"""
ALTER TABLE auth_throttle
    ADD CONSTRAINT auth_throttle_kind CHECK (
        bucket_kind IN ({_quoted(_WINDOW_BUCKETS)})
    )
"""


def upgrade() -> None:
    # ── secret ที่เปิดใช้แล้ว ─────────────────────────────────────────────
    #
    # `user_id` เป็น PRIMARY KEY จึงบังคับ "หนึ่ง active secret ต่อผู้ใช้"
    # ที่ระดับฐานข้อมูล ไม่ใช่ด้วยเงื่อนไขในโค้ด (`requirements.md` Q-10)
    op.execute(
        """
        CREATE TABLE user_totp (
            user_id uuid PRIMARY KEY REFERENCES users (id),
            secret_sealed bytea NOT NULL,
            key_version text NOT NULL,
            secret_version integer NOT NULL,
            last_accepted_step bigint NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT user_totp_secret_version CHECK (secret_version >= 1),
            CONSTRAINT user_totp_step CHECK (last_accepted_step >= 0),
            CONSTRAINT user_totp_key_version_shape CHECK (key_version <> '')
        )
        """
    )
    op.execute("ALTER TABLE user_totp ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_totp FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY user_totp_self ON user_totp
            FOR ALL
            TO tiewtrade_auth
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )
    op.execute("GRANT SELECT, DELETE ON user_totp TO tiewtrade_auth")
    op.execute(
        "GRANT INSERT (user_id, secret_sealed, key_version, secret_version, last_accepted_step)"
        " ON user_totp TO tiewtrade_auth"
    )
    # **ไม่มี `user_id`** จึงเปลี่ยนเจ้าของแถวไม่ได้ · และไม่มี `created_at`
    # เพราะเวลาที่สร้างต้องไม่ถูกเขียนย้อนหลัง
    op.execute(
        "GRANT UPDATE (secret_sealed, key_version, secret_version, last_accepted_step, updated_at)"
        " ON user_totp TO tiewtrade_auth"
    )

    # ── secret ที่ยังไม่พิสูจน์ ────────────────────────────────────────────
    #
    # **ไม่มีผลกับการยืนยันตัวตนใด ๆ** การทิ้งแถวนี้ไว้จึงไม่ทำให้ผู้ใช้เสียอะไร
    # และเรียกตั้งค่าใหม่ทับได้เรื่อย ๆ (`plan.md` หัวข้อ 1.6)
    op.execute(
        """
        CREATE TABLE user_totp_pending (
            user_id uuid PRIMARY KEY REFERENCES users (id),
            secret_sealed bytea NOT NULL,
            key_version text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT user_totp_pending_key_version_shape CHECK (key_version <> '')
        )
        """
    )
    op.execute("ALTER TABLE user_totp_pending ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_totp_pending FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY user_totp_pending_self ON user_totp_pending
            FOR ALL
            TO tiewtrade_auth
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )
    op.execute("GRANT SELECT, DELETE ON user_totp_pending TO tiewtrade_auth")
    op.execute(
        "GRANT INSERT (user_id, secret_sealed, key_version) ON user_totp_pending TO tiewtrade_auth"
    )
    # ให้ `UPDATE` เพื่อให้เขียนทับด้วย `INSERT ... ON CONFLICT DO UPDATE` ได้
    op.execute("GRANT UPDATE (secret_sealed, key_version) ON user_totp_pending TO tiewtrade_auth")

    # ── รหัสสำรอง ────────────────────────────────────────────────────────
    #
    # **เก็บแฮช ไม่เก็บค่าจริง** และใช้ argon2 ตัวเดียวกับรหัสผ่าน จึงไม่มีค่าความแรง
    # ชุดที่สองให้ต้องดูแล (`plan.md` หัวข้อ 6.3)
    op.execute(
        """
        CREATE TABLE user_recovery_codes (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users (id),
            code_hash text NOT NULL,
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT user_recovery_codes_hash_shape CHECK (code_hash <> '')
        )
        """
    )
    op.execute("CREATE INDEX user_recovery_codes_by_user ON user_recovery_codes (user_id)")
    op.execute("ALTER TABLE user_recovery_codes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_recovery_codes FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY user_recovery_codes_self ON user_recovery_codes
            FOR ALL
            TO tiewtrade_auth
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )
    op.execute("GRANT SELECT, DELETE ON user_recovery_codes TO tiewtrade_auth")
    op.execute("GRANT INSERT (id, user_id, code_hash) ON user_recovery_codes TO tiewtrade_auth")
    # **ให้เขียนได้ช่องเดียว** จึงเปลี่ยนแฮชของรหัสสำรองที่ออกไปแล้วไม่ได้
    op.execute("GRANT UPDATE (used_at) ON user_recovery_codes TO tiewtrade_auth")

    # ── ขั้นที่สองของการเข้าสู่ระบบ ─────────────────────────────────────────
    #
    # เก็บ **แฮชของโทเคน** รูปแบบเดียวกับ `sessions` — ฐานข้อมูลไม่เคยเห็นโทเคนจริง
    # · `credential_updated_at` คือ **รุ่นของรหัสผ่าน** ตอนที่ออก challenge
    #   เพื่อให้ challenge ที่ออกด้วยรหัสผ่านเก่าใช้ต่อไม่ได้ (`plan.md` หัวข้อ 1.4)
    op.execute(
        """
        CREATE TABLE login_challenges (
            token_hash text PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users (id),
            credential_updated_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT login_challenges_token_hash_shape CHECK (token_hash ~ '^[0-9a-f]{64}$')
        )
        """
    )
    op.execute("CREATE INDEX login_challenges_by_user ON login_challenges (user_id)")
    op.execute("ALTER TABLE login_challenges ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE login_challenges FORCE ROW LEVEL SECURITY")
    # ก่อนรู้ว่าเป็นผู้ใช้คนไหน: เห็นได้แถวเดียวเท่าที่โทเคนที่พามาเปิดให้
    # **และต้องยังไม่หมดอายุ**
    op.execute(
        """
        CREATE POLICY login_challenges_presented ON login_challenges
            FOR SELECT
            TO tiewtrade_auth
            USING (
                token_hash = tiewtrade_presented_token_hash()
                AND now() < expires_at
            )
        """
    )
    # หลังรู้ตัวตนแล้ว: แถวของตัวเองทั้งหมด **รวมที่หมดอายุ** เพื่อให้ลบได้
    #
    # ต้องมี policy ตัวนี้เพราะคำสั่งลบอ้างคอลัมน์ ซึ่งทำให้ PostgreSQL นำ SELECT
    # policy มาใช้ด้วย แล้วแถวที่หมดอายุจะมองไม่เห็นและลบไม่ได้ (`plan.md` หัวข้อ 1.5)
    op.execute(
        """
        CREATE POLICY login_challenges_auth_owner ON login_challenges
            FOR ALL
            TO tiewtrade_auth
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )
    # เก็บกวาดแถวที่หมดอายุ **ข้ามผู้ใช้** — ของที่ไม่มีใครเก็บได้คือของที่ค้างตลอดไป
    #
    # **คำสั่งเก็บกวาดต้องเป็น `DELETE FROM login_challenges` ที่ไม่มี `WHERE`**
    # เพราะคำสั่งที่อ้างคอลัมน์จะดึง SELECT policy มาใช้ด้วย แล้วจะลบได้ศูนย์แถว
    # แบบเงียบ ๆ (ข้อเดียวกับ "ออกจากระบบทุกเครื่อง" ของ F-05 — ดู `sessions.py`)
    # เงื่อนไข "หมดอายุแล้ว" อยู่ใน policy นี้ ไม่ใช่ในคำสั่ง
    #
    # **ไม่เพิ่ม SELECT policy ให้การเก็บกวาด** — ลองแล้วพบว่ามันทำให้ challenge
    # ที่หมดอายุมองเห็นได้ทาง `presented()` ด้วย ซึ่งเท่ากับยอมรับใบที่หมดอายุแล้ว
    # เป็นการถอยหลังด้านความปลอดภัย (เทสต์ V-49 และเทสต์เรื่องใบหมดอายุจับได้)
    op.execute(
        """
        CREATE POLICY login_challenges_sweep ON login_challenges
            FOR DELETE
            TO tiewtrade_auth
            USING (expires_at <= now())
        """
    )
    op.execute("GRANT SELECT, DELETE ON login_challenges TO tiewtrade_auth")
    op.execute(
        "GRANT INSERT (token_hash, user_id, credential_updated_at, expires_at)"
        " ON login_challenges TO tiewtrade_auth"
    )
    # **ไม่ให้ `UPDATE` กับใครเลย** — challenge ยืดอายุไม่ได้ และ "ผ่านแล้ว"
    # คือการลบแถว ไม่ใช่การตั้งธง

    # ── สิทธิ์กู้บัญชี ─────────────────────────────────────────────────────
    #
    # ผูกกับ session ใบเดียว ใช้ครั้งเดียว และ **หายไปพร้อม session**
    # ส่วนการตรวจว่า session นั้นยังใช้ได้อยู่ทำใน policy เพราะ `ON DELETE CASCADE`
    # ทำงานตอนลบ ไม่ใช่ตอนหมดอายุ (`plan.md` หัวข้อ 1.8 และ 6.5)
    op.execute(
        """
        CREATE TABLE recovery_grants (
            session_token_hash text PRIMARY KEY
                REFERENCES sessions (token_hash) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users (id),
            used_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("ALTER TABLE recovery_grants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recovery_grants FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY recovery_grants_self ON recovery_grants
            FOR ALL
            TO tiewtrade_auth
            USING (
                user_id = tiewtrade_current_user_id()
                AND EXISTS (
                    SELECT 1
                    FROM sessions AS s
                    WHERE s.token_hash = recovery_grants.session_token_hash
                      AND now() < s.idle_expires_at
                      AND now() < s.absolute_expires_at
                )
            )
            WITH CHECK (
                user_id = tiewtrade_current_user_id()
                AND EXISTS (
                    SELECT 1
                    FROM sessions AS s
                    WHERE s.token_hash = recovery_grants.session_token_hash
                      AND now() < s.idle_expires_at
                      AND now() < s.absolute_expires_at
                )
            )
        """
    )
    op.execute("GRANT SELECT, DELETE ON recovery_grants TO tiewtrade_auth")
    op.execute("GRANT INSERT (session_token_hash, user_id) ON recovery_grants TO tiewtrade_auth")
    op.execute("GRANT UPDATE (used_at) ON recovery_grants TO tiewtrade_auth")

    # ── ถังแบบ token bucket ─────────────────────────────────────────────
    #
    # `CHECK` แทนที่กันไม่ได้ จึงถอนของเดิมแล้วเขียนใหม่ทั้งก้อน
    op.execute("ALTER TABLE auth_throttle DROP CONSTRAINT auth_throttle_kind")
    op.execute("ALTER TABLE auth_throttle ADD COLUMN tokens_left integer")
    op.execute("ALTER TABLE auth_throttle ADD COLUMN refilled_at timestamptz")
    op.execute(
        "ALTER TABLE auth_throttle"
        " ADD CONSTRAINT auth_throttle_tokens CHECK (tokens_left IS NULL OR tokens_left >= 0)"
    )
    op.execute(_BUCKET_SHAPE)

    # ── ชนิดเหตุการณ์ใหม่ห้าชนิด ─────────────────────────────────────────
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_SHAPE_WITH_TOTP)


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_SHAPE_BEFORE_TOTP)
    op.execute("ALTER TABLE auth_throttle DROP CONSTRAINT auth_throttle_bucket_shape")
    op.execute("ALTER TABLE auth_throttle DROP CONSTRAINT auth_throttle_tokens")
    op.execute("ALTER TABLE auth_throttle DROP CONSTRAINT auth_throttle_kind")
    op.execute(f"DELETE FROM auth_throttle WHERE bucket_kind IN ({_quoted(_TOKEN_BUCKETS)})")
    op.execute("ALTER TABLE auth_throttle DROP COLUMN refilled_at")
    op.execute("ALTER TABLE auth_throttle DROP COLUMN tokens_left")
    op.execute(_BUCKET_SHAPE_BEFORE)
    op.execute("DROP TABLE recovery_grants")
    op.execute("DROP TABLE login_challenges")
    op.execute("DROP TABLE user_recovery_codes")
    op.execute("DROP TABLE user_totp_pending")
    op.execute("DROP TABLE user_totp")
