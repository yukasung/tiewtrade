"""Index exact financial revisions for deferred chronological risk replay."""

from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing facts predate every F18 boundary. NULL means pre-protocol history,
    # not an inferred ordering among historical corrections.
    op.execute("ALTER TABLE paper_position_events ADD risk_source_revision bigint")
    op.execute("""CREATE FUNCTION risk_position_event_revision() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
        SELECT revision+1 INTO NEW.risk_source_revision FROM public.paper_position_activity
          WHERE episode_id=NEW.episode_id AND user_id=NEW.user_id;
        IF NEW.risk_source_revision IS NULL THEN
          RAISE EXCEPTION 'position revision unavailable' USING ERRCODE='TT028'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION risk_position_event_revision() FROM PUBLIC")
    op.execute("""CREATE TRIGGER risk_position_revision BEFORE INSERT ON paper_position_events
      FOR EACH ROW EXECUTE FUNCTION risk_position_event_revision()""")
    op.execute("""CREATE INDEX risk_position_event_version
      ON paper_position_events(episode_id,risk_source_revision)""")
    op.execute("""ALTER TABLE risk_financial_boundaries
      ADD sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE""")
    op.execute("GRANT USAGE ON SEQUENCE risk_financial_boundaries_sequence_seq TO tiewtrade_engine")
    op.execute("ALTER TABLE risk_owner_state ADD boundary_cursor bigint NOT NULL DEFAULT 0")


def downgrade() -> None:
    for table in ("risk_owner_state", "risk_financial_boundaries"):
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'versioned risk financial history prevents downgrade'; END IF; END $$""")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM paper_position_events
      WHERE risk_source_revision IS NOT NULL) THEN
      RAISE EXCEPTION 'versioned risk financial history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE risk_owner_state DROP boundary_cursor")
    op.execute("ALTER TABLE risk_financial_boundaries DROP sequence")
    op.execute("DROP INDEX risk_position_event_version")
    op.execute("DROP TRIGGER risk_position_revision ON paper_position_events")
    op.execute("DROP FUNCTION risk_position_event_revision()")
    op.execute("ALTER TABLE paper_position_events DROP risk_source_revision")
