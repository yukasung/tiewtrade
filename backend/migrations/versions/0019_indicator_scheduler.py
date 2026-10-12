"""DB-clock coalescing, refresh eligibility and evidence-based terminal recovery."""

from pathlib import Path

from alembic import op
from alembic.util import load_python_file

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

# Preserve the exact prior definitions for downgrade; amend only the terminal
# boundary. Publication already enters with the source guard before slot/job.
PREVIOUS = dict(load_python_file(Path(__file__).parent, "0016_indicator_build_claims.py").FUNCTIONS)
PREVIOUS.update(
    dict(load_python_file(Path(__file__).parent, "0017_indicator_staging.py").FUNCTIONS)
)
COMPLETE = "complete_indicator_build_attempt(uuid,text)"
RELEASE = "release_indicator_build_claim(uuid,bigint,uuid,uuid,uuid,uuid,text)"
REAP = "reap_indicator_build_slot(uuid,uuid,bigint)"
SEED = "seed_indicator_build_jobs()"
INITIALIZE = "initialize_indicator_staging(uuid,bigint,uuid,uuid,uuid,uuid,timestamptz,uuid,bigint)"

BOUNDS = """CREATE FUNCTION indicator_calculation_bounds(p_timeframe text,p_as_of timestamptz)
RETURNS TABLE(calculation_start timestamptz,calculation_end timestamptz)
LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE width interval;
BEGIN
  width:=make_interval(secs=>CASE p_timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300
    WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400 END);
  IF width IS NULL OR NOT isfinite(p_as_of) THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_BOUNDS_INVALID';
  END IF;
  calculation_start:=date_bin(width,p_as_of-interval '365 days','1970-01-01 UTC');
  IF calculation_start<p_as_of-interval '365 days' THEN
    calculation_start:=calculation_start+width;
  END IF;
  calculation_end:=date_bin(width,p_as_of,'1970-01-01 UTC');
  RETURN NEXT;
END $$"""


def replacement(signature: str, old: str, new: str) -> str:
    statement = PREVIOUS[signature]
    assert statement.count(old) == 1
    return statement.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1).replace(old, new)


