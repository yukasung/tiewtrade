"""Spot position facts, projections and authoritative activity (F-14).

Revision ID: 0032
Revises: 0031
"""

# ruff: noqa: E501 -- financial DDL is kept as complete reviewable constraints

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

_AUDIT_EXTENSION = """
            WHEN 'PAPER_POSITION_APPLIED' THEN
                actor_kind='SYSTEM' AND actor_id IS NULL
                AND subject_kind='PAPER_POSITION_EVENT' AND outcome='SUCCEEDED'
                AND subject_id=details->>'event_id'
                AND mode='PAPER' AND failure_code IS NULL
                AND details ?& ARRAY['event_id','execution_id','episode_id','base','quote',
                                     'quantity','quantity_unit','quote_amount','quote_currency']
                AND details - ARRAY['event_id','execution_id','episode_id','base','quote',
                                    'quantity','quantity_unit','quote_amount','quote_currency'] = '{}'::jsonb
            WHEN 'PAPER_POSITION_CORRECTED' THEN
                actor_kind='SYSTEM' AND actor_id IS NULL
                AND subject_kind='PAPER_POSITION_EVENT' AND outcome='SUCCEEDED'
                AND subject_id=details->>'event_id'
                AND mode='PAPER' AND failure_code IS NULL
                AND details ?& ARRAY['event_id','execution_id','episode_id','base','quote',
                                     'quantity','quantity_unit','quote_amount','quote_currency']
                AND details - ARRAY['event_id','execution_id','episode_id','base','quote',
                                    'quantity','quantity_unit','quote_amount','quote_currency'] = '{}'::jsonb
            WHEN 'PAPER_POSITION_CONFLICTED' THEN
                actor_kind='SYSTEM' AND actor_id IS NULL
                AND outcome='FAILED' AND mode='PAPER'
                AND failure_code IN ('POSITION_SEQUENCE_GAP','POSITION_DUPLICATE_CONFLICT',
                                     'POSITION_CORRECTION_CONFLICT','POSITION_SOURCE_UNKNOWN',
                                     'POSITION_INSUFFICIENT','POSITION_EXECUTION_INVALID',
                                     'POSITION_PRICE_UNAVAILABLE')
                AND ((subject_kind='PAPER_POSITION_EVENT' AND subject_id=details->>'event_id'
                      AND details ?& ARRAY['event_id','episode_id','base','quote']
                      AND details - ARRAY['event_id','episode_id','base','quote'] = '{}'::jsonb)
                  OR (subject_kind='PAPER_POSITION_ACTIVITY'
                      AND subject_id=details->>'episode_id'
                      AND details ?& ARRAY['initialization_id','episode_id']
                      AND details - ARRAY['initialization_id','episode_id'] = '{}'::jsonb))
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
    op.execute("""CREATE TABLE paper_position_activity (
      episode_id uuid PRIMARY KEY, wallet_id uuid NOT NULL, user_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      availability text NOT NULL DEFAULT 'UNKNOWN'
        CHECK(availability IN ('UNKNOWN','READY','CONFLICTED')),
      source_sequence bigint NOT NULL DEFAULT 0 CHECK(source_sequence>=0),
      revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      source_proof text CHECK(source_proof IS NULL OR source_proof ~ '^[0-9a-f]{64}$'),
      observed_at timestamptz, failure_code text,
      UNIQUE(episode_id,wallet_id,user_id),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((availability='READY' AND source_proof IS NOT NULL
             AND observed_at IS NOT NULL AND failure_code IS NULL) OR
            (availability='UNKNOWN' AND source_proof IS NULL
             AND observed_at IS NULL AND failure_code IS NULL) OR
            (availability='CONFLICTED' AND observed_at IS NOT NULL AND failure_code IS NOT NULL)))""")
    op.execute("""CREATE TABLE paper_position_events (
      id uuid PRIMARY KEY, execution_id uuid NOT NULL,
      user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      event_kind text NOT NULL CHECK(event_kind IN ('RECORD','REPLACE','VOID')),
      source_sequence bigint NOT NULL CHECK(source_sequence>0),
      request_fingerprint text NOT NULL CHECK(request_fingerprint ~ '^[0-9a-f]{64}$'),
      supersedes_event_id uuid UNIQUE,
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      side text, gross_quantity tiewtrade_money_amount, quote_amount tiewtrade_money_amount,
      fee_amount tiewtrade_money_amount, fee_unit tiewtrade_unit_code,
      occurred_at timestamptz, recorded_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(id,user_id), UNIQUE(id,user_id,episode_id),
      UNIQUE(id,user_id,episode_id,base,quote),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      FOREIGN KEY(supersedes_event_id,user_id)
        REFERENCES paper_position_events(id,user_id),
      CHECK(base<>quote),
      CHECK((event_kind IN ('RECORD','REPLACE') AND side IS NOT NULL
             AND gross_quantity IS NOT NULL AND quote_amount IS NOT NULL
             AND side IN ('BUY','SELL') AND gross_quantity>0 AND quote_amount>0
             AND occurred_at IS NOT NULL) OR
            (event_kind='VOID' AND side IS NULL AND gross_quantity IS NULL
             AND quote_amount IS NULL AND fee_amount IS NULL AND fee_unit IS NULL
             AND occurred_at IS NULL)),
      CHECK((event_kind='RECORD' AND supersedes_event_id IS NULL) OR
            (event_kind IN ('REPLACE','VOID') AND supersedes_event_id IS NOT NULL)),
      CHECK((fee_amount IS NULL)=(fee_unit IS NULL)),
      CHECK(fee_amount IS NULL OR fee_amount<>0))""")
    op.execute("""CREATE UNIQUE INDEX paper_position_record_execution
      ON paper_position_events(user_id,episode_id,execution_id)
      WHERE event_kind='RECORD'""")
    op.execute("""CREATE UNIQUE INDEX paper_position_record_sequence
      ON paper_position_events(user_id,episode_id,source_sequence)
      WHERE event_kind='RECORD'""")
    op.execute("""CREATE TABLE paper_position_projections (
      episode_id uuid NOT NULL, wallet_id uuid NOT NULL, user_id uuid NOT NULL,
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      held_quantity tiewtrade_money_amount NOT NULL CHECK(held_quantity>=0),
      total_cost tiewtrade_money_amount NOT NULL CHECK(total_cost>=0),
      realized_pnl tiewtrade_money_amount NOT NULL,
      last_sequence bigint NOT NULL CHECK(last_sequence>0),
      revision bigint NOT NULL CHECK(revision>0), last_event_id uuid NOT NULL,
      PRIMARY KEY(episode_id,base,quote), UNIQUE(episode_id,wallet_id,user_id,base,quote),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      FOREIGN KEY(last_event_id,user_id,episode_id,base,quote)
        REFERENCES paper_position_events(id,user_id,episode_id,base,quote),
      CHECK(base<>quote), CHECK(held_quantity>0 OR total_cost=0))""")
    op.execute("""CREATE TABLE paper_position_external_fees (
      id uuid PRIMARY KEY, event_id uuid NOT NULL, user_id uuid NOT NULL,
      wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      amount tiewtrade_money_amount NOT NULL CHECK(amount<>0),
      asset tiewtrade_unit_code NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(event_id,user_id,asset),
      FOREIGN KEY(event_id,user_id,episode_id)
        REFERENCES paper_position_events(id,user_id,episode_id),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE paper_position_conflicts (
      id uuid PRIMARY KEY, attempted_event_id uuid, initialization_id uuid,
      user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      failure_code text NOT NULL CHECK(failure_code IN
        ('POSITION_SEQUENCE_GAP','POSITION_DUPLICATE_CONFLICT',
         'POSITION_CORRECTION_CONFLICT','POSITION_SOURCE_UNKNOWN',
         'POSITION_INSUFFICIENT','POSITION_EXECUTION_INVALID',
         'POSITION_PRICE_UNAVAILABLE')),
      base tiewtrade_unit_code, quote tiewtrade_unit_code,
      recorded_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,episode_id,fingerprint),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((attempted_event_id IS NOT NULL AND initialization_id IS NULL
             AND base IS NOT NULL AND quote IS NOT NULL AND base<>quote) OR
            (attempted_event_id IS NULL AND initialization_id IS NOT NULL
             AND base IS NULL AND quote IS NULL)))""")

    op.execute("""INSERT INTO paper_position_activity(episode_id,wallet_id,user_id)
      SELECT id,wallet_id,user_id FROM paper_wallet_episodes""")

    op.execute("""CREATE FUNCTION tiewtrade_position_correction_valid()
      RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE prior paper_position_events%ROWTYPE; BEGIN
        IF NEW.event_kind='RECORD' THEN RETURN NEW; END IF;
        SELECT * INTO prior FROM paper_position_events WHERE id=NEW.supersedes_event_id;
        IF NOT FOUND OR (NEW.user_id,NEW.wallet_id,NEW.episode_id,NEW.execution_id,
                         NEW.source_sequence,NEW.base,NEW.quote)
           IS DISTINCT FROM
                        (prior.user_id,prior.wallet_id,prior.episode_id,prior.execution_id,
                         prior.source_sequence,prior.base,prior.quote) THEN
          RAISE EXCEPTION 'position correction identity does not match superseded event';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE CONSTRAINT TRIGGER paper_position_correction_valid
      AFTER INSERT ON paper_position_events DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW
      EXECUTE FUNCTION tiewtrade_position_correction_valid()""")
    op.execute("""CREATE FUNCTION tiewtrade_position_external_fee_valid()
      RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE event_row paper_position_events%ROWTYPE; BEGIN
        SELECT * INTO event_row FROM paper_position_events WHERE id=NEW.event_id;
        IF NOT FOUND OR NEW.asset IN (event_row.base,event_row.quote)
           OR (NEW.user_id,NEW.wallet_id,NEW.episode_id)
              IS DISTINCT FROM (event_row.user_id,event_row.wallet_id,event_row.episode_id) THEN
          RAISE EXCEPTION 'external position effect does not match its event';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE CONSTRAINT TRIGGER paper_position_external_fee_valid
      AFTER INSERT ON paper_position_external_fees DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW
      EXECUTE FUNCTION tiewtrade_position_external_fee_valid()""")

    for table in (
        "paper_position_activity",
        "paper_position_events",
        "paper_position_projections",
        "paper_position_external_fees",
        "paper_position_conflicts",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_engine_self ON {table} TO tiewtrade_engine
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_engine")

    op.execute("GRANT INSERT,UPDATE ON paper_position_activity TO tiewtrade_engine")
    op.execute("GRANT INSERT ON paper_position_events TO tiewtrade_engine")
    op.execute("GRANT INSERT,UPDATE ON paper_position_projections TO tiewtrade_engine")
    op.execute(
        "GRANT INSERT ON paper_position_external_fees,paper_position_conflicts TO tiewtrade_engine"
    )

    for table in (
        "paper_position_events",
        "paper_position_external_fees",
        "paper_position_conflicts",
    ):
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")

    op.execute("""CREATE FUNCTION tiewtrade_position_activity_identity_immutable()
      RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF (NEW.episode_id,NEW.wallet_id,NEW.user_id,NEW.mode)
           IS DISTINCT FROM (OLD.episode_id,OLD.wallet_id,OLD.user_id,OLD.mode) THEN
          RAISE EXCEPTION 'paper position activity identity is immutable';
        END IF;
        IF NEW.revision<>OLD.revision+1 OR NEW.source_sequence<OLD.source_sequence
           OR NEW.source_sequence>OLD.source_sequence+1 THEN
          RAISE EXCEPTION 'paper position activity revision is not contiguous';
        END IF;
        IF OLD.source_proof IS NOT NULL AND NEW.source_proof IS DISTINCT FROM OLD.source_proof THEN
          RAISE EXCEPTION 'paper position source proof is immutable';
        END IF;
        IF (OLD.availability='CONFLICTED' AND NEW.availability<>'CONFLICTED')
           OR (OLD.availability='READY' AND NEW.availability='UNKNOWN') THEN
          RAISE EXCEPTION 'paper position activity recovery requires reconciliation';
        END IF;
        RETURN NEW; END $$""")
    op.execute("""CREATE TRIGGER paper_position_activity_identity
      BEFORE UPDATE ON paper_position_activity FOR EACH ROW
      EXECUTE FUNCTION tiewtrade_position_activity_identity_immutable()""")
    op.execute("""CREATE FUNCTION tiewtrade_position_projection_identity_immutable()
      RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF (NEW.episode_id,NEW.wallet_id,NEW.user_id,NEW.base,NEW.quote)
           IS DISTINCT FROM (OLD.episode_id,OLD.wallet_id,OLD.user_id,OLD.base,OLD.quote) THEN
          RAISE EXCEPTION 'paper position projection identity is immutable';
        END IF;
        IF NEW.revision<>OLD.revision+1 OR NEW.last_sequence<OLD.last_sequence THEN
          RAISE EXCEPTION 'paper position projection revision is not contiguous';
        END IF;
        RETURN NEW; END $$""")
    op.execute("""CREATE TRIGGER paper_position_projection_identity
      BEFORE UPDATE ON paper_position_projections FOR EACH ROW
      EXECUTE FUNCTION tiewtrade_position_projection_identity_immutable()""")

    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute("""ALTER TABLE audit_events ADD CONSTRAINT audit_events_failure_code CHECK(
      failure_code IS NULL OR failure_code IN
      ('VENUE_CREDENTIAL_REJECTED','VENUE_REJECTED','VENUE_RATE_LIMITED',
       'VENUE_UNAVAILABLE','VENUE_OUTCOME_UNKNOWN','VENUE_PROTOCOL','VERIFICATION_EXPIRED',
       'INITIAL_CAPITAL_INVALID','INITIAL_CAPITAL_TOO_SMALL','IDEMPOTENCY_CONFLICT',
       'WALLET_EXISTS','ACTIVITY_UNKNOWN','EPISODE_CONFLICT','RESET_UNSAFE',
       'POSITION_SEQUENCE_GAP','POSITION_DUPLICATE_CONFLICT',
       'POSITION_CORRECTION_CONFLICT','POSITION_SOURCE_UNKNOWN',
       'POSITION_INSUFFICIENT','POSITION_EXECUTION_INVALID',
       'POSITION_PRICE_UNAVAILABLE'))""")
    _extend_audit_shape()


def downgrade() -> None:
    for table in (
        "paper_wallet_commands",
        "paper_wallet_admission_results",
        "paper_wallets",
    ):
        op.execute(
            f"CREATE POLICY {table}_position_downgrade_check ON {table} "
            "FOR SELECT TO tiewtrade_migrator USING (true)"
        )
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM paper_wallet_commands)
         OR EXISTS(SELECT 1 FROM paper_wallet_admission_results)
         OR EXISTS(SELECT 1 FROM paper_wallets) THEN
        RAISE EXCEPTION 'paper wallet data exists; downgrade refused before removing position schema';
      END IF; END $$""")
    for table in (
        "paper_wallet_commands",
        "paper_wallet_admission_results",
        "paper_wallets",
    ):
        op.execute(f"DROP POLICY {table}_position_downgrade_check ON {table}")

    op.execute("""CREATE POLICY paper_position_activity_downgrade_check
      ON paper_position_activity FOR SELECT TO tiewtrade_migrator USING (true)""")
    for table in (
        "paper_position_events",
        "paper_position_projections",
        "paper_position_external_fees",
        "paper_position_conflicts",
    ):
        op.execute(
            f"CREATE POLICY {table}_downgrade_check ON {table} "
            "FOR SELECT TO tiewtrade_migrator USING (true)"
        )
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM paper_position_events)
         OR EXISTS(SELECT 1 FROM paper_position_projections)
         OR EXISTS(SELECT 1 FROM paper_position_external_fees)
         OR EXISTS(SELECT 1 FROM paper_position_conflicts)
         OR EXISTS(SELECT 1 FROM paper_position_activity
                   WHERE availability<>'UNKNOWN' OR source_sequence<>0 OR revision<>1
                      OR source_proof IS NOT NULL OR observed_at IS NOT NULL
                      OR failure_code IS NOT NULL) THEN
        RAISE EXCEPTION 'position/PnL data exists; downgrade refused';
      END IF; END $$""")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute("""ALTER TABLE audit_events ADD CONSTRAINT audit_events_failure_code CHECK(
      failure_code IS NULL OR failure_code IN
      ('VENUE_CREDENTIAL_REJECTED','VENUE_REJECTED','VENUE_RATE_LIMITED',
       'VENUE_UNAVAILABLE','VENUE_OUTCOME_UNKNOWN','VENUE_PROTOCOL','VERIFICATION_EXPIRED',
       'INITIAL_CAPITAL_INVALID','INITIAL_CAPITAL_TOO_SMALL','IDEMPOTENCY_CONFLICT',
       'WALLET_EXISTS','ACTIVITY_UNKNOWN','EPISODE_CONFLICT','RESET_UNSAFE')) NOT VALID""")
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
      WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed := regexp_replace(definition,
        'WHEN ''PAPER_POSITION_APPLIED''.*ELSE false', 'ELSE false');
      IF changed = definition THEN RAISE EXCEPTION 'position audit rollback point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '
              || changed || ' NOT VALID';
    END $$""")
    op.execute("DROP TRIGGER paper_position_projection_identity ON paper_position_projections")
    op.execute("DROP FUNCTION tiewtrade_position_projection_identity_immutable()")
    op.execute("DROP TRIGGER paper_position_activity_identity ON paper_position_activity")
    op.execute("DROP FUNCTION tiewtrade_position_activity_identity_immutable()")
    op.execute("DROP TRIGGER paper_position_correction_valid ON paper_position_events")
    op.execute("DROP FUNCTION tiewtrade_position_correction_valid()")
    op.execute("DROP TRIGGER paper_position_external_fee_valid ON paper_position_external_fees")
    op.execute("DROP FUNCTION tiewtrade_position_external_fee_valid()")
    for table in (
        "paper_position_conflicts",
        "paper_position_external_fees",
        "paper_position_projections",
        "paper_position_events",
        "paper_position_activity",
    ):
        op.execute(f"DROP TABLE {table}")
