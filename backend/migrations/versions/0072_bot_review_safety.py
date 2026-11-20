"""Bound recovery scheduling and grant read-only prepared indicator access."""

from alembic import op

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None

READS = (
    "indicator_ready_heads",
    "indicator_ready_generations",
    "indicator_ready_checkpoints",
    "indicator_numeric_failures",
    "indicator_rollout_control",
    "indicator_source_guard",
    "indicator_source_changes",
    "market_candles",
    "market_candle_demand",
)


OLD_PROBES = """CREATE FUNCTION due_bot_recovery_probes(p_limit integer)
      RETURNS TABLE(run_id uuid,user_id uuid,stop_id uuid)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      BEGIN
        IF session_user<>'tiewtrade_engine_scan' OR p_limit IS NULL
           OR p_limit NOT BETWEEN 1 AND 20 THEN
          RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='BOT_RECOVERY_SCAN_NOT_AUTHORIZED';
        END IF;
        RETURN QUERY SELECT b.id,b.user_id,s.id
        FROM public.bot_runs b
        JOIN public.bot_run_events e ON e.run_id=b.id AND e.user_id=b.user_id
          AND e.mode=b.mode AND e.revision=b.revision
          AND e.event IN ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
        JOIN public.trading_stop_requests s ON s.user_id=b.user_id AND s.mode=b.mode
          AND s.id::text=e.details->>'stop_id' AND s.action='STOP' AND s.cause='SYSTEM'
        WHERE b.mode='PAPER' AND b.status='STOPPED' AND NOT EXISTS (
          SELECT 1 FROM public.bot_resume_proofs p
          JOIN public.risk_price_publication t ON t.watermark=p.watermark
          WHERE p.stop_id=s.id AND p.run_revision=b.revision AND p.expires_at>clock_timestamp())
        ORDER BY s.recorded_at,s.id LIMIT p_limit;
      END $$"""


def upgrade() -> None:
    op.execute("DROP POLICY bot_system_stop_discovery ON trading_stop_requests")
    op.execute("""CREATE POLICY bot_system_stop_discovery ON trading_stop_requests
      FOR SELECT TO tiewtrade_migrator USING(action='STOP' AND cause='SYSTEM' AND mode='PAPER')""")
    op.execute("""CREATE POLICY bot_system_cause_discovery ON trading_stop_causes
      FOR SELECT TO tiewtrade_migrator USING(cause='SYSTEM')""")
    op.execute("""CREATE TABLE bot_recovery_schedule (
      run_id uuid PRIMARY KEY,user_id uuid NOT NULL,mode text NOT NULL CHECK(mode='PAPER'),
      last_attempt_at timestamptz NOT NULL,
      FOREIGN KEY(run_id,user_id,mode) REFERENCES bot_runs(id,user_id,mode))""")
    op.execute("ALTER TABLE bot_recovery_schedule ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_recovery_schedule FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY bot_recovery_schedule_owner ON bot_recovery_schedule
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("""CREATE POLICY bot_recovery_schedule_scan ON bot_recovery_schedule
      FOR SELECT TO tiewtrade_migrator USING(true)""")
    op.execute("GRANT SELECT,INSERT ON bot_recovery_schedule TO tiewtrade_engine")
    op.execute("GRANT UPDATE(last_attempt_at) ON bot_recovery_schedule TO tiewtrade_engine")
    op.execute("""CREATE OR REPLACE FUNCTION due_bot_recovery_probes(p_limit integer)
      RETURNS TABLE(run_id uuid,user_id uuid,stop_id uuid)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      BEGIN
        IF session_user<>'tiewtrade_engine_scan' OR p_limit IS NULL
           OR p_limit NOT BETWEEN 1 AND 20 THEN
          RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='BOT_RECOVERY_SCAN_NOT_AUTHORIZED';
        END IF;
        RETURN QUERY SELECT b.id,b.user_id,s.id
        FROM public.bot_runs b
        JOIN LATERAL (
          SELECT r.* FROM public.trading_stop_requests r
          WHERE r.user_id=b.user_id AND r.mode=b.mode AND r.action='STOP' AND r.cause='SYSTEM'
          ORDER BY r.revision DESC LIMIT 1
        ) s ON s.reason_code IN ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED')
        JOIN public.trading_stop_causes authority ON authority.stop_id=s.id
          AND authority.cause='SYSTEM' AND authority.active
        LEFT JOIN public.bot_recovery_schedule attempts ON attempts.run_id=b.id
        WHERE b.mode='PAPER' AND b.status='STOPPED'
          AND EXISTS(SELECT 1 FROM public.bot_run_events e WHERE e.run_id=b.id
            AND e.user_id=b.user_id AND e.mode=b.mode AND e.details->>'stop_id'=s.id::text
            AND e.event IN ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED'))
          AND NOT EXISTS(SELECT 1 FROM public.bot_resume_proofs p
            JOIN public.risk_price_publication t ON t.watermark=p.watermark
            WHERE p.stop_id=s.id AND p.run_revision=b.revision
              AND p.expires_at>clock_timestamp())
        ORDER BY attempts.last_attempt_at NULLS FIRST,s.recorded_at,s.id LIMIT p_limit;
      END $$""")
    # Ordinary ENGINE cannot update the guard. The bounded function only locks
    # public source metadata; producer changes must wait until decision commit.
    op.execute("""CREATE FUNCTION hold_bot_indicator_source() RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      BEGIN
        IF session_user<>'tiewtrade_engine' THEN
          RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='BOT_INDICATOR_NOT_AUTHORIZED';
        END IF;
        PERFORM 1 FROM public.indicator_source_guard WHERE id=1 FOR SHARE;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION hold_bot_indicator_source() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION hold_bot_indicator_source() TO tiewtrade_engine")
    op.execute("GRANT EXECUTE ON FUNCTION indicator_source_triggers_valid() TO tiewtrade_engine")
    for table in READS:
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_engine")
    op.execute(
        """ALTER TABLE bot_decisions ADD COLUMN input_provenance jsonb
      CHECK(input_provenance IS NULL OR jsonb_typeof(input_provenance)='object')"""
    )


def downgrade() -> None:
    op.execute("LOCK TABLE bot_recovery_schedule,bot_decisions IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE bot_recovery_schedule NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_decisions NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM bot_recovery_schedule)
        OR EXISTS(SELECT 1 FROM bot_decisions WHERE input_provenance IS NOT NULL) THEN
        RAISE EXCEPTION 'bot review safety history prevents downgrade';
      END IF;
    END $$""")
    op.execute("ALTER TABLE bot_decisions FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_decisions DROP COLUMN input_provenance")
    op.execute("DROP FUNCTION hold_bot_indicator_source()")
    op.execute("REVOKE EXECUTE ON FUNCTION indicator_source_triggers_valid() FROM tiewtrade_engine")
    for table in READS:
        op.execute(f"REVOKE SELECT ON {table} FROM tiewtrade_engine")
    op.execute("DROP TABLE bot_recovery_schedule")
    op.execute(OLD_PROBES.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
    op.execute("DROP POLICY bot_system_cause_discovery ON trading_stop_causes")
    op.execute("DROP POLICY bot_system_stop_discovery ON trading_stop_requests")
    op.execute("""CREATE POLICY bot_system_stop_discovery ON trading_stop_requests
      FOR SELECT TO tiewtrade_migrator USING(action='STOP' AND cause='SYSTEM' AND mode='PAPER'
        AND reason_code IN ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED'))""")
