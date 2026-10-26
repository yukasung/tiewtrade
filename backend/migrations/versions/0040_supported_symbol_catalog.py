"""Create the durable supported-symbol catalog and one-shot owner bootstrap.

Revision ID: 0039
Revises: 0038

Catalog mutations remain disabled after this additive migration. Static readers stay
compatible until ADR-005 protocol heartbeats are implemented and explicitly enabled.
"""

# ruff: noqa: E501 -- reviewed SQL fragments must match stored function definitions exactly

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

_PAIR_TABLES = (
    ("market_candles", "market_candles_check"),
    ("market_candle_demand", "market_candle_demand_check"),
    ("market_latest_prices", "market_latest_prices_check"),
    ("market_candle_preview", "market_candle_preview_check1"),
    ("indicator_build_jobs", "indicator_build_jobs_base_check"),
    ("indicator_generations", "indicator_generations_base_check"),
)


def _replace_function(signature: str, replacements: tuple[tuple[str, str], ...]) -> None:
    connection = op.get_bind()
    definition: str | None = connection.execute(
        text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
        {"signature": f"public.{signature}"},
    ).scalar_one()
    if definition is None:
        raise RuntimeError(f"missing function: {signature}")
    for before, after in replacements:
        if definition.count(before) != 1:
            raise RuntimeError(f"unexpected function definition: {signature}: {before}")
        definition = definition.replace(before, after)
    op.execute(definition)


def _replace_function_one_of(signature: str, befores: tuple[str, ...], after: str) -> None:
    connection = op.get_bind()
    definition: str | None = connection.execute(
        text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
        {"signature": f"public.{signature}"},
    ).scalar_one()
    if definition is None:
        raise RuntimeError(f"missing function: {signature}")
    matches = tuple(before for before in befores if definition.count(before) == 1)
    if len(matches) != 1:
        raise RuntimeError(f"unexpected function definition: {signature}")
    op.execute(definition.replace(matches[0], after))


def _replace_function_all(signature: str, before: str, after: str, count: int) -> None:
    connection = op.get_bind()
    definition: str | None = connection.execute(
        text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
        {"signature": f"public.{signature}"},
    ).scalar_one()
    if definition is None or definition.count(before) != count:
        raise RuntimeError(f"unexpected function definition: {signature}: {before}")
    op.execute(definition.replace(before, after))


