"""ADR-002 expand schema and opt-in committed source journal.

Expansion leaves legacy candle writers working. Only the migrator may activate
strict proof after the documented source-writer drain. Runtime metadata writes
remain denied until the builder's fenced functions are implemented.
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

TABLES = (
    "indicator_rollout_control",
    "indicator_source_guard",
    "indicator_source_changes",
    "indicator_build_slot",
    "indicator_build_jobs",
    "indicator_generations",
    "indicator_checkpoints",
    "indicator_heads",
    "indicator_retry_requests",
)

SCHEMA = (
    """CREATE TABLE indicator_rollout_control (
      id smallint PRIMARY KEY CHECK(id=1),
      mode text NOT NULL DEFAULT 'LEGACY' CHECK(mode IN
      ('LEGACY','PREPARING','PREPARED','PAUSED')),
      rollout_epoch uuid NOT NULL DEFAULT gen_random_uuid(),
      active_cursor_format smallint NOT NULL DEFAULT 1 CHECK(active_cursor_format IN
      (1,2)),
      codec_version integer NOT NULL DEFAULT 1 CHECK(codec_version>0),
      protocol_version integer NOT NULL DEFAULT 1 CHECK(protocol_version>0),
      source_proof_state text NOT NULL DEFAULT 'PENDING' CHECK(source_proof_state IN
      ('PENDING','READY')),
      retention_policy text NOT NULL DEFAULT 'GRACE' CHECK(retention_policy IN
      ('LEGACY','GRACE')),
      last_v2_issue_cutoff timestamptz)""",
    "INSERT INTO indicator_rollout_control(id) VALUES(1)",
    """CREATE TABLE indicator_source_guard (
      id smallint PRIMARY KEY CHECK(id=1), epoch uuid NOT NULL DEFAULT gen_random_uuid(),
      revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
      journal_floor bigint NOT NULL DEFAULT 0 CHECK(journal_floor BETWEEN 0 AND revision),
      scope_owner_xid xid8, scope_kind text CHECK(scope_kind IN ('WRITE','MAINTENANCE')),
      protected_relations oid[] NOT NULL DEFAULT '{}',
      CHECK((scope_owner_xid IS NULL)=(scope_kind IS NULL)))""",
    "INSERT INTO indicator_source_guard(id) VALUES(1)",
    """CREATE TABLE indicator_source_changes (
      epoch uuid NOT NULL, revision bigint NOT NULL CHECK(revision>0),
      source text NOT NULL CHECK(source='primary_spot'),
      base text NOT NULL, quote text NOT NULL, timeframe text NOT NULL,
      open_at timestamptz NOT NULL, kind text NOT NULL CHECK(kind IN
      ('WRITE','DELETE','RESET')),
      PRIMARY KEY(epoch,revision,source,base,quote,timeframe,open_at,kind))""",
    """CREATE INDEX indicator_source_changes_proof ON indicator_source_changes
       (epoch,source,base,quote,timeframe,revision,open_at)""",
    """CREATE TABLE indicator_build_slot (
      id smallint PRIMARY KEY CHECK(id=1), slot_epoch uuid NOT NULL DEFAULT
      gen_random_uuid(),
      fence bigint NOT NULL DEFAULT 0 CHECK(fence>=0), owner_instance uuid,
      owner_backend_pid integer, job_id uuid, generation_id uuid, claim_token uuid,
      lease_until timestamptz, attempt_deadline timestamptz, last_heartbeat timestamptz,
      state text NOT NULL DEFAULT 'IDLE' CHECK(state IN ('IDLE','RUNNING')),
      dispatch_round bigint NOT NULL DEFAULT 1 CHECK(dispatch_round>0),
      CHECK((state='IDLE' AND owner_instance IS NULL AND owner_backend_pid IS NULL
        AND job_id IS NULL AND generation_id IS NULL AND claim_token IS NULL
        AND lease_until IS NULL AND attempt_deadline IS NULL AND last_heartbeat IS NULL)
        OR (state='RUNNING' AND owner_instance IS NOT NULL AND owner_backend_pid IS NOT
        NULL
        AND job_id IS NOT NULL AND generation_id IS NOT NULL AND claim_token IS NOT NULL
        AND lease_until IS NOT NULL AND attempt_deadline IS NOT NULL AND last_heartbeat IS
        NOT NULL)))""",
    "INSERT INTO indicator_build_slot(id) VALUES(1)",
    """CREATE TABLE indicator_build_jobs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source text NOT NULL
      CHECK(source='primary_spot'),
      base text NOT NULL CHECK(base IN ('BTC','ETH','SOL','XRP','DOGE')), quote text NOT
      NULL CHECK(quote='USDT'),
      timeframe text NOT NULL CHECK(timeframe IN ('1m','5m','15m','1h','4h','1d')),
      formula_version text NOT NULL, UNIQUE(source,base,quote,timeframe,formula_version),
      status text NOT NULL DEFAULT 'QUEUED' CHECK(status IN ('QUEUED','RUNNING','READY',
        'FAILED_NUMERIC','FAILED_TRANSIENT','FAILED_OPERATIONAL','FAILED_SUPERSEDED')),
      current_candidate uuid, generation_sequence bigint NOT NULL DEFAULT 0
      CHECK(generation_sequence>=0),
      claim_token uuid, lease_until timestamptz, build_rollout_epoch uuid,
      desired_start timestamptz, desired_end timestamptz,
      failed_calculation_key jsonb, failed_input_version jsonb,
      first_eligible_at timestamptz, availability_deadline timestamptz,
      attempts_used smallint NOT NULL DEFAULT 0 CHECK(attempts_used BETWEEN 0 AND 3),
      cycle_id uuid NOT NULL DEFAULT gen_random_uuid(), retry_not_before timestamptz,
      last_served_round bigint NOT NULL DEFAULT 0 CHECK(last_served_round>=0),
      deadline_missed_at timestamptz, failure_category text,
      failure_reason text, failed_at timestamptz, recovery_event_revision bigint,
      CHECK((desired_start IS NULL AND desired_end IS NULL) OR
        (desired_start IS NOT NULL AND desired_end IS NOT NULL AND
        desired_start<desired_end
         AND desired_end-desired_start<=interval '365 days')),
      CHECK((claim_token IS NULL)=(lease_until IS NULL)))""",
    """CREATE TABLE indicator_generations (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(), job_id uuid NOT NULL REFERENCES
      indicator_build_jobs(id),
      source text NOT NULL CHECK(source='primary_spot'),
      base text NOT NULL CHECK(base IN ('BTC','ETH','SOL','XRP','DOGE')), quote text NOT
      NULL CHECK(quote='USDT'),
      timeframe text NOT NULL CHECK(timeframe IN ('1m','5m','15m','1h','4h','1d')),
      formula_version text NOT NULL, calculation_start timestamptz NOT NULL,
      calculation_end timestamptz NOT NULL, as_of timestamptz NOT NULL,
      source_epoch uuid NOT NULL, source_fence bigint NOT NULL CHECK(source_fence>=0),
      dataset_revision text CHECK(dataset_revision ~ '^[0-9a-f]{64}$'),
      checkpoint_count integer NOT NULL DEFAULT 0 CHECK(checkpoint_count BETWEEN 0 AND
      527),
      codec_version integer NOT NULL CHECK(codec_version>0), build_rollout_epoch uuid NOT
      NULL,
      candidate_sequence bigint NOT NULL CHECK(candidate_sequence>0), claim_token uuid NOT
      NULL,
      status text NOT NULL DEFAULT 'STAGING' CHECK(status IN
      ('STAGING','READY','FAILED_NUMERIC','SUPERSEDED','EXPIRED')),
      expires_at timestamptz NOT NULL, prepared_at timestamptz,
      failure_code text CHECK(failure_code='INDICATOR_NUMERIC_ERROR'), failed_at
      timestamptz,
      UNIQUE(job_id,candidate_sequence),
      CHECK(calculation_start<calculation_end AND calculation_end<=as_of
        AND calculation_end-calculation_start<=interval '365 days'),
      CHECK(expires_at=as_of+interval '6 hours 10 minutes'),
      CHECK(status<>'READY' OR (dataset_revision IS NOT NULL AND checkpoint_count>0
        AND prepared_at IS NOT NULL AND failure_code IS NULL)),
      CHECK(status<>'FAILED_NUMERIC' OR (failure_code IS NOT NULL AND failed_at IS NOT
      NULL)))""",
    """ALTER TABLE indicator_build_jobs ADD CONSTRAINT indicator_job_candidate_fk
       FOREIGN KEY(current_candidate) REFERENCES indicator_generations(id) DEFERRABLE
       INITIALLY DEFERRED""",
    """CREATE TABLE indicator_checkpoints (
      generation_id uuid NOT NULL REFERENCES indicator_generations(id) ON DELETE CASCADE,
      next_open_at timestamptz NOT NULL, payload jsonb NOT NULL,
      PRIMARY KEY(generation_id,next_open_at), CHECK(jsonb_typeof(payload)='object'),
      CHECK(octet_length(payload::text)<=16384))""",
    """CREATE TABLE indicator_heads (
      source text NOT NULL, base text NOT NULL, quote text NOT NULL, timeframe text NOT
      NULL,
      formula_version text NOT NULL, generation_id uuid NOT NULL REFERENCES
      indicator_generations(id),
      PRIMARY KEY(source,base,quote,timeframe,formula_version))""",
    """CREATE TABLE indicator_retry_requests (
      request_id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES
      indicator_build_jobs(id),
      cycle_id uuid NOT NULL, result text NOT NULL CHECK(result IN ('QUEUED','REJECTED')),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
    """CREATE VIEW indicator_ready_generations AS SELECT g.id,g.source,g.base,g.quote,g.timeframe,
       g.formula_version,g.calculation_start,g.calculation_end,g.as_of,g.source_epoch,g.source_fence,
       g.dataset_revision,g.checkpoint_count,g.codec_version,g.expires_at,g.prepared_at
       FROM indicator_generations g
       WHERE g.status='READY'""",
    """CREATE VIEW indicator_ready_checkpoints AS SELECT c.* FROM indicator_checkpoints c
       JOIN indicator_generations g ON g.id=c.generation_id WHERE g.status='READY'""",
    """CREATE VIEW indicator_ready_heads AS SELECT h.* FROM indicator_heads h
       JOIN indicator_generations g ON g.id=h.generation_id WHERE g.status='READY'""",
    """CREATE VIEW indicator_numeric_failures AS SELECT
g.id,g.source,g.base,g.quote,g.timeframe,
g.formula_version,g.calculation_start,g.calculation_end,g.as_of,g.source_epoch,g.source_fence,
g.codec_version,g.candidate_sequence,g.expires_at,g.failure_code,j.desired_start,j.desired_end
       FROM indicator_generations g JOIN indicator_build_jobs j ON
       j.current_candidate=g.id
       WHERE g.status='FAILED_NUMERIC'""",
)

