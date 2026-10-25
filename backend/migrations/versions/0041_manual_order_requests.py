"""Owner-scoped manual Paper inbox; API never becomes a financial writer."""

# ruff: noqa: E501 -- keep relational and audit predicates reviewable
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

_TABLES = ("paper_order_requests", "paper_order_request_results", "paper_order_request_dispatch")
_READ_COLUMNS = {
    "paper_order_commands": "id,user_id,episode_id,order_id,action",
    "paper_order_command_results": "command_id,user_id,episode_id,state,failure_code,snapshot,completed_at",
    "paper_orders": "id,user_id,wallet_id,episode_id,sequence,base,quote,origin,side,kind,time_in_force,quantity,budget,limit_price,accepted_at,command_id",
    "paper_order_projections": "order_id,user_id,episode_id,status,filled_quantity,spent,revision,last_event_id",
    "paper_reservations": "order_id,user_id,episode_id,base,quote,quote_reserved,base_reserved,revision",
    "paper_position_projections": "episode_id,user_id,base,quote,held_quantity,total_cost,revision",
}
_PRIOR_AUDIT_FAILURES = (
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
)
_REQUEST_FAILURES = (
    "CATALOG_PAIR_REMOVED",
    "ORDER_CONFLICT",
    "ORDER_SAFETY_UNAVAILABLE",
    "MANUAL_USE_REQUIRED",
    "ORDER_UNSUPPORTED",
    "ORDER_INPUT_INVALID",
)


def _audit_failures(*, reverse: bool = False) -> None:
    codes = _PRIOR_AUDIT_FAILURES if reverse else (*_PRIOR_AUDIT_FAILURES, *_REQUEST_FAILURES)
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT audit_events_failure_code")
    op.execute(
        f"ALTER TABLE audit_events ADD CONSTRAINT audit_events_failure_code CHECK(failure_code IS NULL OR failure_code IN {codes!r})"
    )


_PENDING_OLD = "(SELECT count(oc.id) FROM public.paper_order_commands oc"
_PENDING_NEW = """(SELECT count(*) FROM public.paper_order_requests ir
         WHERE ir.episode_id=target_episode AND ir.user_id=public.tiewtrade_current_user_id()
           AND NOT EXISTS(SELECT 1 FROM public.paper_order_request_results rr WHERE rr.request_id=ir.id))
        + (SELECT count(oc.id) FROM public.paper_order_commands oc"""


def _pending(*, reverse: bool = False) -> None:
    old, new = (_PENDING_NEW, _PENDING_OLD) if reverse else (_PENDING_OLD, _PENDING_NEW)
    op.execute(f"""DO $$ DECLARE original text; changed text; BEGIN
      SELECT pg_get_functiondef('paper_wallet_reset_readiness(uuid)'::regprocedure) INTO original;
      changed:=replace(original,$old${old}$old$,$new${new}$new$);
      IF changed=original THEN RAISE EXCEPTION 'reset pending predicate missing'; END IF;
      EXECUTE changed;
    END $$""")


