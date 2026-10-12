"""Fenced builder claims and a single pinned-session build slot (ADR-002).

No rollout activation or publication is performed by this migration. Claims
reserve a generation identity; its STAGING row is initialized from the source
snapshot in the subsequent builder phase.
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

IDENTITY_ARGS = "uuid,bigint,uuid,uuid,uuid,uuid"
FUNCTIONS = (
    (
        "indicator_build_lock_held()",
        """CREATE FUNCTION indicator_build_lock_held() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_locks l
            WHERE l.locktype='advisory' AND l.pid=pg_backend_pid() AND l.granted
            AND l.mode='ExclusiveLock' AND l.classid=711 AND l.objid=1 AND l.objsubid=2
            AND l.database=(SELECT oid FROM pg_catalog.pg_database
              WHERE datname=current_database()))
        $$""",
    ),
    (
        "try_indicator_build_lock()",
        """CREATE FUNCTION try_indicator_build_lock() RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        BEGIN
          IF public.indicator_build_lock_held() THEN
            RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_LOCK_REENTRANT';
          END IF;
          RETURN pg_try_advisory_lock(711,1);
        END $$""",
    ),
    (
        "unlock_indicator_build_lock()",
        """CREATE FUNCTION unlock_indicator_build_lock() RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE released boolean;
        BEGIN
          IF EXISTS(SELECT 1 FROM public.indicator_build_slot s WHERE s.id=1
            AND s.state='RUNNING' AND s.owner_backend_pid=pg_backend_pid()) THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_OWNER_NOT_RELEASED';
          END IF;
          released:=pg_advisory_unlock(711,1);
          RETURN released AND NOT public.indicator_build_lock_held();
        END $$""",
    ),
    (
        "seed_indicator_build_jobs()",
        """CREATE FUNCTION seed_indicator_build_jobs() RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
        SET TimeZone='UTC' AS $$
        DECLARE c public.indicator_rollout_control%ROWTYPE;
          observed timestamptz:=clock_timestamp(); inserted integer;
        BEGIN
          SELECT * INTO STRICT c FROM public.indicator_rollout_control WHERE id=1 FOR SHARE;
          IF c.mode NOT IN ('PREPARING','PREPARED') OR c.source_proof_state<>'READY'
            OR c.retention_policy<>'GRACE' THEN RETURN 0; END IF;
          IF c.codec_version<>1 OR c.protocol_version<>1 THEN
            RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_PROTOCOL_UNSUPPORTED';
          END IF;
          INSERT INTO public.indicator_build_jobs(source,base,quote,timeframe,formula_version,
            desired_start,desired_end,first_eligible_at,availability_deadline,retry_not_before)
          SELECT 'primary_spot',b.base,'USDT',t.timeframe,'indicators-v1',
            bounds.floor_start+CASE WHEN bounds.floor_start<observed-interval '365 days'
              THEN make_interval(secs=>t.seconds) ELSE interval '0' END,
            date_bin(make_interval(secs=>t.seconds),observed,'1970-01-01 UTC'::timestamptz),
            observed,observed+interval '600 seconds',observed
          FROM (VALUES('BTC'),('DOGE'),('ETH'),('SOL'),('XRP')) b(base)
          CROSS JOIN (VALUES('1m',60),('5m',300),('15m',900),('1h',3600),
            ('4h',14400),('1d',86400)) t(timeframe,seconds)
          CROSS JOIN LATERAL (SELECT date_bin(make_interval(secs=>t.seconds),
            observed-interval '365 days','1970-01-01 UTC'::timestamptz) AS floor_start) bounds
          ON CONFLICT(source,base,quote,timeframe,formula_version) DO NOTHING;
          GET DIAGNOSTICS inserted=ROW_COUNT;
          RETURN inserted;
        END $$""",
    ),
    (
        "indicator_numeric_candidate_allowed(public.indicator_build_jobs)",
        """CREATE FUNCTION indicator_numeric_candidate_allowed(j public.indicator_build_jobs)
          RETURNS boolean LANGUAGE plpgsql STABLE SECURITY DEFINER
          SET search_path=pg_catalog,public AS $$
        DECLARE failed_start timestamptz; failed_end timestamptz;
          failed_epoch uuid; failed_fence bigint; g public.indicator_source_guard%ROWTYPE;
        BEGIN
          IF j.failed_calculation_key IS NULL THEN RETURN true; END IF;
          -- This internal manifest encoding is also used by the subsequent failure writer.
          IF jsonb_typeof(j.failed_calculation_key) IS DISTINCT FROM 'object' THEN
            RETURN false;
          END IF;
          IF (j.failed_calculation_key-'start'-'end') IS DISTINCT FROM jsonb_build_object(
            'source',j.source,'base',j.base,'quote',j.quote,'timeframe',j.timeframe,
            'formula_version',j.formula_version)
            OR jsonb_typeof(j.failed_calculation_key->'start') IS DISTINCT FROM 'string'
            OR jsonb_typeof(j.failed_calculation_key->'end') IS DISTINCT FROM 'string' THEN
            RETURN false;
          END IF;
          BEGIN
            failed_start:=(j.failed_calculation_key->>'start')::timestamptz;
            failed_end:=(j.failed_calculation_key->>'end')::timestamptz;
            IF failed_start>=failed_end OR failed_end-failed_start>interval '365 days'
              OR to_char(failed_start AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')<>j.failed_calculation_key->>'start'
              OR to_char(failed_end AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')<>j.failed_calculation_key->>'end'
              THEN RETURN false; END IF;
            IF failed_start<>j.desired_start OR failed_end<>j.desired_end THEN RETURN true; END IF;
            IF jsonb_typeof(j.failed_input_version) IS DISTINCT FROM 'object' THEN
              RETURN false;
            END IF;
            IF j.failed_input_version- 'epoch'-'fence'<>'{}'::jsonb
              OR jsonb_typeof(j.failed_input_version->'epoch') IS DISTINCT FROM 'string'
              OR jsonb_typeof(j.failed_input_version->'fence') IS DISTINCT FROM 'number'
              THEN RETURN false; END IF;
            failed_epoch:=(j.failed_input_version->>'epoch')::uuid;
            failed_fence:=(j.failed_input_version->>'fence')::bigint;
            IF failed_fence<0 OR failed_epoch::text<>j.failed_input_version->>'epoch' THEN
              RETURN false; END IF;
          EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range
            OR datetime_field_overflow OR invalid_datetime_format THEN RETURN false;
          END;
          SELECT * INTO STRICT g FROM public.indicator_source_guard WHERE id=1;
          IF g.epoch<>failed_epoch OR g.journal_floor>failed_fence OR g.revision<failed_fence
            OR NOT public.indicator_source_triggers_valid() THEN RETURN false; END IF;
          RETURN EXISTS(SELECT 1 FROM public.indicator_source_changes e
            WHERE e.epoch=failed_epoch AND e.revision>failed_fence AND (e.kind='RESET' OR
              (e.source=j.source AND e.base=j.base AND e.quote=j.quote
                AND e.timeframe=j.timeframe AND e.open_at>=failed_start AND e.open_at<failed_end)));
        END $$""",
    ),
    (
        "claim_indicator_build_job(uuid)",
        """CREATE FUNCTION claim_indicator_build_job(p_owner uuid) RETURNS TABLE(
          job_id uuid,generation_id uuid,claim_token uuid,slot_epoch uuid,fence bigint,
          owner_backend_pid integer,attempt_deadline timestamptz,lease_until timestamptz,
          source text,base text,quote text,timeframe text,formula_version text,
          candidate_sequence bigint,build_rollout_epoch uuid,codec_version integer,
          dispatch_round bigint)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE c public.indicator_rollout_control%ROWTYPE;
          s public.indicator_build_slot%ROWTYPE; j public.indicator_build_jobs%ROWTYPE;
          observed timestamptz; gen uuid:=gen_random_uuid(); token uuid:=gen_random_uuid();
          chosen integer; pass integer;
        BEGIN
          IF p_owner IS NULL OR NOT public.indicator_build_lock_held() THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_LOCK_REQUIRED';
          END IF;
          SELECT * INTO STRICT c FROM public.indicator_rollout_control WHERE id=1 FOR SHARE;
          IF c.mode NOT IN ('PREPARING','PREPARED') OR c.source_proof_state<>'READY'
            OR c.retention_policy<>'GRACE' THEN RETURN; END IF;
          IF c.codec_version<>1 OR c.protocol_version<>1 THEN
            RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_PROTOCOL_UNSUPPORTED';
          END IF;
          SELECT * INTO STRICT s FROM public.indicator_build_slot WHERE id=1 FOR UPDATE;
          -- An orphan is not permission to resume, even after lease expiry or PID loss.
          IF s.state<>'IDLE' THEN RETURN; END IF;
          observed:=clock_timestamp();
          FOR pass IN 1..2 LOOP
            SELECT eligible.* INTO j FROM public.indicator_build_jobs eligible
            WHERE eligible.status='QUEUED' AND eligible.attempts_used<3
              AND coalesce(eligible.retry_not_before,'-infinity')<=observed
              AND eligible.desired_start IS NOT NULL AND eligible.desired_end IS NOT NULL
              AND eligible.last_served_round<s.dispatch_round
              AND public.indicator_numeric_candidate_allowed(eligible)
            ORDER BY eligible.availability_deadline,
              mod((CASE eligible.base WHEN 'BTC' THEN 0 WHEN 'DOGE' THEN 1
                WHEN 'ETH' THEN 2 WHEN 'SOL' THEN 3 ELSE 4 END)*6+
                (CASE eligible.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1
                WHEN '15m' THEN 2 WHEN '1h' THEN 3 WHEN '4h' THEN 4 ELSE 5 END)
                -s.dispatch_cursor+29,30),eligible.formula_version
            FOR UPDATE SKIP LOCKED LIMIT 1;
            EXIT WHEN FOUND;
            -- A locked, unserved job still owns its place in this round.
            IF pass=2 OR EXISTS(SELECT 1 FROM public.indicator_build_jobs eligible
              WHERE eligible.status='QUEUED' AND eligible.attempts_used<3
                AND coalesce(eligible.retry_not_before,'-infinity')<=observed
                AND eligible.desired_start IS NOT NULL
                AND eligible.last_served_round<s.dispatch_round
                AND public.indicator_numeric_candidate_allowed(eligible))
              OR NOT EXISTS(SELECT 1 FROM public.indicator_build_jobs eligible
                WHERE eligible.status='QUEUED' AND eligible.attempts_used<3
                AND coalesce(eligible.retry_not_before,'-infinity')<=observed
                AND eligible.desired_start IS NOT NULL
                AND public.indicator_numeric_candidate_allowed(eligible)) THEN RETURN; END IF;
            IF s.dispatch_round=9223372036854775807 THEN
              RAISE EXCEPTION USING ERRCODE='TT016',MESSAGE='INDICATOR_ROUND_EXHAUSTED';
            END IF;
            s.dispatch_round:=s.dispatch_round+1;
          END LOOP;
          IF s.fence=9223372036854775807 OR j.generation_sequence=9223372036854775807 THEN
            RAISE EXCEPTION USING ERRCODE='TT016',MESSAGE='INDICATOR_FENCE_EXHAUSTED';
          END IF;
          chosen:=(CASE j.base WHEN 'BTC' THEN 0 WHEN 'DOGE' THEN 1
            WHEN 'ETH' THEN 2 WHEN 'SOL' THEN 3 ELSE 4 END)*6+
            (CASE j.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1 WHEN '15m' THEN 2
             WHEN '1h' THEN 3 WHEN '4h' THEN 4 ELSE 5 END);
          observed:=clock_timestamp();
          UPDATE public.indicator_build_slot target SET state='RUNNING',fence=s.fence+1,
            owner_instance=p_owner,owner_backend_pid=pg_backend_pid(),job_id=j.id,
            generation_id=gen,claim_token=token,lease_until=observed+interval '150 seconds',
            attempt_deadline=observed+interval '120 seconds',last_heartbeat=observed,
            dispatch_round=s.dispatch_round,dispatch_cursor=chosen WHERE target.id=1;
          UPDATE public.indicator_build_jobs target SET status='RUNNING',
            generation_sequence=j.generation_sequence+1,current_candidate=NULL,
            claim_token=token,lease_until=observed+interval '150 seconds',
            build_rollout_epoch=c.rollout_epoch,attempts_used=j.attempts_used+1,
            last_served_round=s.dispatch_round,
            deadline_missed_at=CASE WHEN observed>j.availability_deadline
              THEN coalesce(j.deadline_missed_at,observed) ELSE j.deadline_missed_at END
            WHERE target.id=j.id;
          RETURN QUERY SELECT j.id,gen,token,s.slot_epoch,s.fence+1,pg_backend_pid(),
            observed+interval '120 seconds',observed+interval '150 seconds',
            j.source,j.base,j.quote,j.timeframe,j.formula_version,j.generation_sequence+1,
            c.rollout_epoch,c.codec_version,s.dispatch_round;
        END $$""",
    ),
    (
        f"lock_indicator_build_identity({IDENTITY_ARGS})",
        """CREATE FUNCTION lock_indicator_build_identity(p_epoch uuid,p_fence bigint,
          p_owner uuid,p_job uuid,p_generation uuid,p_token uuid) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE s public.indicator_build_slot%ROWTYPE; j public.indicator_build_jobs%ROWTYPE;
        BEGIN
          IF NOT public.indicator_build_lock_held() THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_LOCK_REQUIRED';
          END IF;
          SELECT * INTO STRICT s FROM public.indicator_build_slot WHERE id=1 FOR UPDATE;
          IF s.state<>'RUNNING' OR s.slot_epoch IS DISTINCT FROM p_epoch
            OR s.fence IS DISTINCT FROM p_fence OR s.owner_instance IS DISTINCT FROM p_owner
            OR s.owner_backend_pid<>pg_backend_pid() OR s.job_id IS DISTINCT FROM p_job
            OR s.generation_id IS DISTINCT FROM p_generation
            OR s.claim_token IS DISTINCT FROM p_token THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
          END IF;
          SELECT * INTO STRICT j FROM public.indicator_build_jobs WHERE id=p_job FOR UPDATE;
          IF j.status<>'RUNNING' OR j.claim_token IS DISTINCT FROM p_token
            OR (j.current_candidate IS NOT NULL AND j.current_candidate<>p_generation) THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
          END IF;
          IF j.current_candidate IS NOT NULL THEN
            PERFORM 1 FROM public.indicator_generations g WHERE g.id=p_generation
              AND g.job_id=p_job AND g.claim_token=p_token
              AND g.candidate_sequence=j.generation_sequence
              AND g.build_rollout_epoch=j.build_rollout_epoch FOR UPDATE;
            IF NOT FOUND THEN
              RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
            END IF;
          END IF;
        END $$""",
    ),
    (
        f"require_indicator_build_claim({IDENTITY_ARGS})",
        """CREATE FUNCTION require_indicator_build_claim(p_epoch uuid,p_fence bigint,
          p_owner uuid,p_job uuid,p_generation uuid,p_token uuid) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        BEGIN
          PERFORM public.lock_indicator_build_identity(p_epoch,p_fence,p_owner,p_job,
            p_generation,p_token);
          IF NOT EXISTS(SELECT 1 FROM public.indicator_build_slot s
            JOIN public.indicator_build_jobs j ON j.id=s.job_id
            CROSS JOIN public.indicator_rollout_control c
            WHERE s.id=1 AND c.id=1 AND s.lease_until>clock_timestamp()
              AND j.lease_until>clock_timestamp() AND s.attempt_deadline>clock_timestamp()
              AND j.build_rollout_epoch=c.rollout_epoch
              AND c.mode IN ('PREPARING','PREPARED') AND c.source_proof_state='READY'
              AND c.retention_policy='GRACE' AND c.codec_version=1 AND c.protocol_version=1) THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
          END IF;
          -- Ownership cleanup may accept a maintenance-expired candidate; live writes may not.
          IF EXISTS(SELECT 1 FROM public.indicator_build_jobs j WHERE j.id=p_job
              AND j.current_candidate IS NOT NULL)
            AND NOT EXISTS(SELECT 1 FROM public.indicator_generations g
              WHERE g.id=p_generation AND g.status='STAGING') THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
          END IF;
        END $$""",
    ),
    (
        f"heartbeat_indicator_build_claim({IDENTITY_ARGS})",
        """CREATE FUNCTION heartbeat_indicator_build_claim(p_epoch uuid,p_fence bigint,
          p_owner uuid,p_job uuid,p_generation uuid,p_token uuid) RETURNS timestamptz
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE observed timestamptz;
        BEGIN
          PERFORM public.require_indicator_build_claim(p_epoch,p_fence,p_owner,p_job,
            p_generation,p_token);
          observed:=clock_timestamp();
          UPDATE public.indicator_build_slot SET lease_until=observed+interval '150 seconds',
            last_heartbeat=observed WHERE id=1 AND lease_until>observed
              AND attempt_deadline>observed;
          IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
          END IF;
          UPDATE public.indicator_build_jobs SET lease_until=observed+interval '150 seconds'
            WHERE id=p_job AND lease_until>observed;
          IF NOT FOUND THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
          END IF;
          RETURN observed+interval '150 seconds';
        END $$""",
    ),
    (
        "complete_indicator_build_attempt(uuid,text)",
        """CREATE FUNCTION complete_indicator_build_attempt(p_job uuid,p_reason text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE j public.indicator_build_jobs%ROWTYPE; observed timestamptz:=clock_timestamp();
          category text; next_status text;
        BEGIN
          IF p_reason IS NULL OR p_reason NOT IN
            ('TRANSIENT','SOURCE_CHANGED','OWNERSHIP_LOST','OPERATIONAL') THEN
            RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_FAILURE_UNSUPPORTED';
          END IF;
          SELECT * INTO STRICT j FROM public.indicator_build_jobs WHERE id=p_job FOR UPDATE;
          IF j.status<>'RUNNING' THEN
            RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
          END IF;
          category:=CASE WHEN p_reason IN ('SOURCE_CHANGED','OWNERSHIP_LOST')
            THEN 'SUPERSEDED' ELSE p_reason END;
          next_status:=CASE WHEN category='OPERATIONAL' THEN 'FAILED_OPERATIONAL'
            WHEN j.attempts_used>=3 THEN 'FAILED_'||category ELSE 'QUEUED' END;
          UPDATE public.indicator_generations SET status='SUPERSEDED'
            WHERE job_id=p_job AND claim_token=j.claim_token AND status='STAGING';
          UPDATE public.indicator_build_jobs SET status=next_status,claim_token=NULL,
            lease_until=NULL,failure_category=category,failure_reason=p_reason,
            failed_at=CASE WHEN next_status<>'QUEUED' THEN observed ELSE NULL END,
            retry_not_before=CASE WHEN next_status='QUEUED' THEN observed+
              CASE WHEN j.attempts_used=1 THEN interval '30 seconds'
                ELSE interval '60 seconds' END ELSE retry_not_before END
            WHERE id=p_job;
          UPDATE public.indicator_build_slot SET state='IDLE',owner_instance=NULL,
            owner_backend_pid=NULL,job_id=NULL,generation_id=NULL,claim_token=NULL,
            lease_until=NULL,attempt_deadline=NULL,last_heartbeat=NULL WHERE id=1;
        END $$""",
    ),
    (
        f"release_indicator_build_claim({IDENTITY_ARGS},text)",
        """CREATE FUNCTION release_indicator_build_claim(p_epoch uuid,p_fence bigint,
          p_owner uuid,p_job uuid,p_generation uuid,p_token uuid,p_reason text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        BEGIN
          -- Caller stops/joins CPU and closes source first. Expiry does not forbid cleanup.
          PERFORM public.lock_indicator_build_identity(p_epoch,p_fence,p_owner,p_job,
            p_generation,p_token);
          PERFORM public.complete_indicator_build_attempt(p_job,p_reason);
        END $$""",
    ),
    (
        "reap_indicator_build_slot(uuid,uuid,bigint)",
        """CREATE FUNCTION reap_indicator_build_slot(p_owner uuid,p_epoch uuid,p_fence bigint)
          RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE s public.indicator_build_slot%ROWTYPE; j public.indicator_build_jobs%ROWTYPE;
          result text;
        BEGIN
          -- Migrator-only; operator must first verify the owner process is stopped.
          IF NOT public.try_indicator_build_lock() THEN RETURN 'LOCK_BUSY'; END IF;
          BEGIN
            PERFORM 1 FROM public.indicator_rollout_control WHERE id=1 FOR SHARE;
            SELECT * INTO STRICT s FROM public.indicator_build_slot WHERE id=1 FOR UPDATE;
            IF s.state<>'RUNNING' OR s.owner_instance IS DISTINCT FROM p_owner
              OR s.slot_epoch IS DISTINCT FROM p_epoch OR s.fence IS DISTINCT FROM p_fence THEN
              result:='STALE';
            ELSE
              IF s.fence=9223372036854775807 THEN
                RAISE EXCEPTION USING ERRCODE='TT016',MESSAGE='INDICATOR_FENCE_EXHAUSTED';
              END IF;
              SELECT * INTO STRICT j FROM public.indicator_build_jobs WHERE id=s.job_id FOR UPDATE;
              IF j.claim_token IS DISTINCT FROM s.claim_token THEN
                RAISE EXCEPTION USING ERRCODE='TT014',MESSAGE='INDICATOR_BUILD_OWNERSHIP_LOST';
              END IF;
              PERFORM public.complete_indicator_build_attempt(s.job_id,'OWNERSHIP_LOST');
              UPDATE public.indicator_build_slot SET fence=s.fence+1 WHERE id=1;
              result:='REAPED';
            END IF;
          EXCEPTION WHEN query_canceled THEN
            -- OTHERS excludes cancellation; rollback does not release session locks.
            PERFORM pg_advisory_unlock(711,1);
            RAISE;
          WHEN OTHERS THEN
            PERFORM pg_advisory_unlock(711,1);
            RAISE;
          END;
          PERFORM pg_advisory_unlock(711,1);
          RETURN result;
        END $$""",
    ),
)

RUNTIME_FUNCTIONS = (
    "try_indicator_build_lock()",
    "unlock_indicator_build_lock()",
    "seed_indicator_build_jobs()",
    "claim_indicator_build_job(uuid)",
    f"heartbeat_indicator_build_claim({IDENTITY_ARGS})",
    f"release_indicator_build_claim({IDENTITY_ARGS},text)",
)


def upgrade() -> None:
    op.execute("""ALTER TABLE indicator_build_slot ADD COLUMN dispatch_cursor smallint
        NOT NULL DEFAULT -1 CHECK(dispatch_cursor BETWEEN -1 AND 29)""")
    for signature, statement in FUNCTIONS:
        op.execute(statement)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    for signature in RUNTIME_FUNCTIONS:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO tiewtrade_indicator_builder")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM indicator_build_slot WHERE state<>'IDLE')
        OR EXISTS(SELECT 1 FROM indicator_rollout_control WHERE mode NOT IN ('LEGACY','PAUSED'))
      THEN RAISE EXCEPTION 'INDICATOR_DOWNGRADE_NOT_DRAINED'; END IF;
    END $$""")
    for signature, _ in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
    op.execute("ALTER TABLE indicator_build_slot DROP COLUMN dispatch_cursor")