def _extend_audit_shape() -> None:
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='public.audit_events'::regclass
          AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false',
        'WHEN ''CATALOG_MUTATIONS_ENABLED'' THEN
          actor_kind=''PLATFORM'' AND actor_id=owner_user_id
          AND mode=''NOT_APPLICABLE'' AND subject_kind=''SUPPORTED_SYMBOL''
          AND subject_id=''CATALOG'' AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''deployment_generation'',''revision'']
          AND details-ARRAY[''deployment_generation'',''revision'']=''{}''::jsonb
        WHEN ''CATALOG_ADD_REQUESTED'' THEN
          actor_kind=''PLATFORM'' AND actor_id=owner_user_id
          AND mode=''NOT_APPLICABLE'' AND subject_kind=''SUPPORTED_SYMBOL''
          AND subject_id=(details->>''base'')||''/''||(details->>''quote'')
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']
          AND details-ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']=''{}''::jsonb
        WHEN ''CATALOG_PREPARING'' THEN
          actor_kind=''SYSTEM'' AND actor_id IS NULL
          AND mode=''NOT_APPLICABLE'' AND subject_kind=''SUPPORTED_SYMBOL''
          AND subject_id=(details->>''base'')||''/''||(details->>''quote'')
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']
          AND details-ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']=''{}''::jsonb
        WHEN ''CATALOG_PREPARATION_REJECTED'' THEN
          actor_kind=''SYSTEM'' AND actor_id IS NULL
          AND mode=''NOT_APPLICABLE'' AND subject_kind=''SUPPORTED_SYMBOL''
          AND subject_id=(details->>''base'')||''/''||(details->>''quote'')
          AND outcome=''FAILED'' AND failure_code IN
            (''VENUE_CREDENTIAL_REJECTED'',''VENUE_REJECTED'',
             ''VENUE_OUTCOME_UNKNOWN'',''VENUE_PROTOCOL'')
          AND details ?& ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']
          AND details-ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']=''{}''::jsonb
        WHEN ''CATALOG_REMOVED'' THEN
          actor_kind=''PLATFORM'' AND actor_id=owner_user_id
          AND mode=''NOT_APPLICABLE'' AND subject_kind=''SUPPORTED_SYMBOL''
          AND subject_id=(details->>''base'')||''/''||(details->>''quote'')
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']
          AND details-ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']=''{}''::jsonb
        WHEN ''CATALOG_ACTIVATED'' THEN
          actor_kind=''SYSTEM'' AND actor_id IS NULL
          AND mode=''NOT_APPLICABLE'' AND subject_kind=''SUPPORTED_SYMBOL''
          AND subject_id=(details->>''base'')||''/''||(details->>''quote'')
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']
          AND details-ARRAY[''base'',''command_id'',''quote'',
            ''reason_code'',''revision_after'',''revision_before'']=''{}''::jsonb
        WHEN ''PLATFORM_OWNER_BOOTSTRAPPED'' THEN
          actor_kind=''SYSTEM'' AND actor_id IS NULL AND mode=''NOT_APPLICABLE''
          AND subject_kind=''PLATFORM_MEMBERSHIP'' AND subject_id=owner_user_id::text
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details=jsonb_build_object(''role'',''PLATFORM_OWNER'')
        ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension point missing'; END IF;
      ALTER TABLE public.audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE public.audit_events ADD CONSTRAINT audit_events_action_shape '
        ||changed;
    END $$""")


def _create_catalog() -> None:
    op.execute("""CREATE TABLE public.supported_symbol_registry(
      base text NOT NULL,quote text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(base,quote),
      CONSTRAINT supported_symbol_registry_shape CHECK(
        base<>'' AND base=upper(base) AND quote='USDT' AND base<>quote))""")
    op.execute("""CREATE TABLE public.supported_symbol_catalog_control(
      id smallint PRIMARY KEY CHECK(id=1),current_revision bigint NOT NULL CHECK(current_revision>=0),
      mutations_enabled boolean NOT NULL DEFAULT false,
      protocol_version integer NOT NULL CHECK(protocol_version>0),
      deployment_generation uuid,updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT supported_symbol_protocol_gate CHECK(
        NOT mutations_enabled OR deployment_generation IS NOT NULL))""")
    op.execute("""CREATE TABLE public.supported_symbol_events(
      revision bigint PRIMARY KEY CHECK(revision>0),command_id uuid NOT NULL,
      base text NOT NULL,quote text NOT NULL,status text NOT NULL,
      requested_by uuid,reason_code text NOT NULL,recorded_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY(base,quote) REFERENCES public.supported_symbol_registry(base,quote),
      CONSTRAINT supported_symbol_event_status CHECK(
        status IN ('REQUESTED','PREPARING','ACTIVE','REMOVED','FAILED')),
      CONSTRAINT supported_symbol_event_reason CHECK(
        reason_code IN ('F38_INITIAL_CATALOG','ADMIN_LIQUIDITY_REVIEWED',
          'ADMIN_RISK_REVIEW','VENUE_UNAVAILABLE','READINESS_FAILED')),
      CONSTRAINT supported_symbol_event_actor CHECK(
        (reason_code='F38_INITIAL_CATALOG' AND requested_by IS NULL)
        OR (reason_code<>'F38_INITIAL_CATALOG' AND requested_by IS NOT NULL)))""")
    op.execute("""CREATE TABLE public.supported_symbol_fences(
      base text NOT NULL,quote text NOT NULL,status text NOT NULL,revision bigint NOT NULL UNIQUE,
      command_id uuid NOT NULL,requested_by uuid,updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(base,quote),
      FOREIGN KEY(base,quote) REFERENCES public.supported_symbol_registry(base,quote),
      FOREIGN KEY(revision) REFERENCES public.supported_symbol_events(revision),
      CONSTRAINT supported_symbol_fence_status CHECK(
        status IN ('REQUESTED','PREPARING','ACTIVE','REMOVED','FAILED')))""")
    op.execute("""CREATE TABLE public.platform_memberships(
      user_id uuid PRIMARY KEY REFERENCES public.users(id),role text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),created_by uuid,
      CONSTRAINT platform_membership_role CHECK(role IN ('PLATFORM_ADMIN','PLATFORM_OWNER')),
      CONSTRAINT platform_owner_bootstrap_shape CHECK(
        role='PLATFORM_OWNER' OR created_by IS NOT NULL))""")
    op.execute("""CREATE TABLE public.supported_symbol_commands(
      id uuid PRIMARY KEY,requested_by uuid NOT NULL REFERENCES public.users(id),
      idempotency_key text NOT NULL,action text NOT NULL,base text NOT NULL,quote text NOT NULL,
      expected_revision bigint NOT NULL CHECK(expected_revision>=0),reason_code text NOT NULL,
      state text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
      completed_at timestamptz,revision bigint UNIQUE,
      UNIQUE(requested_by,idempotency_key),
      FOREIGN KEY(base,quote) REFERENCES public.supported_symbol_registry(base,quote),
      CONSTRAINT supported_symbol_command_idempotency CHECK(btrim(idempotency_key)<>''),
      CONSTRAINT supported_symbol_command_action CHECK(action IN ('ADD','REMOVE')),
      CONSTRAINT supported_symbol_command_reason CHECK(reason_code IN (
        'ADMIN_LIQUIDITY_REVIEWED','ADMIN_RISK_REVIEW')),
      CONSTRAINT supported_symbol_command_state CHECK(
        state IN ('REQUESTED','PREPARING','SUCCEEDED','FAILED')),
      CONSTRAINT supported_symbol_command_completion CHECK(
        (state IN ('REQUESTED','PREPARING') AND completed_at IS NULL)
        OR (state IN ('SUCCEEDED','FAILED') AND completed_at IS NOT NULL)))""")
    op.execute("""CREATE TABLE public.supported_symbol_constraint_snapshots(
      id uuid PRIMARY KEY,base text NOT NULL,quote text NOT NULL,
      venue_symbol text NOT NULL,source_at timestamptz NOT NULL,recorded_at timestamptz NOT NULL DEFAULT now(),
      payload jsonb NOT NULL,source_digest text NOT NULL,
      FOREIGN KEY(base,quote) REFERENCES public.supported_symbol_registry(base,quote),
      CONSTRAINT supported_symbol_constraint_payload CHECK(jsonb_typeof(payload)='object'),
      CONSTRAINT supported_symbol_constraint_digest CHECK(source_digest ~ '^[0-9a-f]{64}$'))""")
    op.execute("""CREATE TABLE public.supported_symbol_readiness(
      base text NOT NULL,quote text NOT NULL,catalog_revision bigint NOT NULL,
      venue_validated_at timestamptz,constraints_snapshot_id uuid,
      realtime_price_at timestamptz,ready_timeframe_count smallint NOT NULL DEFAULT 0,
      updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(base,quote),
      FOREIGN KEY(base,quote) REFERENCES public.supported_symbol_registry(base,quote),
      FOREIGN KEY(catalog_revision) REFERENCES public.supported_symbol_events(revision),
      FOREIGN KEY(constraints_snapshot_id)
        REFERENCES public.supported_symbol_constraint_snapshots(id),
      CONSTRAINT supported_symbol_ready_timeframes CHECK(ready_timeframe_count BETWEEN 0 AND 8))""")
    op.execute("""CREATE TABLE public.supported_symbol_effects(
      event_revision bigint PRIMARY KEY REFERENCES public.supported_symbol_events(revision),
      status text NOT NULL DEFAULT 'PENDING',attempts integer NOT NULL DEFAULT 0,
      bots_stopped integer NOT NULL DEFAULT 0,commands_rejected integer NOT NULL DEFAULT 0,
      orders_canceled integer NOT NULL DEFAULT 0,orders_unresolved integer NOT NULL DEFAULT 0,
      error_code text,updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT supported_symbol_effect_status CHECK(status IN ('PENDING','COMPLETE','PARTIAL')),
      CONSTRAINT supported_symbol_effect_counts CHECK(attempts>=0 AND bots_stopped>=0
        AND commands_rejected>=0 AND orders_canceled>=0 AND orders_unresolved>=0),
      CONSTRAINT supported_symbol_effect_error CHECK(
        error_code IS NULL OR error_code IN (
          'ORDER_CANCEL_FAILED','ORDER_OUTCOME_UNKNOWN','DEPENDENCY_UNAVAILABLE')))""")
    op.execute("""CREATE TABLE public.supported_symbol_maintenance_proofs(
      base text NOT NULL,quote text NOT NULL,catalog_revision bigint NOT NULL,
      zero_exposure_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(base,quote,catalog_revision),
      FOREIGN KEY(base,quote) REFERENCES public.supported_symbol_registry(base,quote),
      FOREIGN KEY(catalog_revision) REFERENCES public.supported_symbol_events(revision))""")
    op.execute("""CREATE TABLE public.catalog_protocol_heartbeats(
      process_kind text NOT NULL,instance_id uuid NOT NULL,protocol_version integer NOT NULL,
      deployment_generation uuid NOT NULL,lease_expires_at timestamptz NOT NULL,
      observed_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(process_kind,instance_id),
      CONSTRAINT catalog_protocol_process CHECK(
        process_kind IN ('API','ENGINE','MARKET_DATA','INDICATOR_BUILDER')),
      CONSTRAINT catalog_protocol_version CHECK(protocol_version>0),
      CONSTRAINT catalog_protocol_lease CHECK(lease_expires_at>observed_at))""")
    op.execute("""CREATE TABLE public.supported_symbol_timeframe_readiness(
      base text NOT NULL,quote text NOT NULL,catalog_revision bigint NOT NULL,
      timeframe text NOT NULL,candles_ready_at timestamptz,indicators_ready_at timestamptz,
      updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(base,quote,catalog_revision,timeframe),
      FOREIGN KEY(base,quote) REFERENCES public.supported_symbol_registry(base,quote),
      FOREIGN KEY(catalog_revision) REFERENCES public.supported_symbol_events(revision),
      CONSTRAINT supported_symbol_timeframe_value CHECK(
        timeframe IN ('1m','5m','15m','1h','4h','1d','1w','1M')))""")
    op.execute("ALTER TABLE public.platform_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.platform_memberships FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY platform_memberships_self ON public.platform_memberships
      FOR SELECT TO tiewtrade_api,tiewtrade_engine
      USING(user_id=public.tiewtrade_current_user_id())""")
    # The SECURITY DEFINER bootstrap must see whether any owner already exists while
    # still being allowed to insert only the explicitly scoped user.
    op.execute("""CREATE POLICY platform_memberships_bootstrap_read
      ON public.platform_memberships FOR SELECT TO tiewtrade_migrator USING(true)""")
    op.execute("""CREATE POLICY platform_memberships_bootstrap_insert
      ON public.platform_memberships FOR INSERT TO tiewtrade_migrator
      WITH CHECK(user_id=public.tiewtrade_current_user_id() AND role='PLATFORM_OWNER'
        AND created_by IS NULL)""")
    op.execute("""CREATE POLICY user_totp_platform_bootstrap_check ON public.user_totp
      FOR SELECT TO tiewtrade_migrator
      USING(user_id=public.tiewtrade_current_user_id())""")
    op.execute(
        "GRANT SELECT(user_id,role,created_at) ON platform_memberships TO tiewtrade_api,tiewtrade_engine"
    )
    op.execute("ALTER TABLE public.supported_symbol_commands ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.supported_symbol_commands FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY supported_symbol_commands_requester
      ON public.supported_symbol_commands FOR ALL TO tiewtrade_api,tiewtrade_engine
      USING(requested_by=public.tiewtrade_current_user_id())
      WITH CHECK(requested_by=public.tiewtrade_current_user_id())""")
    op.execute("""CREATE POLICY supported_symbol_commands_definer
      ON public.supported_symbol_commands FOR ALL TO tiewtrade_migrator
      USING(requested_by=public.tiewtrade_current_user_id())
      WITH CHECK(requested_by=public.tiewtrade_current_user_id())""")
    op.execute("""GRANT SELECT(id,requested_by,idempotency_key,action,base,quote,
      expected_revision,reason_code,state,created_at,completed_at,revision)
      ON public.supported_symbol_commands TO tiewtrade_api""")

    op.execute("""INSERT INTO public.supported_symbol_registry(base,quote)
      VALUES('BTC','USDT'),('ETH','USDT')""")
    op.execute("""INSERT INTO public.supported_symbol_events(
      revision,command_id,base,quote,status,reason_code)
      VALUES(1,'00000000-0000-0000-0000-000000000001','BTC','USDT','ACTIVE','F38_INITIAL_CATALOG'),
            (2,'00000000-0000-0000-0000-000000000002','ETH','USDT','ACTIVE','F38_INITIAL_CATALOG')""")
    op.execute("""INSERT INTO public.supported_symbol_fences(
      base,quote,status,revision,command_id)
      SELECT base,quote,status,revision,command_id FROM public.supported_symbol_events""")
    op.execute("""INSERT INTO public.supported_symbol_catalog_control(
      id,current_revision,mutations_enabled,protocol_version)
      VALUES(1,2,false,1)""")

    op.execute("""CREATE FUNCTION public.supported_symbol_projection_consistent()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE pair_base text;pair_quote text;latest public.supported_symbol_events%ROWTYPE;
      projected public.supported_symbol_fences%ROWTYPE;
    BEGIN
      pair_base:=coalesce(NEW.base,OLD.base);pair_quote:=coalesce(NEW.quote,OLD.quote);
      SELECT * INTO latest FROM public.supported_symbol_events
        WHERE base=pair_base AND quote=pair_quote ORDER BY revision DESC LIMIT 1;
      SELECT * INTO projected FROM public.supported_symbol_fences
        WHERE base=pair_base AND quote=pair_quote;
      IF latest.revision IS NULL OR projected.revision IS NULL
        OR latest.revision<>projected.revision OR latest.status<>projected.status
        OR latest.command_id<>projected.command_id THEN
        RAISE EXCEPTION USING ERRCODE='TT020',MESSAGE='CATALOG_PROJECTION_MISMATCH';
      END IF;
      RETURN NULL;
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.supported_symbol_projection_consistent() FROM PUBLIC")
    for table in ("supported_symbol_events", "supported_symbol_fences"):
        op.execute(f"""CREATE CONSTRAINT TRIGGER supported_symbol_projection_consistency
          AFTER INSERT OR UPDATE OR DELETE ON public.{table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION public.supported_symbol_projection_consistent()""")
    op.execute("""CREATE FUNCTION public.supported_symbol_revision_consistent()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF (SELECT current_revision FROM public.supported_symbol_catalog_control WHERE id=1)
        IS DISTINCT FROM (SELECT coalesce(max(revision),0) FROM public.supported_symbol_events)
      THEN
        RAISE EXCEPTION USING ERRCODE='TT020',MESSAGE='CATALOG_REVISION_MISMATCH';
      END IF;
      RETURN NULL;
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.supported_symbol_revision_consistent() FROM PUBLIC")
    for table in ("supported_symbol_events", "supported_symbol_catalog_control"):
        op.execute(f"""CREATE CONSTRAINT TRIGGER supported_symbol_revision_consistency
          AFTER INSERT OR UPDATE OR DELETE ON public.{table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION public.supported_symbol_revision_consistent()""")

    # Catalog coordination needs only a cross-user boolean/count, never user rows.
    # The migration owner is the SECURITY DEFINER for those narrow contracts and
    # needs an explicit policy because the underlying projections FORCE RLS.
    op.execute("""CREATE POLICY supported_symbol_catalog_reader
      ON public.paper_position_projections FOR SELECT TO tiewtrade_migrator USING(true)""")
    op.execute("""CREATE POLICY supported_symbol_catalog_reader
      ON public.paper_order_projections FOR SELECT TO tiewtrade_migrator USING(true)""")
    for table in (
        "paper_order_commands",
        "paper_order_command_results",
        "paper_orders",
        "paper_order_events",
    ):
        op.execute(f"""CREATE POLICY supported_symbol_effect_reader
          ON public.{table} FOR SELECT TO tiewtrade_migrator USING(true)""")
    op.execute("""CREATE FUNCTION public.supported_symbol_requires_maintenance(
      p_base text,p_quote text) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
      SET search_path=pg_catalog,public AS $$
      SELECT EXISTS(SELECT 1 FROM public.paper_position_projections p
        WHERE p.base=p_base AND p.quote=p_quote AND p.held_quantity>0)
      OR EXISTS(SELECT 1 FROM public.paper_order_projections o
        WHERE o.base=p_base AND o.quote=p_quote
          AND o.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')) $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.supported_symbol_requires_maintenance(text,text) FROM PUBLIC"
    )
    op.execute("""GRANT EXECUTE ON FUNCTION public.supported_symbol_requires_maintenance(text,text)
      TO tiewtrade_engine,tiewtrade_market_data,tiewtrade_indicator_builder""")

    op.execute("""CREATE VIEW public.active_supported_symbols AS
      SELECT f.base,f.quote,f.revision,c.current_revision
      FROM public.supported_symbol_fences f
      CROSS JOIN public.supported_symbol_catalog_control c
      WHERE f.status='ACTIVE'""")
    op.execute("""CREATE VIEW public.runtime_supported_symbols AS
      SELECT f.base,f.quote,f.status,f.revision,c.current_revision,
        CASE WHEN f.status='ACTIVE' THEN 'PUBLIC'
             WHEN f.status='PREPARING' THEN 'PREPARING'
             ELSE 'MAINTENANCE' END AS runtime_mode
      FROM public.supported_symbol_fences f
      CROSS JOIN public.supported_symbol_catalog_control c
      WHERE f.status IN ('ACTIVE','PREPARING')
        OR (f.status IN ('REMOVED','REQUESTED','FAILED')
          AND public.supported_symbol_requires_maintenance(f.base,f.quote))
        OR (f.status='REMOVED' AND NOT EXISTS(
          SELECT 1 FROM public.supported_symbol_maintenance_proofs proof
          WHERE proof.base=f.base AND proof.quote=f.quote
            AND proof.catalog_revision=f.revision))""")
    op.execute("""GRANT SELECT ON public.active_supported_symbols TO
      tiewtrade_api,tiewtrade_engine,tiewtrade_market_data,tiewtrade_indicator_builder""")
    op.execute("""GRANT SELECT ON public.runtime_supported_symbols TO
      tiewtrade_engine,tiewtrade_market_data,tiewtrade_indicator_builder""")
    op.execute("SELECT public.tiewtrade_make_append_only('supported_symbol_registry'::regclass)")
    op.execute("SELECT public.tiewtrade_make_append_only('supported_symbol_events'::regclass)")
    op.execute(
        "SELECT public.tiewtrade_make_append_only('supported_symbol_maintenance_proofs'::regclass)"
    )
    op.execute(
        "SELECT public.tiewtrade_make_append_only("
        "'supported_symbol_constraint_snapshots'::regclass)"
    )
    op.execute("SELECT public.tiewtrade_make_append_only('platform_memberships'::regclass)")


def _create_catalog_runtime() -> None:
    op.execute("""CREATE FUNCTION public.catalog_protocol_heartbeat(
      p_process_kind text,p_instance_id uuid,p_protocol_version integer,
      p_generation uuid,p_lease_expires_at timestamptz) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE expected_role text;
    BEGIN
      expected_role:=CASE p_process_kind
        WHEN 'API' THEN 'tiewtrade_api' WHEN 'ENGINE' THEN 'tiewtrade_engine'
        WHEN 'MARKET_DATA' THEN 'tiewtrade_market_data'
        WHEN 'INDICATOR_BUILDER' THEN 'tiewtrade_indicator_builder' END;
      IF expected_role IS NULL OR session_user<>expected_role
        OR p_lease_expires_at<=clock_timestamp() THEN
        RAISE EXCEPTION USING ERRCODE='TT024',MESSAGE='CATALOG_HEARTBEAT_REJECTED';
      END IF;
      INSERT INTO public.catalog_protocol_heartbeats(
        process_kind,instance_id,protocol_version,deployment_generation,lease_expires_at)
      VALUES(p_process_kind,p_instance_id,p_protocol_version,p_generation,p_lease_expires_at)
      ON CONFLICT(process_kind,instance_id) DO UPDATE SET
        protocol_version=EXCLUDED.protocol_version,
        deployment_generation=EXCLUDED.deployment_generation,
        lease_expires_at=EXCLUDED.lease_expires_at,observed_at=clock_timestamp();
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.catalog_protocol_heartbeat(text,uuid,integer,uuid,timestamptz) FROM PUBLIC"
    )
    op.execute("""GRANT EXECUTE ON FUNCTION public.catalog_protocol_heartbeat(
      text,uuid,integer,uuid,timestamptz) TO tiewtrade_api,tiewtrade_engine,
      tiewtrade_market_data,tiewtrade_indicator_builder""")

    op.execute("""CREATE FUNCTION public.catalog_protocol_ready(p_generation uuid)
      RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT NOT EXISTS(
        SELECT 1 FROM unnest(ARRAY['API','ENGINE','MARKET_DATA','INDICATOR_BUILDER']) required(kind)
        WHERE NOT EXISTS(SELECT 1 FROM public.catalog_protocol_heartbeats h
          JOIN public.supported_symbol_catalog_control c ON c.id=1
          WHERE h.process_kind=required.kind AND h.protocol_version=c.protocol_version
            AND h.deployment_generation=p_generation
            AND h.lease_expires_at>clock_timestamp()))
      AND NOT EXISTS(SELECT 1 FROM public.catalog_protocol_heartbeats h
        JOIN public.supported_symbol_catalog_control c ON c.id=1
        WHERE h.lease_expires_at>clock_timestamp()
          AND (h.protocol_version<>c.protocol_version
            OR h.deployment_generation<>p_generation)) $$""")
    op.execute("REVOKE ALL ON FUNCTION public.catalog_protocol_ready(uuid) FROM PUBLIC")

    op.execute("""CREATE FUNCTION public.enable_supported_symbol_mutations(
      p_requester uuid,p_generation uuid,p_expected_revision bigint) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE control public.supported_symbol_catalog_control%ROWTYPE;
    BEGIN
      IF p_requester IS DISTINCT FROM public.tiewtrade_current_user_id()
        OR NOT EXISTS(SELECT 1 FROM public.platform_memberships
          WHERE user_id=p_requester AND role='PLATFORM_OWNER') THEN
        RAISE EXCEPTION USING ERRCODE='TT024',MESSAGE='CATALOG_NOT_AUTHORIZED';
      END IF;
      PERFORM pg_advisory_xact_lock(737,2);
      SELECT * INTO control FROM public.supported_symbol_catalog_control WHERE id=1 FOR UPDATE;
      IF control.current_revision<>p_expected_revision THEN
        RAISE EXCEPTION USING ERRCODE='TT025',MESSAGE='CATALOG_REVISION_CONFLICT';
      END IF;
      IF NOT public.catalog_protocol_ready(p_generation) THEN
        RAISE EXCEPTION USING ERRCODE='TT023',MESSAGE='CATALOG_PROTOCOL_NOT_READY';
      END IF;
      UPDATE public.supported_symbol_catalog_control SET mutations_enabled=true,
        deployment_generation=p_generation,updated_at=clock_timestamp() WHERE id=1;
      INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,
        subject_kind,subject_id,mode,outcome,failure_code,details)
      VALUES(gen_random_uuid(),p_requester,'PLATFORM',p_requester,'CATALOG_MUTATIONS_ENABLED',
        'SUPPORTED_SYMBOL','CATALOG','NOT_APPLICABLE','SUCCEEDED',NULL,
        jsonb_build_object('deployment_generation',p_generation::text,
          'revision',control.current_revision));
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.enable_supported_symbol_mutations(uuid,uuid,bigint) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.enable_supported_symbol_mutations(uuid,uuid,bigint) TO tiewtrade_api"
    )

    op.execute("""CREATE FUNCTION public.assert_catalog_mutation_ready()
      RETURNS public.supported_symbol_catalog_control
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE control public.supported_symbol_catalog_control%ROWTYPE;
    BEGIN
      SELECT * INTO control FROM public.supported_symbol_catalog_control WHERE id=1 FOR UPDATE;
      IF NOT control.mutations_enabled OR control.deployment_generation IS NULL
        OR NOT public.catalog_protocol_ready(control.deployment_generation) THEN
        RAISE EXCEPTION USING ERRCODE='TT023',MESSAGE='CATALOG_PROTOCOL_NOT_READY';
      END IF;
      RETURN control;
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.assert_catalog_mutation_ready() FROM PUBLIC")

    op.execute("""CREATE FUNCTION public.request_supported_symbol_add(
      p_command_id uuid,p_requester uuid,p_idempotency_key text,p_base text,p_quote text,
      p_expected_revision bigint,p_reason text,p_snapshot_id uuid,p_venue_symbol text,
      p_source_at timestamptz,p_payload jsonb,p_digest text)
      RETURNS TABLE(id uuid,action text,base text,quote text,state text,revision bigint,
        created_at timestamptz,completed_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE existing public.supported_symbol_commands%ROWTYPE;
      control public.supported_symbol_catalog_control%ROWTYPE;next_revision bigint;
    BEGIN
      IF p_requester IS DISTINCT FROM public.tiewtrade_current_user_id()
        OR NOT EXISTS(SELECT 1 FROM public.platform_memberships WHERE user_id=p_requester) THEN
        RAISE EXCEPTION USING ERRCODE='TT024',MESSAGE='CATALOG_NOT_AUTHORIZED';
      END IF;
      PERFORM pg_advisory_xact_lock(737,2);
      SELECT * INTO existing FROM public.supported_symbol_commands
        WHERE requested_by=p_requester AND idempotency_key=p_idempotency_key;
      IF FOUND THEN
        IF (existing.action,existing.base,existing.quote,existing.expected_revision,existing.reason_code)
          IS DISTINCT FROM ('ADD',p_base,p_quote,p_expected_revision,p_reason) THEN
          RAISE EXCEPTION USING ERRCODE='TT026',MESSAGE='CATALOG_IDEMPOTENCY_CONFLICT';
        END IF;
        RETURN QUERY SELECT existing.id,existing.action,existing.base,existing.quote,
          existing.state,existing.revision,existing.created_at,existing.completed_at;RETURN;
      END IF;
      IF p_quote<>'USDT' OR p_base='' OR p_base<>upper(p_base) OR p_base=p_quote
        OR p_reason<>'ADMIN_LIQUIDITY_REVIEWED' OR jsonb_typeof(p_payload)<>'object'
        OR p_venue_symbol<>p_base||p_quote OR p_source_at>clock_timestamp()
        OR p_digest!~'^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_INPUT_INVALID';
      END IF;
      control:=public.assert_catalog_mutation_ready();
      IF control.current_revision<>p_expected_revision THEN
        RAISE EXCEPTION USING ERRCODE='TT025',MESSAGE='CATALOG_REVISION_CONFLICT';
      END IF;
      IF EXISTS(SELECT 1 FROM public.supported_symbol_fences f
        WHERE f.base=p_base AND f.quote=p_quote
          AND f.status IN ('ACTIVE','PREPARING','REQUESTED')) THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_PAIR_ALREADY_SUPPORTED';
      END IF;
      INSERT INTO public.supported_symbol_registry(base,quote) VALUES(p_base,p_quote)
        ON CONFLICT DO NOTHING;
      next_revision:=control.current_revision+1;
      INSERT INTO public.supported_symbol_commands(id,requested_by,idempotency_key,action,
        base,quote,expected_revision,reason_code,state,revision)
      VALUES(p_command_id,p_requester,p_idempotency_key,'ADD',p_base,p_quote,
        p_expected_revision,p_reason,'REQUESTED',next_revision);
      INSERT INTO public.supported_symbol_constraint_snapshots(id,base,quote,venue_symbol,
        source_at,payload,source_digest)
      VALUES(p_snapshot_id,p_base,p_quote,p_venue_symbol,p_source_at,p_payload,p_digest);
      INSERT INTO public.supported_symbol_events(revision,command_id,base,quote,status,
        requested_by,reason_code)
      VALUES(next_revision,p_command_id,p_base,p_quote,'REQUESTED',p_requester,p_reason);
      INSERT INTO public.supported_symbol_fences(base,quote,status,revision,command_id,requested_by)
      VALUES(p_base,p_quote,'REQUESTED',next_revision,p_command_id,p_requester)
      ON CONFLICT ON CONSTRAINT supported_symbol_fences_pkey DO UPDATE
        SET status='REQUESTED',revision=next_revision,
        command_id=p_command_id,requested_by=p_requester,updated_at=clock_timestamp();
      INSERT INTO public.supported_symbol_readiness(base,quote,catalog_revision,
        venue_validated_at,constraints_snapshot_id)
      VALUES(p_base,p_quote,next_revision,p_source_at,p_snapshot_id)
      ON CONFLICT ON CONSTRAINT supported_symbol_readiness_pkey DO UPDATE
        SET catalog_revision=next_revision,
        venue_validated_at=p_source_at,constraints_snapshot_id=p_snapshot_id,
        realtime_price_at=NULL,ready_timeframe_count=0,updated_at=clock_timestamp();
      UPDATE public.supported_symbol_catalog_control AS catalog_control
        SET current_revision=next_revision,updated_at=clock_timestamp()
        WHERE catalog_control.id=1;
      INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,
        subject_kind,subject_id,mode,outcome,failure_code,details)
      VALUES(gen_random_uuid(),p_requester,'PLATFORM',p_requester,'CATALOG_ADD_REQUESTED',
        'SUPPORTED_SYMBOL',p_base||'/'||p_quote,'NOT_APPLICABLE','SUCCEEDED',NULL,
        jsonb_build_object('command_id',p_command_id::text,'base',p_base,'quote',p_quote,
          'revision_before',p_expected_revision,'revision_after',next_revision,'reason_code',p_reason));
      RETURN QUERY SELECT c.id,c.action,c.base,c.quote,c.state,c.revision,c.created_at,c.completed_at
        FROM public.supported_symbol_commands c WHERE c.id=p_command_id;
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.request_supported_symbol_add(uuid,uuid,text,text,text,bigint,text,uuid,text,timestamptz,jsonb,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.request_supported_symbol_add(uuid,uuid,text,text,text,bigint,text,uuid,text,timestamptz,jsonb,text) TO tiewtrade_api"
    )

    op.execute("""CREATE FUNCTION public.prepare_supported_symbol(
      p_requester uuid,p_base text,p_quote text,p_expected_revision bigint)
      RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE control public.supported_symbol_catalog_control%ROWTYPE;
      fence public.supported_symbol_fences%ROWTYPE;
      command public.supported_symbol_commands%ROWTYPE;next_revision bigint;
    BEGIN
      IF session_user<>'tiewtrade_engine'
        OR p_requester IS DISTINCT FROM public.tiewtrade_current_user_id() THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_PREPARATION_INVALID';
      END IF;
      PERFORM pg_advisory_xact_lock(737,2);
      control:=public.assert_catalog_mutation_ready();
      IF control.current_revision<>p_expected_revision THEN
        RAISE EXCEPTION USING ERRCODE='TT025',MESSAGE='CATALOG_REVISION_CONFLICT';
      END IF;
      SELECT * INTO fence FROM public.supported_symbol_fences
        WHERE base=p_base AND quote=p_quote FOR UPDATE;
      IF fence.status<>'REQUESTED' OR fence.requested_by<>p_requester THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_PAIR_NOT_REQUESTED';
      END IF;
      SELECT * INTO command FROM public.supported_symbol_commands WHERE id=fence.command_id;
      next_revision:=control.current_revision+1;
      INSERT INTO public.supported_symbol_events(revision,command_id,base,quote,status,
        requested_by,reason_code)
      VALUES(next_revision,fence.command_id,p_base,p_quote,'PREPARING',p_requester,
        command.reason_code);
      UPDATE public.supported_symbol_fences SET status='PREPARING',revision=next_revision,
        updated_at=clock_timestamp() WHERE base=p_base AND quote=p_quote;
      UPDATE public.supported_symbol_readiness SET catalog_revision=next_revision,
        updated_at=clock_timestamp() WHERE base=p_base AND quote=p_quote
          AND catalog_revision=fence.revision;
      IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_READINESS_STALE';
      END IF;
      UPDATE public.supported_symbol_commands SET state='PREPARING',revision=next_revision
        WHERE id=fence.command_id;
      UPDATE public.supported_symbol_catalog_control SET current_revision=next_revision,
        updated_at=clock_timestamp() WHERE id=1;
      INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,
        subject_kind,subject_id,mode,outcome,failure_code,details)
      VALUES(gen_random_uuid(),p_requester,'SYSTEM',NULL,'CATALOG_PREPARING',
        'SUPPORTED_SYMBOL',p_base||'/'||p_quote,'NOT_APPLICABLE','SUCCEEDED',NULL,
        jsonb_build_object('command_id',fence.command_id::text,'base',p_base,'quote',p_quote,
          'revision_before',p_expected_revision,'revision_after',next_revision,
          'reason_code',command.reason_code));
      RETURN next_revision;
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.prepare_supported_symbol(uuid,text,text,bigint) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.prepare_supported_symbol(uuid,text,text,bigint) TO tiewtrade_engine"
    )

    op.execute("""CREATE FUNCTION public.fail_supported_symbol_preparation(
      p_requester uuid,p_base text,p_quote text,p_expected_revision bigint,p_failure_code text)
      RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE control public.supported_symbol_catalog_control%ROWTYPE;
      fence public.supported_symbol_fences%ROWTYPE;
      command public.supported_symbol_commands%ROWTYPE;next_revision bigint;
    BEGIN
      IF session_user<>'tiewtrade_engine'
        OR p_requester IS DISTINCT FROM public.tiewtrade_current_user_id()
        OR p_failure_code NOT IN ('VENUE_CREDENTIAL_REJECTED','VENUE_REJECTED',
          'VENUE_OUTCOME_UNKNOWN','VENUE_PROTOCOL') THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_PREPARATION_INVALID';
      END IF;
      PERFORM pg_advisory_xact_lock(737,2);
      control:=public.assert_catalog_mutation_ready();
      IF control.current_revision<>p_expected_revision THEN
        RAISE EXCEPTION USING ERRCODE='TT025',MESSAGE='CATALOG_REVISION_CONFLICT';
      END IF;
      SELECT * INTO fence FROM public.supported_symbol_fences
        WHERE base=p_base AND quote=p_quote FOR UPDATE;
      IF fence.status NOT IN ('REQUESTED','PREPARING') OR fence.requested_by<>p_requester THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_PAIR_NOT_PREPARING';
      END IF;
      SELECT * INTO command FROM public.supported_symbol_commands WHERE id=fence.command_id;
      next_revision:=control.current_revision+1;
      INSERT INTO public.supported_symbol_events(revision,command_id,base,quote,status,
        requested_by,reason_code)
      VALUES(next_revision,fence.command_id,p_base,p_quote,'FAILED',p_requester,
        'READINESS_FAILED');
      UPDATE public.supported_symbol_fences SET status='FAILED',revision=next_revision,
        updated_at=clock_timestamp() WHERE base=p_base AND quote=p_quote;
      UPDATE public.supported_symbol_commands SET state='FAILED',completed_at=clock_timestamp(),
        revision=next_revision WHERE id=fence.command_id;
      UPDATE public.supported_symbol_catalog_control SET current_revision=next_revision,
        updated_at=clock_timestamp() WHERE id=1;
      INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,
        subject_kind,subject_id,mode,outcome,failure_code,details)
      VALUES(gen_random_uuid(),p_requester,'SYSTEM',NULL,'CATALOG_PREPARATION_REJECTED',
        'SUPPORTED_SYMBOL',p_base||'/'||p_quote,'NOT_APPLICABLE','FAILED',p_failure_code,
        jsonb_build_object('command_id',fence.command_id::text,'base',p_base,'quote',p_quote,
          'revision_before',p_expected_revision,'revision_after',next_revision,
          'reason_code',command.reason_code));
      RETURN next_revision;
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.fail_supported_symbol_preparation(uuid,text,text,bigint,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.fail_supported_symbol_preparation(uuid,text,text,bigint,text) TO tiewtrade_engine"
    )

    op.execute("""CREATE FUNCTION public.request_supported_symbol_remove(
      p_command_id uuid,p_requester uuid,p_idempotency_key text,p_base text,p_quote text,
      p_expected_revision bigint,p_reason text)
      RETURNS TABLE(id uuid,action text,base text,quote text,state text,revision bigint,
        created_at timestamptz,completed_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE existing public.supported_symbol_commands%ROWTYPE;
      control public.supported_symbol_catalog_control%ROWTYPE;next_revision bigint;
    BEGIN
      IF p_requester IS DISTINCT FROM public.tiewtrade_current_user_id()
        OR NOT EXISTS(SELECT 1 FROM public.platform_memberships WHERE user_id=p_requester) THEN
        RAISE EXCEPTION USING ERRCODE='TT024',MESSAGE='CATALOG_NOT_AUTHORIZED';
      END IF;
      PERFORM pg_advisory_xact_lock(737,2);
      SELECT * INTO existing FROM public.supported_symbol_commands
        WHERE requested_by=p_requester AND idempotency_key=p_idempotency_key;
      IF FOUND THEN
        IF (existing.action,existing.base,existing.quote,existing.expected_revision,existing.reason_code)
          IS DISTINCT FROM ('REMOVE',p_base,p_quote,p_expected_revision,p_reason) THEN
          RAISE EXCEPTION USING ERRCODE='TT026',MESSAGE='CATALOG_IDEMPOTENCY_CONFLICT';
        END IF;
        RETURN QUERY SELECT existing.id,existing.action,existing.base,existing.quote,
          existing.state,existing.revision,existing.created_at,existing.completed_at;RETURN;
      END IF;
      IF p_quote<>'USDT' OR p_base='' OR p_base<>upper(p_base) OR p_base=p_quote
        OR p_reason<>'ADMIN_RISK_REVIEW' THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_INPUT_INVALID';
      END IF;
      control:=public.assert_catalog_mutation_ready();
      IF control.current_revision<>p_expected_revision THEN
        RAISE EXCEPTION USING ERRCODE='TT025',MESSAGE='CATALOG_REVISION_CONFLICT';
      END IF;
      PERFORM 1 FROM public.supported_symbol_fences f
        WHERE f.base=p_base AND f.quote=p_quote AND f.status='ACTIVE' FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_PAIR_NOT_ACTIVE'; END IF;
      next_revision:=control.current_revision+1;
      INSERT INTO public.supported_symbol_commands(id,requested_by,idempotency_key,action,
        base,quote,expected_revision,reason_code,state,completed_at,revision)
      VALUES(p_command_id,p_requester,p_idempotency_key,'REMOVE',p_base,p_quote,
        p_expected_revision,p_reason,'SUCCEEDED',clock_timestamp(),next_revision);
      INSERT INTO public.supported_symbol_events(revision,command_id,base,quote,status,
        requested_by,reason_code)
      VALUES(next_revision,p_command_id,p_base,p_quote,'REMOVED',p_requester,p_reason);
      UPDATE public.supported_symbol_fences AS fence
        SET status='REMOVED',revision=next_revision,
        command_id=p_command_id,requested_by=p_requester,updated_at=clock_timestamp()
        WHERE fence.base=p_base AND fence.quote=p_quote;
      INSERT INTO public.supported_symbol_effects(event_revision) VALUES(next_revision);
      UPDATE public.supported_symbol_catalog_control AS catalog_control
        SET current_revision=next_revision,updated_at=clock_timestamp()
        WHERE catalog_control.id=1;
      INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,
        subject_kind,subject_id,mode,outcome,failure_code,details)
      VALUES(gen_random_uuid(),p_requester,'PLATFORM',p_requester,'CATALOG_REMOVED',
        'SUPPORTED_SYMBOL',p_base||'/'||p_quote,'NOT_APPLICABLE','SUCCEEDED',NULL,
        jsonb_build_object('command_id',p_command_id::text,'base',p_base,'quote',p_quote,
          'revision_before',p_expected_revision,'revision_after',next_revision,'reason_code',p_reason));
      RETURN QUERY SELECT c.id,c.action,c.base,c.quote,c.state,c.revision,c.created_at,c.completed_at
        FROM public.supported_symbol_commands c WHERE c.id=p_command_id;
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.request_supported_symbol_remove(uuid,uuid,text,text,text,bigint,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.request_supported_symbol_remove(uuid,uuid,text,text,text,bigint,text) TO tiewtrade_api"
    )

    op.execute("""CREATE FUNCTION public.lock_supported_symbol_pair(p_base text,p_quote text)
      RETURNS TABLE(current_revision bigint,protocol_version integer,status text,
        latest_removed_revision bigint)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF session_user NOT IN ('tiewtrade_api','tiewtrade_engine') THEN
        RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CATALOG_PAIR_LOCK_NOT_AUTHORIZED';
      END IF;
      RETURN QUERY SELECT c.current_revision,c.protocol_version,f.status,
        (SELECT max(e.revision) FROM public.supported_symbol_events e
          WHERE e.base=p_base AND e.quote=p_quote AND e.status='REMOVED')
        FROM public.supported_symbol_catalog_control c
        CROSS JOIN public.supported_symbol_fences f
        WHERE c.id=1 AND f.base=p_base AND f.quote=p_quote
        FOR SHARE OF f;
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.lock_supported_symbol_pair(text,text) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.lock_supported_symbol_pair(text,text) TO tiewtrade_api,tiewtrade_engine"
    )

    op.execute("""CREATE FUNCTION public.reconcile_supported_symbol_effects() RETURNS integer
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE changed integer;
    BEGIN
      IF session_user<>'tiewtrade_engine' THEN
        RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CATALOG_EFFECT_NOT_AUTHORIZED';
      END IF;
      WITH progress AS (
        SELECT effect.event_revision,
          (SELECT count(*) FROM public.paper_order_commands c
            LEFT JOIN public.paper_order_command_results r ON r.command_id=c.id
            WHERE c.action='NEW' AND r.command_id IS NULL
              AND coalesce((c.payload->>'catalog_revision')::bigint,0)<event.revision
              AND c.payload->'intent'->>'base'=event.base
              AND c.payload->'intent'->>'quote'=event.quote
              AND c.payload->'intent'->>'side'='BUY') AS queued,
          (SELECT count(*) FROM public.paper_order_commands c
            JOIN public.paper_order_command_results r ON r.command_id=c.id
            WHERE c.action='NEW' AND r.failure_code='CATALOG_PAIR_REMOVED'
              AND coalesce((c.payload->>'catalog_revision')::bigint,0)<event.revision
              AND r.completed_at>=event.recorded_at
              AND c.payload->'intent'->>'base'=event.base
              AND c.payload->'intent'->>'quote'=event.quote
              AND c.payload->'intent'->>'side'='BUY') AS rejected,
          (SELECT count(*) FROM public.paper_orders o
            JOIN public.paper_order_commands c ON c.id=o.command_id
            JOIN public.paper_order_projections projection ON projection.order_id=o.id
            WHERE o.base=event.base AND o.quote=event.quote AND o.side='BUY'
              AND coalesce((c.payload->>'catalog_revision')::bigint,0)<event.revision
              AND projection.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')) AS active,
          (SELECT count(*) FROM public.paper_orders o
            JOIN public.paper_order_commands c ON c.id=o.command_id
            JOIN public.paper_order_projections projection ON projection.order_id=o.id
            WHERE o.base=event.base AND o.quote=event.quote AND o.side='BUY'
              AND coalesce((c.payload->>'catalog_revision')::bigint,0)<event.revision
              AND projection.status='CANCELED'
              AND EXISTS(SELECT 1 FROM public.paper_order_events order_event
                WHERE order_event.order_id=o.id AND order_event.event_kind='CANCELED'
                  AND order_event.occurred_at>=event.recorded_at)) AS canceled
        FROM public.supported_symbol_effects effect
        JOIN public.supported_symbol_events event ON event.revision=effect.event_revision
        WHERE effect.status='PENDING' AND event.status='REMOVED')
      UPDATE public.supported_symbol_effects effect SET
        attempts=effect.attempts+1,
        commands_rejected=progress.rejected,
        orders_canceled=progress.canceled,
        orders_unresolved=progress.queued+progress.active,
        status=CASE WHEN progress.queued+progress.active=0 THEN 'PARTIAL' ELSE 'PENDING' END,
        error_code=CASE WHEN progress.queued+progress.active=0
          THEN 'DEPENDENCY_UNAVAILABLE' ELSE NULL END,
        updated_at=clock_timestamp()
      FROM progress WHERE progress.event_revision=effect.event_revision;
      GET DIAGNOSTICS changed=ROW_COUNT;
      RETURN changed;
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.reconcile_supported_symbol_effects() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.reconcile_supported_symbol_effects() TO tiewtrade_engine"
    )

    op.execute("""CREATE FUNCTION public.reconcile_supported_symbol_maintenance() RETURNS integer
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE changed integer;
    BEGIN
      IF session_user<>'tiewtrade_engine' THEN
        RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CATALOG_MAINTENANCE_NOT_AUTHORIZED';
      END IF;
      INSERT INTO public.supported_symbol_maintenance_proofs(
        base,quote,catalog_revision,zero_exposure_at)
      SELECT fence.base,fence.quote,fence.revision,clock_timestamp()
      FROM public.supported_symbol_fences fence
      WHERE fence.status='REMOVED'
        AND NOT public.supported_symbol_requires_maintenance(fence.base,fence.quote)
      ON CONFLICT DO NOTHING;
      GET DIAGNOSTICS changed=ROW_COUNT;
      RETURN changed;
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.reconcile_supported_symbol_maintenance() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.reconcile_supported_symbol_maintenance() TO tiewtrade_engine"
    )

    op.execute("""CREATE FUNCTION public.supported_symbol_impact_preview(p_base text,p_quote text)
      RETURNS TABLE(bots bigint,open_entry_orders bigint,protective_orders bigint,
        reduce_risk_orders bigint,positions bigint,complete boolean,snapshot_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.platform_memberships
        WHERE user_id=public.tiewtrade_current_user_id()) THEN
        RAISE EXCEPTION USING ERRCODE='TT024',MESSAGE='CATALOG_NOT_AUTHORIZED';
      END IF;
      RETURN QUERY SELECT
        count(DISTINCT (o.user_id,o.episode_id)) FILTER(WHERE o.origin='BOT'),
        count(*) FILTER(WHERE o.side='BUY'),0::bigint,
        count(*) FILTER(WHERE o.side='SELL'),
        (SELECT count(*) FROM public.paper_position_projections p
          WHERE p.base=p_base AND p.quote=p_quote AND p.held_quantity>0),
        false,clock_timestamp()
      FROM public.paper_order_projections projection
      JOIN public.paper_orders o ON o.id=projection.order_id
      WHERE projection.base=p_base AND projection.quote=p_quote
        AND projection.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED');
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.supported_symbol_impact_preview(text,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.supported_symbol_impact_preview(text,text) TO tiewtrade_api"
    )

    op.execute("""CREATE FUNCTION public.record_supported_symbol_price_readiness(
      p_base text,p_quote text,p_catalog_revision bigint,p_price_at timestamptz) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF session_user<>'tiewtrade_market_data' OR p_price_at>clock_timestamp()
        OR NOT EXISTS(SELECT 1 FROM public.supported_symbol_fences f
          JOIN public.supported_symbol_events e ON e.revision=f.revision
          WHERE f.base=p_base AND f.quote=p_quote AND f.status='PREPARING'
            AND f.revision=p_catalog_revision AND p_price_at>=e.recorded_at) THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_READINESS_STALE';
      END IF;
      UPDATE public.supported_symbol_readiness SET realtime_price_at=p_price_at,
        updated_at=clock_timestamp() WHERE base=p_base AND quote=p_quote
          AND catalog_revision=p_catalog_revision;
      IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_READINESS_STALE';
      END IF;
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.record_supported_symbol_price_readiness(text,text,bigint,timestamptz) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.record_supported_symbol_price_readiness(text,text,bigint,timestamptz) TO tiewtrade_market_data"
    )

    op.execute("""CREATE FUNCTION public.record_supported_symbol_timeframe_readiness(
      p_base text,p_quote text,p_catalog_revision bigint,p_timeframe text,p_ready_at timestamptz)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE candle_writer boolean:=session_user='tiewtrade_market_data';
      indicator_writer boolean:=session_user='tiewtrade_indicator_builder';
    BEGIN
      IF (NOT candle_writer AND NOT indicator_writer) OR p_ready_at>clock_timestamp()
        OR p_timeframe NOT IN ('1m','5m','15m','1h','4h','1d','1w','1M')
        OR NOT EXISTS(SELECT 1 FROM public.supported_symbol_fences f
          JOIN public.supported_symbol_events e ON e.revision=f.revision
          WHERE f.base=p_base AND f.quote=p_quote AND f.status='PREPARING'
            AND f.revision=p_catalog_revision AND p_ready_at>=e.recorded_at) THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_READINESS_STALE';
      END IF;
      INSERT INTO public.supported_symbol_timeframe_readiness(
        base,quote,catalog_revision,timeframe,candles_ready_at,indicators_ready_at)
      VALUES(p_base,p_quote,p_catalog_revision,p_timeframe,
        CASE WHEN candle_writer THEN p_ready_at END,
        CASE WHEN indicator_writer THEN p_ready_at END)
      ON CONFLICT(base,quote,catalog_revision,timeframe) DO UPDATE SET
        candles_ready_at=CASE WHEN candle_writer THEN p_ready_at
          ELSE supported_symbol_timeframe_readiness.candles_ready_at END,
        indicators_ready_at=CASE WHEN indicator_writer THEN p_ready_at
          ELSE supported_symbol_timeframe_readiness.indicators_ready_at END,
        updated_at=clock_timestamp();
      UPDATE public.supported_symbol_readiness SET ready_timeframe_count=(
        SELECT count(*) FROM public.supported_symbol_timeframe_readiness t
        WHERE t.base=p_base AND t.quote=p_quote AND t.catalog_revision=p_catalog_revision
          AND t.candles_ready_at IS NOT NULL AND t.indicators_ready_at IS NOT NULL),
        updated_at=clock_timestamp() WHERE base=p_base AND quote=p_quote
          AND catalog_revision=p_catalog_revision;
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.record_supported_symbol_timeframe_readiness(text,text,bigint,text,timestamptz) FROM PUBLIC"
    )
    op.execute("""GRANT EXECUTE ON FUNCTION public.record_supported_symbol_timeframe_readiness(
      text,text,bigint,text,timestamptz) TO tiewtrade_market_data,tiewtrade_indicator_builder""")

    op.execute("""CREATE FUNCTION public.activate_supported_symbol(
      p_requester uuid,p_base text,p_quote text,p_expected_revision bigint,
      p_snapshot_id uuid,p_venue_symbol text,p_validation_started_at timestamptz,
      p_source_at timestamptz,p_payload jsonb,p_digest text)
      RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE control public.supported_symbol_catalog_control%ROWTYPE;
      fence public.supported_symbol_fences%ROWTYPE;
      readiness public.supported_symbol_readiness%ROWTYPE;
      command public.supported_symbol_commands%ROWTYPE;next_revision bigint;
    BEGIN
      IF session_user<>'tiewtrade_engine'
        OR p_requester IS DISTINCT FROM public.tiewtrade_current_user_id()
        OR p_source_at<p_validation_started_at OR p_source_at>clock_timestamp()
        OR p_venue_symbol<>p_base||p_quote OR jsonb_typeof(p_payload)<>'object'
        OR p_digest!~'^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_ACTIVATION_INVALID';
      END IF;
      PERFORM pg_advisory_xact_lock(737,2);
      control:=public.assert_catalog_mutation_ready();
      IF control.current_revision<>p_expected_revision THEN
        RAISE EXCEPTION USING ERRCODE='TT025',MESSAGE='CATALOG_REVISION_CONFLICT';
      END IF;
      SELECT * INTO fence FROM public.supported_symbol_fences
        WHERE base=p_base AND quote=p_quote FOR UPDATE;
      IF fence.status<>'PREPARING' OR fence.requested_by<>p_requester THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_PAIR_NOT_PREPARING';
      END IF;
      SELECT * INTO readiness FROM public.supported_symbol_readiness
        WHERE base=p_base AND quote=p_quote AND catalog_revision=fence.revision;
      IF readiness.catalog_revision IS NULL OR readiness.ready_timeframe_count<>8
        OR readiness.realtime_price_at IS NULL
        OR readiness.realtime_price_at<clock_timestamp()-interval '10 seconds'
        OR EXISTS(SELECT 1 FROM public.supported_symbol_timeframe_readiness t
          JOIN public.supported_symbol_events e ON e.revision=t.catalog_revision
          WHERE t.base=p_base AND t.quote=p_quote AND t.catalog_revision=fence.revision
            AND (t.candles_ready_at<e.recorded_at OR t.indicators_ready_at<e.recorded_at)) THEN
        RAISE EXCEPTION USING ERRCODE='TT027',MESSAGE='CATALOG_READINESS_INCOMPLETE';
      END IF;
      SELECT * INTO command FROM public.supported_symbol_commands WHERE id=fence.command_id;
      next_revision:=control.current_revision+1;
      INSERT INTO public.supported_symbol_constraint_snapshots(id,base,quote,venue_symbol,
        source_at,payload,source_digest)
      VALUES(p_snapshot_id,p_base,p_quote,p_venue_symbol,p_source_at,p_payload,p_digest);
      UPDATE public.supported_symbol_readiness SET venue_validated_at=p_source_at,
        constraints_snapshot_id=p_snapshot_id,updated_at=clock_timestamp()
        WHERE base=p_base AND quote=p_quote AND catalog_revision=fence.revision;
      INSERT INTO public.supported_symbol_events(revision,command_id,base,quote,status,
        requested_by,reason_code)
      VALUES(next_revision,fence.command_id,p_base,p_quote,'ACTIVE',p_requester,command.reason_code);
      UPDATE public.supported_symbol_fences SET status='ACTIVE',revision=next_revision,
        updated_at=clock_timestamp() WHERE base=p_base AND quote=p_quote;
      UPDATE public.supported_symbol_commands SET state='SUCCEEDED',completed_at=clock_timestamp(),
        revision=next_revision WHERE id=fence.command_id;
      UPDATE public.supported_symbol_catalog_control SET current_revision=next_revision,
        updated_at=clock_timestamp() WHERE id=1;
      INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,
        subject_kind,subject_id,mode,outcome,failure_code,details)
      VALUES(gen_random_uuid(),p_requester,'SYSTEM',NULL,'CATALOG_ACTIVATED',
        'SUPPORTED_SYMBOL',p_base||'/'||p_quote,'NOT_APPLICABLE','SUCCEEDED',NULL,
        jsonb_build_object('command_id',fence.command_id::text,'base',p_base,'quote',p_quote,
          'revision_before',p_expected_revision,'revision_after',next_revision,
          'reason_code',command.reason_code));
      RETURN next_revision;
    END $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.activate_supported_symbol(uuid,text,text,bigint,uuid,text,timestamptz,timestamptz,jsonb,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.activate_supported_symbol(uuid,text,text,bigint,uuid,text,timestamptz,timestamptz,jsonb,text) TO tiewtrade_engine"
    )

    op.execute("""GRANT SELECT(id,current_revision,mutations_enabled,protocol_version,
      deployment_generation,updated_at) ON public.supported_symbol_catalog_control
      TO tiewtrade_api,tiewtrade_engine""")
    op.execute("""GRANT SELECT(base,quote,status,revision,updated_at)
      ON public.supported_symbol_fences TO tiewtrade_api""")
    op.execute("""GRANT SELECT(event_revision,status,attempts,bots_stopped,commands_rejected,
      orders_canceled,orders_unresolved,error_code,updated_at)
      ON public.supported_symbol_effects TO tiewtrade_api""")
    op.execute("""GRANT SELECT ON public.supported_symbol_fences,
      public.supported_symbol_readiness,public.supported_symbol_effects TO tiewtrade_engine""")


def _create_bootstrap() -> None:
    op.execute("""CREATE FUNCTION public.bootstrap_platform_owner(p_user_id uuid) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF p_user_id IS NULL THEN
        RAISE EXCEPTION USING ERRCODE='TT021',MESSAGE='PLATFORM_BOOTSTRAP_USER_INELIGIBLE';
      END IF;
      PERFORM set_config('tiewtrade.current_user_id',p_user_id::text,true);
      IF NOT EXISTS(
        SELECT 1 FROM public.users WHERE id=p_user_id) OR NOT EXISTS(
        SELECT 1 FROM public.user_totp WHERE user_id=p_user_id) THEN
        RAISE EXCEPTION USING ERRCODE='TT021',MESSAGE='PLATFORM_BOOTSTRAP_USER_INELIGIBLE';
      END IF;
      PERFORM pg_advisory_xact_lock(737,1);
      IF EXISTS(SELECT 1 FROM public.platform_memberships WHERE role='PLATFORM_OWNER') THEN
        RAISE EXCEPTION USING ERRCODE='TT022',MESSAGE='PLATFORM_OWNER_ALREADY_EXISTS';
      END IF;
      INSERT INTO public.platform_memberships(user_id,role)
        VALUES(p_user_id,'PLATFORM_OWNER');
      INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,
        subject_kind,subject_id,mode,outcome,failure_code,details)
      VALUES(gen_random_uuid(),p_user_id,'SYSTEM',NULL,'PLATFORM_OWNER_BOOTSTRAPPED',
        'PLATFORM_MEMBERSHIP',p_user_id::text,'NOT_APPLICABLE','SUCCEEDED',NULL,
        jsonb_build_object('role','PLATFORM_OWNER'));
    END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.bootstrap_platform_owner(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.bootstrap_platform_owner(uuid) TO tiewtrade_platform_bootstrap"
    )


def _make_pair_storage_dynamic() -> None:
    op.execute("SELECT public.begin_indicator_source_maintenance()")
    for table, constraint in _PAIR_TABLES:
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {constraint}")
        op.execute(f"""ALTER TABLE public.{table}
          ADD CONSTRAINT {table}_supported_symbol_fk FOREIGN KEY(base,quote)
          REFERENCES public.supported_symbol_registry(base,quote),
          ADD CONSTRAINT {table}_usdt_quote CHECK(quote='USDT')""")

    _replace_function(
        "seed_indicator_build_jobs()",
        (
            (
                "FROM (VALUES('BTC'),('ETH')) b(base)",
                "FROM (SELECT base FROM public.supported_symbol_fences WHERE status IN ('ACTIVE','PREPARING')) b",
            ),
        ),
    )
    _replace_function(
        "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)",
        (
            (
                "ready_count<>16",
                "ready_count<>(SELECT count(*)*8 FROM public.supported_symbol_fences WHERE status='ACTIVE')",
            ),
        ),
    )
    _replace_function(
        "claim_indicator_build_job(uuid)",
        (
            (
                "CASE eligible.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
                "SELECT count(*) FROM public.supported_symbol_fences f WHERE f.status IN ('ACTIVE','PREPARING') AND f.base<eligible.base)*8",
            ),
            (
                "-s.dispatch_cursor+15,16)",
                "-s.dispatch_cursor+((SELECT count(*) FROM public.supported_symbol_fences WHERE status IN ('ACTIVE','PREPARING'))*8)-1,((SELECT count(*) FROM public.supported_symbol_fences WHERE status IN ('ACTIVE','PREPARING'))*8))",
            ),
            (
                "CASE j.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
                "SELECT count(*) FROM public.supported_symbol_fences f WHERE f.status IN ('ACTIVE','PREPARING') AND f.base<j.base)*8",
            ),
        ),
    )
    _replace_function(
        "claim_indicator_build_job(uuid)",
        (
            (
                "SELECT eligible.* INTO j FROM public.indicator_build_jobs eligible\n"
                "            WHERE ",
                "SELECT eligible.* INTO j FROM public.indicator_build_jobs eligible\n"
                "            JOIN public.supported_symbol_fences pair_fence\n"
                "              ON pair_fence.base=eligible.base AND pair_fence.quote=eligible.quote\n"
                "              AND pair_fence.status IN ('ACTIVE','PREPARING')\n"
                "            WHERE ",
            ),
        ),
    )
    _replace_function_all(
        "claim_indicator_build_job(uuid)",
        "AND public.indicator_numeric_candidate_allowed(eligible)",
        "AND public.indicator_numeric_candidate_allowed(eligible)\n"
        "              AND EXISTS(SELECT 1 FROM public.supported_symbol_fences pair_fence\n"
        "                WHERE pair_fence.base=eligible.base AND pair_fence.quote=eligible.quote\n"
        "                  AND pair_fence.status IN ('ACTIVE','PREPARING'))",
        3,
    )
    _replace_function(
        "coalesce_indicator_build_jobs()",
        (
            (
                "FOR j IN SELECT * FROM public.indicator_build_jobs\n"
                "    WHERE formula_version='indicators-v2' ORDER BY id FOR UPDATE LOOP",
                "FOR j IN SELECT jobs.* FROM public.indicator_build_jobs jobs\n"
                "    JOIN public.supported_symbol_fences pair_fence\n"
                "      ON pair_fence.base=jobs.base AND pair_fence.quote=jobs.quote\n"
                "      AND pair_fence.status IN ('ACTIVE','PREPARING')\n"
                "    WHERE jobs.formula_version='indicators-v2' ORDER BY jobs.id FOR UPDATE OF jobs LOOP",
            ),
        ),
    )
    _replace_function(
        "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)",
        (
            (
                "SELECT count(*) INTO ready_count FROM public.indicator_build_jobs j\n"
                "          JOIN public.indicator_heads h "
                "USING(source,base,quote,timeframe,formula_version)",
                "SELECT count(*) INTO ready_count FROM public.indicator_build_jobs j\n"
                "          JOIN public.indicator_heads h "
                "USING(source,base,quote,timeframe,formula_version)\n"
                "          JOIN public.supported_symbol_fences pair_fence\n"
                "            ON pair_fence.base=j.base AND pair_fence.quote=j.quote\n"
                "            AND pair_fence.status='ACTIVE'",
            ),
        ),
    )
    op.execute(
        "ALTER TABLE public.indicator_build_slot DROP CONSTRAINT indicator_build_slot_dispatch_cursor_check"
    )
    op.execute("ALTER TABLE public.indicator_build_slot ALTER COLUMN dispatch_cursor TYPE integer")
    op.execute("""ALTER TABLE public.indicator_build_slot
      ADD CONSTRAINT indicator_build_slot_dispatch_cursor_check CHECK(dispatch_cursor>=-1)""")


def upgrade() -> None:
    _extend_audit_shape()
    _create_catalog()
    _create_catalog_runtime()
    _create_bootstrap()
    _make_pair_storage_dynamic()


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.platform_memberships)
        OR EXISTS(SELECT 1 FROM public.supported_symbol_registry
          WHERE (base,quote) NOT IN (('BTC','USDT'),('ETH','USDT')))
        OR EXISTS(SELECT 1 FROM public.supported_symbol_events
          WHERE reason_code<>'F38_INITIAL_CATALOG')
      THEN RAISE EXCEPTION 'supported-symbol runtime history prevents downgrade'; END IF;
    END $$""")
    op.execute(
        "DROP FUNCTION IF EXISTS public.activate_supported_symbol(uuid,text,text,bigint,uuid,text,timestamptz,timestamptz,jsonb,text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.fail_supported_symbol_preparation(uuid,text,text,bigint,text)"
    )
    op.execute("DROP FUNCTION IF EXISTS public.prepare_supported_symbol(uuid,text,text,bigint)")
    op.execute(
        "DROP FUNCTION IF EXISTS public.record_supported_symbol_timeframe_readiness(text,text,bigint,text,timestamptz)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.record_supported_symbol_price_readiness(text,text,bigint,timestamptz)"
    )
    op.execute("DROP FUNCTION IF EXISTS public.supported_symbol_impact_preview(text,text)")
    op.execute(
        "DROP FUNCTION IF EXISTS public.request_supported_symbol_remove(uuid,uuid,text,text,text,bigint,text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.request_supported_symbol_add(uuid,uuid,text,text,text,bigint,text,uuid,text,timestamptz,jsonb,text)"
    )
    op.execute("DROP FUNCTION IF EXISTS public.assert_catalog_mutation_ready()")
    op.execute("DROP FUNCTION IF EXISTS public.enable_supported_symbol_mutations(uuid,uuid,bigint)")
    op.execute("DROP FUNCTION IF EXISTS public.catalog_protocol_ready(uuid)")
    op.execute(
        "DROP FUNCTION IF EXISTS public.catalog_protocol_heartbeat(text,uuid,integer,uuid,timestamptz)"
    )
    op.execute("DROP VIEW IF EXISTS public.runtime_supported_symbols")
    op.execute("DROP VIEW public.active_supported_symbols")
    op.execute("DROP FUNCTION IF EXISTS public.reconcile_supported_symbol_maintenance()")
    op.execute("DROP FUNCTION IF EXISTS public.reconcile_supported_symbol_effects()")
    op.execute("DROP FUNCTION IF EXISTS public.lock_supported_symbol_pair(text,text)")
    op.execute("DROP FUNCTION IF EXISTS public.supported_symbol_requires_maintenance(text,text)")
    op.execute(
        "DROP POLICY IF EXISTS supported_symbol_catalog_reader ON public.paper_order_projections"
    )
    for table in (
        "paper_order_commands",
        "paper_order_command_results",
        "paper_orders",
        "paper_order_events",
    ):
        op.execute(f"DROP POLICY IF EXISTS supported_symbol_effect_reader ON public.{table}")
    op.execute(
        "DROP POLICY IF EXISTS supported_symbol_catalog_reader ON public.paper_position_projections"
    )
    op.execute("DROP FUNCTION public.bootstrap_platform_owner(uuid)")
    op.execute(
        "ALTER TABLE public.indicator_build_slot DROP CONSTRAINT indicator_build_slot_dispatch_cursor_check"
    )
    op.execute("ALTER TABLE public.indicator_build_slot ALTER COLUMN dispatch_cursor TYPE smallint")
    op.execute("""ALTER TABLE public.indicator_build_slot
      ADD CONSTRAINT indicator_build_slot_dispatch_cursor_check
      CHECK(dispatch_cursor BETWEEN -1 AND 15)""")
    _replace_function(
        "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)",
        (
            (
                "SELECT count(*) INTO ready_count FROM public.indicator_build_jobs j\n"
                "          JOIN public.indicator_heads h "
                "USING(source,base,quote,timeframe,formula_version)\n"
                "          JOIN public.supported_symbol_fences pair_fence\n"
                "            ON pair_fence.base=j.base AND pair_fence.quote=j.quote\n"
                "            AND pair_fence.status='ACTIVE'",
                "SELECT count(*) INTO ready_count FROM public.indicator_build_jobs j\n"
                "          JOIN public.indicator_heads h "
                "USING(source,base,quote,timeframe,formula_version)",
            ),
        ),
    )
    _replace_function(
        "coalesce_indicator_build_jobs()",
        (
            (
                "FOR j IN SELECT jobs.* FROM public.indicator_build_jobs jobs\n"
                "    JOIN public.supported_symbol_fences pair_fence\n"
                "      ON pair_fence.base=jobs.base AND pair_fence.quote=jobs.quote\n"
                "      AND pair_fence.status IN ('ACTIVE','PREPARING')\n"
                "    WHERE jobs.formula_version='indicators-v2' ORDER BY jobs.id FOR UPDATE OF jobs LOOP",
                "FOR j IN SELECT * FROM public.indicator_build_jobs\n"
                "    WHERE formula_version='indicators-v2' ORDER BY id FOR UPDATE LOOP",
            ),
        ),
    )
    _replace_function_all(
        "claim_indicator_build_job(uuid)",
        "AND public.indicator_numeric_candidate_allowed(eligible)\n"
        "              AND EXISTS(SELECT 1 FROM public.supported_symbol_fences pair_fence\n"
        "                WHERE pair_fence.base=eligible.base AND pair_fence.quote=eligible.quote\n"
        "                  AND pair_fence.status IN ('ACTIVE','PREPARING'))",
        "AND public.indicator_numeric_candidate_allowed(eligible)",
        3,
    )
    _replace_function(
        "claim_indicator_build_job(uuid)",
        (
            (
                "SELECT eligible.* INTO j FROM public.indicator_build_jobs eligible\n"
                "            JOIN public.supported_symbol_fences pair_fence\n"
                "              ON pair_fence.base=eligible.base AND pair_fence.quote=eligible.quote\n"
                "              AND pair_fence.status IN ('ACTIVE','PREPARING')\n"
                "            WHERE ",
                "SELECT eligible.* INTO j FROM public.indicator_build_jobs eligible\n"
                "            WHERE ",
            ),
        ),
    )
    _replace_function(
        "claim_indicator_build_job(uuid)",
        (
            (
                "SELECT count(*) FROM public.supported_symbol_fences f WHERE f.status IN ('ACTIVE','PREPARING') AND f.base<eligible.base)*8",
                "CASE eligible.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
            ),
            (
                "-s.dispatch_cursor+((SELECT count(*) FROM public.supported_symbol_fences WHERE status IN ('ACTIVE','PREPARING'))*8)-1,((SELECT count(*) FROM public.supported_symbol_fences WHERE status IN ('ACTIVE','PREPARING'))*8))",
                "-s.dispatch_cursor+15,16)",
            ),
            (
                "SELECT count(*) FROM public.supported_symbol_fences f WHERE f.status IN ('ACTIVE','PREPARING') AND f.base<j.base)*8",
                "CASE j.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
            ),
        ),
    )
    _replace_function(
        "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)",
        (
            (
                (
                    "ready_count<>(SELECT count(*)*8 FROM public.supported_symbol_fences WHERE status='ACTIVE')"
                ),
                "ready_count<>16",
            ),
        ),
    )
    _replace_function_one_of(
        "seed_indicator_build_jobs()",
        (
            "FROM (SELECT base FROM public.supported_symbol_fences WHERE status IN ('ACTIVE','PREPARING')) b",
            "FROM (SELECT base FROM public.supported_symbol_fences WHERE status='ACTIVE') b",
        ),
        "FROM (VALUES('BTC'),('ETH')) b(base)",
    )
    op.execute("SELECT public.begin_indicator_source_maintenance()")
    for table, constraint in reversed(_PAIR_TABLES):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {table}_supported_symbol_fk")
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {table}_usdt_quote")
        op.execute(f"""ALTER TABLE public.{table} ADD CONSTRAINT {constraint}
          CHECK(quote='USDT' AND base IN ('BTC','ETH'))""")
    op.execute("DROP POLICY user_totp_platform_bootstrap_check ON public.user_totp")
    op.execute("DROP TABLE public.platform_memberships")
    op.execute("DROP TABLE IF EXISTS public.catalog_protocol_heartbeats")
    op.execute("DROP TABLE IF EXISTS public.supported_symbol_timeframe_readiness")
    op.execute("DROP TABLE IF EXISTS public.supported_symbol_effects")
    op.execute("DROP TABLE IF EXISTS public.supported_symbol_maintenance_proofs")
    op.execute("DROP TABLE IF EXISTS public.supported_symbol_readiness")
    op.execute("DROP TABLE IF EXISTS public.supported_symbol_constraint_snapshots")
    op.execute("DROP TABLE IF EXISTS public.supported_symbol_commands")
    op.execute("DROP TABLE public.supported_symbol_fences")
    op.execute("DROP TABLE public.supported_symbol_events")
    op.execute("DROP FUNCTION public.supported_symbol_projection_consistent()")
    op.execute("DROP TABLE public.supported_symbol_catalog_control")
    op.execute("DROP FUNCTION IF EXISTS public.supported_symbol_revision_consistent()")
    op.execute("DROP TABLE public.supported_symbol_registry")
    op.execute("""DO $$ DECLARE definition text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='public.audit_events'::regclass
          AND conname='audit_events_action_shape';
      ALTER TABLE public.audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE public.audit_events ADD CONSTRAINT audit_events_action_shape '
        ||CASE WHEN position('CATALOG_MUTATIONS_ENABLED' IN definition)>0
          THEN regexp_replace(definition,
            'WHEN ''CATALOG_MUTATIONS_ENABLED''.*ELSE false','ELSE false')
          ELSE regexp_replace(definition,
            'WHEN ''PLATFORM_OWNER_BOOTSTRAPPED''.*ELSE false','ELSE false') END
        ||' NOT VALID';
    END $$""")
