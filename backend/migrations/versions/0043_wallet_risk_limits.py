"""F-18 owner-scoped loss limits, authorization receipts and durable inbox.

Price publication/financial boundaries are installed separately before activation.
"""

# ruff: noqa: E501 -- keep relational predicates together for schema review
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

_TABLES = (
    "risk_limit_settings",
    "risk_limit_authorizations",
    "risk_limit_requests",
    "risk_limit_results",
    "risk_limit_dispatch",
    "risk_limit_events",
    "risk_limit_baselines",
    "risk_limit_pairs",
    "risk_limit_evaluations",
)
_IMMUTABLE = (
    "risk_limit_authorizations",
    "risk_limit_requests",
    "risk_limit_results",
    "risk_limit_events",
    "risk_limit_baselines",
)
_FAILURES = (
    "RISK_REVISION_CONFLICT",
    "RISK_SCOPE_CONFLICT",
    "RISK_SOURCE_UNAVAILABLE",
    "RISK_PRICE_UNAVAILABLE",
    "RISK_INPUT_INVALID",
    "RISK_LIMIT_UNSET",
    "RISK_LOSS_LIMIT_REACHED",
    "RISK_AUTHORIZATION_REQUIRED",
    "RISK_CANCEL_FAILED",
)
_PRIOR_FAILURES = (
    "VENUE_CREDENTIAL_REJECTED",
    "VENUE_REJECTED",
    "VENUE_RATE_LIMITED",
    "VENUE_UNAVAILABLE",
    "VENUE_OUTCOME_UNKNOWN",
    "VENUE_PROTOCOL",
    "VERIFICATION_EXPIRED",
    "INITIAL_CAPITAL_INVALID",
    "INITIAL_CAPITAL_TOO_SMALL",
    "IDEMPOTENCY_CONFLICT",
    "WALLET_EXISTS",
    "ACTIVITY_UNKNOWN",
    "EPISODE_CONFLICT",
    "RESET_UNSAFE",
    "POSITION_SEQUENCE_GAP",
    "POSITION_DUPLICATE_CONFLICT",
    "POSITION_CORRECTION_CONFLICT",
    "POSITION_SOURCE_UNKNOWN",
    "POSITION_INSUFFICIENT",
    "POSITION_EXECUTION_INVALID",
    "POSITION_PRICE_UNAVAILABLE",
    "CATALOG_PAIR_REMOVED",
    "ORDER_CONFLICT",
    "ORDER_SAFETY_UNAVAILABLE",
    "MANUAL_USE_REQUIRED",
    "ORDER_UNSUPPORTED",
    "ORDER_INPUT_INVALID",
)


