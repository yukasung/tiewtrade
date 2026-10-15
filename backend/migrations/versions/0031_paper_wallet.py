"""Paper wallet, immutable episodes and durable commands (F-13).

Revision ID: 0031
Revises: 0030
"""

# ruff: noqa: E501 -- keeping financial DDL constraints readable as complete SQL clauses

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

_AUDIT_EXTENSION = """
            WHEN 'PAPER_WALLET_CREATED' THEN
                actor_kind='USER' AND actor_id=owner_user_id
                AND subject_kind='PAPER_WALLET' AND outcome='SUCCEEDED'
                AND mode='PAPER' AND failure_code IS NULL
                AND details ?& ARRAY['command_id','episode_id','amount','currency']
                AND details - ARRAY['command_id','episode_id','amount','currency'] = '{}'::jsonb
                AND details->>'currency'='USDT'
            WHEN 'PAPER_WALLET_CREATE_REJECTED' THEN
                actor_kind='USER' AND actor_id=owner_user_id
                AND subject_kind='PAPER_WALLET_COMMAND' AND outcome='REJECTED'
                AND mode='PAPER'
                AND failure_code IN ('INITIAL_CAPITAL_INVALID','INITIAL_CAPITAL_TOO_SMALL',
                                     'IDEMPOTENCY_CONFLICT','WALLET_EXISTS')
                AND details='{}'::jsonb
            WHEN 'PAPER_WALLET_RESET_REJECTED' THEN
                actor_kind='USER' AND actor_id=owner_user_id
                AND subject_kind='PAPER_WALLET_COMMAND' AND outcome='REJECTED'
                AND mode='PAPER'
                AND failure_code IN ('INITIAL_CAPITAL_INVALID','INITIAL_CAPITAL_TOO_SMALL',
                                     'IDEMPOTENCY_CONFLICT','ACTIVITY_UNKNOWN',
                                     'EPISODE_CONFLICT','RESET_UNSAFE')
                AND details='{}'::jsonb
"""


def _extend_audit_shape() -> None:
    escaped = _AUDIT_EXTENSION.replace("'", "''")
    op.execute(
        f"""DO $$ DECLARE definition text; changed text; BEGIN
          SELECT pg_get_constraintdef(oid) INTO definition
          FROM pg_constraint WHERE conrelid='audit_events'::regclass
            AND conname='audit_events_action_shape';
          changed := replace(definition, 'ELSE false', '{escaped}            ELSE false');
          IF changed = definition THEN RAISE EXCEPTION 'audit shape extension point missing'; END IF;
          ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
          EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape ' || changed;
        END $$"""
    )


