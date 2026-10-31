"""One source-resumption probe per dispatch failure streak, with narrow hints."""

from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

_COLUMNS = "source_wait_since,source_wait_revision,source_resume_used,source_resume_claim"
_SCAN_COLUMNS = (
    ("paper_order_dispatch", _COLUMNS + ",attempts,claim_revision"),
    ("market_execution_state", "source,base,quote,ready,generation,lease_until,verified_at"),
    (
        "market_latest_prices",
        "source,base,quote,received_at,trade_at,reconciled_generation,effective_readiness",
    ),
    ("market_price_feed", "source,generation,lease_until,connected"),
)


def upgrade() -> None:
    op.execute("LOCK TABLE paper_order_dispatch IN ACCESS EXCLUSIVE MODE NOWAIT")
    op.execute("""ALTER TABLE paper_order_dispatch
      ADD source_wait_since timestamptz, ADD source_wait_revision bigint,
      ADD source_resume_used boolean NOT NULL DEFAULT false,
      ADD source_resume_claim boolean NOT NULL DEFAULT false""")
    # A downgrade discards the guard. On re-upgrade, an existing failure streak
    # has unknown probe history: conservatively suppress probes until a healthy
    # checkpoint resets attempts, rather than accidentally granting a second one.
    op.execute("ALTER TABLE paper_order_dispatch NO FORCE ROW LEVEL SECURITY")
    op.execute("UPDATE paper_order_dispatch SET source_resume_used=true WHERE attempts>0")
    op.execute("ALTER TABLE paper_order_dispatch FORCE ROW LEVEL SECURITY")
    op.execute(f"GRANT UPDATE({_COLUMNS}) ON paper_order_dispatch TO tiewtrade_engine")
    for table, columns in _SCAN_COLUMNS:
        op.execute(f"GRANT SELECT({columns}) ON {table} TO tiewtrade_engine_scan")
    # Healthy finish/covered-pair reschedule already reset attempts atomically.
    # Handle old and new writers identically, without requiring 0057 SQL on the
    # default-off path. No trigger copies or inspects a financial/source payload.
    op.execute("""CREATE FUNCTION paper_dispatch_source_reset() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      BEGIN
        NEW.source_wait_since:=NULL;
        NEW.source_wait_revision:=NULL;
        NEW.source_resume_used:=false;
        NEW.source_resume_claim:=false;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION paper_dispatch_source_reset() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION paper_dispatch_source_reset() TO tiewtrade_engine")
    op.execute("""CREATE TRIGGER paper_dispatch_source_reset
      BEFORE UPDATE OF attempts ON paper_order_dispatch
      FOR EACH ROW WHEN(NEW.attempts=0)
      EXECUTE FUNCTION paper_dispatch_source_reset()""")


def downgrade() -> None:
    # Disable source-resumption mode before downgrade, as with R9/R10 rollout.
    op.execute("LOCK TABLE paper_order_dispatch IN ACCESS EXCLUSIVE MODE NOWAIT")
    op.execute("DROP TRIGGER paper_dispatch_source_reset ON paper_order_dispatch")
    op.execute("DROP FUNCTION paper_dispatch_source_reset()")
    for table, columns in _SCAN_COLUMNS:
        op.execute(f"REVOKE SELECT({columns}) ON {table} FROM tiewtrade_engine_scan")
    op.execute("""ALTER TABLE paper_order_dispatch
      DROP source_wait_since, DROP source_wait_revision,
      DROP source_resume_used, DROP source_resume_claim""")