def upgrade() -> None:
    op.execute("""CREATE TABLE risk_limit_settings (
      user_id uuid NOT NULL REFERENCES users(id), mode text NOT NULL CHECK(mode IN ('PAPER','LIVE')),
      revision bigint NOT NULL CHECK(revision>0), amount tiewtrade_money_amount NOT NULL CHECK(amount>0),
      currency text NOT NULL DEFAULT 'USDT' CHECK(currency='USDT'),
      latched boolean NOT NULL DEFAULT false, baseline_id uuid,
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(user_id,mode))""")
    for table in ("risk_limit_authorizations", "risk_limit_requests"):
        extra = "authorization_id uuid," if table == "risk_limit_requests" else ""
        op.execute(f"""CREATE TABLE {table} (
          id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
          mode text NOT NULL CHECK(mode IN ('PAPER','LIVE')),
          action text NOT NULL CHECK(action IN ('SET','DECREASE','INCREASE','RESET')),
          idempotency_key uuid NOT NULL, expected_revision bigint NOT NULL CHECK(expected_revision>=0),
          amount tiewtrade_money_amount CHECK(amount>0), wallet_id uuid, episode_id uuid,
          fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{{64}}$'), {extra}
          recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
          UNIQUE(user_id,mode,idempotency_key), UNIQUE(id,user_id,mode),
          FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
          CHECK((mode='PAPER' AND wallet_id IS NOT NULL AND episode_id IS NOT NULL)
            OR (mode='LIVE' AND wallet_id IS NULL AND episode_id IS NULL)),
          CHECK((action='RESET' AND amount IS NULL) OR (action<>'RESET' AND amount IS NOT NULL)))""")
    op.execute("ALTER TABLE risk_limit_authorizations ADD CHECK(action='INCREASE')")
    op.execute("""ALTER TABLE risk_limit_requests ADD CONSTRAINT risk_authorization_link
      FOREIGN KEY(authorization_id,user_id,mode) REFERENCES risk_limit_authorizations(id,user_id,mode)""")
    op.execute("""ALTER TABLE risk_limit_requests ADD CHECK(
      (action='INCREASE')=(authorization_id IS NOT NULL))""")
    op.execute("""CREATE UNIQUE INDEX risk_authorization_one_request
      ON risk_limit_requests(authorization_id) WHERE authorization_id IS NOT NULL""")
    op.execute("""CREATE TABLE risk_limit_results (
      request_id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL,
      state text NOT NULL CHECK(state IN ('APPLIED','REJECTED')), failure_code text,
      revision bigint CHECK(revision>0), snapshot jsonb NOT NULL CHECK(jsonb_typeof(snapshot)='object'),
      completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id,mode) REFERENCES risk_limit_requests(id,user_id,mode),
      CHECK((state='APPLIED' AND revision IS NOT NULL AND failure_code IS NULL)
        OR (state='REJECTED' AND failure_code IS NOT NULL AND failure_code IN
          ('RISK_REVISION_CONFLICT','RISK_SCOPE_CONFLICT','RISK_SOURCE_UNAVAILABLE',
           'RISK_PRICE_UNAVAILABLE','RISK_INPUT_INVALID','RISK_AUTHORIZATION_REQUIRED'))))""")
    op.execute("""CREATE TABLE risk_limit_dispatch (
      request_id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL,
      state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','CLAIMED','TERMINAL')),
      worker text CHECK(length(worker) BETWEEN 1 AND 128), claim_id uuid,
      claim_revision bigint NOT NULL DEFAULT 0 CHECK(claim_revision>=0), lease_until timestamptz,
      attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
      next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id,mode) REFERENCES risk_limit_requests(id,user_id,mode),
      CHECK((state='CLAIMED' AND worker IS NOT NULL AND claim_id IS NOT NULL AND lease_until IS NOT NULL)
        OR (state<>'CLAIMED' AND worker IS NULL AND claim_id IS NULL AND lease_until IS NULL)))""")
    op.execute("""CREATE TABLE risk_limit_events (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL,
      revision bigint NOT NULL CHECK(revision>0),
      kind text NOT NULL CHECK(kind IN ('SET','DECREASE','INCREASE','RESET','BREACH','CONFLICT')),
      request_id uuid, amount tiewtrade_money_amount NOT NULL CHECK(amount>0),
      latched boolean NOT NULL, source_revision bigint CHECK(source_revision>=0),
      details jsonb NOT NULL CHECK(jsonb_typeof(details)='object'),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(user_id,mode,revision), UNIQUE(id,user_id,mode),
      FOREIGN KEY(user_id,mode) REFERENCES risk_limit_settings(user_id,mode),
      FOREIGN KEY(request_id,user_id,mode) REFERENCES risk_limit_requests(id,user_id,mode))""")
    op.execute("""CREATE TABLE risk_limit_baselines (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL,
      request_id uuid NOT NULL UNIQUE, source_revision bigint NOT NULL CHECK(source_revision>=0),
      wallet_id uuid, episode_id uuid, source_proof text NOT NULL CHECK(source_proof ~ '^[0-9a-f]{64}$'),
      snapshot jsonb NOT NULL CHECK(jsonb_typeof(snapshot)='object'),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(id,user_id,mode),
      FOREIGN KEY(request_id,user_id,mode) REFERENCES risk_limit_requests(id,user_id,mode),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((mode='PAPER' AND wallet_id IS NOT NULL AND episode_id IS NOT NULL)
        OR (mode='LIVE' AND wallet_id IS NULL AND episode_id IS NULL)))""")
    op.execute("""ALTER TABLE risk_limit_settings ADD FOREIGN KEY(baseline_id,user_id,mode)
      REFERENCES risk_limit_baselines(id,user_id,mode)""")
    op.execute("""CREATE TABLE risk_limit_pairs (
      user_id uuid NOT NULL, mode text NOT NULL, base text NOT NULL CHECK(base ~ '^[A-Z][A-Z0-9]{0,19}$'),
      quote text NOT NULL DEFAULT 'USDT' CHECK(quote='USDT' AND base<>quote),
      allowance tiewtrade_money_amount NOT NULL CHECK(allowance>=0),
      adjusted_realized tiewtrade_money_amount NOT NULL, source_sequence bigint NOT NULL CHECK(source_sequence>=0),
      source_revision bigint NOT NULL CHECK(source_revision>=0),
      PRIMARY KEY(user_id,mode,base,quote),
      FOREIGN KEY(user_id,mode) REFERENCES risk_limit_settings(user_id,mode))""")
    op.execute("""CREATE TABLE risk_limit_evaluations (
      user_id uuid NOT NULL, mode text NOT NULL, setting_revision bigint NOT NULL CHECK(setting_revision>0),
      source_revision bigint CHECK(source_revision>=0), price_watermark bigint CHECK(price_watermark>=0),
      reason text NOT NULL CHECK(reason IN ('READY','RISK_LIMIT_UNSET','RISK_SOURCE_UNAVAILABLE',
        'RISK_PRICE_UNAVAILABLE','RISK_LOSS_LIMIT_REACHED')),
      loss tiewtrade_money_amount CHECK(loss>=0), latched boolean NOT NULL,
      evaluated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      input_ready_at timestamptz, replay_pending boolean NOT NULL DEFAULT false,
      PRIMARY KEY(user_id,mode), FOREIGN KEY(user_id,mode) REFERENCES risk_limit_settings(user_id,mode),
      CHECK((reason IN ('READY','RISK_LIMIT_UNSET','RISK_LOSS_LIMIT_REACHED'))=(loss IS NOT NULL)),
      CHECK(reason<>'READY' OR NOT latched), CHECK(reason<>'RISK_LOSS_LIMIT_REACHED' OR latched))""")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api,tiewtrade_engine")
    for table in _IMMUTABLE:
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
    for table in _TABLES:
        if table != "risk_limit_authorizations":
            op.execute(f"GRANT INSERT ON {table} TO tiewtrade_engine")
    op.execute("REVOKE INSERT ON risk_limit_requests FROM tiewtrade_engine")
    op.execute("GRANT SELECT,INSERT ON risk_limit_authorizations TO tiewtrade_auth")
    op.execute("GRANT INSERT ON risk_limit_requests,risk_limit_dispatch TO tiewtrade_migrator")
    for table in (
        "risk_limit_settings",
        "risk_limit_pairs",
        "risk_limit_evaluations",
        "risk_limit_dispatch",
    ):
        op.execute(f"GRANT UPDATE ON {table} TO tiewtrade_engine")
    op.execute("""GRANT SELECT(request_id,user_id,mode,state,lease_until,next_attempt_at)
      ON risk_limit_dispatch TO tiewtrade_engine_scan""")
    op.execute("""CREATE INDEX risk_dispatch_due ON risk_limit_dispatch(next_attempt_at,user_id)
      WHERE state<>'TERMINAL'""")
    op.execute(
        "CREATE INDEX risk_requests_owner_time ON risk_limit_requests(user_id,mode,recorded_at,id)"
    )
    _submission_function()
    _audit()


