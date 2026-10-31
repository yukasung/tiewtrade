"""Exact immutable lifecycle cuts for bounded stop target enrollment."""

from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE risk_order_lifecycle (
      sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      user_id uuid NOT NULL,order_id uuid NOT NULL,episode_id uuid NOT NULL,
      base text NOT NULL,quote text NOT NULL,
      status text NOT NULL CHECK(status IN ('ACCEPTED','PARTIALLY_FILLED','FILLED',
        'CANCELED','EXPIRED','REJECTED')),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(order_id,user_id,episode_id,base,quote)
        REFERENCES paper_orders(id,user_id,episode_id,base,quote))""")
    # Old terminal facts precede every protocol stop. Never guess their relative
    # order retrospectively; snapshot existing projections at rollout instead.
    op.execute("ALTER TABLE paper_order_projections NO FORCE ROW LEVEL SECURITY")
    op.execute("""INSERT INTO risk_order_lifecycle(user_id,order_id,episode_id,base,quote,status)
      SELECT user_id,order_id,episode_id,base,quote,status FROM paper_order_projections""")
    op.execute("ALTER TABLE paper_order_projections FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE risk_order_lifecycle ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE risk_order_lifecycle FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY risk_lifecycle_owner ON risk_order_lifecycle FOR ALL
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT ON risk_order_lifecycle TO tiewtrade_engine")
    op.execute("SELECT tiewtrade_make_append_only('risk_order_lifecycle'::regclass)")
    op.execute("""CREATE INDEX risk_lifecycle_cut
      ON risk_order_lifecycle(order_id,recorded_at DESC,sequence DESC)""")
    op.execute("""CREATE FUNCTION risk_capture_order_lifecycle() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$ BEGIN
        IF TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status THEN
          INSERT INTO public.risk_order_lifecycle(user_id,order_id,episode_id,base,quote,status)
            VALUES(NEW.user_id,NEW.order_id,NEW.episode_id,NEW.base,NEW.quote,NEW.status);
        END IF;
        RETURN NULL;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION risk_capture_order_lifecycle() FROM PUBLIC")
    op.execute("""CREATE TRIGGER risk_lifecycle_capture
      AFTER INSERT OR UPDATE ON paper_order_projections
      FOR EACH ROW EXECUTE FUNCTION risk_capture_order_lifecycle()""")
    for table in ("paper_order_request_results", "paper_order_command_results"):
        op.execute(
            f"ALTER TABLE {table} ADD risk_recorded_at timestamptz "
            "NOT NULL DEFAULT clock_timestamp()"
        )
    op.execute("GRANT SELECT(risk_recorded_at) ON paper_order_command_results TO tiewtrade_api")


def downgrade() -> None:
    op.execute("LOCK TABLE risk_order_lifecycle IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE risk_order_lifecycle NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM risk_order_lifecycle) THEN
      RAISE EXCEPTION 'risk lifecycle history prevents downgrade'; END IF; END $$""")
    for table in ("paper_order_request_results", "paper_order_command_results"):
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'risk lifecycle history prevents downgrade'; END IF; END $$""")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER risk_lifecycle_capture ON paper_order_projections")
    op.execute("DROP FUNCTION risk_capture_order_lifecycle()")
    op.execute("DROP TABLE risk_order_lifecycle")
    for table in ("paper_order_request_results", "paper_order_command_results"):
        op.execute(f"ALTER TABLE {table} DROP risk_recorded_at")
