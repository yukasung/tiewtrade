"""Single trading account preference and one credential per user (F-08)."""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Frozen historical shape; never import runtime audit definitions.
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
                    'VENUE_REJECTED', 'VENUE_RATE_LIMITED', 'VENUE_UNAVAILABLE',
                    'VENUE_OUTCOME_UNKNOWN', 'VENUE_PROTOCOL'
                )

            ELSE false
        END
    )
"""
_AFTER_SHAPE = """
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
                    'VENUE_REJECTED', 'VENUE_RATE_LIMITED', 'VENUE_UNAVAILABLE',
                    'VENUE_OUTCOME_UNKNOWN', 'VENUE_PROTOCOL'
                )

            WHEN 'TRADING_USE_SELECTED' THEN
                actor_kind = 'USER' AND actor_id = owner_user_id
                AND subject_kind = 'USER' AND subject_id = owner_user_id::text
                AND outcome = 'SUCCEEDED' AND mode = 'NOT_APPLICABLE'
                AND failure_code IS NULL
                AND details ? 'use' AND details - 'use' = '{}'::jsonb
                AND jsonb_typeof(details -> 'use') = 'string'
                AND details ->> 'use' IN ('MANUAL', 'BOT')
            ELSE false
        END
    )
"""


def upgrade() -> None:
    # FORCE RLS hides rows from the owner; temporary policy exists only during
    # migration and rollback removes it if the metadata precheck refuses.
    op.execute(
        "CREATE POLICY trading_account_key_precheck ON public.user_api_keys "
        "FOR SELECT TO tiewtrade_migrator USING (true)"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT user_id FROM public.user_api_keys
                   GROUP BY user_id HAVING count(*) > 1) THEN
            RAISE EXCEPTION 'multiple API keys exist; migration refused';
        END IF;
    END $$""")
    op.execute(
        "ALTER TABLE public.user_api_keys ADD CONSTRAINT user_api_keys_one_per_user "
        "UNIQUE (user_id)"
    )
    op.execute("DROP POLICY trading_account_key_precheck ON public.user_api_keys")
    op.execute("""CREATE TABLE public.user_trading_preferences (
        user_id uuid PRIMARY KEY REFERENCES public.users(id),
        use text NOT NULL CHECK (use IN ('MANUAL', 'BOT')),
        created_at timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("ALTER TABLE public.user_trading_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.user_trading_preferences FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY trading_preferences_api_self
        ON public.user_trading_preferences FOR ALL TO tiewtrade_api
        USING (user_id = public.tiewtrade_current_user_id())
        WITH CHECK (user_id = public.tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT (user_id, use) ON public.user_trading_preferences TO tiewtrade_api")
    op.execute("GRANT INSERT (user_id, use) ON public.user_trading_preferences TO tiewtrade_api")
    op.execute("ALTER TABLE public.audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_AFTER_SHAPE)


def downgrade() -> None:
    op.execute(
        "CREATE POLICY trading_preferences_downgrade_check ON public.user_trading_preferences "
        "FOR SELECT TO tiewtrade_migrator USING (true)"
    )
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM public.user_trading_preferences) THEN
            RAISE EXCEPTION 'trading preferences populated; downgrade refused';
        END IF;
    END $$""")
    op.execute("DROP TABLE public.user_trading_preferences")
    op.execute("ALTER TABLE public.user_api_keys DROP CONSTRAINT user_api_keys_one_per_user")
    op.execute("ALTER TABLE public.audit_events DROP CONSTRAINT audit_events_action_shape")
    op.execute(_BEFORE_SHAPE + " NOT VALID")