def _submission_function() -> None:
    op.execute("""CREATE FUNCTION risk_submit_request(
      request uuid, request_mode text, request_action text, request_key uuid,
      request_revision bigint, request_amount public.tiewtrade_money_amount,
      request_wallet uuid, request_episode uuid, request_fingerprint text, request_authorization uuid)
      RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE owner uuid:=public.tiewtrade_current_user_id(); prior public.risk_limit_requests%ROWTYPE;
        proof public.risk_limit_authorizations%ROWTYPE; current_amount public.tiewtrade_money_amount;
        current_revision bigint;
      BEGIN
        IF owner IS NULL OR request_mode NOT IN ('PAPER','LIVE') THEN
          RAISE EXCEPTION 'RISK_SCOPE_CONFLICT' USING ERRCODE='23514'; END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(
          CASE WHEN request_mode='PAPER' THEN 'paper-wallet:' ELSE 'risk-live:' END||owner::text,0));
        SELECT * INTO prior FROM public.risk_limit_requests
          WHERE user_id=owner AND mode=request_mode AND idempotency_key=request_key;
        IF FOUND THEN
          IF prior.fingerprint<>request_fingerprint OR prior.action<>request_action
            OR prior.expected_revision<>request_revision
            OR prior.amount IS DISTINCT FROM request_amount
            OR prior.wallet_id IS DISTINCT FROM request_wallet
            OR prior.episode_id IS DISTINCT FROM request_episode THEN
            RAISE EXCEPTION 'RISK_REVISION_CONFLICT' USING ERRCODE='23514'; END IF;
          RETURN prior.id;
        END IF;
        IF request_mode='PAPER' AND NOT EXISTS(SELECT 1 FROM public.paper_wallet_state s
          WHERE s.user_id=owner AND s.wallet_id=request_wallet AND s.active_episode_id=request_episode
          AND NOT EXISTS(SELECT 1 FROM public.paper_wallet_episode_closures c WHERE c.episode_id=request_episode))
          THEN RAISE EXCEPTION 'RISK_SCOPE_CONFLICT' USING ERRCODE='23514'; END IF;
        SELECT revision,amount INTO current_revision,current_amount FROM public.risk_limit_settings
          WHERE user_id=owner AND mode=request_mode;
        IF coalesce(current_revision,0)<>request_revision THEN
          RAISE EXCEPTION 'RISK_REVISION_CONFLICT' USING ERRCODE='23514'; END IF;
        IF request_action='SET' AND current_amount IS NOT NULL
          OR request_action='DECREASE' AND (current_amount IS NULL OR request_amount>=current_amount)
          OR request_action IN ('INCREASE','RESET') AND current_amount IS NULL THEN
          RAISE EXCEPTION 'RISK_REVISION_CONFLICT' USING ERRCODE='23514'; END IF;
        IF request_action='INCREASE' THEN
          SELECT * INTO proof FROM public.risk_limit_authorizations WHERE id=request_authorization AND user_id=owner;
          IF NOT FOUND OR proof.mode<>request_mode OR proof.action<>request_action
            OR proof.idempotency_key<>request_key OR proof.expected_revision<>request_revision
            OR proof.fingerprint<>request_fingerprint OR proof.amount IS DISTINCT FROM request_amount
            OR proof.wallet_id IS DISTINCT FROM request_wallet
            OR proof.episode_id IS DISTINCT FROM request_episode OR request_amount<=current_amount THEN
            RAISE EXCEPTION 'RISK_AUTHORIZATION_REQUIRED' USING ERRCODE='23514'; END IF;
        END IF;
        INSERT INTO public.risk_limit_requests
          (id,user_id,mode,action,idempotency_key,expected_revision,amount,wallet_id,episode_id,fingerprint,authorization_id)
          VALUES(request,owner,request_mode,request_action,request_key,request_revision,request_amount,
            request_wallet,request_episode,request_fingerprint,request_authorization);
        INSERT INTO public.risk_limit_dispatch(request_id,user_id,mode) VALUES(request,owner,request_mode);
        INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,subject_kind,
          subject_id,mode,outcome,details) VALUES(request,owner,'USER',owner,'RISK_LIMIT_REQUESTED',
          'RISK_LIMIT',owner::text,request_mode,'SUCCEEDED',jsonb_build_object(
          'event_id',request::text,'request_id',request::text,'risk_revision',request_revision,
          'limit_amount',CASE WHEN request_amount IS NULL THEN NULL ELSE request_amount::text END,
          'stop_id',NULL,'order_id',NULL));
        RETURN request;
      END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION risk_submit_request(uuid,text,text,uuid,bigint,tiewtrade_money_amount,uuid,uuid,text,uuid) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION risk_submit_request(uuid,text,text,uuid,bigint,tiewtrade_money_amount,uuid,uuid,text,uuid) TO tiewtrade_api"
    )


def _audit() -> None:
    op.execute("""CREATE FUNCTION risk_audit_shape(d jsonb) RETURNS boolean
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$ SELECT (
        d ?& ARRAY['event_id','request_id','risk_revision','limit_amount','stop_id','order_id']
        AND d-ARRAY['event_id','request_id','risk_revision','limit_amount','stop_id','order_id']='{}'::jsonb
        AND jsonb_typeof(d->'event_id')='string'
        AND d->>'event_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
        AND jsonb_typeof(d->'risk_revision')='number' AND d->>'risk_revision' ~ '^[0-9]+$'
        AND (d->'limit_amount'='null'::jsonb OR public.paper_request_positive_amount(d->'limit_amount'))
        AND NOT EXISTS(SELECT 1 FROM unnest(ARRAY['request_id','stop_id','order_id']) k
          WHERE NOT(d->k='null'::jsonb OR (jsonb_typeof(d->k)='string'
            AND d->>k ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$')))
        ) IS TRUE $$""")
    op.execute(f"""CREATE FUNCTION risk_system_audit_valid(
      actor text,actor_id uuid,subject text,subject_id text,owner uuid,event_mode text,
      outcome text,failure text,details jsonb,rejected boolean) RETURNS boolean
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$ SELECT (
        actor='SYSTEM' AND actor_id IS NULL AND subject='RISK_LIMIT' AND subject_id=owner::text
        AND event_mode IN ('PAPER','LIVE') AND public.risk_audit_shape(details)
        AND CASE WHEN rejected THEN outcome IN ('FAILED','REJECTED')
          AND failure IS NOT NULL AND failure IN {_FAILURES!r}
        ELSE outcome='SUCCEEDED' AND failure IS NULL END) IS TRUE $$""")
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute(f"""ALTER TABLE audit_events ADD CONSTRAINT audit_events_failure_code
      CHECK(failure_code IS NULL OR failure_code IN {(*_PRIOR_FAILURES, *_FAILURES)!r})""")
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false',
        'WHEN ''RISK_LIMIT_REQUESTED'' THEN
          subject_kind=''RISK_LIMIT'' AND subject_id=owner_user_id::text
          AND actor_kind=''USER'' AND actor_id=owner_user_id AND mode IN (''PAPER'',''LIVE'')
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL AND risk_audit_shape(details)
          AND details->>''request_id''=details->>''event_id''
         WHEN ''RISK_LIMIT_SET'' THEN public.risk_system_audit_valid(actor_kind,actor_id,
           subject_kind,subject_id,owner_user_id,mode,outcome,failure_code,details,false)
         WHEN ''RISK_LIMIT_RESET'' THEN public.risk_system_audit_valid(actor_kind,actor_id,
           subject_kind,subject_id,owner_user_id,mode,outcome,failure_code,details,false)
         WHEN ''RISK_LIMIT_BREACHED'' THEN public.risk_system_audit_valid(actor_kind,actor_id,
           subject_kind,subject_id,owner_user_id,mode,outcome,failure_code,details,false)
         WHEN ''RISK_STOP_UPDATED'' THEN public.risk_system_audit_valid(actor_kind,actor_id,
           subject_kind,subject_id,owner_user_id,mode,outcome,failure_code,details,false)
         WHEN ''RISK_SOURCE_CONFLICTED'' THEN public.risk_system_audit_valid(actor_kind,actor_id,
           subject_kind,subject_id,owner_user_id,mode,outcome,failure_code,details,true)
         WHEN ''RISK_LIMIT_REJECTED'' THEN public.risk_system_audit_valid(actor_kind,actor_id,
           subject_kind,subject_id,owner_user_id,mode,outcome,failure_code,details,true)
         ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||changed;
    END $$""")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
          RAISE EXCEPTION 'risk history prevents downgrade'; END IF; END $$""")
    op.execute("""DO $$ DECLARE d text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO d FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||
        regexp_replace(d,'WHEN ''RISK_LIMIT_REQUESTED''.*ELSE false','ELSE false','s'); END $$""")
    op.execute(
        "DROP FUNCTION risk_submit_request(uuid,text,text,uuid,bigint,tiewtrade_money_amount,uuid,uuid,text,uuid)"
    )
    op.execute(
        "ALTER TABLE risk_limit_settings DROP CONSTRAINT risk_limit_settings_baseline_id_user_id_mode_fkey"
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION risk_audit_shape(jsonb)")
    op.execute(
        "DROP FUNCTION risk_system_audit_valid(text,uuid,text,text,uuid,text,text,text,jsonb,boolean)"
    )
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute(f"""ALTER TABLE audit_events ADD CONSTRAINT audit_events_failure_code
      CHECK(failure_code IS NULL OR failure_code IN {_PRIOR_FAILURES!r})""")
