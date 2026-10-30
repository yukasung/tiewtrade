"""Allow PAPER risk-limit increases without a TOTP authorization receipt."""

# ruff: noqa: E501 -- keep the security-definer predicate reviewable as one unit
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

_SIGNATURE = (
    "risk_submit_request(uuid,text,text,uuid,bigint,tiewtrade_money_amount,uuid,uuid,text,uuid)"
)


def _drop_authorization_constraint() -> None:
    op.execute("""DO $$ DECLARE name text; BEGIN
      SELECT conname INTO name FROM pg_constraint
      WHERE conrelid='risk_limit_requests'::regclass AND contype='c'
        AND pg_get_constraintdef(oid) LIKE '%authorization_id IS NOT NULL%'
        AND pg_get_constraintdef(oid) LIKE '%action%';
      IF name IS NULL THEN RAISE EXCEPTION 'risk authorization constraint missing'; END IF;
      EXECUTE format('ALTER TABLE risk_limit_requests DROP CONSTRAINT %I',name);
    END $$""")


def _submission_function(*, paper_without_authorization: bool) -> None:
    paper_guard = (
        """IF request_mode='PAPER' AND request_authorization IS NOT NULL THEN
            RAISE EXCEPTION 'RISK_AUTHORIZATION_REQUIRED' USING ERRCODE='23514'; END IF;
          IF request_mode='LIVE' THEN"""
        if paper_without_authorization
        else "IF request_mode IN ('PAPER','LIVE') THEN"
    )
    op.execute(f"""CREATE OR REPLACE FUNCTION risk_submit_request(
      request uuid, request_mode text, request_action text, request_key uuid,
      request_revision bigint, request_amount public.tiewtrade_money_amount,
      request_wallet uuid, request_episode uuid, request_fingerprint text, request_authorization uuid)
      RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE owner uuid:=public.tiewtrade_current_user_id(); prior public.risk_limit_requests%ROWTYPE;
        proof public.risk_limit_authorizations%ROWTYPE; current_amount public.tiewtrade_money_amount;
        current_revision bigint;
      BEGIN
        IF owner IS NULL OR request_mode NOT IN ('PAPER','LIVE') THEN
          RAISE EXCEPTION 'RISK_SCOPE_CONFLICT' USING ERRCODE='23514'; END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(
          CASE WHEN request_mode='PAPER' THEN 'paper-wallet:' ELSE 'risk-live:' END||owner::text,0));
        SELECT * INTO prior FROM public.risk_limit_requests
          WHERE user_id=owner AND mode=request_mode AND idempotency_key=request_key;
        IF FOUND THEN
          IF prior.fingerprint<>request_fingerprint OR prior.action<>request_action
            OR prior.expected_revision<>request_revision
            OR prior.amount IS DISTINCT FROM request_amount
            OR prior.wallet_id IS DISTINCT FROM request_wallet
            OR prior.episode_id IS DISTINCT FROM request_episode THEN
            RAISE EXCEPTION 'RISK_REVISION_CONFLICT' USING ERRCODE='23514'; END IF;
          RETURN prior.id;
        END IF;
        IF request_mode='PAPER' AND NOT EXISTS(SELECT 1 FROM public.paper_wallet_state s
          WHERE s.user_id=owner AND s.wallet_id=request_wallet AND s.active_episode_id=request_episode
          AND NOT EXISTS(SELECT 1 FROM public.paper_wallet_episode_closures c WHERE c.episode_id=request_episode))
          THEN RAISE EXCEPTION 'RISK_SCOPE_CONFLICT' USING ERRCODE='23514'; END IF;
        SELECT revision,amount INTO current_revision,current_amount FROM public.risk_limit_settings
          WHERE user_id=owner AND mode=request_mode;
        IF coalesce(current_revision,0)<>request_revision THEN
          RAISE EXCEPTION 'RISK_REVISION_CONFLICT' USING ERRCODE='23514'; END IF;
        IF request_action='SET' AND current_amount IS NOT NULL
          OR request_action='DECREASE' AND (current_amount IS NULL OR request_amount>=current_amount)
          OR request_action IN ('INCREASE','RESET') AND current_amount IS NULL THEN
          RAISE EXCEPTION 'RISK_REVISION_CONFLICT' USING ERRCODE='23514'; END IF;
        IF request_action='INCREASE' THEN
          IF request_amount<=current_amount THEN
            RAISE EXCEPTION 'RISK_REVISION_CONFLICT' USING ERRCODE='23514'; END IF;
          {paper_guard}
            SELECT * INTO proof FROM public.risk_limit_authorizations
              WHERE id=request_authorization AND user_id=owner;
            IF NOT FOUND OR proof.mode<>request_mode OR proof.action<>request_action
              OR proof.idempotency_key<>request_key OR proof.expected_revision<>request_revision
              OR proof.fingerprint<>request_fingerprint OR proof.amount IS DISTINCT FROM request_amount
              OR proof.wallet_id IS DISTINCT FROM request_wallet
              OR proof.episode_id IS DISTINCT FROM request_episode THEN
              RAISE EXCEPTION 'RISK_AUTHORIZATION_REQUIRED' USING ERRCODE='23514'; END IF;
          END IF;
        END IF;
        INSERT INTO public.risk_limit_requests
          (id,user_id,mode,action,idempotency_key,expected_revision,amount,wallet_id,episode_id,fingerprint,authorization_id)
          VALUES(request,owner,request_mode,request_action,request_key,request_revision,request_amount,
            request_wallet,request_episode,request_fingerprint,request_authorization);
        INSERT INTO public.risk_limit_dispatch(request_id,user_id,mode) VALUES(request,owner,request_mode);
        INSERT INTO public.audit_events(id,owner_user_id,actor_kind,actor_id,action,subject_kind,
          subject_id,mode,outcome,details) VALUES(request,owner,'USER',owner,'RISK_LIMIT_REQUESTED',
          'RISK_LIMIT',owner::text,request_mode,'SUCCEEDED',jsonb_build_object(
          'event_id',request::text,'request_id',request::text,'risk_revision',request_revision,
          'limit_amount',CASE WHEN request_amount IS NULL THEN NULL ELSE request_amount::text END,
          'stop_id',NULL,'order_id',NULL));
        RETURN request;
      END $$""")
    op.execute(f"REVOKE ALL ON FUNCTION {_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {_SIGNATURE} TO tiewtrade_api")


