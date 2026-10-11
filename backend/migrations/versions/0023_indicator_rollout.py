"""Migrator-only rollout CAS, replay safety and fresh-head activation gate."""

from pathlib import Path

from alembic import op
from alembic.util import load_python_file

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def required_privileges() -> tuple[tuple[str, str, str], ...]:
    """Required F-11 grants, reusing signatures from their owning migrations."""
    tables = [
        (role, name, "SELECT")
        for role in ("tiewtrade_api", "tiewtrade_indicator_builder")
        for name in (
            "indicator_source_guard",
            "indicator_source_changes",
            "indicator_rollout_control",
        )
    ]
    tables += [
        ("tiewtrade_market_data", "indicator_rollout_control", "SELECT"),
        ("tiewtrade_indicator_builder", "market_candles", "SELECT"),
    ]
    tables += [
        ("tiewtrade_api", name, "SELECT")
        for name in (
            "market_candles",
            "indicator_ready_generations",
            "indicator_ready_checkpoints",
            "indicator_ready_heads",
            "indicator_numeric_failures",
        )
    ]
    functions = [
        (role, "indicator_source_triggers_valid()", "EXECUTE")
        for role in ("tiewtrade_api", "tiewtrade_indicator_builder")
    ]
    functions += [
        ("tiewtrade_market_data", name + "()", "EXECUTE")
        for name in ("begin_indicator_source_write", "require_indicator_source_write")
    ]
    root = Path(__file__).parent
    claims = load_python_file(root, "0016_indicator_build_claims.py")
    staging = load_python_file(root, "0017_indicator_staging.py")
    publication = load_python_file(root, "0018_indicator_publication.py")
    signatures = list(claims.RUNTIME_FUNCTIONS) + [name for name, _ in staging.FUNCTIONS]
    signatures += [
        f"publish_indicator_{name}({publication.ARGS})" for name in ("ready", "numeric_failure")
    ]
    signatures += [
        "coalesce_indicator_build_jobs()",
        "retry_indicator_build_job(uuid,uuid)",
        "gc_indicator_data()",
    ]
    functions += [("tiewtrade_indicator_builder", name, "EXECUTE") for name in signatures]
    return tuple(tables + functions)


