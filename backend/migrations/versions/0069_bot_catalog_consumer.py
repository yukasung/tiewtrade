"""Persist bot acknowledgement of a supported-symbol withdrawal."""

from alembic import op

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE bot_catalog_stops (
      run_id uuid NOT NULL, user_id uuid NOT NULL, mode text NOT NULL,
      withdrawal_revision bigint NOT NULL REFERENCES supported_symbol_events(revision),
      stopped_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(run_id,withdrawal_revision),
      FOREIGN KEY(run_id,user_id,mode) REFERENCES bot_runs(id,user_id,mode))""")
    op.execute("ALTER TABLE bot_catalog_stops ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_catalog_stops FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY bot_catalog_stops_owner ON bot_catalog_stops
      USING(user_id=tiewtrade_current_user_id())
      WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT,INSERT ON bot_catalog_stops TO tiewtrade_engine")
    op.execute("SELECT tiewtrade_make_append_only('bot_catalog_stops'::regclass)")
    for table in ("bot_runs", "bot_run_events", "bot_catalog_stops"):
        op.execute(f"""CREATE POLICY bot_catalog_reader ON {table}
           FOR SELECT TO tiewtrade_migrator USING(true)""")
    op.execute("""CREATE FUNCTION due_bot_catalog_stops(p_limit integer)
      RETURNS TABLE(run_id uuid,user_id uuid,mode text,withdrawal_revision bigint)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      BEGIN
        IF session_user<>'tiewtrade_engine_scan' OR p_limit IS NULL
           OR p_limit NOT BETWEEN 1 AND 20 THEN
          RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='BOT_CATALOG_SCAN_NOT_AUTHORIZED';
        END IF;
        RETURN QUERY SELECT DISTINCT ON (r.user_id)
          r.id,r.user_id,r.mode,withdrawn.revision
        FROM public.bot_runs r
        JOIN public.bot_run_events started ON started.run_id=r.id AND started.user_id=r.user_id
          AND started.mode=r.mode AND started.event='START_REQUEST_APPLIED'
          AND started.revision=1
        JOIN public.supported_symbol_events withdrawn
          ON withdrawn.base=started.details->>'base' AND withdrawn.quote=started.details->>'quote'
          AND withdrawn.status='REMOVED'
          AND withdrawn.revision>(started.details->>'catalog_revision')::bigint
        WHERE r.status<>'RETIRED' AND NOT EXISTS (
          SELECT 1 FROM public.bot_catalog_stops done
          WHERE done.run_id=r.id AND done.withdrawal_revision=withdrawn.revision)
        ORDER BY r.user_id,withdrawn.revision,r.id LIMIT p_limit;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION due_bot_catalog_stops(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION due_bot_catalog_stops(integer) TO tiewtrade_engine_scan")
    op.execute("""CREATE TABLE bot_run_leases (
      run_id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL CHECK(mode='PAPER'),
      worker_id uuid NOT NULL, generation bigint NOT NULL CHECK(generation>0),
      lease_until timestamptz NOT NULL,
      FOREIGN KEY(run_id,user_id,mode) REFERENCES bot_runs(id,user_id,mode))""")
    op.execute("ALTER TABLE bot_run_leases ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_run_leases FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY bot_run_leases_owner ON bot_run_leases
      USING(user_id=tiewtrade_current_user_id())
      WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT,INSERT,UPDATE ON bot_run_leases TO tiewtrade_engine")
    op.execute("""CREATE FUNCTION due_paper_bot_runs(p_after uuid,p_limit integer)
      RETURNS TABLE(run_id uuid,user_id uuid)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      BEGIN
        IF session_user<>'tiewtrade_engine_scan' OR p_limit IS NULL
           OR p_limit NOT BETWEEN 1 AND 20 THEN
          RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='BOT_RUN_SCAN_NOT_AUTHORIZED';
        END IF;
        RETURN QUERY SELECT r.id,r.user_id FROM public.bot_runs r
          WHERE r.mode='PAPER' AND r.status IN ('STARTING','RUNNING','PAUSED','RECOVERING')
            AND (p_after IS NULL OR r.id>p_after)
          ORDER BY r.id LIMIT p_limit;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION due_paper_bot_runs(uuid,integer) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION due_paper_bot_runs(uuid,integer) TO tiewtrade_engine_scan"
    )
    # Expose only pair metadata, not the operator or reason text, to the owner worker.
    op.execute("""GRANT SELECT(base,quote,revision,status)
      ON supported_symbol_events TO tiewtrade_engine""")

    op.execute("""CREATE FUNCTION reconcile_bot_catalog_stop_counts() RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      BEGIN
        IF session_user<>'tiewtrade_engine' THEN
          RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='BOT_CATALOG_EFFECT_NOT_AUTHORIZED';
        END IF;
        WITH counts AS (
          SELECT withdrawal_revision,count(*)::integer AS stopped
          FROM public.bot_catalog_stops GROUP BY withdrawal_revision
        )
        UPDATE public.supported_symbol_effects effect
        SET bots_stopped=counts.stopped,updated_at=clock_timestamp()
        FROM counts WHERE effect.event_revision=counts.withdrawal_revision
          AND effect.bots_stopped<counts.stopped;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION reconcile_bot_catalog_stop_counts() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION reconcile_bot_catalog_stop_counts() TO tiewtrade_engine")


def downgrade() -> None:
    op.execute("LOCK TABLE bot_catalog_stops,bot_run_leases IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE bot_catalog_stops NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_run_leases NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM bot_catalog_stops) OR EXISTS(SELECT 1 FROM bot_run_leases) THEN
        RAISE EXCEPTION 'bot catalog stop history prevents downgrade';
      END IF;
    END $$""")
    op.execute("DROP FUNCTION due_paper_bot_runs(uuid,integer)")
    op.execute("DROP FUNCTION reconcile_bot_catalog_stop_counts()")
    op.execute("DROP FUNCTION due_bot_catalog_stops(integer)")
    for table in ("bot_runs", "bot_run_events"):
        op.execute(f"DROP POLICY bot_catalog_reader ON {table}")
    # Engine had no column grant from this migration's predecessor.
    op.execute(
        "REVOKE SELECT(base,quote,revision,status) ON supported_symbol_events FROM tiewtrade_engine"
    )
    op.execute("DROP TABLE bot_run_leases")
    op.execute("DROP TABLE bot_catalog_stops")
