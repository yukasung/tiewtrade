"""Durable scoped stop enrollment, effects, and recovery cursors."""

from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

_TABLES = ("risk_stop_requests", "risk_stop_progress", "risk_stop_targets", "risk_stop_effects")


def upgrade() -> None:
    op.execute("""CREATE TABLE risk_stop_requests (
      id uuid PRIMARY KEY,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      event_id uuid NOT NULL UNIQUE,wallet_id uuid NOT NULL,episode_id uuid NOT NULL,
      risk_revision bigint NOT NULL CHECK(risk_revision>0),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(id,user_id,mode),
      FOREIGN KEY(event_id,user_id,mode) REFERENCES risk_limit_events(id,user_id,mode),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE risk_stop_progress (
      stop_id uuid PRIMARY KEY,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      target_set_complete boolean NOT NULL DEFAULT false,
      effects_revision bigint NOT NULL DEFAULT 0 CHECK(effects_revision>=0),
      target_count bigint NOT NULL DEFAULT 0 CHECK(target_count>=0),
      pending_count bigint NOT NULL DEFAULT 0 CHECK(pending_count>=0),
      failed_count bigint NOT NULL DEFAULT 0 CHECK(failed_count>=0),
      due_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      alert_due boolean NOT NULL DEFAULT false,
      CHECK(failed_count<=pending_count AND pending_count<=target_count),
      FOREIGN KEY(stop_id,user_id,mode) REFERENCES risk_stop_requests(id,user_id,mode))""")
    op.execute("""CREATE TABLE risk_stop_targets (
      stop_id uuid NOT NULL,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      target_kind text NOT NULL CHECK(target_kind IN ('REQUEST','COMMAND','ORDER')),
      target_id uuid NOT NULL,order_id uuid NOT NULL,
      enrolled_sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
      PRIMARY KEY(stop_id,target_kind,target_id),
      UNIQUE(stop_id,target_kind,target_id,user_id,mode),
      FOREIGN KEY(stop_id,user_id,mode) REFERENCES risk_stop_requests(id,user_id,mode))""")
    op.execute("""CREATE TABLE risk_stop_effects (
      sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      stop_id uuid NOT NULL,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      target_kind text NOT NULL,target_id uuid NOT NULL,
      state text NOT NULL CHECK(state IN ('PENDING','CANCEL_PENDING','CANCELED',
        'FILLED','REJECTED','ALREADY_TERMINAL','FAILED')),
      attempt integer NOT NULL CHECK(attempt>=0),
      next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      details jsonb NOT NULL CHECK(jsonb_typeof(details)='object'),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(stop_id,target_kind,target_id,user_id,mode)
        REFERENCES risk_stop_targets(stop_id,target_kind,target_id,user_id,mode))""")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO tiewtrade_engine")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api")
        if table != "risk_stop_progress":
            op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
    op.execute("GRANT UPDATE ON risk_stop_progress TO tiewtrade_engine")
    op.execute("""GRANT USAGE ON SEQUENCE risk_stop_targets_enrolled_sequence_seq,
      risk_stop_effects_sequence_seq TO tiewtrade_engine""")
    op.execute("""GRANT SELECT(user_id,mode,stop_id,due_at) ON risk_stop_progress
      TO tiewtrade_engine_scan""")
    op.execute("CREATE INDEX risk_stop_due ON risk_stop_progress(due_at,user_id)")
    op.execute("""CREATE INDEX risk_stop_effect_latest
      ON risk_stop_effects(stop_id,target_kind,target_id,sequence DESC)""")
    op.execute("CREATE INDEX risk_stops_owner_time ON risk_stop_requests(user_id,recorded_at,id)")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'risk stop history prevents downgrade'; END IF; END $$""")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
