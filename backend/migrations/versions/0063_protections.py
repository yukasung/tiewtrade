"""Durable owner-scoped Paper protection intents, allocations and immutable history."""

# ruff: noqa: E501 -- relational predicates are reviewed as SQL
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

_TABLES = (
    "paper_protection_requests",
    "paper_protection_results",
    "paper_protections",
    "paper_protection_events",
    "paper_protection_exits",
    "paper_protection_exit_progress",
)
_PENDING = "(SELECT count(oc.id) FROM public.paper_order_commands oc"
_EXTRA_PENDING = """(SELECT count(*) FROM public.paper_protection_requests pr WHERE pr.episode_id=target_episode
    AND pr.user_id=public.tiewtrade_current_user_id() AND NOT EXISTS(
      SELECT 1 FROM public.paper_protection_results rr WHERE rr.request_id=pr.id))
    + (SELECT count(*) FROM public.paper_protections pg WHERE pg.episode_id=target_episode
      AND pg.user_id=public.tiewtrade_current_user_id() AND pg.state NOT IN ('CLOSED','CANCELED'))
    + (SELECT count(oc.id) FROM public.paper_order_commands oc"""


def upgrade() -> None:
    op.execute("""CREATE TABLE paper_protection_protocol (
      singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
      enabled boolean NOT NULL DEFAULT false)
    """)
    op.execute("INSERT INTO paper_protection_protocol(singleton) VALUES(true)")
    op.execute(
        "GRANT SELECT ON paper_protection_protocol TO tiewtrade_api,tiewtrade_engine,tiewtrade_engine_scan"
    )
    op.execute("""CREATE TABLE paper_protection_requests (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      protection_id uuid NOT NULL, action text NOT NULL CHECK(action IN ('CREATE','REPLACE','CANCEL')),
      idempotency_key uuid NOT NULL, fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(user_id,action,idempotency_key), UNIQUE(id,user_id,episode_id),
      UNIQUE(id,user_id,episode_id,protection_id),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("""CREATE TABLE paper_protection_results (
      request_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
      state text NOT NULL CHECK(state IN ('APPLIED','REJECTED')), failure_code text,
      protection_id uuid, revision bigint,
      snapshot jsonb NOT NULL CHECK(jsonb_typeof(snapshot)='object'),
      completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      FOREIGN KEY(request_id,user_id,episode_id) REFERENCES paper_protection_requests(id,user_id,episode_id),
      CHECK((state='APPLIED' AND failure_code IS NULL AND protection_id IS NOT NULL AND revision>0
        AND snapshot->>'protection_id'=protection_id::text AND (snapshot->>'revision')::bigint=revision) OR (state='REJECTED'
        AND protection_id IS NULL AND revision IS NULL
        AND failure_code IN ('ORDER_INPUT_INVALID','ORDER_CONFLICT','ORDER_SAFETY_UNAVAILABLE','EPISODE_CONFLICT'))))""")
    op.execute("""CREATE TABLE paper_protections (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'), base text NOT NULL, quote text NOT NULL CHECK(quote='USDT' AND base<>quote),
      state text NOT NULL CHECK(state IN ('WAITING_ENTRY','ARMING','ARMED','EXITING','CLOSED','CANCELED','FAILED')),
      revision bigint NOT NULL CHECK(revision>0), quantity tiewtrade_money_amount NOT NULL CHECK(quantity>=0),
      acquired tiewtrade_money_amount NOT NULL DEFAULT 0 CHECK(acquired>=0),
      disposed tiewtrade_money_amount NOT NULL DEFAULT 0 CHECK(disposed>=0),
      extra_exit tiewtrade_money_amount NOT NULL DEFAULT 0 CHECK(extra_exit>=0),
      CHECK(extra_exit<=quantity),
      entry_request_id uuid, entry_order_id uuid,
      entry_action text GENERATED ALWAYS AS ('NEW'::text) STORED,
      document jsonb NOT NULL, failure_code text,
      observed_source uuid, observed_generation bigint CHECK(observed_generation>=0),
      observed_sequence bigint CHECK(observed_sequence>=0),
      next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(id,user_id,episode_id), UNIQUE(entry_request_id),
      FOREIGN KEY(episode_id,wallet_id,user_id) REFERENCES paper_wallet_episodes(id,wallet_id,user_id),
      FOREIGN KEY(entry_request_id,user_id,episode_id,entry_order_id,entry_action)
        REFERENCES paper_order_requests(id,user_id,episode_id,order_id,action),
      CHECK((entry_request_id IS NULL)=(entry_order_id IS NULL)),
      CHECK(state NOT IN ('CLOSED','CANCELED') OR quantity=0),
      CHECK((document->>'id'=id::text AND document->>'owner'=user_id::text
        AND document->>'episode'=episode_id::text AND document->>'mode'=mode
        AND document->>'base'=base AND document->>'quote'=quote
        AND document->>'state'=state AND (document->>'revision')::bigint=revision
        AND (document->>'quantity')::tiewtrade_money_amount=quantity
        AND coalesce(document->>'entry','')=coalesce(entry_order_id::text,'')) IS TRUE))""")
    op.execute("""CREATE TABLE paper_protection_events (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL, protection_id uuid NOT NULL,
      revision bigint NOT NULL CHECK(revision>0), kind text NOT NULL,
      document jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      UNIQUE(protection_id,revision),
      UNIQUE(protection_id,revision,user_id,episode_id,document),
      UNIQUE(protection_id,revision,user_id,episode_id),
      FOREIGN KEY(protection_id,user_id,episode_id) REFERENCES paper_protections(id,user_id,episode_id))""")
    op.execute("""CREATE TABLE paper_protection_exits (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL, protection_id uuid NOT NULL,
      order_id uuid NOT NULL UNIQUE, command_id uuid NOT NULL UNIQUE,
      action text GENERATED ALWAYS AS ('NEW'::text) STORED,
      quantity tiewtrade_money_amount NOT NULL CHECK(quantity>0),
      UNIQUE(id,user_id,episode_id),
      UNIQUE(id,user_id,episode_id,quantity),
      FOREIGN KEY(protection_id,user_id,episode_id) REFERENCES paper_protections(id,user_id,episode_id),
      FOREIGN KEY(command_id,user_id,episode_id,order_id,action)
        REFERENCES paper_order_commands(id,user_id,episode_id,order_id,action))""")
    op.execute("""CREATE TABLE paper_protection_exit_progress (
      id uuid PRIMARY KEY,user_id uuid NOT NULL,episode_id uuid NOT NULL,
      quantity tiewtrade_money_amount NOT NULL CHECK(quantity>0),
      accounted tiewtrade_money_amount NOT NULL DEFAULT 0 CHECK(accounted>=0 AND accounted<=quantity),
      settled boolean NOT NULL DEFAULT false,
      FOREIGN KEY(id,user_id,episode_id,quantity) REFERENCES paper_protection_exits(id,user_id,episode_id,quantity))""")
    op.execute("""ALTER TABLE paper_protection_results
      ADD FOREIGN KEY(request_id,user_id,episode_id,protection_id)
        REFERENCES paper_protection_requests(id,user_id,episode_id,protection_id),
      ADD FOREIGN KEY(protection_id,revision,user_id,episode_id)
        REFERENCES paper_protection_events(protection_id,revision,user_id,episode_id)""")
    op.execute("""ALTER TABLE paper_protections ADD CONSTRAINT protection_current_history
      FOREIGN KEY(id,revision,user_id,episode_id,document)
      REFERENCES paper_protection_events(protection_id,revision,user_id,episode_id,document)
      DEFERRABLE INITIALLY DEFERRED""")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_self ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO tiewtrade_engine")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api")
        op.execute(
            f"CREATE POLICY {table}_reset ON {table} FOR SELECT TO tiewtrade_migrator USING(user_id=tiewtrade_current_user_id())"
        )
    op.execute("GRANT INSERT ON paper_protection_requests TO tiewtrade_api")
    op.execute(
        "GRANT UPDATE(state,revision,quantity,document,acquired,disposed,extra_exit,failure_code,next_attempt_at,observed_source,observed_generation,observed_sequence) ON paper_protections TO tiewtrade_engine"
    )
    op.execute(
        "GRANT UPDATE(accounted,settled) ON paper_protection_exit_progress TO tiewtrade_engine"
    )
    for table in (
        "paper_protection_exits",
        "paper_protection_requests",
        "paper_protection_results",
        "paper_protection_events",
    ):
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")
    op.execute(
        "GRANT SELECT(id,user_id,recorded_at) ON paper_protection_requests TO tiewtrade_engine_scan"
    )
    op.execute("GRANT SELECT(request_id) ON paper_protection_results TO tiewtrade_engine_scan")
    op.execute(
        "GRANT SELECT(id,user_id,state,next_attempt_at) ON paper_protections TO tiewtrade_engine_scan"
    )
    op.execute(
        "CREATE INDEX paper_protections_due ON paper_protections(next_attempt_at,user_id) WHERE state NOT IN ('CLOSED','CANCELED')"
    )
    op.execute(
        "CREATE INDEX paper_protections_owner_pair ON paper_protections(user_id,episode_id,base,quote)"
    )
    op.execute(
        "CREATE INDEX paper_protection_requests_owner_time ON paper_protection_requests(user_id,recorded_at,id)"
    )
    op.execute("""ALTER TABLE paper_order_requests ADD protection jsonb,
      ADD protection_allocations jsonb NOT NULL DEFAULT '[]'::jsonb,
      ADD CONSTRAINT manual_protection_shape CHECK(
        (protection IS NULL OR (action='NEW' AND payload->>'side'='BUY' AND jsonb_typeof(protection)='object'))
        AND jsonb_typeof(protection_allocations)='array'
        AND (protection_allocations='[]'::jsonb OR (action='NEW' AND payload->>'side'='SELL')))""")
    op.execute("""CREATE FUNCTION require_protection_writer() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF ((SELECT enabled FROM public.paper_protection_protocol WHERE singleton)
        OR EXISTS(SELECT 1 FROM public.paper_protections WHERE episode_id=NEW.episode_id
          AND state NOT IN ('CLOSED','CANCELED')))
        AND current_setting('tiewtrade.protection_writer_version',true) IS DISTINCT FROM 'F17_V1'
      THEN RAISE EXCEPTION 'compatible protection writer required' USING ERRCODE='42501'; END IF;
      RETURN NEW; END $$""")
    for table in ("paper_orders", "paper_execution_links"):
        op.execute(
            f"CREATE TRIGGER {table}_protection_writer BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION require_protection_writer()"
        )
    op.execute("""CREATE FUNCTION protection_audit_shape(d jsonb,subject text) RETURNS boolean
      LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$ SELECT (
        d ?& ARRAY['episode_id','protection_id','event_id','revision','kind']
        AND d-ARRAY['episode_id','protection_id','event_id','revision','kind']='{}'::jsonb
        AND d->>'episode_id'=subject
        AND d->>'protection_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
        AND d->>'event_id' ~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
        AND jsonb_typeof(d->'revision')='number' AND (d->>'revision')::bigint>=0
        AND d->>'kind' IN ('REQUEST','CREATE','REPLACE','CANCEL','ARM','FILL','TRIGGER','EXIT','MANUAL_RELEASE','CONFLICT','RETRY','FAIL','REJECT')) IS TRUE $$""")
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false','WHEN ''PROTECTION_EVENT'' THEN
        mode=''PAPER'' AND subject_kind=''PAPER_ORDER_ACTIVITY'' AND outcome=''SUCCEEDED'' AND failure_code IS NULL
        AND protection_audit_shape(details,subject_id)
        AND ((details->>''kind''=''REQUEST'' AND actor_kind=''USER'' AND actor_id=owner_user_id)
          OR (details->>''kind''<>''REQUEST'' AND actor_kind=''SYSTEM'' AND actor_id IS NULL)) ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||changed;
    END $$""")
    op.execute(f"""DO $$ DECLARE original text; changed text; BEGIN
      SELECT pg_get_functiondef('paper_wallet_reset_readiness(uuid)'::regprocedure) INTO original;
      changed:=replace(original,$old${_PENDING}$old$,$new${_EXTRA_PENDING}$new$);
      IF changed=original THEN RAISE EXCEPTION 'reset pending predicate missing'; END IF;
      EXECUTE changed;
    END $$""")