FUNCTIONS = (
    """CREATE FUNCTION indicator_source_triggers_valid() RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      -- pg_partition_tree takes relation locks, which would invert the
      -- publication guard -> maintenance relation lock order. Read catalogs only.
      WITH RECURSIVE root(relid) AS (
        SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname='market_candles' AND c.relkind='p'
      ), partitions(relid) AS (
        SELECT relid FROM root
        UNION
        SELECT i.inhrelid FROM pg_inherits i JOIN partitions p ON i.inhparent=p.relid
      )
      SELECT EXISTS(SELECT 1 FROM root) AND NOT EXISTS (
        SELECT 1 FROM partitions p
        CROSS JOIN (VALUES
          ('indicator_source_statement',62,
            'public.indicator_source_statement_guard()'),
          ('indicator_source_rows',29,'public.indicator_source_row_journal()')
        ) expected(name,kind,handler)
        WHERE NOT EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgrelid=p.relid
          AND t.tgname=expected.name AND t.tgtype=expected.kind
          AND t.tgfoid=to_regprocedure(expected.handler) AND t.tgenabled='O'
          AND NOT t.tgisinternal AND t.tgnargs=0 AND t.tgqual IS NULL
          AND t.tgattr=''::int2vector))
    $$""",
    """CREATE FUNCTION begin_indicator_source_write() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      LOCK TABLE public.market_candles IN ROW EXCLUSIVE MODE;
      PERFORM 1 FROM public.indicator_source_guard WHERE id=1 FOR UPDATE;
      UPDATE public.indicator_source_guard SET scope_owner_xid=pg_current_xact_id(),
        scope_kind=CASE WHEN scope_owner_xid=pg_current_xact_id() AND
        scope_kind='MAINTENANCE'
          THEN 'MAINTENANCE' ELSE 'WRITE' END WHERE id=1;
    END $$""",
    """CREATE FUNCTION require_indicator_source_write() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
        AND scope_owner_xid=pg_current_xact_id_if_assigned() AND scope_kind IN
        ('WRITE','MAINTENANCE'))
      THEN RAISE EXCEPTION 'SOURCE_WRITE_SCOPE_REQUIRED' USING ERRCODE='TT011'; END IF;
    END $$""",
    """CREATE FUNCTION begin_indicator_source_maintenance() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
        AND scope_owner_xid=pg_current_xact_id_if_assigned() AND scope_kind='WRITE')
      THEN RAISE EXCEPTION 'SOURCE_MAINTENANCE_SCOPE_REQUIRED' USING ERRCODE='TT012'; END
      IF;
      LOCK TABLE public.market_candles IN ACCESS EXCLUSIVE MODE;
      PERFORM 1 FROM public.indicator_source_guard WHERE id=1 FOR UPDATE;
      IF EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
        AND scope_owner_xid=pg_current_xact_id_if_assigned() AND scope_kind='MAINTENANCE')
      THEN RETURN; END IF;
      UPDATE public.indicator_source_guard SET scope_owner_xid=pg_current_xact_id(),
        scope_kind='MAINTENANCE',epoch=gen_random_uuid(),revision=0,journal_floor=0 WHERE
        id=1;
      UPDATE public.indicator_generations SET status='EXPIRED' WHERE status IN
      ('READY','STAGING','FAILED_NUMERIC');
      DELETE FROM public.indicator_heads;
    END $$""",
    """CREATE FUNCTION indicator_source_statement_guard() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    BEGIN
      PERFORM public.require_indicator_source_write();
      IF TG_OP='TRUNCATE' AND NOT EXISTS(SELECT 1 FROM public.indicator_source_guard
        WHERE id=1 AND scope_owner_xid=pg_current_xact_id_if_assigned() AND
        scope_kind='MAINTENANCE')
      THEN RAISE EXCEPTION 'SOURCE_MAINTENANCE_SCOPE_REQUIRED' USING ERRCODE='TT012'; END
      IF;
      IF EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1 AND
      revision=9223372036854775807)
      THEN RAISE EXCEPTION 'SOURCE_REVISION_EXHAUSTED' USING ERRCODE='TT013'; END IF;
      UPDATE public.indicator_source_guard SET revision=revision+1 WHERE id=1;
      RETURN NULL;
    END $$""",
    """CREATE FUNCTION indicator_source_row_journal() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE g public.indicator_source_guard%ROWTYPE;
    BEGIN
      PERFORM public.require_indicator_source_write();
      IF TG_OP='UPDATE' AND
      ROW(OLD.source,OLD.base,OLD.quote,OLD.timeframe,OLD.open_at,OLD.end_at,
OLD.open,OLD.high,OLD.low,OLD.close,OLD.volume,OLD.finality,OLD.observed_at,OLD.fetch_started_at)
        IS NOT DISTINCT FROM
        ROW(NEW.source,NEW.base,NEW.quote,NEW.timeframe,NEW.open_at,NEW.end_at,
NEW.open,NEW.high,NEW.low,NEW.close,NEW.volume,NEW.finality,NEW.observed_at,NEW.fetch_started_at)
      THEN RETURN NULL; END IF;
      SELECT * INTO STRICT g FROM public.indicator_source_guard WHERE id=1;
      IF TG_OP IN ('DELETE','UPDATE') THEN
        INSERT INTO public.indicator_source_changes VALUES(g.epoch,g.revision,OLD.source,
          OLD.base,OLD.quote,OLD.timeframe,OLD.open_at,'DELETE') ON CONFLICT DO NOTHING;
      END IF;
      IF TG_OP IN ('INSERT','UPDATE') THEN
        INSERT INTO public.indicator_source_changes VALUES(g.epoch,g.revision,NEW.source,
          NEW.base,NEW.quote,NEW.timeframe,NEW.open_at,'WRITE') ON CONFLICT DO NOTHING;
      END IF;
      RETURN NULL;
    END $$""",
    # DDL identifiers come only from PostgreSQL's partition catalog. This is an
    # invoker function restricted to the migrator, never a dynamic-SQL definer.
    """CREATE FUNCTION install_indicator_source_partitions() RETURNS void
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    DECLARE p record;
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.indicator_rollout_control
        WHERE id=1 AND source_proof_state='READY') AND NOT EXISTS(
          SELECT 1 FROM public.indicator_source_guard WHERE id=1
            AND scope_owner_xid=pg_current_xact_id_if_assigned()
            AND scope_kind='MAINTENANCE') THEN RETURN; END IF;
      FOR p IN SELECT relid FROM pg_partition_tree('public.market_candles'::regclass)
      LOOP
        IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=p.relid
          AND tgname='indicator_source_statement' AND NOT tgisinternal) THEN
          IF NOT EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
            AND scope_owner_xid=pg_current_xact_id_if_assigned() AND
            scope_kind='MAINTENANCE')
          THEN RAISE EXCEPTION 'SOURCE_MAINTENANCE_SCOPE_REQUIRED' USING ERRCODE='TT012';
          END IF;
          EXECUTE format('CREATE TRIGGER indicator_source_statement BEFORE INSERT OR
          UPDATE OR DELETE OR TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION
          public.indicator_source_statement_guard()',p.relid);
        END IF;
      END LOOP;
      UPDATE public.indicator_source_guard SET protected_relations=ARRAY(
        SELECT relid::oid FROM pg_partition_tree('public.market_candles'::regclass))
        WHERE id=1 AND protected_relations IS DISTINCT FROM ARRAY(
          SELECT relid::oid FROM pg_partition_tree('public.market_candles'::regclass));
    END $$""",
    """CREATE FUNCTION protect_indicator_source_partitions() RETURNS void
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.indicator_rollout_control
        WHERE id=1 AND source_proof_state='READY') THEN RETURN; END IF;
      IF EXISTS(SELECT 1 FROM pg_event_trigger_ddl_commands() d
        CROSS JOIN public.indicator_source_guard g WHERE
        d.objid=ANY(g.protected_relations))
        AND NOT EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
          AND scope_owner_xid=pg_current_xact_id_if_assigned() AND
          scope_kind='MAINTENANCE')
      THEN RAISE EXCEPTION 'SOURCE_MAINTENANCE_SCOPE_REQUIRED' USING ERRCODE='TT012'; END
      IF;
      PERFORM public.install_indicator_source_partitions();
      IF NOT public.indicator_source_triggers_valid() THEN
        UPDATE public.indicator_rollout_control SET source_proof_state='PENDING' WHERE id=1;
      END IF;
    END $$""",
    """CREATE FUNCTION activate_indicator_source_proof() RETURNS void
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    DECLARE p record;
    BEGIN
      IF (SELECT count(*) FROM pg_event_trigger WHERE evtenabled='O'
          AND ((evtname='tiewtrade_protect_partitions' AND evtevent='ddl_command_end')
            OR (evtname='tiewtrade_indicator_source_drop' AND evtevent='sql_drop')
            OR (evtname='tiewtrade_indicator_trigger_ddl' AND evtevent='ddl_command_end'))) <> 3
      THEN RAISE EXCEPTION 'SOURCE_BOOTSTRAP_REQUIRED' USING ERRCODE='TT013'; END IF;
      LOCK TABLE public.market_candles IN ACCESS EXCLUSIVE MODE;
      PERFORM 1 FROM public.indicator_source_guard WHERE id=1 FOR UPDATE;
      PERFORM 1 FROM public.indicator_rollout_control WHERE id=1 FOR UPDATE;
      IF NOT EXISTS(SELECT 1 FROM public.indicator_rollout_control WHERE id=1 AND
      mode='LEGACY')
      THEN RAISE EXCEPTION 'SOURCE_ACTIVATION_STAGE_REQUIRED' USING ERRCODE='TT013'; END
      IF;
      IF EXISTS(SELECT 1 FROM public.indicator_rollout_control WHERE id=1 AND
      source_proof_state='READY')
        AND public.indicator_source_triggers_valid()
      THEN RETURN; END IF;
      PERFORM public.begin_indicator_source_maintenance();
      UPDATE public.indicator_rollout_control SET source_proof_state='PENDING' WHERE id=1;
      FOR p IN SELECT relid FROM pg_partition_tree('public.market_candles'::regclass) LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS indicator_source_statement ON %s',p.relid);
      END LOOP;
      DROP TRIGGER IF EXISTS indicator_source_rows ON public.market_candles;
      CREATE TRIGGER indicator_source_rows AFTER INSERT OR UPDATE OR DELETE ON
      public.market_candles
        FOR EACH ROW EXECUTE FUNCTION public.indicator_source_row_journal();
      -- Trigger-installation is performed by the DDL event hook; this initial
      -- explicit call uses the same catalog loop without event-command lookup.
      PERFORM public.install_indicator_source_partitions();
      IF NOT public.indicator_source_triggers_valid()
      THEN RAISE EXCEPTION 'SOURCE_TRIGGER_COVERAGE_REQUIRED' USING ERRCODE='TT013'; END IF;
      UPDATE public.indicator_rollout_control SET
      source_proof_state='READY',retention_policy='GRACE' WHERE id=1;
    END $$""",
    """CREATE OR REPLACE FUNCTION tiewtrade_protect_partitions_on_ddl() RETURNS event_trigger
    LANGUAGE plpgsql AS $$ BEGIN
      IF to_regprocedure('public.tiewtrade_protect_all_partitions()') IS NOT NULL THEN
        PERFORM public.tiewtrade_protect_all_partitions(); END IF;
      IF to_regprocedure('public.protect_indicator_source_partitions()') IS NOT NULL THEN
        PERFORM public.protect_indicator_source_partitions(); END IF;
    END $$""",
    """CREATE OR REPLACE FUNCTION tiewtrade_indicator_source_on_trigger_ddl()
    RETURNS event_trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF to_regclass('public.indicator_source_guard') IS NULL THEN RETURN; END IF;
      IF NOT EXISTS(SELECT 1 FROM public.indicator_rollout_control
        WHERE id=1 AND source_proof_state='READY') THEN RETURN; END IF;
      IF EXISTS(SELECT 1 FROM pg_event_trigger_ddl_commands() d
        JOIN pg_trigger t ON d.classid='pg_trigger'::regclass AND d.objid=t.oid
        CROSS JOIN public.indicator_source_guard g
        WHERE t.tgrelid=ANY(g.protected_relations)
          AND t.tgname IN ('indicator_source_rows','indicator_source_statement')) THEN
        IF NOT EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
          AND scope_owner_xid=pg_current_xact_id_if_assigned() AND scope_kind='MAINTENANCE')
        THEN RAISE EXCEPTION 'SOURCE_MAINTENANCE_SCOPE_REQUIRED' USING ERRCODE='TT012'; END IF;
        IF NOT public.indicator_source_triggers_valid() THEN
          UPDATE public.indicator_rollout_control SET source_proof_state='PENDING' WHERE id=1;
        END IF;
      END IF;
    END $$""",
    """CREATE OR REPLACE FUNCTION tiewtrade_indicator_source_on_drop() RETURNS event_trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF to_regclass('public.indicator_source_guard') IS NULL THEN RETURN; END IF;
      IF NOT EXISTS(SELECT 1 FROM public.indicator_rollout_control
        WHERE id=1 AND source_proof_state='READY') THEN RETURN; END IF;
      IF (EXISTS(SELECT 1 FROM pg_event_trigger_dropped_objects() d
        CROSS JOIN public.indicator_source_guard g WHERE
        d.classid='pg_class'::regclass AND d.objid=ANY(g.protected_relations))
        OR NOT public.indicator_source_triggers_valid())
        AND NOT EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
          AND scope_owner_xid=pg_current_xact_id_if_assigned() AND
          scope_kind='MAINTENANCE')
      THEN RAISE EXCEPTION 'SOURCE_MAINTENANCE_SCOPE_REQUIRED' USING ERRCODE='TT012'; END
      IF;
      IF NOT public.indicator_source_triggers_valid() THEN
        UPDATE public.indicator_rollout_control SET source_proof_state='PENDING' WHERE id=1;
      END IF;
    END $$""",
)


