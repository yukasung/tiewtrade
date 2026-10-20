"""Public execution inputs, fenced ring buffer and private retention references."""

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE market_execution_state (
      source text NOT NULL CHECK(source='primary_spot'),
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL CHECK(quote='USDT'),
      owner uuid NOT NULL, generation bigint NOT NULL CHECK(generation>0),
      lease_until timestamptz NOT NULL,
      last_input_id bigint NOT NULL DEFAULT 0 CHECK(last_input_id>=0),
      ready boolean NOT NULL DEFAULT false, failure_code text,
      received_at timestamptz, verified_at timestamptz, book_payload jsonb,
      revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      PRIMARY KEY(source,base,quote), CHECK(base<>quote),
      CHECK(NOT ready OR (book_payload IS NOT NULL AND verified_at IS NOT NULL)))""")
    op.execute("""CREATE TABLE market_execution_buffer (
      source text NOT NULL, base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      slot integer NOT NULL CHECK(slot>=0 AND slot<4096),
      input_id bigint NOT NULL CHECK(input_id>0), generation bigint NOT NULL CHECK(generation>0),
      kind text NOT NULL CHECK(kind IN ('BOOK','TRADE')),
      received_at timestamptz NOT NULL, payload jsonb NOT NULL, capability jsonb NOT NULL,
      digest text NOT NULL CHECK(digest ~ '^[0-9a-f]{64}$'),
      PRIMARY KEY(source,base,quote,slot), UNIQUE(source,base,quote,input_id),
      FOREIGN KEY(source,base,quote) REFERENCES market_execution_state(source,base,quote),
      CHECK(slot=mod(input_id,4096)))""")
    op.execute("""CREATE TABLE market_execution_demand (
      source text NOT NULL CHECK(source='primary_spot'), base tiewtrade_unit_code NOT NULL,
      quote tiewtrade_unit_code NOT NULL CHECK(quote='USDT'),
      references_count bigint NOT NULL CHECK(references_count>=0),
      revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      PRIMARY KEY(source,base,quote), CHECK(base<>quote))""")
    op.execute("""CREATE TABLE paper_market_dependencies (
      user_id uuid NOT NULL, wallet_id uuid NOT NULL, episode_id uuid NOT NULL,
      mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER'),
      source text NOT NULL CHECK(source='primary_spot'), base tiewtrade_unit_code NOT NULL,
      quote tiewtrade_unit_code NOT NULL CHECK(quote='USDT'), needed boolean NOT NULL,
      PRIMARY KEY(user_id,episode_id,source,base,quote), CHECK(base<>quote),
      FOREIGN KEY(episode_id,wallet_id,user_id)
        REFERENCES paper_wallet_episodes(id,wallet_id,user_id))""")
    op.execute("ALTER TABLE paper_market_dependencies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE paper_market_dependencies FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY paper_market_dependencies_owner ON paper_market_dependencies
      FOR ALL TO tiewtrade_engine USING(user_id=tiewtrade_current_user_id())
      WITH CHECK(user_id=tiewtrade_current_user_id())""")
    # Only an RLS-checked change to the private row can update the public count.
    # No SECURITY DEFINER query reads private owners or financial records.
    op.execute("""CREATE FUNCTION execution_demand_changed() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
      DECLARE change bigint;
      BEGIN
        IF TG_OP='UPDATE' AND
          (NEW.user_id,NEW.wallet_id,NEW.episode_id,NEW.mode,NEW.source,NEW.base,NEW.quote)
          IS DISTINCT FROM
          (OLD.user_id,OLD.wallet_id,OLD.episode_id,OLD.mode,OLD.source,OLD.base,OLD.quote)
          THEN RAISE EXCEPTION 'immutable dependency identity'; END IF;
        IF TG_OP='INSERT' THEN change:=CASE WHEN NEW.needed THEN 1 ELSE 0 END;
        ELSE change:=(CASE WHEN NEW.needed THEN 1 ELSE 0 END)
                     -(CASE WHEN OLD.needed THEN 1 ELSE 0 END); END IF;
        IF change>0 THEN
          INSERT INTO public.market_execution_demand(source,base,quote,references_count)
          VALUES(NEW.source,NEW.base,NEW.quote,change)
          ON CONFLICT(source,base,quote) DO UPDATE SET
            references_count=public.market_execution_demand.references_count+change,
            revision=public.market_execution_demand.revision+1;
        ELSIF change<0 THEN
          UPDATE public.market_execution_demand SET references_count=references_count+change,
            revision=revision+1 WHERE source=NEW.source AND base=NEW.base AND quote=NEW.quote;
          IF NOT FOUND THEN RAISE EXCEPTION 'missing demand projection'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION execution_demand_changed() FROM PUBLIC")
    op.execute("""CREATE TRIGGER execution_demand_projection
      AFTER INSERT OR UPDATE ON paper_market_dependencies
      FOR EACH ROW EXECUTE FUNCTION execution_demand_changed()""")
    op.execute("GRANT SELECT,INSERT ON paper_market_dependencies TO tiewtrade_engine")
    op.execute("GRANT UPDATE(needed) ON paper_market_dependencies TO tiewtrade_engine")
    op.execute("""GRANT SELECT ON market_execution_state,market_execution_buffer,
      market_execution_demand TO tiewtrade_engine""")
    op.execute("GRANT SELECT ON market_execution_state TO tiewtrade_api")
    op.execute("""GRANT SELECT,INSERT,UPDATE ON market_execution_state,market_execution_buffer
      TO tiewtrade_market_data""")
    op.execute("GRANT SELECT ON market_execution_demand TO tiewtrade_market_data")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM market_execution_state WHERE lease_until>clock_timestamp())
      THEN RAISE EXCEPTION 'stop execution producers before downgrade'; END IF;
      IF EXISTS(SELECT 1 FROM market_execution_demand WHERE references_count>0)
      THEN RAISE EXCEPTION 'active execution dependencies prevent downgrade'; END IF;
      END $$""")
    op.execute("DROP TABLE paper_market_dependencies")
    op.execute("DROP FUNCTION execution_demand_changed()")
    op.execute("DROP TABLE market_execution_demand")
    op.execute("DROP TABLE market_execution_buffer")
    op.execute("DROP TABLE market_execution_state")
