"""Public price journal and transaction-bound financial fences for F-18.

All protocol switches start disabled. This migration never opens order admission.
"""

# ruff: noqa: E501 -- preserve complete SQL predicates for review
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

_FINANCIAL = (
    "paper_wallet_state",
    "paper_wallet_ledger",
    "paper_wallet_episode_closures",
    "paper_position_activity",
    "paper_position_events",
    "paper_position_projections",
    "paper_position_external_fees",
    "paper_position_conflicts",
)
_USER_TABLES = ("risk_owner_state", "risk_boundary_claims", "risk_financial_boundaries")


def upgrade() -> None:
    op.execute("""CREATE TABLE risk_protocol_control (
      singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
      publication_enabled boolean NOT NULL DEFAULT false,
      financial_enabled boolean NOT NULL DEFAULT false,
      admission_enabled boolean NOT NULL DEFAULT false,
      CHECK(NOT financial_enabled OR publication_enabled),
      CHECK(NOT admission_enabled OR financial_enabled))""")
    op.execute("INSERT INTO risk_protocol_control(singleton) VALUES(true)")
    op.execute("""CREATE TABLE risk_price_publication (
      singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
      watermark bigint NOT NULL DEFAULT 0 CHECK(watermark>=0))""")
    op.execute("INSERT INTO risk_price_publication(singleton) VALUES(true)")
    op.execute("""CREATE TABLE market_risk_price_frames (
      id bigint PRIMARY KEY CHECK(id>0), publication_xid text NOT NULL,
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      proof text NOT NULL CHECK(proof ~ '^[0-9a-f]{64}$'),
      captured_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    op.execute("SELECT tiewtrade_make_append_only('market_risk_price_frames'::regclass)")
    op.execute("""GRANT SELECT ON risk_protocol_control,risk_price_publication,market_risk_price_frames
      TO tiewtrade_api,tiewtrade_engine,tiewtrade_market_data""")
    op.execute("""CREATE TABLE risk_owner_state (
      user_id uuid NOT NULL, mode text NOT NULL, wallet_id uuid, episode_id uuid,
      cursor bigint NOT NULL CHECK(cursor>=0), source_revision bigint NOT NULL CHECK(source_revision>=0),
      source_proof text CHECK(source_proof ~ '^[0-9a-f]{64}$'),
      book jsonb NOT NULL CHECK(jsonb_typeof(book)='object'),
      replay_pending boolean NOT NULL DEFAULT false,
      due_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(user_id,mode), FOREIGN KEY(user_id,mode) REFERENCES risk_limit_settings(user_id,mode),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((mode='PAPER' AND wallet_id IS NOT NULL AND episode_id IS NOT NULL)
         OR (mode='LIVE' AND wallet_id IS NULL AND episode_id IS NULL)))""")
    op.execute("""CREATE TABLE risk_boundary_claims (
      id uuid PRIMARY KEY,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      wallet_id uuid NOT NULL,episode_id uuid NOT NULL,after_episode_id uuid,
      kind text NOT NULL CHECK(kind IN ('INIT','FILL','CORRECTION','RESET','EPISODE','SETTING')),
      price_watermark bigint NOT NULL CHECK(price_watermark>=0),
      before_state jsonb NOT NULL CHECK(jsonb_typeof(before_state)='object'),
      transaction_id text NOT NULL DEFAULT pg_current_xact_id()::text,
      finalized boolean NOT NULL DEFAULT false,
      UNIQUE(id,user_id,mode), FOREIGN KEY(user_id,mode) REFERENCES risk_limit_settings(user_id,mode),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      FOREIGN KEY(after_episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id)
        DEFERRABLE INITIALLY DEFERRED)""")
    op.execute("""CREATE TABLE risk_financial_boundaries (
      id uuid PRIMARY KEY,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      wallet_id uuid NOT NULL,episode_id uuid NOT NULL,after_episode_id uuid,
      kind text NOT NULL CHECK(kind IN ('INIT','FILL','CORRECTION','RESET','EPISODE','SETTING')),
      price_watermark bigint NOT NULL CHECK(price_watermark>=0),
      before_state jsonb NOT NULL CHECK(jsonb_typeof(before_state)='object'),
      after_state jsonb NOT NULL CHECK(jsonb_typeof(after_state)='object'),
      replay_pending boolean NOT NULL,recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(id,user_id,mode) REFERENCES risk_boundary_claims(id,user_id,mode))""")
    for table in _USER_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO tiewtrade_engine")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api")
    op.execute("GRANT UPDATE ON risk_owner_state TO tiewtrade_engine")
    op.execute("GRANT UPDATE(finalized) ON risk_boundary_claims TO tiewtrade_engine")
    op.execute("SELECT tiewtrade_make_append_only('risk_financial_boundaries'::regclass)")
    op.execute("""GRANT SELECT(user_id,mode,due_at) ON risk_owner_state TO tiewtrade_engine_scan""")
    op.execute("CREATE INDEX risk_owner_due ON risk_owner_state(due_at,user_id,mode)")
    op.execute(
        "CREATE INDEX risk_boundaries_cursor ON risk_financial_boundaries(user_id,mode,price_watermark,recorded_at,id)"
    )
    op.execute("""ALTER TABLE risk_limit_evaluations ADD unavailable_since timestamptz,
      ADD pause_alert_due boolean NOT NULL DEFAULT false""")
    _publication()
    _financial()


def _publication() -> None:
    op.execute("""CREATE FUNCTION risk_publication_lock_held(shared boolean) RETURNS boolean
      LANGUAGE sql VOLATILE SET search_path=pg_catalog AS $$ SELECT EXISTS(
        SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid() AND granted
          AND classid=hashtext('tiewtrade.risk_publication')::oid
          AND objid=hashtext('primary_spot')::oid AND objsubid=2
          AND (mode='ExclusiveLock' OR (shared AND mode='ShareLock'))) $$""")
    op.execute("""CREATE FUNCTION risk_publication_fence() RETURNS bigint
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      BEGIN
        PERFORM pg_advisory_xact_lock(hashtext('tiewtrade.risk_publication'),hashtext('primary_spot'));
        PERFORM set_config('tiewtrade.risk_publication_version','F18_V1',true);
        RETURN (SELECT watermark FROM public.risk_price_publication);
      END $$""")
    op.execute("""CREATE FUNCTION risk_financial_fence() RETURNS bigint
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      BEGIN
        PERFORM pg_advisory_xact_lock_shared(hashtext('tiewtrade.risk_publication'),hashtext('primary_spot'));
        PERFORM set_config('tiewtrade.risk_financial_version','F18_V1',true);
        RETURN (SELECT watermark FROM public.risk_price_publication);
      END $$""")
    op.execute("""CREATE FUNCTION risk_price_writer_guard() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      BEGIN
        IF (SELECT publication_enabled FROM public.risk_protocol_control) AND (
          current_setting('tiewtrade.risk_publication_version',true) IS DISTINCT FROM 'F18_V1'
          OR NOT public.risk_publication_lock_held(false)) THEN
          RAISE EXCEPTION 'price publication requires the F18 writer fence' USING ERRCODE='TT028';
        END IF;
        RETURN NULL;
      END $$""")
    op.execute("""CREATE FUNCTION risk_capture_price_frame() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE frame jsonb; watermark bigint;
      BEGIN
        IF NOT (SELECT publication_enabled FROM public.risk_protocol_control) THEN RETURN NULL; END IF;
        IF NOT public.risk_publication_lock_held(false) THEN
          RAISE EXCEPTION 'publication frame requires exclusive fence' USING ERRCODE='TT028'; END IF;
        SELECT jsonb_build_object('feed',(SELECT to_jsonb(f) FROM public.market_price_feed f
            WHERE f.source='primary_spot'),'rows',coalesce((SELECT jsonb_agg(
            jsonb_build_object('source',p.source,'base',p.base,'quote',p.quote,
              'amount',p.amount::text,'trade_id',p.trade_id,'trade_at',p.trade_at,
              'received_at',p.received_at,'observation_kind',p.observation_kind,
              'reconciled_generation',p.reconciled_generation,'revision',p.revision,
              'effective_readiness',p.effective_readiness,'reason',p.reason,
              'order_ambiguous_at',p.order_ambiguous_at)
            ORDER BY p.base,p.quote) FROM public.market_latest_prices p
            WHERE p.source='primary_spot'),'[]'::jsonb)) INTO frame;
        UPDATE public.risk_price_publication p SET watermark=p.watermark+1
          RETURNING p.watermark INTO watermark;
        INSERT INTO public.market_risk_price_frames(id,publication_xid,payload,proof)
          VALUES(watermark,pg_current_xact_id()::text,frame,
            encode(sha256(convert_to(frame::text,'UTF8')),'hex'));
        RETURN NULL;
      END $$""")
    for table in ("market_price_feed", "market_latest_prices"):
        op.execute(f"""CREATE TRIGGER risk_publication_guard BEFORE INSERT OR UPDATE OR DELETE ON {table}
          FOR EACH STATEMENT EXECUTE FUNCTION risk_price_writer_guard()""")
        op.execute(f"""CREATE TRIGGER risk_publication_capture AFTER INSERT OR UPDATE OR DELETE ON {table}
          FOR EACH STATEMENT EXECUTE FUNCTION risk_capture_price_frame()""")
    for function in (
        "risk_publication_lock_held(boolean)",
        "risk_publication_fence()",
        "risk_financial_fence()",
        "risk_price_writer_guard()",
        "risk_capture_price_frame()",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION risk_publication_lock_held(boolean) TO tiewtrade_engine,tiewtrade_market_data"
    )
    op.execute("GRANT EXECUTE ON FUNCTION risk_publication_fence() TO tiewtrade_market_data")
    op.execute("GRANT EXECUTE ON FUNCTION risk_financial_fence() TO tiewtrade_engine")


def _financial() -> None:
    op.execute("""CREATE FUNCTION risk_require_financial_boundary() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      DECLARE row_data jsonb; claim uuid; episode uuid; wallet uuid; owner uuid;
      BEGIN
        IF NOT (SELECT financial_enabled FROM public.risk_protocol_control) THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END IF;
        row_data:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
        owner:=(row_data->>'user_id')::uuid;
        IF NOT EXISTS(SELECT 1 FROM public.risk_limit_settings WHERE user_id=owner AND mode='PAPER') THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END IF;
        episode:=coalesce(row_data->>'episode_id',row_data->>'active_episode_id')::uuid;
        wallet:=coalesce((row_data->>'wallet_id')::uuid,
          (SELECT e.wallet_id FROM public.paper_wallet_episodes e WHERE e.id=episode AND e.user_id=owner));
        claim:=nullif(current_setting('tiewtrade.risk_boundary_id',true),'')::uuid;
        IF current_setting('tiewtrade.risk_financial_version',true) IS DISTINCT FROM 'F18_V1'
          OR NOT public.risk_publication_lock_held(true)
          OR NOT EXISTS(SELECT 1 FROM public.risk_boundary_claims b
            WHERE b.id=claim AND b.user_id=owner AND b.mode='PAPER' AND b.wallet_id=wallet
            AND (b.episode_id=episode OR b.after_episode_id=episode)
            AND b.transaction_id=pg_current_xact_id()::text AND NOT b.finalized) THEN
          RAISE EXCEPTION 'managed financial write requires the F18 boundary' USING ERRCODE='TT028'; END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
      END $$""")
    for table in _FINANCIAL:
        op.execute(f"""CREATE TRIGGER paper_f18_writer_fence BEFORE INSERT OR UPDATE OR DELETE
          ON {table} FOR EACH ROW EXECUTE FUNCTION risk_require_financial_boundary()""")
    op.execute("""CREATE FUNCTION risk_require_finalized_boundary() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      BEGIN
        IF NOT EXISTS(SELECT 1 FROM public.risk_boundary_claims c
          JOIN public.risk_financial_boundaries b ON b.id=c.id AND b.user_id=c.user_id AND b.mode=c.mode
          WHERE c.id=NEW.id AND c.finalized AND b.wallet_id=c.wallet_id
            AND b.episode_id=c.episode_id AND b.price_watermark=c.price_watermark
            AND b.kind=c.kind AND b.before_state=c.before_state
            AND b.after_episode_id IS NOT DISTINCT FROM c.after_episode_id) THEN
          RAISE EXCEPTION 'financial boundary must be finalized in its transaction' USING ERRCODE='TT028';
        END IF;
        RETURN NULL;
      END $$""")
    op.execute("""CREATE CONSTRAINT TRIGGER risk_boundary_finalize
      AFTER INSERT ON risk_boundary_claims DEFERRABLE INITIALLY DEFERRED
      FOR EACH ROW EXECUTE FUNCTION risk_require_finalized_boundary()""")
    op.execute(
        "REVOKE ALL ON FUNCTION risk_require_financial_boundary(),risk_require_finalized_boundary() FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION risk_require_financial_boundary(),risk_require_finalized_boundary() TO tiewtrade_engine"
    )


def downgrade() -> None:
    op.execute(
        "LOCK TABLE risk_protocol_control,risk_price_publication,market_risk_price_frames IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM market_risk_price_frames)
      OR EXISTS(SELECT 1 FROM risk_protocol_control WHERE publication_enabled OR financial_enabled OR admission_enabled)
      THEN RAISE EXCEPTION 'risk protocol history prevents downgrade'; END IF; END $$""")
    for table in _USER_TABLES:
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'risk boundary history prevents downgrade'; END IF; END $$""")
    for table in _FINANCIAL:
        op.execute(f"DROP TRIGGER paper_f18_writer_fence ON {table}")
    for table in ("market_price_feed", "market_latest_prices"):
        op.execute(f"DROP TRIGGER risk_publication_capture ON {table}")
        op.execute(f"DROP TRIGGER risk_publication_guard ON {table}")
    op.execute("DROP TRIGGER risk_boundary_finalize ON risk_boundary_claims")
    for function in (
        "risk_require_finalized_boundary()",
        "risk_require_financial_boundary()",
        "risk_capture_price_frame()",
        "risk_price_writer_guard()",
        "risk_financial_fence()",
        "risk_publication_fence()",
        "risk_publication_lock_held(boolean)",
    ):
        op.execute(f"DROP FUNCTION {function}")
    op.execute("ALTER TABLE risk_limit_evaluations DROP unavailable_since,DROP pause_alert_due")
    for table in reversed(_USER_TABLES):
        op.execute(f"DROP TABLE {table}")
    for table in ("market_risk_price_frames", "risk_price_publication", "risk_protocol_control"):
        op.execute(f"DROP TABLE {table}")