def privilege_predicate() -> str:
    # Static migration-owned identifiers only. No runtime/user SQL interpolation.
    checks = []
    for role, name, privilege in required_privileges():
        kind = "function" if privilege == "EXECUTE" else "table"
        resolver = "to_regprocedure" if kind == "function" else "to_regclass"
        checks.append(
            f"coalesce(has_{kind}_privilege('{role}',"
            f"{resolver}('public.{name}'),'{privilege}'),false)"
        )
    return " AND ".join(checks)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE indicator_rollout_mode AS ENUM ('LEGACY','PREPARING','PREPARED','PAUSED')"
    )
    op.execute("""ALTER TABLE indicator_rollout_control
      ADD COLUMN transition_from_mode public.indicator_rollout_mode,
      ADD COLUMN transition_from_epoch uuid,
      ADD COLUMN transition_target public.indicator_rollout_mode""")
    op.execute(
        """CREATE FUNCTION transition_indicator_rollout(
      p_mode public.indicator_rollout_mode,p_epoch uuid,p_target public.indicator_rollout_mode)
      RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE c public.indicator_rollout_control%ROWTYPE;
      guard public.indicator_source_guard%ROWTYPE; observed timestamptz; ready_count integer;
    BEGIN
      IF p_mode IS NULL OR p_epoch IS NULL OR p_target IS NULL THEN
        RETURN jsonb_build_object('result','REJECTED'); END IF;
      -- Publication lock order. Never obtain relation locks under this guard.
      SELECT * INTO STRICT guard FROM public.indicator_source_guard WHERE id=1 FOR UPDATE;
      SELECT * INTO STRICT c FROM public.indicator_rollout_control WHERE id=1 FOR UPDATE;
      IF c.transition_from_mode=p_mode AND c.transition_from_epoch=p_epoch
        AND c.transition_target=p_target AND c.mode=p_target::text THEN
        RETURN jsonb_build_object('result','ALREADY_APPLIED','epoch',c.rollout_epoch,
          'cutoff',c.last_v2_issue_cutoff); END IF;
      IF c.mode<>p_mode::text OR c.rollout_epoch<>p_epoch THEN
        RETURN jsonb_build_object('result','STALE'); END IF;
      IF NOT ((p_mode='LEGACY' AND p_target='PREPARING')
        OR (p_mode='PREPARING' AND p_target IN ('PREPARED','PAUSED'))
        OR (p_mode='PREPARED' AND p_target='PAUSED')
        OR (p_mode='PAUSED' AND p_target='PREPARING')) THEN
        RETURN jsonb_build_object('result','REJECTED'); END IF;
      PERFORM 1 FROM public.indicator_build_slot WHERE id=1 FOR UPDATE;
      IF NOT EXISTS(SELECT 1 FROM public.indicator_build_slot WHERE id=1 AND state='IDLE')
        OR EXISTS(SELECT 1 FROM public.indicator_build_jobs WHERE status='RUNNING')
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_locks WHERE locktype='advisory'
          AND classid=711 AND objid=1 AND objsubid=2 AND granted
          AND database=(SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database()))
        THEN RETURN jsonb_build_object('result','NOT_DRAINED'); END IF;
      -- Pausing must remain possible when proof/configuration is broken.
      IF p_target<>'PAUSED' AND (c.protocol_version<>1 OR c.codec_version<>1
        OR c.source_proof_state<>'READY' OR c.retention_policy<>'GRACE'
        OR NOT public.indicator_source_triggers_valid()
        OR NOT (__REQUIRED_PRIVILEGES__)) THEN
        RETURN jsonb_build_object('result','POLICY_UNSUPPORTED'); END IF;
      observed:=clock_timestamp();
      IF p_target='PREPARED' THEN
        SELECT count(*) INTO ready_count FROM public.indicator_build_jobs j
          JOIN public.indicator_heads h USING(source,base,quote,timeframe,formula_version)
          JOIN public.indicator_generations g ON g.id=h.generation_id
          WHERE j.formula_version='indicators-v1' AND g.status='READY'
            AND g.source=j.source AND g.base=j.base AND g.quote=j.quote
            AND g.timeframe=j.timeframe AND g.formula_version=j.formula_version
            AND g.codec_version=1 AND g.dataset_revision IS NOT NULL
            AND (SELECT count(*) FROM public.indicator_checkpoints cp
              WHERE cp.generation_id=g.id)=g.checkpoint_count
            AND EXISTS(SELECT 1 FROM public.indicator_checkpoints cp
              WHERE cp.generation_id=g.id AND cp.next_open_at=g.calculation_start)
            AND EXISTS(SELECT 1 FROM public.indicator_checkpoints cp
              WHERE cp.generation_id=g.id AND cp.next_open_at=g.calculation_end)
            AND g.expires_at>observed AND g.as_of<=observed
            AND g.as_of>=observed-interval '600 seconds'
            AND g.source_epoch=guard.epoch
            AND g.source_fence BETWEEN guard.journal_floor AND guard.revision
            AND (j.failed_calculation_key IS NULL OR g.candidate_sequence>=j.generation_sequence)
            AND NOT EXISTS(SELECT 1 FROM public.indicator_source_changes e
              WHERE e.epoch=guard.epoch AND e.revision>g.source_fence
                AND (e.kind='RESET' OR (e.source=g.source AND e.base=g.base AND e.quote=g.quote
                  AND e.timeframe=g.timeframe AND e.open_at>=g.calculation_start
                  AND e.open_at<g.calculation_end)));
        IF ready_count<>30 THEN RETURN jsonb_build_object('result','HEADS_NOT_READY'); END IF;
      END IF;
      UPDATE public.indicator_rollout_control SET mode=p_target::text,
        rollout_epoch=CASE WHEN p_mode='LEGACY' THEN rollout_epoch ELSE gen_random_uuid() END,
        active_cursor_format=CASE WHEN p_target='PREPARED' THEN 2 ELSE active_cursor_format END,
        last_v2_issue_cutoff=CASE WHEN p_target='PAUSED' AND p_mode='PREPARED'
          THEN observed ELSE last_v2_issue_cutoff END,
        transition_from_mode=p_mode,transition_from_epoch=p_epoch,transition_target=p_target
        WHERE id=1 RETURNING * INTO c;
      RETURN jsonb_build_object('result','APPLIED','epoch',c.rollout_epoch,
        'cutoff',c.last_v2_issue_cutoff);
    END $$""".replace("__REQUIRED_PRIVILEGES__", privilege_predicate())
    )
    signature = "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)"
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    # The migrator owns the function; no runtime grant is added.


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.indicator_rollout_control WHERE mode NOT IN
        ('LEGACY','PAUSED') OR (last_v2_issue_cutoff IS NOT NULL AND
          clock_timestamp()<last_v2_issue_cutoff+interval '6 hours'))
        OR EXISTS(SELECT 1 FROM public.indicator_build_slot WHERE state<>'IDLE')
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_locks WHERE locktype='advisory'
          AND classid=711 AND objid=1 AND objsubid=2 AND granted
          AND database=(SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database()))
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_stat_activity WHERE datname=current_database()
          AND pid<>pg_backend_pid() AND usename IN
            ('tiewtrade_api','tiewtrade_market_data','tiewtrade_indicator_builder'))
      THEN RAISE EXCEPTION 'INDICATOR_DOWNGRADE_NOT_DRAINED'; END IF;
    END $$""")
    op.execute(
        "DROP FUNCTION transition_indicator_rollout"
        "(indicator_rollout_mode,uuid,indicator_rollout_mode)"
    )
    op.execute("""ALTER TABLE indicator_rollout_control DROP COLUMN transition_from_mode,
      DROP COLUMN transition_from_epoch,DROP COLUMN transition_target""")
    op.execute("DROP TYPE indicator_rollout_mode")