def upgrade() -> None:
    op.execute("""CREATE TABLE paper_wallet_commands (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
      action text NOT NULL CHECK(action IN ('CREATE','RESET')),
      idempotency_key uuid NOT NULL, request_fingerprint text NOT NULL
        CHECK(request_fingerprint ~ '^[0-9a-f]{64}$'),
      initial_capital tiewtrade_money_amount NOT NULL,
      currency tiewtrade_unit_code NOT NULL CHECK(currency='USDT'),
      expected_episode_id uuid, requested_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(id,user_id),
      UNIQUE(user_id,action,idempotency_key),
      CHECK((action='CREATE' AND expected_episode_id IS NULL) OR
            (action='RESET' AND expected_episode_id IS NOT NULL)))""")
    op.execute("""CREATE TABLE paper_wallet_admission_results (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
      action text NOT NULL CHECK(action IN ('CREATE','RESET')),
      idempotency_key uuid NOT NULL, request_fingerprint text NOT NULL
        CHECK(request_fingerprint ~ '^[0-9a-f]{64}$'),
      failure_code text NOT NULL CHECK(failure_code IN
        ('INITIAL_CAPITAL_INVALID','INITIAL_CAPITAL_TOO_SMALL','IDEMPOTENCY_CONFLICT')),
      rejected_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,action,idempotency_key,request_fingerprint,failure_code))""")
    op.execute("""CREATE TABLE paper_wallet_command_dispatch (
      command_id uuid PRIMARY KEY REFERENCES paper_wallet_commands(id),
      user_id uuid NOT NULL REFERENCES users(id), attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
      next_attempt_at timestamptz NOT NULL DEFAULT now(), claimed_by text,
      claim_id uuid, claim_expires_at timestamptz, last_failure_code text,
      FOREIGN KEY(command_id,user_id) REFERENCES paper_wallet_commands(id,user_id),
      CHECK((claimed_by IS NULL AND claim_id IS NULL AND claim_expires_at IS NULL) OR
            (claimed_by IS NOT NULL AND claim_id IS NOT NULL AND claim_expires_at IS NOT NULL)))""")
    op.execute("""CREATE TABLE paper_wallets (
      id uuid PRIMARY KEY, user_id uuid NOT NULL UNIQUE REFERENCES users(id),
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(id,user_id))""")
    op.execute("""CREATE TABLE paper_wallet_episodes (
      id uuid PRIMARY KEY, wallet_id uuid NOT NULL, user_id uuid NOT NULL,
      sequence integer NOT NULL CHECK(sequence>0), started_at timestamptz NOT NULL DEFAULT now(),
      initial_capital tiewtrade_money_amount NOT NULL CHECK(initial_capital>1000),
      currency tiewtrade_unit_code NOT NULL CHECK(currency='USDT'),
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      UNIQUE(wallet_id,sequence), UNIQUE(id,wallet_id,user_id),
      FOREIGN KEY(wallet_id,user_id) REFERENCES paper_wallets(id,user_id))""")
    op.execute("""CREATE TABLE paper_wallet_episode_closures (
      episode_id uuid PRIMARY KEY, wallet_id uuid NOT NULL, user_id uuid NOT NULL,
      closed_at timestamptz NOT NULL DEFAULT now(), reset_command_id uuid UNIQUE NOT NULL,
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      FOREIGN KEY(reset_command_id,user_id) REFERENCES paper_wallet_commands(id,user_id))""")
    op.execute("""CREATE TABLE paper_wallet_state (
      wallet_id uuid PRIMARY KEY, user_id uuid NOT NULL UNIQUE,
      active_episode_id uuid NOT NULL, revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      FOREIGN KEY(wallet_id,user_id) REFERENCES paper_wallets(id,user_id),
      FOREIGN KEY(active_episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE paper_wallet_ledger (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      kind text NOT NULL CHECK(kind='EXTERNAL_CAPITAL'),
      amount tiewtrade_money_amount NOT NULL CHECK(amount>1000),
      currency tiewtrade_unit_code NOT NULL CHECK(currency='USDT'),
      source_command_id uuid NOT NULL UNIQUE,
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(episode_id),
      FOREIGN KEY(source_command_id,user_id) REFERENCES paper_wallet_commands(id,user_id),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE paper_wallet_command_results (
      command_id uuid PRIMARY KEY REFERENCES paper_wallet_commands(id),
      user_id uuid NOT NULL REFERENCES users(id), state text NOT NULL CHECK(state IN ('SUCCEEDED','REJECTED')),
      failure_code text, wallet_id uuid, episode_id uuid, initial_capital tiewtrade_money_amount,
      balance tiewtrade_money_amount, currency tiewtrade_unit_code,
      completed_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY(command_id,user_id) REFERENCES paper_wallet_commands(id,user_id),
      FOREIGN KEY(wallet_id,user_id) REFERENCES paper_wallets(id,user_id),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((state='SUCCEEDED' AND failure_code IS NULL AND wallet_id IS NOT NULL
             AND episode_id IS NOT NULL AND initial_capital IS NOT NULL
             AND balance IS NOT NULL AND currency='USDT') OR
            (state='REJECTED' AND failure_code IS NOT NULL AND wallet_id IS NULL
             AND episode_id IS NULL AND initial_capital IS NULL AND balance IS NULL
             AND currency IS NULL)),
      CHECK(failure_code IS NULL OR failure_code IN
        ('WALLET_EXISTS','ACTIVITY_UNKNOWN','EPISODE_CONFLICT','RESET_UNSAFE')))""")
    op.execute("""CREATE INDEX paper_wallet_dispatch_due_idx
      ON paper_wallet_command_dispatch(next_attempt_at,command_id)""")

    owner_tables = (
        "paper_wallet_commands",
        "paper_wallet_admission_results",
        "paper_wallet_command_dispatch",
        "paper_wallets",
        "paper_wallet_episodes",
        "paper_wallet_episode_closures",
        "paper_wallet_state",
        "paper_wallet_ledger",
        "paper_wallet_command_results",
    )
    for table in owner_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_api_self ON {table} TO tiewtrade_api
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"""CREATE POLICY {table}_engine_self ON {table} TO tiewtrade_engine
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())""")

    op.execute("GRANT SELECT,INSERT ON paper_wallet_commands TO tiewtrade_api")
    op.execute("GRANT SELECT,INSERT ON paper_wallet_admission_results TO tiewtrade_api")
    op.execute("GRANT SELECT ON paper_wallet_command_dispatch TO tiewtrade_api")
    op.execute(
        "GRANT INSERT(command_id,user_id,next_attempt_at) ON paper_wallet_command_dispatch TO tiewtrade_api"
    )
    for table in (
        "paper_wallets",
        "paper_wallet_episodes",
        "paper_wallet_episode_closures",
        "paper_wallet_state",
        "paper_wallet_ledger",
        "paper_wallet_command_results",
    ):
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api")
    for table in owner_tables:
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_engine")
    op.execute(
        "GRANT INSERT ON paper_wallets,paper_wallet_episodes,paper_wallet_ledger,paper_wallet_command_results TO tiewtrade_engine"
    )
    op.execute(
        "GRANT INSERT ON paper_wallet_state,paper_wallet_episode_closures TO tiewtrade_engine"
    )
    op.execute(
        "GRANT UPDATE ON paper_wallet_state,paper_wallet_command_dispatch TO tiewtrade_engine"
    )
    op.execute(
        "GRANT SELECT(command_id,user_id,next_attempt_at,claim_expires_at) ON paper_wallet_command_dispatch TO tiewtrade_engine_scan"
    )
    op.execute(
        "GRANT SELECT(id,user_id,requested_at) ON paper_wallet_commands TO tiewtrade_engine_scan"
    )
    op.execute("GRANT SELECT(command_id) ON paper_wallet_command_results TO tiewtrade_engine_scan")

    for table in (
        "paper_wallet_commands",
        "paper_wallet_admission_results",
        "paper_wallets",
        "paper_wallet_episodes",
        "paper_wallet_episode_closures",
        "paper_wallet_ledger",
        "paper_wallet_command_results",
    ):
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")

    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind CHECK(bucket_kind IN
      ('API_KEY_ADD','API_KEY_RETRY','PRICE_STREAM_HANDSHAKE','PAPER_WALLET_MUTATION'))""")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute("""ALTER TABLE audit_events ADD CONSTRAINT audit_events_failure_code CHECK(
      failure_code IS NULL OR failure_code IN
      ('VENUE_CREDENTIAL_REJECTED','VENUE_REJECTED','VENUE_RATE_LIMITED',
       'VENUE_UNAVAILABLE','VENUE_OUTCOME_UNKNOWN','VENUE_PROTOCOL','VERIFICATION_EXPIRED',
       'INITIAL_CAPITAL_INVALID','INITIAL_CAPITAL_TOO_SMALL','IDEMPOTENCY_CONFLICT',
       'WALLET_EXISTS','ACTIVITY_UNKNOWN','EPISODE_CONFLICT','RESET_UNSAFE'))""")
    _extend_audit_shape()


def downgrade() -> None:
    for table in (
        "paper_wallet_commands",
        "paper_wallet_admission_results",
        "paper_wallets",
    ):
        op.execute(
            f"CREATE POLICY {table}_downgrade_check ON {table} "
            "FOR SELECT TO tiewtrade_migrator USING (true)"
        )
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM paper_wallet_commands)
      OR EXISTS(SELECT 1 FROM paper_wallet_admission_results)
      OR EXISTS(SELECT 1 FROM paper_wallets) THEN
      RAISE EXCEPTION 'paper wallet data exists; downgrade refused'; END IF; END $$""")
    op.execute("DELETE FROM api_throttle WHERE bucket_kind='PAPER_WALLET_MUTATION'")
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind CHECK(bucket_kind IN
      ('API_KEY_ADD','API_KEY_RETRY','PRICE_STREAM_HANDSHAKE'))""")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute("""ALTER TABLE audit_events ADD CONSTRAINT audit_events_failure_code CHECK(
      failure_code IS NULL OR failure_code IN
      ('VENUE_CREDENTIAL_REJECTED','VENUE_REJECTED','VENUE_RATE_LIMITED',
       'VENUE_UNAVAILABLE','VENUE_OUTCOME_UNKNOWN','VENUE_PROTOCOL','VERIFICATION_EXPIRED'))
       NOT VALID""")
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
      WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed := regexp_replace(definition,
        'WHEN ''PAPER_WALLET_CREATED''.*ELSE false', 'ELSE false');
      IF changed = definition THEN RAISE EXCEPTION 'audit shape rollback point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '
              || changed || ' NOT VALID';
    END $$""")
    for table in (
        "paper_wallet_command_results",
        "paper_wallet_ledger",
        "paper_wallet_state",
        "paper_wallet_episode_closures",
        "paper_wallet_episodes",
        "paper_wallets",
        "paper_wallet_command_dispatch",
        "paper_wallet_admission_results",
        "paper_wallet_commands",
    ):
        op.execute(f"DROP TABLE {table}")