def upgrade() -> None:
    op.execute("LOCK TABLE risk_limit_requests IN ACCESS EXCLUSIVE MODE")
    _drop_authorization_constraint()
    op.execute("""ALTER TABLE risk_limit_requests
      ADD CONSTRAINT risk_request_authorization_mode CHECK(
        (mode='LIVE' AND action='INCREASE')=(authorization_id IS NOT NULL)) NOT VALID""")
    _submission_function(paper_without_authorization=True)


def downgrade() -> None:
    op.execute("LOCK TABLE risk_limit_requests IN ACCESS EXCLUSIVE MODE")
    # The table is FORCE RLS and the migration has no owner context. Temporarily
    # let its owning role inspect every row; a raised exception rolls this DDL back.
    op.execute("ALTER TABLE risk_limit_requests NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM risk_limit_requests
        WHERE mode='PAPER' AND action='INCREASE' AND authorization_id IS NULL) THEN
        RAISE EXCEPTION 'Paper increases without authorization prevent downgrade';
      END IF;
    END $$""")
    op.execute("ALTER TABLE risk_limit_requests FORCE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE risk_limit_requests DROP CONSTRAINT risk_request_authorization_mode"
    )
    op.execute("""ALTER TABLE risk_limit_requests
      ADD CONSTRAINT risk_request_authorization_required CHECK(
        (action='INCREASE')=(authorization_id IS NOT NULL))""")
    _submission_function(paper_without_authorization=False)
