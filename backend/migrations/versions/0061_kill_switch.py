"""Durable user/platform kill-switch authority and Paper effect linkage."""

# ruff: noqa: E501 -- keep reviewed SQL predicates and signatures intact

from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

_TABLES = (
    "trading_stop_requests",
    "trading_stop_results",
    "trading_stop_events",
    "trading_stop_causes",
    "platform_stop_progress",
    "platform_stop_targets",
    "trading_stop_dispatch",
    "trading_reconciliation_clock",
)


def upgrade() -> None:
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind CHECK(bucket_kind IN
      ('API_KEY_ADD','API_KEY_RETRY','PRICE_STREAM_HANDSHAKE','PAPER_WALLET_MUTATION',
       'PAPER_ORDER_NEW','PAPER_ORDER_CANCEL','RISK_LIMIT_MUTATION','TRADING_STOP_MUTATION'))""")
    op.execute("""CREATE TABLE trading_stop_requests (
      id uuid PRIMARY KEY,user_id uuid NOT NULL,scope_owner_id uuid,mode text,
      action text NOT NULL CHECK(action IN ('STOP','RESUME')),
      cause text NOT NULL CHECK(cause IN ('USER','SYSTEM','LOSS_LIMIT','PLATFORM')),
      actor_role text NOT NULL CHECK(actor_role IN ('USER','SYSTEM','PLATFORM_ADMIN','PLATFORM_OWNER')),
      idempotency_key uuid NOT NULL,fingerprint text NOT NULL CHECK(length(fingerprint)=64),
      expected_stop_id uuid,expected_stop_revision bigint,expected_summary_revision bigint,
      expected_reconciliation_revision bigint,
      reason_code text NOT NULL CHECK(length(reason_code) BETWEEN 1 AND 64),
      reason_text text CHECK(reason_text IS NULL OR char_length(reason_text) BETWEEN 1 AND 500),
      generation bigint NOT NULL CHECK(generation>0),
      revision bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(id,user_id),
      CHECK((cause='PLATFORM' AND scope_owner_id IS NULL AND mode IS NULL)
        OR (cause<>'PLATFORM' AND scope_owner_id=user_id AND mode IN ('PAPER','LIVE'))),
      CHECK((action='STOP' AND expected_stop_id IS NULL AND expected_stop_revision IS NULL)
        OR (action='RESUME' AND expected_stop_id IS NOT NULL AND expected_stop_revision IS NOT NULL)))""")
    op.execute("""CREATE UNIQUE INDEX trading_stop_request_key
      ON trading_stop_requests(user_id,action,coalesce(mode,'PLATFORM'),idempotency_key)""")
    op.execute("""CREATE INDEX trading_stop_effective
      ON trading_stop_requests(coalesce(scope_owner_id,'00000000-0000-0000-0000-000000000000'),
        coalesce(mode,'PLATFORM'),cause,revision DESC)""")
    op.execute("""CREATE TABLE trading_stop_results (
      request_id uuid PRIMARY KEY,user_id uuid NOT NULL,
      state text NOT NULL CHECK(state IN ('APPLIED','REJECTED')),
      stop_id uuid NOT NULL,revision bigint NOT NULL CHECK(revision>0),failure_code text,
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id) REFERENCES trading_stop_requests(id,user_id),
      CHECK((state='APPLIED' AND failure_code IS NULL)
        OR (state='REJECTED' AND failure_code IS NOT NULL)))""")
    op.execute("""CREATE TABLE trading_stop_events (
      sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      request_id uuid NOT NULL UNIQUE,user_id uuid NOT NULL,stop_id uuid NOT NULL,
      scope_owner_id uuid,mode text,cause text NOT NULL,active boolean NOT NULL,
      revision bigint NOT NULL CHECK(revision>0),recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id) REFERENCES trading_stop_requests(id,user_id))""")
    op.execute("""CREATE TABLE trading_stop_causes (
      scope_key text NOT NULL,cause text NOT NULL,scope_owner_id uuid,mode text,
      stop_id uuid NOT NULL,request_id uuid NOT NULL,user_id uuid NOT NULL,
      generation bigint NOT NULL CHECK(generation>0),revision bigint NOT NULL CHECK(revision>0),
      active boolean NOT NULL,updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(scope_key,cause),
      FOREIGN KEY(request_id,user_id) REFERENCES trading_stop_requests(id,user_id))""")
    op.execute("""CREATE TABLE platform_stop_progress (
      stop_id uuid PRIMARY KEY,user_id uuid NOT NULL,request_id uuid NOT NULL UNIQUE,
      discovery_complete boolean NOT NULL DEFAULT false,cursor uuid,
      owner_count bigint NOT NULL DEFAULT 0 CHECK(owner_count>=0),
      pending_count bigint NOT NULL DEFAULT 0 CHECK(pending_count>=0),
      failed_count bigint NOT NULL DEFAULT 0 CHECK(failed_count>=0),
      revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id) REFERENCES trading_stop_requests(id,user_id))""")
    op.execute("""CREATE TABLE platform_stop_targets (
      stop_id uuid NOT NULL,user_id uuid NOT NULL,wallet_id uuid NOT NULL,episode_id uuid NOT NULL,
      risk_stop_id uuid NOT NULL UNIQUE,recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(stop_id,user_id),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE trading_stop_dispatch (
      request_id uuid PRIMARY KEY,user_id uuid NOT NULL,
      next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      attempt integer NOT NULL DEFAULT 0 CHECK(attempt>=0),
      FOREIGN KEY(request_id,user_id) REFERENCES trading_stop_requests(id,user_id))""")
    op.execute("""CREATE INDEX trading_stop_dispatch_due
      ON trading_stop_dispatch(next_attempt_at,request_id)""")
    op.execute("""CREATE TABLE trading_reconciliation_clock (
      singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
      revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0))""")
    op.execute("INSERT INTO trading_reconciliation_clock(singleton) VALUES(true)")
    op.execute("""CREATE FUNCTION advance_trading_reconciliation_clock() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$ BEGIN
        IF EXISTS(SELECT 1 FROM public.trading_stop_causes
          WHERE scope_key='PLATFORM' AND cause='PLATFORM' AND active) THEN
          UPDATE public.trading_reconciliation_clock SET revision=revision+1 WHERE singleton;
        END IF;
        RETURN NULL; END $$""")
    op.execute("""CREATE TRIGGER paper_position_activity_reconciliation_clock
      AFTER INSERT OR UPDATE OR DELETE ON paper_position_activity
      FOR EACH STATEMENT EXECUTE FUNCTION advance_trading_reconciliation_clock()""")

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY trading_stop_requests_owner ON trading_stop_requests FOR SELECT
      USING(scope_owner_id=tiewtrade_current_user_id() OR user_id=tiewtrade_current_user_id()
        OR cause='PLATFORM')""")
    op.execute("""CREATE POLICY trading_stop_requests_insert ON trading_stop_requests FOR INSERT
      WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("""CREATE POLICY trading_stop_results_owner ON trading_stop_results FOR ALL
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("""CREATE POLICY trading_stop_results_platform_read ON trading_stop_results
      FOR SELECT USING(EXISTS(SELECT 1 FROM trading_stop_requests r
        WHERE r.id=request_id AND r.cause='PLATFORM'))""")
    for table in ("trading_stop_events", "trading_stop_causes"):
        op.execute(f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id() OR scope_owner_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id() OR scope_owner_id=tiewtrade_current_user_id())""")
    op.execute("""CREATE POLICY trading_stop_causes_platform_engine ON trading_stop_causes
      FOR ALL TO tiewtrade_engine USING(cause='PLATFORM') WITH CHECK(cause='PLATFORM')""")
    op.execute("""CREATE POLICY trading_stop_causes_platform_migrator ON trading_stop_causes
      FOR SELECT TO tiewtrade_migrator
      USING(scope_key='PLATFORM' AND cause='PLATFORM')""")
    op.execute("""CREATE POLICY platform_stop_progress_read ON platform_stop_progress FOR SELECT
      USING(true)""")
    op.execute("""CREATE POLICY platform_stop_progress_owner ON platform_stop_progress FOR ALL
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("""CREATE POLICY platform_stop_targets_owner ON platform_stop_targets FOR ALL
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("""CREATE POLICY trading_stop_dispatch_owner ON trading_stop_dispatch FOR ALL
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute(
        "CREATE POLICY trading_reconciliation_clock_read ON trading_reconciliation_clock FOR SELECT USING(true)"
    )
    op.execute("""CREATE POLICY trading_reconciliation_clock_update
      ON trading_reconciliation_clock FOR UPDATE TO tiewtrade_migrator
      USING(singleton) WITH CHECK(singleton)""")

    for table in (
        "trading_stop_requests",
        "trading_stop_results",
        "trading_stop_events",
        "platform_stop_targets",
    ):
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
    op.execute(
        "GRANT SELECT ON trading_stop_requests,trading_stop_results,trading_stop_events,trading_stop_causes,platform_stop_progress,platform_stop_targets TO tiewtrade_api"
    )
    op.execute("GRANT SELECT ON trading_stop_requests TO tiewtrade_engine")
    op.execute("""GRANT INSERT(id,user_id,scope_owner_id,mode,action,cause,actor_role,
      idempotency_key,fingerprint,reason_code,generation,recorded_at)
      ON trading_stop_requests TO tiewtrade_engine""")
    op.execute("GRANT USAGE ON SEQUENCE trading_stop_requests_revision_seq TO tiewtrade_engine")
    op.execute(
        "GRANT SELECT,INSERT ON trading_stop_results,trading_stop_events,platform_stop_targets TO tiewtrade_engine"
    )
    op.execute("GRANT SELECT,INSERT,UPDATE ON trading_stop_dispatch TO tiewtrade_engine")
    op.execute(
        "GRANT SELECT,INSERT,UPDATE ON trading_stop_causes,platform_stop_progress TO tiewtrade_engine"
    )
    op.execute("GRANT USAGE ON SEQUENCE trading_stop_events_sequence_seq TO tiewtrade_engine")
    op.execute("""GRANT SELECT(id,user_id,scope_owner_id,mode,action,cause,actor_role,generation,
      revision,recorded_at,expected_stop_id) ON trading_stop_requests TO tiewtrade_engine_scan""")
    op.execute(
        """GRANT SELECT(request_id,state) ON trading_stop_results TO tiewtrade_engine_scan"""
    )
    op.execute("""GRANT SELECT(user_id,wallet_id,active_episode_id) ON paper_wallet_state
      TO tiewtrade_engine_scan""")
    op.execute("""GRANT SELECT(stop_id,user_id,discovery_complete,cursor) ON platform_stop_progress
      TO tiewtrade_engine_scan""")
    op.execute("""GRANT SELECT(stop_id,user_id,episode_id,risk_stop_id) ON platform_stop_targets
      TO tiewtrade_engine_scan""")
    op.execute("GRANT SELECT ON trading_stop_dispatch TO tiewtrade_engine_scan")
    op.execute("GRANT SELECT ON trading_reconciliation_clock TO tiewtrade_api,tiewtrade_engine")
    op.execute("""CREATE POLICY paper_position_activity_api_stop_read ON paper_position_activity
      FOR SELECT TO tiewtrade_api USING(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT ON paper_position_activity TO tiewtrade_api")
    op.execute("""GRANT SELECT(episode_id,availability,revision) ON paper_position_activity
      TO tiewtrade_engine_scan""")
    op.execute("""GRANT SELECT(stop_id,target_count,pending_count,failed_count,target_set_complete)
      ON risk_stop_progress TO tiewtrade_engine_scan""")

    op.execute("ALTER TABLE risk_stop_requests ALTER event_id DROP NOT NULL")
    op.execute("ALTER TABLE risk_stop_requests ALTER risk_revision DROP NOT NULL")
    op.execute(
        "CREATE INDEX risk_stop_targets_stop_sequence "
        "ON risk_stop_targets(stop_id,enrolled_sequence)"
    )
    op.execute("""ALTER TABLE risk_stop_requests
      ADD authority_request_id uuid REFERENCES trading_stop_requests(id),
      ADD cause text NOT NULL DEFAULT 'LOSS_LIMIT'
        CHECK(cause IN ('USER','SYSTEM','LOSS_LIMIT','PLATFORM')),
      ADD target_policy text NOT NULL DEFAULT 'ALL'
        CHECK(target_policy IN ('ALL','BOT_ONLY')),
      ADD CONSTRAINT risk_stop_requests_authority_source CHECK((event_id IS NOT NULL AND risk_revision IS NOT NULL
        AND cause='LOSS_LIMIT') OR (event_id IS NULL AND risk_revision IS NULL
        AND authority_request_id IS NOT NULL AND cause IN ('USER','SYSTEM','PLATFORM')))""")
    op.execute("""INSERT INTO trading_stop_requests
      (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,fingerprint,
       reason_code,generation,recorded_at)
      SELECT r.id,r.user_id,r.user_id,r.mode,'STOP','LOSS_LIMIT','SYSTEM',r.id,
        repeat('0',64),'RISK_LOSS_LIMIT_REACHED',
        row_number() OVER(PARTITION BY r.user_id,r.mode ORDER BY r.recorded_at,r.id),r.recorded_at
      FROM risk_stop_requests r""")
    # Populate only the newly-added linkage column. Existing stop facts stay
    # byte-for-byte unchanged; the migrator briefly bypasses the append-only
    # row trigger because runtime roles can never perform this backfill.
    op.execute("ALTER TABLE risk_stop_requests DISABLE TRIGGER tiewtrade_append_only_row")
    op.execute("UPDATE risk_stop_requests SET authority_request_id=id WHERE cause='LOSS_LIMIT'")
    op.execute("ALTER TABLE risk_stop_requests ENABLE TRIGGER tiewtrade_append_only_row")
    op.execute("""INSERT INTO trading_stop_results(request_id,user_id,state,stop_id,revision)
      SELECT id,user_id,'APPLIED',id,revision FROM trading_stop_requests WHERE cause='LOSS_LIMIT'""")
    op.execute("""INSERT INTO trading_stop_events
      (request_id,user_id,stop_id,scope_owner_id,mode,cause,active,revision,recorded_at)
      SELECT id,user_id,id,scope_owner_id,mode,cause,true,revision,recorded_at
      FROM trading_stop_requests WHERE cause='LOSS_LIMIT'""")
    # Historical risk stops that are no longer latched must not become active
    # merely because the shared authority did not exist when they completed.
    # Record an explicit migrated RESUME fact for every inactive historical
    # stop.  For a currently latched owner/mode only its newest stop remains
    # unresolved and therefore authoritative.
    op.execute("""WITH inactive AS (
        SELECT s.*,gen_random_uuid() AS resume_id
        FROM trading_stop_requests s
        WHERE s.cause='LOSS_LIMIT' AND s.action='STOP' AND NOT EXISTS (
          SELECT 1 FROM risk_limit_settings l
          WHERE l.user_id=s.user_id AND l.mode=s.mode AND l.latched
            AND s.id=(SELECT newest.id FROM trading_stop_requests newest
              WHERE newest.user_id=s.user_id AND newest.mode=s.mode
                AND newest.cause='LOSS_LIMIT' AND newest.action='STOP'
              ORDER BY newest.revision DESC LIMIT 1))
      )
      INSERT INTO trading_stop_requests
        (id,user_id,scope_owner_id,mode,action,cause,actor_role,idempotency_key,fingerprint,
         expected_stop_id,expected_stop_revision,expected_summary_revision,
         expected_reconciliation_revision,reason_code,generation,recorded_at)
      SELECT resume_id,user_id,scope_owner_id,mode,'RESUME',cause,'SYSTEM',resume_id,
        repeat('0',64),id,revision,0,0,'LOSS_MIGRATION_INACTIVE',generation,clock_timestamp()
      FROM inactive""")
    op.execute("""INSERT INTO trading_stop_results(request_id,user_id,state,stop_id,revision)
      SELECT r.id,r.user_id,'APPLIED',r.expected_stop_id,r.revision
      FROM trading_stop_requests r WHERE r.reason_code='LOSS_MIGRATION_INACTIVE'""")
    op.execute("""INSERT INTO trading_stop_events
      (request_id,user_id,stop_id,scope_owner_id,mode,cause,active,revision,recorded_at)
      SELECT r.id,r.user_id,r.expected_stop_id,r.scope_owner_id,r.mode,r.cause,false,
        r.revision,r.recorded_at
      FROM trading_stop_requests r WHERE r.reason_code='LOSS_MIGRATION_INACTIVE'""")
    op.execute("""INSERT INTO trading_stop_causes
      (scope_key,cause,scope_owner_id,mode,stop_id,request_id,user_id,generation,revision,active)
      SELECT DISTINCT ON (r.user_id,r.mode) r.mode||':'||r.user_id::text,r.cause,r.user_id,r.mode,
        r.id,r.id,r.user_id,r.generation,r.revision,true
      FROM trading_stop_requests r JOIN risk_limit_settings s
        ON s.user_id=r.user_id AND s.mode=r.mode AND s.latched
      WHERE r.cause='LOSS_LIMIT' ORDER BY r.user_id,r.mode,r.revision DESC""")
    op.execute("""CREATE UNIQUE INDEX risk_stop_authority_owner
      ON risk_stop_requests(authority_request_id,user_id) WHERE authority_request_id IS NOT NULL""")
    for table in ("paper_order_requests", "paper_order_commands"):
        op.execute(f"""ALTER TABLE {table}
          ADD admitted_global_stop_revision bigint NOT NULL DEFAULT 0 CHECK(admitted_global_stop_revision>=0),
          ADD admitted_owner_stop_revision bigint NOT NULL DEFAULT 0 CHECK(admitted_owner_stop_revision>=0)""")

    op.execute("""CREATE FUNCTION trading_stop_audit_shape(d jsonb) RETURNS boolean
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$ SELECT (
        jsonb_typeof(d)='object' AND d ?& ARRAY['request_id','stop_id','cause','scope','revision','reason_code']
        AND d-ARRAY['request_id','stop_id','cause','scope','revision','reason_code']='{}'::jsonb
        AND d->>'request_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
        AND d->>'stop_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
        AND d->>'cause' IN ('USER','SYSTEM','LOSS_LIMIT','PLATFORM')
        AND d->>'scope' IN ('PAPER','LIVE','PLATFORM')
        AND jsonb_typeof(d->'revision')='number' AND (d->>'revision')::bigint>0
        AND length(d->>'reason_code') BETWEEN 1 AND 64) IS TRUE $$""")
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false',
        'WHEN ''STOP_REQUESTED'' THEN subject_kind=''TRADING_STOP''
          AND actor_kind IN (''USER'',''PLATFORM'') AND actor_id=owner_user_id
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL AND trading_stop_audit_shape(details)
         WHEN ''RESUME_REQUESTED'' THEN subject_kind=''TRADING_STOP''
          AND actor_kind IN (''USER'',''PLATFORM'') AND actor_id=owner_user_id
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL AND trading_stop_audit_shape(details)
         WHEN ''STOP_UPDATED'' THEN subject_kind=''TRADING_STOP'' AND actor_kind=''SYSTEM''
          AND actor_id IS NULL AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND trading_stop_audit_shape(details)
         WHEN ''PLATFORM_STOPPED'' THEN subject_kind=''TRADING_STOP'' AND actor_kind=''SYSTEM''
          AND actor_id IS NULL AND mode=''NOT_APPLICABLE'' AND outcome=''SUCCEEDED''
          AND failure_code IS NULL AND trading_stop_audit_shape(details)
         WHEN ''RESUMED'' THEN subject_kind=''TRADING_STOP'' AND actor_kind=''SYSTEM''
          AND actor_id IS NULL AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND trading_stop_audit_shape(details)
         WHEN ''RESUME_REJECTED'' THEN subject_kind=''TRADING_STOP'' AND actor_kind=''SYSTEM''
          AND actor_id IS NULL AND outcome=''REJECTED'' AND failure_code IS NULL
          AND trading_stop_audit_shape(details)
         ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||changed;
    END $$""")

    op.execute("""CREATE FUNCTION submit_trading_stop_request(
      request_id uuid,requester uuid,request_mode text,request_action text,request_key uuid,
      request_fingerprint text,expected_stop uuid,expected_revision bigint,
      expected_summary bigint,expected_reconciliation bigint,request_reason_code text,
      request_reason_text text,platform_scope boolean) RETURNS SETOF trading_stop_requests
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE prior public.trading_stop_requests; next_generation bigint; row public.trading_stop_requests;
        member_role text; audit_action text; audit_actor text; scope_name text; request_cause text;
      BEGIN
        IF requester IS DISTINCT FROM public.tiewtrade_current_user_id() THEN
          RAISE EXCEPTION 'stop requester mismatch' USING ERRCODE='42501'; END IF;
        IF request_action NOT IN ('STOP','RESUME') OR request_fingerprint !~ '^[0-9a-f]{64}$'
          OR request_reason_code IS NULL OR length(request_reason_code) NOT BETWEEN 1 AND 64 THEN
          RAISE EXCEPTION 'invalid stop request' USING ERRCODE='23514'; END IF;
        IF platform_scope THEN
          IF request_mode IS NOT NULL THEN RAISE EXCEPTION 'platform mode invalid' USING ERRCODE='23514'; END IF;
          SELECT role INTO member_role FROM public.platform_memberships WHERE user_id=requester;
          IF member_role IS NULL OR (request_action='RESUME' AND member_role<>'PLATFORM_OWNER') THEN
            RAISE EXCEPTION 'platform stop authorization denied' USING ERRCODE='42501'; END IF;
          PERFORM pg_advisory_xact_lock(hashtextextended('trading-stop:global',0));
        ELSE
          member_role:='USER';
          IF request_mode NOT IN ('PAPER','LIVE') THEN RAISE EXCEPTION 'owner mode invalid' USING ERRCODE='23514'; END IF;
          PERFORM pg_advisory_xact_lock_shared(hashtextextended('trading-stop:global',0));
          PERFORM pg_advisory_xact_lock(hashtextextended(
            CASE WHEN request_mode='PAPER' THEN 'paper-wallet:' ELSE 'risk-live:' END||requester::text,0));
        END IF;
        request_cause:=CASE WHEN platform_scope THEN 'PLATFORM' WHEN request_action='STOP' THEN 'USER'
          ELSE (SELECT cause FROM public.trading_stop_requests
            WHERE id=expected_stop AND scope_owner_id=requester AND mode=request_mode AND action='STOP') END;
        IF request_cause IS NULL OR (NOT platform_scope AND request_cause='PLATFORM') THEN
          RAISE EXCEPTION 'resume stop is unavailable' USING ERRCODE='23514'; END IF;
        SELECT * INTO prior FROM public.trading_stop_requests r WHERE r.user_id=requester
          AND r.action=request_action AND coalesce(r.mode,'PLATFORM')=coalesce(request_mode,'PLATFORM')
          AND r.idempotency_key=request_key;
        IF FOUND THEN
          IF prior.fingerprint<>request_fingerprint THEN
            RAISE EXCEPTION 'stop idempotency conflict' USING ERRCODE='23505'; END IF;
          RETURN NEXT prior; RETURN;
        END IF;
        IF request_action='RESUME' AND (expected_stop IS NULL OR expected_revision IS NULL) THEN
          RAISE EXCEPTION 'resume expectation missing' USING ERRCODE='23514'; END IF;
        SELECT coalesce(max(generation),0)+1 INTO next_generation
          FROM public.trading_stop_requests r WHERE r.action='STOP'
          AND r.cause=request_cause
          AND r.scope_owner_id IS NOT DISTINCT FROM CASE WHEN platform_scope THEN NULL ELSE requester END
          AND r.mode IS NOT DISTINCT FROM request_mode;
        INSERT INTO public.trading_stop_requests(id,user_id,scope_owner_id,mode,action,cause,
          actor_role,idempotency_key,fingerprint,expected_stop_id,expected_stop_revision,
          expected_summary_revision,expected_reconciliation_revision,reason_code,reason_text,generation)
        VALUES(request_id,requester,CASE WHEN platform_scope THEN NULL ELSE requester END,request_mode,
          request_action,request_cause,member_role,
          request_key,request_fingerprint,expected_stop,expected_revision,expected_summary,
          expected_reconciliation,request_reason_code,request_reason_text,next_generation)
        RETURNING * INTO row;
        INSERT INTO public.trading_stop_dispatch(request_id,user_id) VALUES(row.id,row.user_id);
        audit_action:=CASE WHEN request_action='STOP' THEN 'STOP_REQUESTED' ELSE 'RESUME_REQUESTED' END;
        audit_actor:=CASE WHEN platform_scope THEN 'PLATFORM' ELSE 'USER' END;
        scope_name:=coalesce(request_mode,'PLATFORM');
        INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,subject_kind,
          subject_id,mode,outcome,failure_code,details)
        VALUES(gen_random_uuid(),requester,audit_actor,requester,audit_action,'TRADING_STOP',
          coalesce(expected_stop,request_id)::text,CASE WHEN platform_scope THEN 'NOT_APPLICABLE' ELSE request_mode END,
          'SUCCEEDED',NULL,jsonb_build_object('request_id',request_id,'stop_id',coalesce(expected_stop,request_id),
          'cause',request_cause,'scope',scope_name,
          'revision',row.revision,'reason_code',request_reason_code));
        RETURN NEXT row;
      END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION submit_trading_stop_request(uuid,uuid,text,text,uuid,text,uuid,bigint,bigint,bigint,text,text,boolean) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION submit_trading_stop_request(uuid,uuid,text,text,uuid,text,uuid,bigint,bigint,bigint,text,text,boolean) TO tiewtrade_api"
    )


def downgrade() -> None:
    for table in (name for name in _TABLES if name != "trading_reconciliation_clock"):
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'trading stop history prevents downgrade'; END IF; END $$""")
    op.execute("""DO $$ DECLARE d text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO d FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||
        regexp_replace(d,'WHEN ''STOP_REQUESTED''.*ELSE false','ELSE false','s'); END $$""")
    op.execute(
        "DROP FUNCTION submit_trading_stop_request(uuid,uuid,text,text,uuid,text,uuid,bigint,bigint,bigint,text,text,boolean)"
    )
    op.execute("DROP FUNCTION trading_stop_audit_shape(jsonb)")
    op.execute("DROP POLICY paper_position_activity_api_stop_read ON paper_position_activity")
    op.execute("REVOKE SELECT ON paper_position_activity FROM tiewtrade_api")
    op.execute(
        "REVOKE SELECT(episode_id,availability,revision) ON paper_position_activity FROM tiewtrade_engine_scan"
    )
    op.execute("LOCK TABLE api_throttle IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM api_throttle
      WHERE bucket_kind='TRADING_STOP_MUTATION') THEN
      RAISE EXCEPTION 'trading stop throttle history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind CHECK(bucket_kind IN
      ('API_KEY_ADD','API_KEY_RETRY','PRICE_STREAM_HANDSHAKE','PAPER_WALLET_MUTATION',
       'PAPER_ORDER_NEW','PAPER_ORDER_CANCEL','RISK_LIMIT_MUTATION'))""")
    op.execute(
        "DROP TRIGGER paper_position_activity_reconciliation_clock ON paper_position_activity"
    )
    op.execute("DROP FUNCTION advance_trading_reconciliation_clock()")
    op.execute("DROP INDEX risk_stop_targets_stop_sequence")
    op.execute("ALTER TABLE risk_stop_requests DROP CONSTRAINT risk_stop_requests_authority_source")
    op.execute(
        "ALTER TABLE risk_stop_requests DROP target_policy,DROP cause,DROP authority_request_id"
    )
    op.execute("ALTER TABLE risk_stop_requests ALTER risk_revision SET NOT NULL")
    op.execute("ALTER TABLE risk_stop_requests ALTER event_id SET NOT NULL")
    for table in ("paper_order_requests", "paper_order_commands"):
        op.execute(
            f"ALTER TABLE {table} DROP admitted_owner_stop_revision,DROP admitted_global_stop_revision"
        )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
