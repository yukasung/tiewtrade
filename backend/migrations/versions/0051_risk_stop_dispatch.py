"""DB-clock intake cuts and minimal durable stop scheduling hints."""

from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE paper_order_commands
      ADD risk_recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()""")
    op.execute("""GRANT SELECT(target_set_complete,pending_count) ON risk_stop_progress
      TO tiewtrade_engine_scan""")


def downgrade() -> None:
    op.execute("LOCK TABLE paper_order_commands IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE paper_order_commands NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM paper_order_commands) THEN
      RAISE EXCEPTION 'risk queued cutoff history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE paper_order_commands FORCE ROW LEVEL SECURITY")
    op.execute("""REVOKE SELECT(target_set_complete,pending_count) ON risk_stop_progress
      FROM tiewtrade_engine_scan""")
    op.execute("ALTER TABLE paper_order_commands DROP risk_recorded_at")
