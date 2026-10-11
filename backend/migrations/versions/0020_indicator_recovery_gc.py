"""Restricted idempotent manual recovery and bounded derived/source-proof GC."""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

RETRY = """CREATE FUNCTION retry_indicator_build_job(p_job uuid,p_request uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE j public.indicator_build_jobs%ROWTYPE; r public.indicator_retry_requests%ROWTYPE;
  observed timestamptz; answer text; next_cycle uuid; inserted integer;
BEGIN
  IF p_job IS NULL OR p_request IS NULL THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_RETRY_INVALID';
  END IF;
  -- Serialize duplicates, including a request reused against another job.
  INSERT INTO public.indicator_retry_requests(request_id,job_id,cycle_id,result)
    VALUES(p_request,p_job,gen_random_uuid(),'REJECTED') ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS inserted=ROW_COUNT;
  SELECT * INTO STRICT r FROM public.indicator_retry_requests WHERE request_id=p_request FOR UPDATE;
  IF r.job_id<>p_job THEN RETURN 'REJECTED'; END IF;
  -- An existing committed result is immutable, even after a later cycle/failure.
  IF inserted=0 THEN RETURN r.result; END IF;
  SELECT * INTO STRICT j FROM public.indicator_build_jobs WHERE id=p_job FOR UPDATE;
  observed:=clock_timestamp();
  next_cycle:=j.cycle_id;
  answer:='REJECTED';
  IF j.status IN ('FAILED_TRANSIENT','FAILED_SUPERSEDED','FAILED_OPERATIONAL')
    AND j.failed_at IS NOT NULL AND observed>=j.failed_at+interval '600 seconds' THEN
    answer:='QUEUED'; next_cycle:=gen_random_uuid();
    UPDATE public.indicator_build_jobs SET status='QUEUED',attempts_used=0,
      cycle_id=next_cycle,retry_not_before=observed,failed_at=NULL,
      failure_category=NULL,failure_reason=NULL,recovery_event_revision=NULL
      WHERE id=p_job;
  END IF;
  UPDATE public.indicator_retry_requests SET result=answer,cycle_id=next_cycle
    WHERE request_id=p_request;
  RETURN answer;
END $$"""

# Every mutation locks guard -> jobs -> generations. No slot or candles are touched.
# Deleting a proof prefix and advancing its floor is one transaction; revisions
# may have multiple events, so a partially deleted revision is included in floor.
GC = """CREATE FUNCTION gc_indicator_data() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE s public.indicator_source_guard%ROWTYPE; observed timestamptz:=clock_timestamp();
  boundary bigint; removed integer:=0; checkpoints integer:=0; generations integer:=0;
  pressure boolean; g record;
BEGIN
  SELECT * INTO STRICT s FROM public.indicator_source_guard WHERE id=1 FOR UPDATE;
  PERFORM 1 FROM public.indicator_build_jobs ORDER BY id FOR UPDATE;
  pressure:=(pg_total_relation_size('public.indicator_checkpoints')+
    pg_total_relation_size('public.indicator_generations')+
    pg_total_relation_size('public.indicator_heads')+
    pg_total_relation_size('public.indicator_retry_requests'))>3221225472;
  WITH victims AS (
    SELECT c.ctid,c.revision FROM public.indicator_source_changes c
    WHERE c.epoch<>s.epoch OR c.created_at<=observed-interval '6 hours 15 minutes'
      OR (SELECT count(*) FROM public.indicator_source_changes)>2000000
    ORDER BY c.epoch=s.epoch,c.revision LIMIT 10000
  ), deleted AS (
    DELETE FROM public.indicator_source_changes c USING victims v WHERE c.ctid=v.ctid
      RETURNING c.epoch,c.revision
  ) SELECT count(*),max(revision) FILTER(WHERE epoch=s.epoch)
    INTO removed,boundary FROM deleted;
  IF boundary IS NOT NULL THEN
    -- Invalidate before forgetting proof; job numeric identity remains durable.
    UPDATE public.indicator_generations SET status='EXPIRED'
      WHERE source_epoch=s.epoch AND source_fence<boundary
        AND status IN ('READY','STAGING','FAILED_NUMERIC');
    UPDATE public.indicator_source_guard SET journal_floor=greatest(journal_floor,boundary)
      WHERE id=1;
  END IF;
  FOR g IN SELECT id,status,expires_at FROM public.indicator_generations
    WHERE status IN ('SUPERSEDED','EXPIRED') OR expires_at<=observed
      OR (status='FAILED_NUMERIC' AND EXISTS(SELECT 1 FROM public.indicator_checkpoints c
        WHERE c.generation_id=indicator_generations.id))
      OR (status='STAGING' AND NOT EXISTS(SELECT 1 FROM public.indicator_build_jobs j
        WHERE j.current_candidate=indicator_generations.id AND j.status='RUNNING'
          AND j.lease_until>observed))
      OR pressure
    ORDER BY expires_at,id LIMIT 1000 FOR UPDATE LOOP
    IF g.status<>'FAILED_NUMERIC' OR g.expires_at<=observed OR pressure THEN
      UPDATE public.indicator_generations SET status='EXPIRED' WHERE id=g.id;
      DELETE FROM public.indicator_heads WHERE generation_id=g.id;
    END IF;
    WITH victim AS (SELECT next_open_at FROM public.indicator_checkpoints
      WHERE generation_id=g.id ORDER BY next_open_at LIMIT 1000-checkpoints), deleted AS (
      DELETE FROM public.indicator_checkpoints c USING victim v
      WHERE c.generation_id=g.id AND c.next_open_at=v.next_open_at RETURNING 1)
      SELECT checkpoints+count(*) INTO checkpoints FROM deleted;
    -- A live/orphan candidate must remain available to fenced cleanup/reap.
    IF NOT EXISTS(SELECT 1 FROM public.indicator_checkpoints WHERE generation_id=g.id)
      AND (g.status<>'FAILED_NUMERIC' OR g.expires_at<=observed OR pressure)
      AND NOT EXISTS(SELECT 1 FROM public.indicator_build_jobs
        WHERE current_candidate=g.id AND status='RUNNING') THEN
      UPDATE public.indicator_build_jobs SET current_candidate=NULL WHERE current_candidate=g.id;
      DELETE FROM public.indicator_generations WHERE id=g.id;
      generations:=generations+1;
    END IF;
    EXIT WHEN checkpoints>=1000;
  END LOOP;
  RETURN jsonb_build_object('journal',removed,'checkpoints',checkpoints,'generations',generations);
END $$"""


def upgrade() -> None:
    op.execute(
        "ALTER TABLE indicator_source_changes ADD COLUMN created_at timestamptz "
        "NOT NULL DEFAULT clock_timestamp()"
    )
    op.execute(RETRY)
    op.execute(GC)
    for name in ("retry_indicator_build_job(uuid,uuid)", "gc_indicator_data()"):
        op.execute(f"REVOKE ALL ON FUNCTION {name} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {name} TO tiewtrade_indicator_builder")


def downgrade() -> None:
    op.execute("DROP FUNCTION gc_indicator_data()")
    op.execute("DROP FUNCTION retry_indicator_build_job(uuid,uuid)")
    op.execute("ALTER TABLE indicator_source_changes DROP COLUMN created_at")
