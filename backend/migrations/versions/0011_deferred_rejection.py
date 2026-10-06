"""Allow retained-secret rejections in the audit shape (F-07 NC-20).

Revision ID: 0011
Revises: 0010

Frozen snapshot of 0009's audit shape; only the deferred failure-code set changes.
Historical REJECTED records remain valid and are never rewritten.
Downgrade uses NOT VALID, as 0009 does, to retain immutable newer records.
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_BEFORE_SHAPE = """
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

            WHEN 'SESSION_STARTED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'SESSION_ENDED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'PASSWORD_CHANGED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'TOTP_ENABLED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'TOTP_DISABLED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'TOTP_SECRET_REPLACED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'ALL_SESSIONS_ENDED' THEN
                details - 'ended' = '{}'::jsonb
                AND jsonb_typeof(details -> 'ended') = 'number'
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'RECOVERY_CODES_ISSUED' THEN
                details - 'issued' = '{}'::jsonb
                AND jsonb_typeof(details -> 'issued') = 'number'
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'RECOVERY_CODE_USED' THEN
                details - 'remaining' = '{}'::jsonb
                AND jsonb_typeof(details -> 'remaining') = 'number'
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'USER'
                AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED'

            WHEN 'API_KEY_ADDED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'API_KEY'
                AND outcome = 'SUCCEEDED'
                AND failure_code IS NULL

            WHEN 'API_KEY_RETRY_REQUESTED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'API_KEY'
                AND outcome = 'SUCCEEDED'
                AND failure_code IS NULL

            WHEN 'API_KEY_DELETED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'USER'
                AND actor_id = owner_user_id
                AND subject_kind = 'API_KEY'
                AND outcome = 'SUCCEEDED'
                AND failure_code IS NULL

            WHEN 'API_KEY_VERIFIED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'SYSTEM'
                AND actor_id IS NULL
                AND subject_kind = 'API_KEY'
                AND outcome = 'SUCCEEDED'
                AND failure_code IS NULL

            WHEN 'API_KEY_REJECTED' THEN
                details = '{}'::jsonb
                AND actor_kind = 'SYSTEM'
                AND actor_id IS NULL
                AND subject_kind = 'API_KEY'
                AND outcome = 'REJECTED'
                AND failure_code IN (
                    'VENUE_CREDENTIAL_REJECTED', 'VENUE_REJECTED', 'VERIFICATION_EXPIRED'
                )

            WHEN 'API_KEY_VERIFICATION_DEFERRED'
                THEN
                details = '{}'::jsonb
                AND actor_kind = 'SYSTEM'
                AND actor_id IS NULL
                AND subject_kind = 'API_KEY'
                AND outcome = 'FAILED'
                AND failure_code IN (
                    'VENUE_RATE_LIMITED', 'VENUE_UNAVAILABLE',
                    'VENUE_OUTCOME_UNKNOWN', 'VENUE_PROTOCOL'
                )

            ELSE false
        END
    )
"""

_AFTER_SHAPE = _BEFORE_SHAPE.replace(
    "'VENUE_RATE_LIMITED',", "'VENUE_REJECTED', 'VENUE_RATE_LIMITED',", 1
)


def upgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_AFTER_SHAPE)


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_BEFORE_SHAPE + " NOT VALID")
