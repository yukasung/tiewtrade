"""Keep unconfigured Paper trades fenced while making the loss limit optional."""

# ruff: noqa: E501 -- preserve complete SQL guard predicates for security review
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


_OPTIONAL_GUARD = """CREATE OR REPLACE FUNCTION risk_require_financial_boundary() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      DECLARE row_data jsonb; claim uuid; episode uuid; wallet uuid; owner uuid; configured boolean;
      BEGIN
        IF NOT (SELECT financial_enabled FROM public.risk_protocol_control) THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END IF;
        row_data:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
        owner:=(row_data->>'user_id')::uuid;
        SELECT EXISTS(SELECT 1 FROM public.risk_limit_settings WHERE user_id=owner AND mode='PAPER')
          INTO configured;
        -- Capital-only wallet lifecycle remains available before any trading boundary exists.
        IF NOT configured AND (
          TG_TABLE_NAME IN ('paper_wallet_state','paper_wallet_episode_closures')
          OR (TG_TABLE_NAME='paper_wallet_ledger' AND row_data->>'kind'='EXTERNAL_CAPITAL')
          OR (TG_TABLE_NAME='paper_position_activity' AND (row_data->>'source_sequence')::bigint=0)
        ) THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END IF;
        -- Configured and optional-unconfigured economic writes use the same owner-scoped fence.
        episode:=coalesce(row_data->>'episode_id',row_data->>'active_episode_id')::uuid;
        wallet:=coalesce((row_data->>'wallet_id')::uuid,
          (SELECT e.wallet_id FROM public.paper_wallet_episodes e WHERE e.id=episode AND e.user_id=owner));
        claim:=nullif(current_setting('tiewtrade.risk_boundary_id',true),'')::uuid;
        IF current_setting('tiewtrade.risk_financial_version',true) IS DISTINCT FROM 'F18_V1'
          OR NOT public.risk_publication_lock_held(true)
          OR NOT EXISTS(SELECT 1 FROM public.risk_boundary_claims b
            WHERE b.id=claim AND b.user_id=owner AND b.mode='PAPER' AND b.wallet_id=wallet
            AND (b.episode_id=episode OR b.after_episode_id=episode)
            AND b.transaction_id=pg_current_xact_id()::text AND NOT b.finalized) THEN
          RAISE EXCEPTION 'financial write requires the F18 boundary' USING ERRCODE='TT028'; END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
      END $$"""


_REQUIRED_GUARD = """CREATE OR REPLACE FUNCTION risk_require_financial_boundary() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      DECLARE row_data jsonb; claim uuid; episode uuid; wallet uuid; owner uuid; configured boolean;
      BEGIN
        IF NOT (SELECT financial_enabled FROM public.risk_protocol_control) THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END IF;
        row_data:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
        owner:=(row_data->>'user_id')::uuid;
        SELECT EXISTS(SELECT 1 FROM public.risk_limit_settings WHERE user_id=owner AND mode='PAPER')
          INTO configured;
        IF NOT configured AND (
          TG_TABLE_NAME IN ('paper_wallet_state','paper_wallet_episode_closures')
          OR (TG_TABLE_NAME='paper_wallet_ledger' AND row_data->>'kind'='EXTERNAL_CAPITAL')
          OR (TG_TABLE_NAME='paper_position_activity' AND (row_data->>'source_sequence')::bigint=0)
        ) THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END IF;
        IF NOT configured AND TG_TABLE_NAME='paper_position_events'
          AND row_data->>'event_kind'='RECORD' AND row_data->>'side'='BUY' THEN
          RAISE EXCEPTION 'opening requires a configured loss limit' USING ERRCODE='TT028';
        END IF;
        episode:=coalesce(row_data->>'episode_id',row_data->>'active_episode_id')::uuid;
        wallet:=coalesce((row_data->>'wallet_id')::uuid,
          (SELECT e.wallet_id FROM public.paper_wallet_episodes e WHERE e.id=episode AND e.user_id=owner));
        claim:=nullif(current_setting('tiewtrade.risk_boundary_id',true),'')::uuid;
        IF current_setting('tiewtrade.risk_financial_version',true) IS DISTINCT FROM 'F18_V1'
          OR NOT public.risk_publication_lock_held(true)
          OR NOT EXISTS(SELECT 1 FROM public.risk_boundary_claims b
            WHERE b.id=claim AND b.user_id=owner AND b.mode='PAPER' AND b.wallet_id=wallet
            AND (b.episode_id=episode OR b.after_episode_id=episode)
            AND b.transaction_id=pg_current_xact_id()::text AND NOT b.finalized) THEN
          RAISE EXCEPTION 'financial write requires the F18 boundary' USING ERRCODE='TT028'; END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
      END $$"""


def upgrade() -> None:
    op.execute(_OPTIONAL_GUARD)


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM risk_protocol_control WHERE financial_enabled)
      THEN RAISE EXCEPTION 'active risk writer protocol prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE paper_position_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE risk_limit_settings NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(
      SELECT 1 FROM paper_position_events e
      WHERE e.event_kind='RECORD' AND e.side='BUY' AND NOT EXISTS(
        SELECT 1 FROM risk_limit_settings s WHERE s.user_id=e.user_id AND s.mode='PAPER'))
      THEN RAISE EXCEPTION 'unconfigured Paper economic history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE risk_limit_settings FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE paper_position_events FORCE ROW LEVEL SECURITY")
    op.execute(_REQUIRED_GUARD)