def upgrade() -> None:
    for statement in SCHEMA + FUNCTIONS:
        op.execute(statement)
    for name in (
        "indicator_source_triggers_valid",
        "begin_indicator_source_write",
        "require_indicator_source_write",
        "begin_indicator_source_maintenance",
        "indicator_source_statement_guard",
        "indicator_source_row_journal",
        "protect_indicator_source_partitions",
        "install_indicator_source_partitions",
        "activate_indicator_source_proof",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {name}() FROM PUBLIC")
    for name in ("begin_indicator_source_write", "require_indicator_source_write"):
        op.execute(f"GRANT EXECUTE ON FUNCTION {name}() TO tiewtrade_market_data")
    for table in (
        "indicator_source_guard",
        "indicator_source_changes",
        "indicator_rollout_control",
    ):
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api,tiewtrade_indicator_builder")
    op.execute("GRANT SELECT ON indicator_rollout_control TO tiewtrade_market_data")
    op.execute("GRANT SELECT ON market_candles TO tiewtrade_indicator_builder")
    op.execute("""GRANT EXECUTE ON FUNCTION indicator_source_triggers_valid()
               TO tiewtrade_api,tiewtrade_indicator_builder""")
    for view in (
        "indicator_ready_generations",
        "indicator_ready_checkpoints",
        "indicator_ready_heads",
        "indicator_numeric_failures",
    ):
        op.execute(f"GRANT SELECT ON {view} TO tiewtrade_api")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM indicator_rollout_control WHERE mode NOT IN
      ('LEGACY','PAUSED')
        OR (last_v2_issue_cutoff IS NOT NULL AND
        clock_timestamp()<last_v2_issue_cutoff+interval '6 hours'))
        OR EXISTS(SELECT 1 FROM indicator_build_slot WHERE state<>'IDLE')
      THEN RAISE EXCEPTION 'INDICATOR_DOWNGRADE_NOT_DRAINED'; END IF;
    END $$""")
    op.execute("SELECT begin_indicator_source_maintenance()")
    # Keep the bootstrap event trigger alive, restoring its pre-0015 behavior.
    op.execute("""CREATE OR REPLACE FUNCTION tiewtrade_protect_partitions_on_ddl()
      RETURNS event_trigger LANGUAGE plpgsql AS $$ BEGIN
      IF to_regprocedure('public.tiewtrade_protect_all_partitions()') IS NOT NULL THEN
        PERFORM public.tiewtrade_protect_all_partitions(); END IF; END $$""")
    op.execute("""DO $$ DECLARE p record; BEGIN
      FOR p IN SELECT relid FROM pg_partition_tree('public.market_candles'::regclass) LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS indicator_source_statement ON %s',p.relid);
      END LOOP; END $$""")
    op.execute("DROP TRIGGER IF EXISTS indicator_source_rows ON market_candles")
    for view in (
        "indicator_numeric_failures",
        "indicator_ready_heads",
        "indicator_ready_checkpoints",
        "indicator_ready_generations",
    ):
        op.execute(f"DROP VIEW {view}")
    op.execute("ALTER TABLE indicator_build_jobs DROP CONSTRAINT indicator_job_candidate_fk")
    for name in (
        "activate_indicator_source_proof",
        "protect_indicator_source_partitions",
        "install_indicator_source_partitions",
        "indicator_source_row_journal",
        "indicator_source_statement_guard",
        "begin_indicator_source_maintenance",
        "require_indicator_source_write",
        "begin_indicator_source_write",
        "indicator_source_triggers_valid",
    ):
        op.execute(f"DROP FUNCTION {name}()")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("REVOKE SELECT ON market_candles FROM tiewtrade_indicator_builder")
