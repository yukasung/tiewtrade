"""Fenced STAGING initialization, ordered checkpoints and completed scan metadata."""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

IDENTITY = "p_epoch uuid,p_fence bigint,p_owner uuid,p_job uuid,p_generation uuid,p_token uuid"
ARGS = "uuid,bigint,uuid,uuid,uuid,uuid"
CHECK = (
    "PERFORM public.require_indicator_build_claim(p_epoch,p_fence,p_owner,p_job,"
    "p_generation,p_token);"
)
FUNCTIONS = (
    (
        f"initialize_indicator_staging({ARGS},timestamptz,uuid,bigint)",
        f"""CREATE FUNCTION initialize_indicator_staging({IDENTITY},p_as_of timestamptz,
          p_source_epoch uuid,p_source_fence bigint) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
        DECLARE j public.indicator_build_jobs%ROWTYPE; seconds integer;
          lo timestamptz; hi timestamptz;
        BEGIN
          {CHECK}
          SELECT * INTO STRICT j FROM public.indicator_build_jobs WHERE id=p_job;
          IF j.current_candidate IS NOT NULL OR j.formula_version<>'indicators-v1'
            OR p_as_of IS NULL OR NOT isfinite(p_as_of) OR p_as_of>clock_timestamp()
            OR p_as_of<(SELECT attempt_deadline-interval '120 seconds'
              FROM public.indicator_build_slot WHERE id=1)
            OR p_source_epoch IS NULL OR p_source_fence IS NULL OR p_source_fence<0
            OR NOT EXISTS(SELECT 1 FROM public.indicator_source_guard WHERE id=1
              AND epoch=p_source_epoch AND revision>=p_source_fence
              AND journal_floor<=p_source_fence)
            OR NOT public.indicator_source_triggers_valid() THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_STAGING_INVALID';
          END IF;
          seconds:=CASE j.timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300
            WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END;
          lo:=date_bin(make_interval(secs=>seconds),p_as_of-interval '365 days','1970-01-01 UTC');
          IF lo<p_as_of-interval '365 days' THEN lo:=lo+make_interval(secs=>seconds); END IF;
          hi:=date_bin(make_interval(secs=>seconds),p_as_of,'1970-01-01 UTC');
          INSERT INTO public.indicator_generations(id,job_id,source,base,quote,timeframe,
            formula_version,calculation_start,calculation_end,as_of,source_epoch,source_fence,
            codec_version,build_rollout_epoch,candidate_sequence,claim_token,expires_at)
          VALUES(p_generation,p_job,j.source,j.base,j.quote,j.timeframe,j.formula_version,
            lo,hi,p_as_of,p_source_epoch,p_source_fence,1,j.build_rollout_epoch,
            j.generation_sequence,p_token,p_as_of+interval '6 hours 10 minutes');
          UPDATE public.indicator_build_jobs SET current_candidate=p_generation WHERE id=p_job;
          {CHECK}
        END $$""",
    ),
    (
        f"append_indicator_checkpoint({ARGS},timestamptz,jsonb)",
        f"""CREATE FUNCTION append_indicator_checkpoint({IDENTITY},p_next timestamptz,
          p_payload jsonb) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
        DECLARE g public.indicator_generations%ROWTYPE; seconds integer; expected timestamptz;
        BEGIN
          {CHECK}
          SELECT * INTO STRICT g FROM public.indicator_generations WHERE id=p_generation FOR UPDATE;
          seconds:=CASE g.timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300
            WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END;
          expected:=least(g.calculation_start+make_interval(secs=>seconds*1000)*g.checkpoint_count,
            g.calculation_end);
          IF g.status<>'STAGING' OR g.dataset_revision IS NOT NULL
            OR g.checkpoint_count>=527 OR p_next IS DISTINCT FROM expected
            OR EXISTS(SELECT 1 FROM public.indicator_checkpoints
              WHERE generation_id=p_generation AND next_open_at=g.calculation_end)
            OR jsonb_typeof(p_payload) IS DISTINCT FROM 'object'
            OR octet_length(p_payload::text)>16384
            OR p_payload->>'generation_id' IS DISTINCT FROM p_generation::text
            OR p_payload->>'source' IS DISTINCT FROM g.source
            OR p_payload->>'base' IS DISTINCT FROM g.base
            OR p_payload->>'quote' IS DISTINCT FROM g.quote
            OR p_payload->>'timeframe' IS DISTINCT FROM g.timeframe
            OR p_payload->>'formula_version' IS DISTINCT FROM g.formula_version
            OR p_payload->>'version' IS DISTINCT FROM '1'
            OR p_payload->>'as_of' IS DISTINCT FROM
              to_char(g.as_of,'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
            OR p_payload->>'start' IS DISTINCT FROM
              to_char(g.calculation_start,'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
            OR p_payload->>'end' IS DISTINCT FROM
              to_char(g.calculation_end,'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
            OR p_payload->>'next_open_at' IS DISTINCT FROM
              to_char(p_next,'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"') THEN
            RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_CHECKPOINT_INVALID';
          END IF;
          INSERT INTO public.indicator_checkpoints VALUES(p_generation,p_next,p_payload);
          UPDATE public.indicator_generations SET checkpoint_count=checkpoint_count+1
            WHERE id=p_generation;
          {CHECK}
        END $$""",
    ),
    (
        f"seal_indicator_staging({ARGS},text)",
        f"""CREATE FUNCTION seal_indicator_staging({IDENTITY},p_digest text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE g public.indicator_generations%ROWTYPE;
        BEGIN
          {CHECK}
          SELECT * INTO STRICT g FROM public.indicator_generations WHERE id=p_generation FOR UPDATE;
          IF g.status<>'STAGING' OR g.dataset_revision IS NOT NULL OR p_digest IS NULL
            OR p_digest !~ '^[0-9a-f]{{64}}$'
            OR NOT EXISTS(SELECT 1 FROM public.indicator_checkpoints
              WHERE generation_id=p_generation AND next_open_at=g.calculation_end) THEN
            RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_SCAN_INCOMPLETE';
          END IF;
          UPDATE public.indicator_generations SET dataset_revision=p_digest WHERE id=p_generation;
          {CHECK}
        END $$""",
    ),
)


def upgrade() -> None:
    for signature, statement in FUNCTIONS:
        op.execute(statement)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO tiewtrade_indicator_builder")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM indicator_build_slot WHERE state<>'IDLE')
        OR EXISTS(SELECT 1 FROM indicator_rollout_control WHERE mode NOT IN ('LEGACY','PAUSED'))
      THEN RAISE EXCEPTION 'INDICATOR_DOWNGRADE_NOT_DRAINED'; END IF;
    END $$""")
    for signature, _ in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION {signature}")
