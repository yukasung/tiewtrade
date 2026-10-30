"""Non-financial routing hints and one preference per original dispatch anchor."""

from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None

_TABLES = (
    "paper_order_dispatch",
    "paper_order_commands",
    "paper_order_command_results",
    "paper_orders",
    "paper_order_projections",
)

_REFRESH_TABLES = ("paper_orders", "paper_order_command_results", "paper_order_projections")
_SCAN_HINT_COLUMNS = (
    ("risk_limit_settings", "revision,latched"),
    ("risk_limit_evaluations", "user_id,mode,reason,replay_pending,setting_revision"),
    ("risk_owner_state", "episode_id,replay_pending"),
    ("risk_protocol_control", "publication_enabled,financial_enabled,admission_enabled"),
)


def upgrade() -> None:
    # Never wait in an inverted runtime lock order while holding a partial DDL
    # lock set. A busy rollout fails atomically and can retry after quiescence.
    op.execute("LOCK TABLE " + ",".join(_TABLES) + " IN ACCESS EXCLUSIVE MODE NOWAIT")
    op.execute("""ALTER TABLE paper_order_dispatch
      ADD routing_action text CHECK(routing_action IN ('NEW','CANCEL')),
      ADD routing_base text, ADD routing_quote text,
      ADD routing_stage text CHECK(routing_stage IN ('PENDING','ACTIVE','TERMINAL')),
      ADD preferred_for_due timestamptz""")
    # Invoker rights: runtime reads/writes stay inside the ENGINE owner's RLS.
    # No monetary value or raw document is copied to the scanner's projection.
    op.execute("""CREATE FUNCTION paper_order_routing(command uuid)
      RETURNS TABLE(action text,base text,quote text,stage text)
      LANGUAGE sql VOLATILE SET search_path=pg_catalog,public AS $$
        SELECT c.action,
          coalesce(o.base::text,c.payload#>>'{intent,base}'),
          coalesce(o.quote::text,c.payload#>>'{intent,quote}'),
          CASE WHEN r.command_id IS NULL THEN 'PENDING'
            WHEN c.action='NEW' AND r.state='SUCCEEDED'
              AND p.status IN ('ACCEPTED','PARTIALLY_FILLED')
              AND o.kind IN ('MARKET','LIMIT') THEN 'ACTIVE'
            WHEN r.state='REJECTED' OR c.action='CANCEL'
              OR p.status IN ('FILLED','CANCELED','EXPIRED','REJECTED') THEN 'TERMINAL'
          END
        FROM public.paper_order_commands c
        LEFT JOIN public.paper_order_command_results r ON r.command_id=c.id
        LEFT JOIN public.paper_orders o ON o.id=c.order_id
          AND o.user_id=c.user_id AND o.episode_id=c.episode_id
        LEFT JOIN public.paper_order_projections p ON p.order_id=o.id
        WHERE c.id=command
      $$""")
    op.execute("""CREATE FUNCTION paper_dispatch_routing_insert() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      BEGIN
        SELECT action,base,quote,stage INTO NEW.routing_action,NEW.routing_base,
          NEW.routing_quote,NEW.routing_stage FROM public.paper_order_routing(NEW.command_id);
        RETURN NEW;
      END $$""")
    op.execute("""CREATE FUNCTION paper_dispatch_routing_refresh() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      DECLARE command uuid;
      BEGIN
        IF TG_TABLE_NAME='paper_order_projections' THEN
          SELECT command_id INTO command FROM public.paper_orders WHERE id=NEW.order_id;
        ELSE command:=NEW.command_id;
        END IF;
        WITH hint AS MATERIALIZED(SELECT * FROM public.paper_order_routing(command))
        UPDATE public.paper_order_dispatch d
          SET routing_action=h.action,routing_base=h.base,
            routing_quote=h.quote,routing_stage=h.stage
          FROM hint h WHERE d.command_id=command
            AND (d.routing_action,d.routing_base,d.routing_quote,d.routing_stage)
              IS DISTINCT FROM (h.action,h.base,h.quote,h.stage);
        RETURN NEW;
      END $$""")
    for function in (
        "paper_order_routing(uuid)",
        "paper_dispatch_routing_insert()",
        "paper_dispatch_routing_refresh()",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO tiewtrade_engine")
    op.execute("""GRANT UPDATE(routing_action,routing_base,routing_quote,routing_stage,
      preferred_for_due)
      ON paper_order_dispatch TO tiewtrade_engine""")
    op.execute("""GRANT SELECT(routing_action,routing_base,routing_quote,routing_stage,
      preferred_for_due)
      ON paper_order_dispatch TO tiewtrade_engine_scan""")
    for table, columns in _SCAN_HINT_COLUMNS:
        op.execute(f"GRANT SELECT({columns}) ON {table} TO tiewtrade_engine_scan")
    # Migration-only owner backfill; any failure rolls FORCE RLS back atomically.
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("""UPDATE paper_order_dispatch d SET
      (routing_action,routing_base,routing_quote,routing_stage)=
      (SELECT action,base,quote,stage FROM paper_order_routing(d.command_id))""")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE TRIGGER paper_dispatch_routing_insert BEFORE INSERT ON paper_order_dispatch
      FOR EACH ROW EXECUTE FUNCTION paper_dispatch_routing_insert()""")
    for table in _REFRESH_TABLES:
        op.execute(f"""CREATE TRIGGER paper_dispatch_routing_insert AFTER INSERT ON {table}
          FOR EACH ROW EXECUTE FUNCTION paper_dispatch_routing_refresh()""")
    op.execute("""CREATE TRIGGER paper_dispatch_routing_status AFTER UPDATE OF status
      ON paper_order_projections FOR EACH ROW WHEN(OLD.status IS DISTINCT FROM NEW.status)
      EXECUTE FUNCTION paper_dispatch_routing_refresh()""")
    op.execute("""CREATE INDEX paper_dispatch_owner_due
      ON paper_order_dispatch(user_id,next_attempt_at,command_id) WHERE state<>'TERMINAL'""")


def downgrade() -> None:
    # Rollout contract: disable preference/use the R8 path before schema downgrade.
    op.execute("LOCK TABLE " + ",".join(_TABLES) + " IN ACCESS EXCLUSIVE MODE NOWAIT")
    op.execute("DROP INDEX paper_dispatch_owner_due")
    op.execute("DROP TRIGGER paper_dispatch_routing_status ON paper_order_projections")
    for table in _REFRESH_TABLES:
        op.execute(f"DROP TRIGGER paper_dispatch_routing_insert ON {table}")
    op.execute("DROP TRIGGER paper_dispatch_routing_insert ON paper_order_dispatch")
    op.execute("DROP FUNCTION paper_dispatch_routing_refresh()")
    op.execute("DROP FUNCTION paper_dispatch_routing_insert()")
    op.execute("DROP FUNCTION paper_order_routing(uuid)")
    for table, columns in _SCAN_HINT_COLUMNS:
        op.execute(f"REVOKE SELECT({columns}) ON {table} FROM tiewtrade_engine_scan")
    op.execute("""ALTER TABLE paper_order_dispatch DROP routing_action,DROP routing_base,
      DROP routing_quote,DROP routing_stage,DROP preferred_for_due""")