SCHEDULE = """CREATE FUNCTION coalesce_indicator_build_jobs() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE c public.indicator_rollout_control%ROWTYPE;
  s public.indicator_source_guard%ROWTYPE; j public.indicator_build_jobs%ROWTYPE;
  h public.indicator_generations%ROWTYPE; observed timestamptz;
  lo timestamptz; hi timestamptz; valid_head boolean;
  event_revision bigint; changed integer:=0; next_status text;
  new_cycle boolean; eligible timestamptz; deadline timestamptz;
BEGIN
  -- No candle relation is accessed here. Match publication's guard-first order.
  SELECT * INTO STRICT s FROM public.indicator_source_guard WHERE id=1 FOR SHARE;
  SELECT * INTO STRICT c FROM public.indicator_rollout_control WHERE id=1 FOR SHARE;
  IF c.mode NOT IN ('PREPARING','PREPARED') OR c.source_proof_state<>'READY'
    OR c.retention_policy<>'GRACE' THEN RETURN 0; END IF;
  IF c.codec_version<>1 OR c.protocol_version<>1 THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_PROTOCOL_UNSUPPORTED';
  END IF;
  IF NOT public.indicator_source_triggers_valid() THEN
    RAISE EXCEPTION USING ERRCODE='TT013',MESSAGE='INDICATOR_SOURCE_PROOF_UNAVAILABLE';
  END IF;
  PERFORM public.seed_indicator_build_jobs();
  observed:=clock_timestamp();
  FOR j IN SELECT * FROM public.indicator_build_jobs
    WHERE formula_version='indicators-v1' ORDER BY id FOR UPDATE LOOP
    SELECT calculation_start,calculation_end INTO STRICT lo,hi
      FROM public.indicator_calculation_bounds(j.timeframe,observed);
    j.desired_start:=lo; j.desired_end:=hi;
    next_status:=j.status; new_cycle:=false;
    eligible:=j.first_eligible_at; deadline:=j.availability_deadline;
    event_revision:=j.recovery_event_revision;
    IF j.status='READY' THEN
      SELECT g.* INTO h FROM public.indicator_heads head
        JOIN public.indicator_generations g ON g.id=head.generation_id
        WHERE head.source=j.source AND head.base=j.base AND head.quote=j.quote
          AND head.timeframe=j.timeframe AND head.formula_version=j.formula_version;
      valid_head:=FOUND AND h.status='READY' AND h.expires_at>observed
        AND h.codec_version=c.codec_version AND h.source_epoch=s.epoch
        AND h.source_fence BETWEEN s.journal_floor AND s.revision
        AND NOT EXISTS(SELECT 1 FROM public.indicator_source_changes e
          WHERE e.epoch=s.epoch AND e.revision>h.source_fence AND (e.kind='RESET' OR
            (e.source=j.source AND e.base=j.base AND e.quote=j.quote
              AND e.timeframe=j.timeframe AND e.open_at>=h.calculation_start
              AND e.open_at<h.calculation_end)));
      IF NOT valid_head OR observed>=h.as_of+interval '470 seconds' THEN
        next_status:='QUEUED';
        eligible:=CASE WHEN valid_head THEN h.as_of+interval '470 seconds' ELSE observed END;
        deadline:=CASE WHEN valid_head THEN h.as_of+interval '600 seconds'
          ELSE observed+interval '600 seconds' END;
      END IF;
    ELSIF j.status='FAILED_NUMERIC' THEN
      IF public.indicator_numeric_candidate_allowed(j) THEN
        next_status:='QUEUED'; new_cycle:=true;
      END IF;
    ELSIF j.status IN ('FAILED_TRANSIENT','FAILED_SUPERSEDED') THEN
      -- Persist a qualifying event during cooldown, so journal GC cannot lose it.
      IF j.failure_source_epoch=s.epoch AND j.failure_source_fence>=s.journal_floor THEN
        SELECT greatest(event_revision,max(e.revision)) INTO event_revision
          FROM public.indicator_source_changes e WHERE e.epoch=s.epoch
          AND e.revision>j.failure_source_fence AND (e.kind='RESET' OR
            (e.source=j.source AND e.base=j.base AND e.quote=j.quote
              AND e.timeframe=j.timeframe AND e.open_at>=lo AND e.open_at<hi));
      END IF;
      IF event_revision IS NOT NULL AND observed>=j.failed_at+interval '600 seconds' THEN
        next_status:='QUEUED'; new_cycle:=true;
      END IF;
    END IF;
    UPDATE public.indicator_build_jobs SET desired_start=lo,desired_end=hi,
      status=next_status,first_eligible_at=eligible,availability_deadline=deadline,
      deadline_missed_at=CASE WHEN j.status='READY' AND next_status='QUEUED'
        THEN CASE WHEN observed>deadline THEN observed END
        WHEN next_status<>'READY' AND observed>deadline
          THEN coalesce(j.deadline_missed_at,observed) ELSE j.deadline_missed_at END,
      attempts_used=CASE WHEN new_cycle THEN 0 ELSE j.attempts_used END,
      cycle_id=CASE WHEN new_cycle THEN gen_random_uuid() ELSE j.cycle_id END,
      retry_not_before=CASE WHEN next_status='QUEUED' AND j.status<>'QUEUED'
        THEN observed ELSE j.retry_not_before END,
      recovery_event_revision=CASE WHEN new_cycle THEN NULL ELSE event_revision END,
      failure_category=CASE WHEN new_cycle THEN NULL ELSE j.failure_category END,
      failure_reason=CASE WHEN new_cycle THEN NULL ELSE j.failure_reason END,
      failed_at=CASE WHEN new_cycle THEN NULL ELSE j.failed_at END
      WHERE id=j.id;
    IF next_status<>j.status THEN changed:=changed+1; END IF;
  END LOOP;
  RETURN changed;
END $$"""


