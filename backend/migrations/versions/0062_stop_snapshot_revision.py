"""Bind platform progress to its reconciliation snapshot and fence resume commits."""

from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL invalidates pre-upgrade summaries until discovery verifies them again.
    op.execute("""ALTER TABLE platform_stop_progress ADD reconciliation_revision bigint
      CHECK(reconciliation_revision>=0)""")
    op.execute("""GRANT SELECT(revision,singleton) ON trading_reconciliation_clock
      TO tiewtrade_engine_scan""")
    op.execute("GRANT SELECT(revision) ON platform_stop_progress TO tiewtrade_engine_scan")
    # Runtime roles still cannot UPDATE the clock. The narrow definer function
    # holds its row lock through resume commit, serializing the existing trigger.
    op.execute("""CREATE FUNCTION lock_trading_reconciliation_clock() RETURNS bigint
      LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        SELECT revision FROM public.trading_reconciliation_clock
        WHERE singleton FOR UPDATE
      $$""")
    op.execute("REVOKE ALL ON FUNCTION lock_trading_reconciliation_clock() FROM PUBLIC")
    op.execute("""GRANT EXECUTE ON FUNCTION lock_trading_reconciliation_clock()
      TO tiewtrade_engine""")


def downgrade() -> None:
    op.execute("LOCK TABLE platform_stop_progress IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE platform_stop_progress NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM platform_stop_progress
      WHERE reconciliation_revision IS NOT NULL) THEN
        RAISE EXCEPTION 'platform reconciliation snapshot history prevents downgrade';
      END IF; END $$""")
    op.execute("ALTER TABLE platform_stop_progress FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION lock_trading_reconciliation_clock()")
    op.execute("REVOKE SELECT(revision) ON platform_stop_progress FROM tiewtrade_engine_scan")
    op.execute("""REVOKE SELECT(revision,singleton) ON trading_reconciliation_clock
      FROM tiewtrade_engine_scan""")
    op.execute("ALTER TABLE platform_stop_progress DROP reconciliation_revision")