def downgrade() -> None:
    tables = (*_TABLES, "paper_order_requests", "audit_events")
    op.execute(
        "LOCK TABLE paper_protection_protocol," + ",".join(tables) + " IN ACCESS EXCLUSIVE MODE"
    )
    # Migration owner bypasses RLS only inside this locked transaction. Rejection
    # rolls these changes back; runtime roles never receive additional rights.
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
        IF (SELECT enabled FROM paper_protection_protocol WHERE singleton) THEN
            RAISE EXCEPTION 'active protection protocol prevents downgrade';
        END IF;
        END $$""")
    for table in _TABLES:
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
            RAISE EXCEPTION 'protection history prevents downgrade'; END IF; END $$""")
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM paper_order_requests
            WHERE protection IS NOT NULL OR protection_allocations<>'[]'::jsonb)
            OR EXISTS(SELECT 1 FROM audit_events WHERE action='PROTECTION_EVENT') THEN
            RAISE EXCEPTION 'protection intent or audit history prevents downgrade';
        END IF;
        END $$""")
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(f"""DO $$ DECLARE original text; changed text; BEGIN
      SELECT pg_get_functiondef('paper_wallet_reset_readiness(uuid)'::regprocedure) INTO original;
      changed:=replace(original,$old${_EXTRA_PENDING}$old$,$new${_PENDING}$new$);
      IF changed=original THEN RAISE EXCEPTION 'protection reset predicate missing'; END IF;
      EXECUTE changed;
    END $$""")
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=regexp_replace(definition,'WHEN ''PROTECTION_EVENT''.*ELSE false','ELSE false','s');
      IF changed=definition THEN RAISE EXCEPTION 'protection audit predicate missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||changed;
    END $$""")
    for table in ("paper_orders", "paper_execution_links"):
        op.execute(f"DROP TRIGGER {table}_protection_writer ON {table}")
    op.execute("DROP FUNCTION require_protection_writer()")
    op.execute("DROP FUNCTION protection_audit_shape(jsonb,text)")
    op.execute("""ALTER TABLE paper_order_requests DROP CONSTRAINT manual_protection_shape,
        DROP COLUMN protection,DROP COLUMN protection_allocations""")
    # Break the deferred projection/history cycle before dropping empty tables.
    op.execute("ALTER TABLE paper_protections DROP CONSTRAINT protection_current_history")
    for table in (
        "paper_protection_results",
        "paper_protection_exit_progress",
        "paper_protection_exits",
        "paper_protection_events",
        "paper_protections",
        "paper_protection_requests",
        "paper_protection_protocol",
    ):
        op.execute(f"DROP TABLE {table}")
