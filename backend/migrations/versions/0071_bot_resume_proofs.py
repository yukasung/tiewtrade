"""Keep generation-bound proof of a successful strategy recovery probe."""

from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE bot_resume_proofs (
      id uuid PRIMARY KEY, run_id uuid NOT NULL, user_id uuid NOT NULL,
      mode text NOT NULL CHECK(mode='PAPER'),
      stop_id uuid NOT NULL, run_revision bigint NOT NULL CHECK(run_revision>0),
      wallet_revision bigint NOT NULL CHECK(wallet_revision>0),
      catalog_revision bigint NOT NULL CHECK(catalog_revision>0),
      risk_revision bigint NOT NULL CHECK(risk_revision>0),
      watermark bigint NOT NULL CHECK(watermark>0),
      expires_at timestamptz NOT NULL,
      FOREIGN KEY(stop_id,user_id) REFERENCES trading_stop_requests(id,user_id),
      FOREIGN KEY(run_id,user_id,mode) REFERENCES bot_runs(id,user_id,mode))""")
    op.execute("CREATE INDEX bot_resume_proof_stop ON bot_resume_proofs(stop_id,expires_at)")
    op.execute("ALTER TABLE bot_resume_proofs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_resume_proofs FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY bot_resume_proofs_owner ON bot_resume_proofs
      USING(user_id=tiewtrade_current_user_id()) WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT ON bot_resume_proofs TO tiewtrade_api,tiewtrade_engine")
    op.execute("GRANT INSERT ON bot_resume_proofs TO tiewtrade_engine")
    op.execute("SELECT tiewtrade_make_append_only('bot_resume_proofs'::regclass)")

    op.execute("""CREATE POLICY bot_resume_proofs_discovery ON bot_resume_proofs
      FOR SELECT TO tiewtrade_migrator USING(true)""")
    op.execute("""CREATE POLICY bot_system_stop_discovery ON trading_stop_requests
      FOR SELECT TO tiewtrade_migrator USING(
        action='STOP' AND cause='SYSTEM' AND mode='PAPER'
        AND reason_code IN ('STRATEGY_VERSION_UNAVAILABLE','STRATEGY_EVALUATION_FAILED'))""")
    op.execute("""CREATE FUNCTION due_bot_recovery_probes(p_limit integer)
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
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION due_bot_recovery_probes(integer) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION due_bot_recovery_probes(integer) TO tiewtrade_engine_scan"
    )


def downgrade() -> None:
    op.execute("LOCK TABLE bot_resume_proofs IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE bot_resume_proofs NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM bot_resume_proofs) THEN
        RAISE EXCEPTION 'bot resume proof history prevents downgrade';
      END IF;
    END $$""")
    op.execute("DROP FUNCTION due_bot_recovery_probes(integer)")
    op.execute("DROP POLICY bot_system_stop_discovery ON trading_stop_requests")
    op.execute("DROP TABLE bot_resume_proofs")
