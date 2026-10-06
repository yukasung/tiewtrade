"""API key ของผู้ใช้ — ตารางเดียว สิทธิ์รายคอลัมน์ และเหตุการณ์ของมัน (F-07)

Revision ID: 0009
Revises: 0008

**ตารางเดียว ไม่ใช่สองตารางแบบ F-06** (`plan.md` ข้อ 4.1) — ที่นั่น "ของที่ยังไม่พิสูจน์"
ต้องไม่มีผลกับการยืนยันตัวตน จึงต้องแยกตาราง ส่วนที่นี่ key ที่ยังไม่ผ่านไม่มีผลกับอะไรเลย
มันแค่ใช้ไม่ได้ สถานะจึงเป็นคอลัมน์ได้

**ข้อที่ทั้งงานตั้งอยู่บน: `tiewtrade_api` ไม่มีสิทธิ์อ่าน `secret_sealed`**
(`tech-stack.md` หัวข้อ 8 · `trading-safety.md` หัวข้อ 2 · RQ-3) ฉะนั้น `SELECT *`
ด้วยบทบาทนั้นจะ **ล้ม** ไม่ใช่คืนค่ามาเงียบ ๆ · `tiewtrade_engine_scan` ก็ไม่ได้สิทธิ์นี้
เพราะมันข้าม RLS ได้ การให้มันเห็นความลับเท่ากับยกเลิกการแยกบทบาททั้งหมด

**สถานะกับการมีอยู่ของ secret ต้องตรงกันเสมอ** — `REJECTED` บังคับว่า secret
ถูกลบไปแล้ว (Q-7 ที่เจ้าของตัดสิน) เขียนเป็น `CHECK` เพราะกฎที่อยู่ในโค้ดอย่างเดียว
คือกฎที่ลืมได้ในงานถัดไป

**คอลัมน์ของการจองงานอยู่ที่นี่ ไม่ใช่ล็อกของ PostgreSQL** (`plan.md` ข้อ 7.5) —
ล็อกหมดอายุเมื่อ transaction จบ แต่รอบตรวจต้องไม่เปิด transaction คร่อมการเรียกตลาด
การจองจึงต้องอยู่ข้าม transaction และหมดอายุเองเมื่อ worker ตาย

**`next_attempt_at` เป็นค่าที่เก็บไว้ ไม่ใช่ค่าที่คำนวณตอนจอง** — ผู้ที่คำนวณคือ worker
ที่เพิ่งตรวจเสร็จ ซึ่งรู้จำนวนครั้งที่แท้จริง ตอนจองจึงเหลือแค่เทียบเวลา ไม่มีค่าที่เก่าได้
"""

from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

#: ชนิดเหตุการณ์ที่งานนี้เพิ่ม — ต้องตรงกับ `AuditAction` ในโค้ด (F-04 Q-1)
_NEW_ACTIONS = (
    "API_KEY_ADDED",
    "API_KEY_RETRY_REQUESTED",
    "API_KEY_DELETED",
    "API_KEY_VERIFIED",
    "API_KEY_REJECTED",
    "API_KEY_VERIFICATION_DEFERRED",
)

#: รหัสความล้มเหลวชุดแรกของโปรเจกต์ — 0005 บังคับให้ `failure_code` ว่างจนกว่าจะมี
#: การประกาศ **ทีละรหัส** · หกรหัสแรกมาจากชนิดข้อผิดพลาดกลางของ F-33 ส่วนรหัสสุดท้าย
#: เป็นของงานนี้เอง (หมดเวลาตรวจ 24 ชั่วโมงตาม Q-7)
_FAILURE_CODES = (
    "VENUE_CREDENTIAL_REJECTED",
    "VENUE_REJECTED",
    "VENUE_RATE_LIMITED",
    "VENUE_UNAVAILABLE",
    "VENUE_OUTCOME_UNKNOWN",
    "VENUE_PROTOCOL",
    "VERIFICATION_EXPIRED",
)

#: รหัสที่ถือว่า "key ใช้ไม่ได้จริง" — ต้องจบที่ `API_KEY_REJECTED`
_PERMANENT_CODES = ("VENUE_CREDENTIAL_REJECTED", "VENUE_REJECTED", "VERIFICATION_EXPIRED")

#: รหัสที่ถือว่า "ตรวจไม่ได้ชั่วคราว" — ต้องจบที่ `API_KEY_VERIFICATION_DEFERRED`
_TRANSIENT_CODES = (
    "VENUE_RATE_LIMITED",
    "VENUE_UNAVAILABLE",
    "VENUE_OUTCOME_UNKNOWN",
    "VENUE_PROTOCOL",
)


def _quoted(values: tuple[str, ...]) -> str:
    """รายการค่าในรูปที่ใส่ใน `IN (...)` ได้"""
    return ", ".join(f"'{value}'" for value in values)


_SELF_ACTION = """
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'
"""


def _self_action_counting(field: str) -> str:
    """เหตุการณ์ที่ผู้ใช้ทำกับตัวเองและมีตัวเลขหนึ่งช่อง (รูปเดิมของ `0008`)"""
    return f"""
                details - '{field}' = '{{}}'::jsonb
                AND jsonb_typeof(details -> '{field}') = 'number'
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'
"""


