"""Durable API evaluation hints; owner financial state remains engine-only."""

from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE risk_evaluation_requests (
      id uuid PRIMARY KEY,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      wallet_id uuid NOT NULL,episode_id uuid NOT NULL,
      setting_revision bigint NOT NULL CHECK(setting_revision>0),
      source_revision bigint NOT NULL CHECK(source_revision>=0),
      price_watermark bigint NOT NULL CHECK(price_watermark>=0),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),UNIQUE(id,user_id,mode),
      UNIQUE(user_id,mode,episode_id,setting_revision,source_revision,price_watermark),
      FOREIGN KEY(user_id,mode) REFERENCES risk_limit_settings(user_id,mode),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE risk_evaluation_results (
      request_id uuid PRIMARY KEY,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      state text NOT NULL CHECK(state IN ('READY','UNAVAILABLE','BREACHED')),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id,mode) REFERENCES risk_evaluation_requests(id,user_id,mode))""")
    for table in ("risk_evaluation_requests", "risk_evaluation_results"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api,tiewtrade_engine")
    op.execute("GRANT INSERT ON risk_evaluation_requests TO tiewtrade_api")
    op.execute("GRANT INSERT ON risk_evaluation_results TO tiewtrade_engine")
    op.execute("""GRANT SELECT(id,user_id,mode,recorded_at) ON risk_evaluation_requests
      TO tiewtrade_engine_scan""")
    op.execute("""GRANT SELECT(request_id,user_id,mode) ON risk_evaluation_results
      TO tiewtrade_engine_scan""")
    op.execute(
        "CREATE INDEX risk_evaluation_owner "
        "ON risk_evaluation_requests(user_id,mode,recorded_at,id)"
    )


def downgrade() -> None:
    for table in ("risk_evaluation_requests", "risk_evaluation_results"):
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'risk evaluation request history prevents downgrade'; END IF; END $$""")
    op.execute("DROP TABLE risk_evaluation_results")
    op.execute("DROP TABLE risk_evaluation_requests")