def upgrade() -> None:
    op.execute(BOUNDS)
    op.execute("REVOKE ALL ON FUNCTION indicator_calculation_bounds(text,timestamptz) FROM PUBLIC")
    seed = replacement(
        SEED,
        """bounds.floor_start+CASE WHEN bounds.floor_start<observed-interval '365 days'
              THEN make_interval(secs=>t.seconds) ELSE interval '0' END,
            date_bin(make_interval(secs=>t.seconds),observed,'1970-01-01 UTC'::timestamptz),""",
        "bounds.calculation_start,bounds.calculation_end,",
    )
    seed = seed.replace(
        """CROSS JOIN LATERAL (SELECT date_bin(make_interval(secs=>t.seconds),
            observed-interval '365 days','1970-01-01 UTC'::timestamptz) AS floor_start) bounds""",
        "CROSS JOIN LATERAL public.indicator_calculation_bounds(t.timeframe,observed) bounds",
    )
    op.execute(seed)
    op.execute(
        replacement(
            INITIALIZE,
            "lo:=date_bin(make_interval(secs=>seconds),p_as_of-interval '365 days',"
            """'1970-01-01 UTC');
          IF lo<p_as_of-interval '365 days' THEN lo:=lo+make_interval(secs=>seconds); END IF;
          hi:=date_bin(make_interval(secs=>seconds),p_as_of,'1970-01-01 UTC');""",
            """SELECT calculation_start,calculation_end INTO STRICT lo,hi
            FROM public.indicator_calculation_bounds(j.timeframe,p_as_of);""",
        )
    )
    op.execute("""ALTER TABLE indicator_build_jobs
      ADD COLUMN failure_source_epoch uuid,
      ADD COLUMN failure_source_fence bigint CHECK(failure_source_fence>=0)""")
    op.execute(
        replacement(
            COMPLETE,
            "failed_at=CASE WHEN next_status<>'QUEUED' THEN observed ELSE NULL END,",
            """failed_at=CASE WHEN next_status<>'QUEUED' THEN observed ELSE NULL END,
            failure_source_epoch=(SELECT epoch FROM public.indicator_source_guard WHERE id=1),
            failure_source_fence=(SELECT revision FROM public.indicator_source_guard WHERE id=1),
            recovery_event_revision=NULL,""",
        )
    )
    op.execute(
        replacement(
            RELEASE,
            "PERFORM public.lock_indicator_build_identity",
            """PERFORM 1 FROM public.indicator_source_guard WHERE id=1 FOR SHARE;
          PERFORM public.lock_indicator_build_identity""",
        )
    )
    op.execute(
        replacement(
            REAP,
            "PERFORM 1 FROM public.indicator_rollout_control",
            """PERFORM 1 FROM public.indicator_source_guard WHERE id=1 FOR SHARE;
            PERFORM 1 FROM public.indicator_rollout_control""",
        )
    )
    op.execute(SCHEDULE)
    op.execute("REVOKE ALL ON FUNCTION coalesce_indicator_build_jobs() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION coalesce_indicator_build_jobs() TO tiewtrade_indicator_builder"
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM indicator_build_slot WHERE state<>'IDLE')
        OR EXISTS(SELECT 1 FROM indicator_rollout_control WHERE mode NOT IN ('LEGACY','PAUSED'))
      THEN RAISE EXCEPTION 'INDICATOR_DOWNGRADE_NOT_DRAINED'; END IF;
    END $$""")
    op.execute("DROP FUNCTION coalesce_indicator_build_jobs()")
    for signature in (COMPLETE, RELEASE, REAP, SEED, INITIALIZE):
        op.execute(PREVIOUS[signature].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
    op.execute("""ALTER TABLE indicator_build_jobs
      DROP COLUMN failure_source_epoch, DROP COLUMN failure_source_fence""")
    op.execute("DROP FUNCTION IF EXISTS indicator_calculation_bounds(text,timestamptz)")