#: เหตุการณ์ที่ผู้ใช้ทำกับ key ของตัวเอง
#:
#: **`details` ว่างเสมอ** — `subject_id` บอกอยู่แล้วว่า key ไหน การใส่ `key_public`
#: ลงไปคือการเอา API key ไปไว้ในบันทึกที่ลบไม่ได้ ซึ่ง `security.md` หัวข้อ 4 ห้าม (RQ-9.1)
_USER_KEY_ACTION = """
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'API_KEY'
                AND outcome = 'SUCCEEDED'
                AND failure_code IS NULL
"""


#: ผลการตรวจที่ระบบเป็นผู้ทำ — **ไม่มีผู้กระทำที่เป็นคน**
def _system_key_outcome(outcome: str, codes: tuple[str, ...]) -> str:
    return f"""
                details = '{{}}'::jsonb
                AND actor_kind = 'SYSTEM'
                AND actor_id IS NULL
                AND subject_kind = 'API_KEY'
                AND outcome = '{outcome}'
                AND failure_code IN ({_quoted(codes)})
"""


_SYSTEM_VERIFIED = """
                details = '{}'::jsonb
                AND actor_kind = 'SYSTEM'
                AND actor_id IS NULL
                AND subject_kind = 'API_KEY'
                AND outcome = 'SUCCEEDED'
                AND failure_code IS NULL
"""

_SHAPE_WITH_API_KEYS = f"""
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
            WHEN 'API_KEY_ADDED' THEN {_USER_KEY_ACTION}
            WHEN 'API_KEY_RETRY_REQUESTED' THEN {_USER_KEY_ACTION}
            WHEN 'API_KEY_DELETED' THEN {_USER_KEY_ACTION}
            WHEN 'API_KEY_VERIFIED' THEN {_SYSTEM_VERIFIED}
            WHEN 'API_KEY_REJECTED' THEN {_system_key_outcome("REJECTED", _PERMANENT_CODES)}
            WHEN 'API_KEY_VERIFICATION_DEFERRED'
                THEN {_system_key_outcome("FAILED", _TRANSIENT_CODES)}
            ELSE false
        END
    )
"""

# เหตุผลของ `NOT VALID` เหมือน `0007` และ `0008`: ตารางนี้ลบแถวไม่ได้ และการถอยกลับ
# ต้องทำได้จริงบนฐานข้อมูลที่เคยมีบันทึกของชนิดใหม่อยู่แล้ว
_SHAPE_BEFORE_API_KEYS = f"""
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
    ) NOT VALID
"""

_FAILURE_CODES_ALLOWED = f"""
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_failure_code CHECK (
        failure_code IS NULL OR failure_code IN ({_quoted(_FAILURE_CODES)})
    )
"""

_FAILURE_CODES_NONE = """
ALTER TABLE audit_events
    ADD CONSTRAINT audit_events_failure_code CHECK (failure_code IS NULL) NOT VALID
"""

_TABLE = """
CREATE TABLE user_api_keys (
    id                 uuid PRIMARY KEY,
    user_id            uuid NOT NULL REFERENCES users (id),
    label              text NOT NULL,
    key_public         text NOT NULL,
    secret_sealed      bytea,
    key_version        text,
    status             text NOT NULL,
    failure_code       text,
    attempts           integer NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT now(),
    verified_at        timestamptz,
    last_attempt_at    timestamptz,
    retry_requested_at timestamptz,
    not_before         timestamptz,
    next_attempt_at    timestamptz,
    claimed_by         text,
    claim_id           uuid,
    claim_expires_at   timestamptz,

    CONSTRAINT user_api_keys_status CHECK (
        status IN ('PENDING', 'ACTIVE', 'REJECTED', 'UNVERIFIABLE')
    ),

    -- **สถานะกับการมีอยู่ของ secret ต้องตรงกันเสมอ**
    -- `REJECTED` คือสถานะเดียวที่ secret ต้องหายไปแล้ว (Q-7)
    CONSTRAINT user_api_keys_secret_shape CHECK (
        CASE
            WHEN status = 'REJECTED'
                THEN secret_sealed IS NULL AND key_version IS NULL
            ELSE secret_sealed IS NOT NULL AND key_version IS NOT NULL
        END
    ),

    -- รหัสเหตุผลมีได้เฉพาะสถานะที่ล้มเหลว และสถานะที่ล้มเหลวต้องมีรหัสเสมอ
    CONSTRAINT user_api_keys_failure_shape CHECK (
        CASE status
            WHEN 'REJECTED' THEN failure_code IS NOT NULL
            WHEN 'UNVERIFIABLE' THEN failure_code IS NOT NULL
            ELSE failure_code IS NULL
        END
    ),

    -- เวลาที่ยืนยันมีได้เฉพาะ key ที่ใช้งานได้
    CONSTRAINT user_api_keys_verified_shape CHECK (
        (status = 'ACTIVE') = (verified_at IS NOT NULL)
    ),

    -- การจองสามช่องต้องมาพร้อมกันหรือว่างพร้อมกัน — ครึ่ง ๆ กลาง ๆ คือสถานะที่
    -- ไม่มีใครรู้ว่าใครถืออยู่
    CONSTRAINT user_api_keys_claim_shape CHECK (
        (claimed_by IS NULL) = (claim_id IS NULL)
        AND (claimed_by IS NULL) = (claim_expires_at IS NULL)
    ),

    CONSTRAINT user_api_keys_label_shape CHECK (label <> ''),
    CONSTRAINT user_api_keys_public_shape CHECK (key_public <> ''),
    CONSTRAINT user_api_keys_version_shape CHECK (key_version IS NULL OR key_version <> ''),
    CONSTRAINT user_api_keys_attempts CHECK (attempts >= 0)
)
"""


