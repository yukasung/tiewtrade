"""Atomic fenced READY and sanitized numeric failure publication."""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

IDENTITY = "p_epoch uuid,p_fence bigint,p_owner uuid,p_job uuid,p_generation uuid,p_token uuid"
ARGS = "uuid,bigint,uuid,uuid,uuid,uuid"
CALL = "p_epoch,p_fence,p_owner,p_job,p_generation,p_token"

PUBLICATION = f"""CREATE FUNCTION publish_indicator_generation({IDENTITY},p_numeric boolean)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE g public.indicator_generations%ROWTYPE; j public.indicator_build_jobs%ROWTYPE;
  seconds integer; expected_count integer; observed timestamptz;
BEGIN
  -- Fresh publication transaction: never request the source guard after slot/job locks.
  PERFORM 1 FROM public.indicator_source_guard WHERE id=1 FOR UPDATE;
  PERFORM 1 FROM public.indicator_rollout_control WHERE id=1 FOR SHARE;
  PERFORM public.lock_indicator_build_identity({CALL});
  SELECT * INTO STRICT j FROM public.indicator_build_jobs WHERE id=p_job;
  IF j.current_candidate IS DISTINCT FROM p_generation OR p_numeric IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_STAGING_INVALID';
  END IF;
  SELECT * INTO STRICT g FROM public.indicator_generations WHERE id=p_generation;
  IF g.status='EXPIRED' THEN
    PERFORM public.complete_indicator_build_attempt(p_job,'SOURCE_CHANGED');
    RETURN 'SUPERSEDED';
  END IF;
  -- Identity remains required even for terminal cleanup of an expired attempt.
  BEGIN
    PERFORM public.require_indicator_build_claim({CALL});
  EXCEPTION WHEN SQLSTATE 'TT014' THEN
    PERFORM public.complete_indicator_build_attempt(p_job,'OWNERSHIP_LOST');
    RETURN 'SUPERSEDED';
  END;
  IF NOT EXISTS(SELECT 1 FROM public.indicator_source_guard s WHERE s.id=1
      AND s.epoch=g.source_epoch AND s.journal_floor<=g.source_fence
      AND s.revision>=g.source_fence)
    OR NOT public.indicator_source_triggers_valid()
    OR EXISTS(SELECT 1 FROM public.indicator_source_changes e
      WHERE e.epoch=g.source_epoch AND e.revision>g.source_fence
      AND (e.kind='RESET' OR (e.source=g.source AND e.base=g.base AND e.quote=g.quote
        AND e.timeframe=g.timeframe AND e.open_at>=g.calculation_start
        AND e.open_at<g.calculation_end))) THEN
    PERFORM public.complete_indicator_build_attempt(p_job,'SOURCE_CHANGED');
    RETURN 'SUPERSEDED';
  END IF;
  IF g.codec_version<>1 OR g.formula_version<>'indicators-v1'
    OR g.source<>j.source OR g.base<>j.base OR g.quote<>j.quote OR g.timeframe<>j.timeframe
    OR g.formula_version<>j.formula_version
    OR EXISTS(SELECT 1 FROM public.indicator_heads h
      JOIN public.indicator_generations old ON old.id=h.generation_id
      WHERE h.source=g.source AND h.base=g.base AND h.quote=g.quote
        AND h.timeframe=g.timeframe AND h.formula_version=g.formula_version
        AND old.candidate_sequence>=g.candidate_sequence) THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_PUBLICATION_INVALID';
  END IF;
  IF NOT p_numeric THEN
    seconds:=CASE g.timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300
      WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END;
    expected_count:=ceil(extract(epoch FROM (g.calculation_end-g.calculation_start))
      /(seconds*1000))::integer+1;
    IF g.dataset_revision IS NULL OR g.checkpoint_count<>expected_count
      OR (SELECT count(*) FROM public.indicator_checkpoints
        WHERE generation_id=p_generation)<>expected_count
      OR EXISTS(SELECT 1 FROM generate_series(0,expected_count-1) n
        WHERE NOT EXISTS(SELECT 1 FROM public.indicator_checkpoints cp
          WHERE cp.generation_id=p_generation AND cp.next_open_at=least(
            g.calculation_start+make_interval(secs=>seconds*1000)*n,g.calculation_end))) THEN
      RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_SCAN_INCOMPLETE';
    END IF;
  END IF;
  -- Recheck the immutable deadline after proof/count work, before any terminal writes.
  BEGIN
    PERFORM public.require_indicator_build_claim({CALL});
  EXCEPTION WHEN SQLSTATE 'TT014' THEN
    PERFORM public.complete_indicator_build_attempt(p_job,'OWNERSHIP_LOST');
    RETURN 'SUPERSEDED';
  END;
  observed:=clock_timestamp();
  IF p_numeric THEN
    UPDATE public.indicator_generations SET status='FAILED_NUMERIC',
      failure_code='INDICATOR_NUMERIC_ERROR',failed_at=observed WHERE id=p_generation;
    UPDATE public.indicator_build_jobs SET status='FAILED_NUMERIC',claim_token=NULL,
      lease_until=NULL,retry_not_before=NULL,failure_category='NUMERIC',
      failure_reason='INDICATOR_NUMERIC_ERROR',failed_at=observed,
      failed_calculation_key=jsonb_build_object('source',g.source,'base',g.base,
        'quote',g.quote,'timeframe',g.timeframe,'formula_version',g.formula_version,
        'start',to_char(g.calculation_start,'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
        'end',to_char(g.calculation_end,'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')),
      failed_input_version=jsonb_build_object('epoch',g.source_epoch,'fence',g.source_fence)
      WHERE id=p_job;
    -- Failed payloads stay invisible; bounded GC owns their eventual deletion.
  ELSE
    UPDATE public.indicator_generations SET status='READY',prepared_at=observed
      WHERE id=p_generation;
    INSERT INTO public.indicator_heads(source,base,quote,timeframe,formula_version,generation_id)
      VALUES(g.source,g.base,g.quote,g.timeframe,g.formula_version,g.id)
      ON CONFLICT(source,base,quote,timeframe,formula_version)
      DO UPDATE SET generation_id=EXCLUDED.generation_id;
    UPDATE public.indicator_build_jobs SET status='READY',claim_token=NULL,lease_until=NULL,
      attempts_used=0,cycle_id=gen_random_uuid(),retry_not_before=NULL,
      failure_category=NULL,failure_reason=NULL,failed_at=NULL,
      failed_calculation_key=NULL,failed_input_version=NULL,recovery_event_revision=NULL
      WHERE id=p_job;
  END IF;
  UPDATE public.indicator_build_slot SET state='IDLE',owner_instance=NULL,
    owner_backend_pid=NULL,job_id=NULL,generation_id=NULL,claim_token=NULL,
    lease_until=NULL,attempt_deadline=NULL,last_heartbeat=NULL WHERE id=1;
  RETURN CASE WHEN p_numeric THEN 'FAILED_NUMERIC' ELSE 'READY' END;
END $$"""


def upgrade() -> None:
    op.execute(PUBLICATION)
    op.execute(f"REVOKE ALL ON FUNCTION publish_indicator_generation({ARGS},boolean) FROM PUBLIC")
    for name, numeric in (("ready", "false"), ("numeric_failure", "true")):
        signature = f"publish_indicator_{name}({ARGS})"
        op.execute(f"""CREATE FUNCTION publish_indicator_{name}({IDENTITY}) RETURNS text
          LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
          SELECT public.publish_indicator_generation({CALL},{numeric}) $$""")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO tiewtrade_indicator_builder")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM indicator_build_slot WHERE state<>'IDLE')
        OR EXISTS(SELECT 1 FROM indicator_rollout_control WHERE mode NOT IN ('LEGACY','PAUSED'))
      THEN RAISE EXCEPTION 'INDICATOR_DOWNGRADE_NOT_DRAINED'; END IF;
    END $$""")
    for name in ("ready", "numeric_failure"):
        op.execute(f"DROP FUNCTION publish_indicator_{name}({ARGS})")
    op.execute(f"DROP FUNCTION publish_indicator_generation({ARGS},boolean)")
