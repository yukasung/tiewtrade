"""Fence legacy writers even when a Paper wallet has no configured loss limit."""

# ruff: noqa: E501 -- preserve complete SQL guard predicates
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE risk_boundary_claims
      DROP CONSTRAINT risk_boundary_claims_user_id_mode_fkey""")
    op.execute("""CREATE OR REPLACE FUNCTION risk_require_financial_boundary() RETURNS trigger
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
        -- Capital-only wallet lifecycle is available before the first risk limit.
        -- It does not authorize a trade or an economic position projection.
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
      END $$""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM risk_protocol_control WHERE financial_enabled)
      THEN RAISE EXCEPTION 'active risk writer protocol prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE risk_boundary_claims NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM risk_boundary_claims b WHERE NOT EXISTS(
      SELECT 1 FROM risk_limit_settings s WHERE (s.user_id,s.mode)=(b.user_id,b.mode))) THEN
      RAISE EXCEPTION 'unconfigured financial boundary history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE risk_boundary_claims FORCE ROW LEVEL SECURITY")
    op.execute("""ALTER TABLE risk_boundary_claims ADD FOREIGN KEY(user_id,mode)
      REFERENCES risk_limit_settings(user_id,mode)""")
    op.execute(_PREVIOUS_GUARD)


_PREVIOUS_GUARD = """CREATE OR REPLACE FUNCTION risk_require_financial_boundary() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
      DECLARE row_data jsonb; claim uuid; episode uuid; wallet uuid; owner uuid;
      BEGIN
        IF NOT (SELECT financial_enabled FROM public.risk_protocol_control) THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
        END IF;
        row_data:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
        owner:=(row_data->>'user_id')::uuid;
        IF NOT EXISTS(SELECT 1 FROM public.risk_limit_settings WHERE user_id=owner AND mode='PAPER') THEN
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
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
          RAISE EXCEPTION 'managed financial write requires the F18 boundary' USING ERRCODE='TT028'; END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
      END $$"""