def upgrade() -> None:
    op.execute(_TABLE)
    # ชื่อซ้ำกันในผู้ใช้คนเดียวไม่ได้ — ชื่อมีไว้ให้ผู้ใช้แยก key ออกจากกัน
    op.execute("CREATE UNIQUE INDEX user_api_keys_one_label ON user_api_keys (user_id, label)")
    # แถวที่ worker ต้องมอง — ดัชนีบางส่วนเพราะแถวที่จบแล้วไม่ต้องถูกกวาดซ้ำ
    op.execute(
        "CREATE INDEX user_api_keys_unfinished ON user_api_keys (status)"
        " WHERE status IN ('PENDING', 'UNVERIFIABLE')"
    )

    op.execute("ALTER TABLE user_api_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_api_keys FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY user_api_keys_api_self ON user_api_keys
            FOR ALL
            TO tiewtrade_api
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )
    op.execute(
        """
        CREATE POLICY user_api_keys_engine_self ON user_api_keys
            FOR ALL
            TO tiewtrade_engine
            USING (user_id = tiewtrade_current_user_id())
            WITH CHECK (user_id = tiewtrade_current_user_id())
        """
    )

    # ── สิทธิ์ของ `api` — **ไม่มี `secret_sealed` และไม่มี `key_version`** ──
    #
    # `SELECT` รายคอลัมน์จึงทำให้ `SELECT *` ของบทบาทนี้ล้ม ซึ่งเป็นสิ่งที่ต้องการ:
    # ความผิดพลาดต้องดัง ไม่ใช่คืนความลับมาเงียบ ๆ (RQ-3)
    op.execute(
        "GRANT SELECT (id, user_id, label, key_public, status, failure_code, attempts,"
        " created_at, verified_at, last_attempt_at, retry_requested_at, not_before,"
        " next_attempt_at) ON user_api_keys TO tiewtrade_api"
    )
    # เขียนค่าที่ปิดผนึกได้ตอน `INSERT` **แต่อ่านกลับไม่ได้** — นี่คือ "รับมาเพื่อ
    # เข้ารหัสทันทีแล้วส่งต่อ" ของ `tech-stack.md` หัวข้อ 8 ในรูปของสิทธิ์
    op.execute(
        "GRANT INSERT (id, user_id, label, key_public, secret_sealed, key_version, status)"
        " ON user_api_keys TO tiewtrade_api"
    )
    op.execute("GRANT DELETE ON user_api_keys TO tiewtrade_api")
    # **ปุ่มลองใหม่เขียนได้ช่องเดียว** — ผลการตรวจเป็นของ `engine` เท่านั้น
    op.execute("GRANT UPDATE (retry_requested_at) ON user_api_keys TO tiewtrade_api")

    # ── สิทธิ์ของ `engine` — ที่เดียวที่เปิดผนึกได้ ──
    op.execute("GRANT SELECT ON user_api_keys TO tiewtrade_engine")
    op.execute(
        "GRANT UPDATE (status, failure_code, attempts, verified_at, last_attempt_at,"
        " not_before, next_attempt_at, secret_sealed, key_version,"
        " claimed_by, claim_id, claim_expires_at) ON user_api_keys TO tiewtrade_engine"
    )

    # ── สิทธิ์ของ `engine_scan` — หาแถวที่ต้องตรวจ **แต่ห้ามเห็นความลับ** ──
    #
    # บทบาทนี้ข้าม RLS ได้ (F-03 Q-3) การให้มันอ่าน `secret_sealed` จึงเท่ากับ
    # เปิดความลับของผู้ใช้ทุกคนให้ process เดียว
    op.execute(
        "GRANT SELECT (id, user_id, status, attempts, created_at, last_attempt_at,"
        " retry_requested_at, not_before, next_attempt_at, claimed_by, claim_id,"
        " claim_expires_at) ON user_api_keys TO tiewtrade_engine_scan"
    )

    # ── เหตุการณ์ใหม่หกชนิด และรหัสความล้มเหลวชุดแรกของโปรเจกต์ ──
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_SHAPE_WITH_API_KEYS)
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute(_FAILURE_CODES_ALLOWED)


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute(_FAILURE_CODES_NONE)
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_SHAPE_BEFORE_API_KEYS)
    op.execute("DROP TABLE user_api_keys")