def upgrade() -> None:
    op.execute("""CREATE FUNCTION paper_request_positive_amount(value jsonb) RETURNS boolean
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$
      SELECT CASE WHEN jsonb_typeof(value)='string'
        AND value#>>'{}' ~ '^[0-9]+(\\.[0-9]+)?$'
      THEN (value#>>'{}')::public.tiewtrade_money_amount>0 ELSE false END $$""")
    op.execute("""CREATE TABLE paper_order_requests (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      action text NOT NULL CHECK(action IN ('NEW','CANCEL')), idempotency_key uuid NOT NULL,
      order_id uuid NOT NULL, request_fingerprint text NOT NULL CHECK(request_fingerprint ~ '^[0-9a-f]{64}$'),
      admitted_catalog_revision bigint CHECK(admitted_catalog_revision>0),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'), recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(user_id,action,idempotency_key), UNIQUE(id,user_id,episode_id,order_id,action),
      UNIQUE(id,user_id,episode_id),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      CHECK((CASE WHEN action='CANCEL' THEN admitted_catalog_revision IS NULL
        AND payload=jsonb_build_object('order_id',order_id::text)
      ELSE payload ?& ARRAY['order_id','key','owner','episode','mode','base','quote','origin','side','kind','budget','quantity','limit','tif']
        AND payload-ARRAY['order_id','key','owner','episode','mode','base','quote','origin','side','kind','budget','quantity','limit','tif']='{}'::jsonb
        AND payload->>'order_id'=order_id::text AND payload->>'key'=idempotency_key::text
        AND payload->>'owner'=user_id::text AND payload->>'episode'=episode_id::text
        AND payload->>'mode'='PAPER' AND payload->>'origin'='MANUAL'
        AND jsonb_typeof(payload->'base')='string' AND payload->>'base' ~ '^[A-Z][A-Z0-9]{0,19}$'
        AND payload->>'quote'='USDT' AND payload->>'base'<>payload->>'quote'
        AND payload->>'side' IN ('BUY','SELL')
        AND ((payload->>'side'='BUY' AND admitted_catalog_revision IS NOT NULL)
          OR (payload->>'side'='SELL' AND admitted_catalog_revision IS NULL))
        AND (CASE WHEN payload->>'kind'='MARKET' THEN payload->'limit'='null'::jsonb
          AND payload->'tif'='null'::jsonb
          AND CASE WHEN payload->>'side'='BUY' THEN paper_request_positive_amount(payload->'budget')
            AND payload->'quantity'='null'::jsonb
          ELSE paper_request_positive_amount(payload->'quantity') AND payload->'budget'='null'::jsonb END
        WHEN payload->>'kind'='LIMIT' THEN payload->'budget'='null'::jsonb
          AND payload->>'tif'='GTC' AND paper_request_positive_amount(payload->'quantity')
          AND paper_request_positive_amount(payload->'limit') ELSE false END)
      END) IS TRUE))""")
    op.execute("""CREATE TABLE paper_order_request_results (
      request_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      order_id uuid NOT NULL, action text NOT NULL,
      state text NOT NULL CHECK(state IN ('TRANSFERRED','REJECTED')),
      command_id uuid UNIQUE, failure_code text, completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id,episode_id,order_id,action)
        REFERENCES paper_order_requests(id,user_id,episode_id,order_id,action),
      FOREIGN KEY(command_id,user_id,episode_id,order_id,action)
        REFERENCES paper_order_commands(id,user_id,episode_id,order_id,action),
      CHECK((state='TRANSFERRED' AND command_id IS NOT NULL AND failure_code IS NULL)
        OR (state='REJECTED' AND command_id IS NULL AND failure_code IS NOT NULL AND failure_code IN
          ('CATALOG_PAIR_REMOVED','EPISODE_CONFLICT','ORDER_CONFLICT','ORDER_SAFETY_UNAVAILABLE',
           'MANUAL_USE_REQUIRED','ORDER_UNSUPPORTED','ORDER_INPUT_INVALID'))))""")
    op.execute("""CREATE TABLE paper_order_request_dispatch (
      request_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','CLAIMED','TERMINAL')),
      worker text CHECK(length(worker) BETWEEN 1 AND 128), claim_id uuid,
      claim_revision bigint NOT NULL DEFAULT 0 CHECK(claim_revision>=0), lease_until timestamptz,
      attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0), next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id,episode_id) REFERENCES paper_order_requests(id,user_id,episode_id),
      CHECK((state='CLAIMED' AND worker IS NOT NULL AND claim_id IS NOT NULL AND lease_until IS NOT NULL)
        OR (state<>'CLAIMED' AND worker IS NULL AND claim_id IS NULL AND lease_until IS NULL)))""")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_self ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO tiewtrade_engine")
    for table in _TABLES[:2]:
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api")
    op.execute("GRANT INSERT ON paper_order_requests,paper_order_request_dispatch TO tiewtrade_api")
    op.execute("""GRANT UPDATE(state,worker,claim_id,claim_revision,lease_until,attempts,next_attempt_at)
      ON paper_order_request_dispatch TO tiewtrade_engine""")
    op.execute("""GRANT SELECT(request_id,user_id,episode_id,state,lease_until,next_attempt_at)
      ON paper_order_request_dispatch TO tiewtrade_engine_scan""")
    for table, columns in _READ_COLUMNS.items():
        op.execute(f"GRANT SELECT({columns}) ON {table} TO tiewtrade_api")
    op.execute(
        "CREATE INDEX paper_order_requests_owner_time ON paper_order_requests(user_id,recorded_at,id)"
    )
    op.execute(
        "CREATE INDEX paper_order_requests_episode ON paper_order_requests(user_id,episode_id)"
    )
    op.execute(
        "CREATE INDEX paper_request_dispatch_due ON paper_order_request_dispatch(next_attempt_at,user_id) WHERE state<>'TERMINAL'"
    )
    for table in _TABLES[:2]:
        op.execute(
            f"CREATE POLICY {table}_reset_reader ON {table} FOR SELECT TO tiewtrade_migrator USING(user_id=tiewtrade_current_user_id())"
        )
    _pending()
    op.execute("""CREATE FUNCTION paper_request_audit_shape(details jsonb,subject text) RETURNS boolean
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$
      SELECT (details ?& ARRAY['request_id','episode_id','request_action','command_id']
        AND details-ARRAY['request_id','episode_id','request_action','command_id']='{}'::jsonb
        AND details->>'request_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
        AND details->>'episode_id'=subject
        AND subject ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
        AND details->>'request_action' IN ('NEW','CANCEL')
        AND (details->'command_id'='null'::jsonb OR
          (jsonb_typeof(details->'command_id')='string'
            AND details->>'command_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'))) IS TRUE $$""")
    _audit_failures()
    # Extend the existing strict CASE, preserving every previously approved action.
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false',
      'WHEN ''PAPER_ORDER_REQUESTED'' THEN
        mode=''PAPER'' AND actor_kind=''USER'' AND actor_id=owner_user_id
        AND subject_kind=''PAPER_ORDER_ACTIVITY'' AND outcome=''SUCCEEDED'' AND failure_code IS NULL
        AND details->>''command_id'' IS NULL
        AND public.paper_request_audit_shape(details,subject_id)
       WHEN ''PAPER_ORDER_REQUEST_TRANSFERRED'' THEN
        mode=''PAPER'' AND actor_kind=''SYSTEM'' AND actor_id IS NULL
        AND subject_kind=''PAPER_ORDER_ACTIVITY'' AND outcome=''SUCCEEDED'' AND failure_code IS NULL
        AND details->>''command_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
        AND public.paper_request_audit_shape(details,subject_id)
       WHEN ''PAPER_ORDER_REQUEST_REJECTED'' THEN
        mode=''PAPER'' AND actor_kind=''SYSTEM'' AND actor_id IS NULL
        AND subject_kind=''PAPER_ORDER_ACTIVITY'' AND outcome=''REJECTED''
        AND failure_code IS NOT NULL AND failure_code IN (''CATALOG_PAIR_REMOVED'',''EPISODE_CONFLICT'',''ORDER_CONFLICT'',
          ''ORDER_SAFETY_UNAVAILABLE'',''MANUAL_USE_REQUIRED'',''ORDER_UNSUPPORTED'',''ORDER_INPUT_INVALID'')
        AND details->>''command_id'' IS NULL
        AND public.paper_request_audit_shape(details,subject_id)
       ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape ' || changed;
    END $$""")


def downgrade() -> None:
    # Lock out new inserts before inspecting data; never discard accepted requests/history.
    op.execute("LOCK TABLE paper_order_requests IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE paper_order_requests NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM paper_order_requests)
      THEN RAISE EXCEPTION 'manual order request history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE paper_order_requests FORCE ROW LEVEL SECURITY")
    _pending(reverse=True)
    _audit_failures(reverse=True)
    op.execute("""DO $$ DECLARE definition text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape ' ||
        regexp_replace(definition,'WHEN ''PAPER_ORDER_REQUESTED''.*ELSE false','ELSE false','s');
    END $$""")
    for table, columns in _READ_COLUMNS.items():
        op.execute(f"REVOKE SELECT({columns}) ON {table} FROM tiewtrade_api")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION paper_request_positive_amount(jsonb)")
    op.execute("DROP FUNCTION paper_request_audit_shape(jsonb,text)")
