"""Verified Paper source adoption and a DB capability fence for managed episodes."""

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

_TABLES = (
    "paper_wallet_state",
    "paper_wallet_ledger",
    "paper_wallet_episode_closures",
    "paper_position_activity",
    "paper_position_events",
    "paper_position_projections",
    "paper_position_external_fees",
    "paper_position_conflicts",
)


def upgrade() -> None:
    op.execute("""CREATE TABLE paper_order_initializations (
      episode_id uuid PRIMARY KEY, wallet_id uuid NOT NULL, user_id uuid NOT NULL,
      initialization_id uuid NOT NULL UNIQUE,
      source_proof text NOT NULL CHECK(source_proof ~ '^[0-9a-f]{64}$'),
      position_proof text NOT NULL CHECK(position_proof ~ '^[0-9a-f]{64}$'),
      baseline jsonb NOT NULL CHECK(jsonb_typeof(baseline)='object'),
      initialized_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_execution_profiles(episode_id,wallet_id,user_id))""")
    op.execute("ALTER TABLE paper_order_initializations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE paper_order_initializations FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY paper_order_initializations_self ON paper_order_initializations
      FOR ALL USING(user_id=tiewtrade_current_user_id())
      WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT,INSERT ON paper_order_initializations TO tiewtrade_engine")
    op.execute("SELECT tiewtrade_make_append_only('paper_order_initializations'::regclass)")
    # This is a mixed-version protocol fence, not a replacement for owner RLS/grants.
    op.execute("""CREATE FUNCTION tiewtrade_paper_writer_fence() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE before_episode uuid; after_episode uuid;
      BEGIN
        IF TG_OP<>'INSERT' THEN
          before_episode:=coalesce(to_jsonb(OLD)->>'episode_id',
                                   to_jsonb(OLD)->>'active_episode_id')::uuid;
        END IF;
        IF TG_OP<>'DELETE' THEN
          after_episode:=coalesce(to_jsonb(NEW)->>'episode_id',
                                  to_jsonb(NEW)->>'active_episode_id')::uuid;
        END IF;
        IF current_setting('tiewtrade.paper_writer_version',true) IS DISTINCT FROM 'F15_V1'
          AND EXISTS(SELECT 1 FROM public.paper_order_initializations
                     WHERE episode_id=before_episode OR episode_id=after_episode) THEN
          RAISE EXCEPTION USING ERRCODE='TT015',
            MESSAGE='managed Paper episode requires the F15 writer protocol';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION tiewtrade_paper_writer_fence() FROM PUBLIC")
    for table in _TABLES:
        op.execute(f"""CREATE TRIGGER paper_f15_writer_fence BEFORE INSERT OR UPDATE OR DELETE
          ON {table} FOR EACH ROW EXECUTE FUNCTION tiewtrade_paper_writer_fence()""")
    # Audit action shape extends the same parent constraint inherited by partitions.
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false',
        'WHEN ''PAPER_ORDER_SOURCE_INITIALIZED'' THEN
          actor_kind=''SYSTEM'' AND actor_id IS NULL AND mode=''PAPER''
          AND subject_kind=''PAPER_ORDER_ACTIVITY'' AND subject_id=details->>''episode_id''
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''episode_id'',''initialization_id'',''source_proof'']
          AND details-ARRAY[''episode_id'',''initialization_id'',''source_proof'']=''{}''::jsonb
          AND jsonb_typeof(details->''episode_id'')=''string''
          AND jsonb_typeof(details->''initialization_id'')=''string''
          AND jsonb_typeof(details->''source_proof'')=''string''
          AND details->>''episode_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
          AND details->>''initialization_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
          AND details->>''source_proof'' ~ ''^[0-9a-f]{64}$''
        ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||changed;
    END $$""")


def downgrade() -> None:
    op.execute("ALTER TABLE paper_order_initializations NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM paper_order_initializations) THEN
        RAISE EXCEPTION 'managed Paper episodes prevent writer fence downgrade';
      END IF;
    END $$""")
    for table in _TABLES:
        op.execute(f"DROP TRIGGER paper_f15_writer_fence ON {table}")
    op.execute("DROP FUNCTION tiewtrade_paper_writer_fence()")
    op.execute("DROP TABLE paper_order_initializations")
    op.execute("""DO $$ DECLARE definition text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape ' ||
        regexp_replace(definition,
          'WHEN ''PAPER_ORDER_SOURCE_INITIALIZED''.*ELSE false','ELSE false') || ' NOT VALID';
    END $$""")
