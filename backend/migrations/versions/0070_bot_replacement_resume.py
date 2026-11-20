"""Bridge an immutable owner-approved replacement to the F-19 resume contract."""

from alembic import op

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE POLICY bot_replacement_request_reader ON bot_control_requests
       FOR SELECT TO tiewtrade_migrator USING(user_id=tiewtrade_current_user_id())""")
    op.execute("""CREATE FUNCTION submit_bot_replacement_resume(p_request uuid,p_resume uuid)
      RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE controls jsonb; resume_id uuid;
      BEGIN
        IF session_user <> 'tiewtrade_engine' THEN
          RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='BOT_REPLACEMENT_NOT_AUTHORIZED';
        END IF;
        SELECT q.payload->'replacement' INTO STRICT controls
        FROM public.bot_control_requests q
        WHERE q.id=p_request AND q.user_id=public.tiewtrade_current_user_id() AND q.mode='PAPER';
        SELECT r.id INTO STRICT resume_id FROM public.submit_trading_stop_request(
          p_resume,public.tiewtrade_current_user_id(),'PAPER','RESUME',p_resume,
          encode(sha256(convert_to(controls::text,'UTF8')),'hex'),
          (controls->>'stop_id')::uuid,(controls->>'stop_revision')::bigint,
          (controls->>'summary_revision')::bigint,(controls->>'reconciliation_revision')::bigint,
          'USER_RESUME',NULL,false) r;
        -- Only the replacement transaction may apply this acknowledgement.
        DELETE FROM public.trading_stop_dispatch WHERE request_id=resume_id
          AND user_id=public.tiewtrade_current_user_id();
        RETURN resume_id;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION submit_bot_replacement_resume(uuid,uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION submit_bot_replacement_resume(uuid,uuid) TO tiewtrade_engine"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION submit_bot_replacement_resume(uuid,uuid)")
    op.execute("DROP POLICY bot_replacement_request_reader ON bot_control_requests")
