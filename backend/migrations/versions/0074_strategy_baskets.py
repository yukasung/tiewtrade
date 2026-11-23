"""Persist F-21 owner configurations, basket authority and execution guards."""

from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None

TABLES = (
    "bot_strategy_configurations",
    "bot_strategy_baskets",
    "bot_strategy_progress",
    "bot_strategy_entries",
    "bot_basket_triggers",
    "bot_strategy_exit_guards",
    "bot_strategy_execution_receipts",
)


def upgrade() -> None:
    op.execute("""ALTER TABLE bot_order_links ADD CONSTRAINT bot_order_link_run_ref
      UNIQUE(command_id,run_id)""")
    op.execute("ALTER TABLE market_price_feed ADD COLUMN bot_recovery_at timestamptz")
    op.execute("""CREATE FUNCTION mark_bot_price_recovery() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF NEW.connected IS DISTINCT FROM OLD.connected
        OR NEW.generation IS DISTINCT FROM OLD.generation THEN
        NEW.bot_recovery_at:=clock_timestamp();
      ELSE NEW.bot_recovery_at:=OLD.bot_recovery_at; END IF;
      RETURN NEW; END $$""")
    op.execute("REVOKE ALL ON FUNCTION mark_bot_price_recovery() FROM PUBLIC")
    op.execute("""CREATE TRIGGER bot_price_recovery BEFORE UPDATE ON market_price_feed
      FOR EACH ROW EXECUTE FUNCTION mark_bot_price_recovery()""")
    op.execute("ALTER TABLE market_candle_demand ADD COLUMN bot_recovery_at timestamptz")
    op.execute("""CREATE FUNCTION mark_bot_candle_recovery() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF (NEW.failure_code IS DISTINCT FROM OLD.failure_code)
        OR (NEW.status IS DISTINCT FROM OLD.status AND
          (NEW.status IN ('FAILED','UNAVAILABLE') OR OLD.status IN ('FAILED','UNAVAILABLE')))
        OR (NEW.phase IS DISTINCT FROM OLD.phase AND (NEW.phase='REPAIR' OR OLD.phase='REPAIR'))
        OR (OLD.token IS NOT NULL AND OLD.lease_until<=clock_timestamp()
          AND NEW.token IS DISTINCT FROM OLD.token) THEN
        NEW.bot_recovery_at:=clock_timestamp();
      ELSE NEW.bot_recovery_at:=OLD.bot_recovery_at; END IF;
      RETURN NEW; END $$""")
    op.execute("REVOKE ALL ON FUNCTION mark_bot_candle_recovery() FROM PUBLIC")
    op.execute("""CREATE TRIGGER bot_candle_recovery BEFORE UPDATE ON market_candle_demand
      FOR EACH ROW EXECUTE FUNCTION mark_bot_candle_recovery()""")
    op.execute("""GRANT INSERT(source,base,quote,timeframe,desired_start,desired_end,requested_at),
      UPDATE(desired_start,desired_end,requested_at,refresh_requested_at)
      ON market_candle_demand TO tiewtrade_engine""")
    op.execute("""CREATE TABLE bot_strategy_configurations (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
      mode text NOT NULL CHECK(mode='PAPER'), idempotency_key uuid NOT NULL,
      fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      configuration jsonb NOT NULL CHECK((jsonb_typeof(configuration)='object') IS TRUE),
      CHECK((configuration->'version'='1'::jsonb) IS TRUE),
      CHECK((jsonb_typeof(configuration->'fields')='array'
        AND jsonb_array_length(configuration->'fields')=5) IS TRUE),
      CHECK((configuration->'fields'->0->>0='base'
        AND configuration->'fields'->0->>1 IN ('BTC','ETH')) IS TRUE),
      CHECK((configuration->'fields'->1->>0='quote'
        AND configuration->'fields'->1->>1='USDT') IS TRUE),
      CHECK((configuration->'fields'->2->>0='timeframe'
        AND configuration->'fields'->2->>1
          IN ('1m','3m','5m','15m','1h','4h','1d','1w','1M')) IS TRUE),
      CHECK((configuration->'fields'->3->>0='capital_per_entry'
        AND configuration->'fields'->3->1->'money'->>'currency'='USDT'
        AND (configuration->'fields'->3->1->'money'->>'amount')::tiewtrade_money_amount>0) IS TRUE),
      CHECK((configuration->'fields'->4->>0='max_entries'
        AND jsonb_typeof(configuration->'fields'->4->1)='number'
        AND (configuration->'fields'->4->>1)::numeric BETWEEN 1 AND 10
        AND (configuration->'fields'->4->>1)::numeric
          =trunc((configuration->'fields'->4->>1)::numeric)) IS TRUE),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(user_id,mode,idempotency_key), UNIQUE(id,user_id,mode))""")
    op.execute("""CREATE TABLE bot_strategy_baskets (
      id uuid PRIMARY KEY, user_id uuid NOT NULL, run_id uuid NOT NULL,
      mode text NOT NULL CHECK(mode='PAPER'), episode_id uuid NOT NULL,
      base tiewtrade_unit_code NOT NULL CHECK(base IN ('BTC','ETH')),
      quote tiewtrade_unit_code NOT NULL CHECK(quote='USDT'),
      timeframe text NOT NULL CHECK(timeframe IN ('1m','3m','5m','15m','1h','4h','1d','1w','1M')),
      status text NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','TRIGGERED','CLOSED')),
      target tiewtrade_money_amount CHECK(target>0),
      price_tick tiewtrade_money_amount CHECK(price_tick>0),
      reconciliation_required boolean NOT NULL DEFAULT false,
      revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      target_revision bigint NOT NULL DEFAULT 0 CHECK(target_revision>=0),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(id,user_id,mode,episode_id,run_id),
      FOREIGN KEY(run_id,user_id,mode,episode_id)
        REFERENCES bot_runs(id,user_id,mode,episode_id))""")
    op.execute("""CREATE UNIQUE INDEX bot_strategy_open_basket
      ON bot_strategy_baskets(run_id) WHERE status<>'CLOSED'""")
    op.execute("""CREATE TABLE bot_strategy_entries (
      order_id uuid PRIMARY KEY, command_id uuid NOT NULL,
      user_id uuid NOT NULL, mode text NOT NULL CHECK(mode='PAPER'),
      episode_id uuid NOT NULL, run_id uuid NOT NULL, basket_id uuid NOT NULL,
      entry_sequence integer NOT NULL CHECK(entry_sequence>0),
      atr tiewtrade_money_amount NOT NULL CHECK(atr>=0),
      signal_open_at timestamptz NOT NULL,
      quantity tiewtrade_money_amount NOT NULL DEFAULT 0 CHECK(quantity>=0),
      gross_quantity tiewtrade_money_amount NOT NULL DEFAULT 0 CHECK(gross_quantity>=0),
      gross_notional tiewtrade_money_amount NOT NULL DEFAULT 0 CHECK(gross_notional>=0),
      price tiewtrade_money_amount CHECK(price>0), filled_at timestamptz,
      UNIQUE(basket_id,entry_sequence),
      FOREIGN KEY(basket_id,user_id,mode,episode_id,run_id)
        REFERENCES bot_strategy_baskets(id,user_id,mode,episode_id,run_id),
      FOREIGN KEY(command_id,user_id,episode_id,order_id)
        REFERENCES bot_order_links(command_id,user_id,episode_id,order_id),
      FOREIGN KEY(command_id,run_id) REFERENCES bot_order_links(command_id,run_id))""")
    op.execute("""CREATE TABLE bot_basket_triggers (
      id uuid PRIMARY KEY, basket_id uuid NOT NULL UNIQUE,
      user_id uuid NOT NULL, mode text NOT NULL CHECK(mode='PAPER'),
      episode_id uuid NOT NULL, run_id uuid NOT NULL,
      target_revision bigint NOT NULL CHECK(target_revision>0),
      evidence jsonb NOT NULL CHECK(jsonb_typeof(evidence)='object'),
      membership jsonb NOT NULL CHECK(jsonb_typeof(membership)='array'),
      recorded_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY(basket_id,user_id,mode,episode_id,run_id)
        REFERENCES bot_strategy_baskets(id,user_id,mode,episode_id,run_id))""")
    op.execute("""CREATE TABLE bot_strategy_exit_guards (
      execution_id uuid NOT NULL, user_id uuid NOT NULL, run_id uuid NOT NULL,
      mode text NOT NULL CHECK(mode='PAPER'), episode_id uuid NOT NULL,
      candle_open_at timestamptz NOT NULL, occurred_at timestamptz NOT NULL,
      PRIMARY KEY(run_id,execution_id),
      FOREIGN KEY(run_id,user_id,mode,episode_id)
        REFERENCES bot_runs(id,user_id,mode,episode_id))""")
    op.execute("""CREATE INDEX bot_strategy_exit_candle
      ON bot_strategy_exit_guards(run_id,candle_open_at)""")
    op.execute("""CREATE TABLE bot_strategy_progress (
      run_id uuid PRIMARY KEY, user_id uuid NOT NULL, mode text NOT NULL CHECK(mode='PAPER'),
      episode_id uuid NOT NULL, guard_revision bigint NOT NULL DEFAULT 0 CHECK(guard_revision>=0),
      reconciliation_required boolean NOT NULL DEFAULT false,
      eligible_after timestamptz NOT NULL DEFAULT clock_timestamp(),
      recovery_required boolean NOT NULL DEFAULT true,
      source_recovery_at timestamptz,
      price_recovery_at timestamptz,
      indicator_source_epoch uuid,
      FOREIGN KEY(run_id,user_id,mode,episode_id)
        REFERENCES bot_runs(id,user_id,mode,episode_id))""")
    op.execute("""CREATE TABLE bot_strategy_execution_receipts (
      execution_id uuid NOT NULL, user_id uuid NOT NULL, run_id uuid NOT NULL,
      mode text NOT NULL CHECK(mode='PAPER'), episode_id uuid NOT NULL,
      order_id uuid NOT NULL, details jsonb NOT NULL,
      PRIMARY KEY(run_id,execution_id),
      FOREIGN KEY(run_id,user_id,mode,episode_id)
        REFERENCES bot_runs(id,user_id,mode,episode_id))""")
    op.execute("""ALTER TABLE bot_strategy_entries ADD CONSTRAINT bot_entry_progress
      FOREIGN KEY(run_id) REFERENCES bot_strategy_progress(run_id)""")
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())""")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api,tiewtrade_engine")
        op.execute(f"GRANT INSERT ON {table} TO tiewtrade_engine")
    for table in ("bot_strategy_baskets", "bot_strategy_entries", "bot_strategy_progress"):
        op.execute(f"GRANT UPDATE ON {table} TO tiewtrade_engine")
    op.execute("GRANT INSERT ON bot_strategy_configurations TO tiewtrade_api")
    op.execute("GRANT SELECT(configuration) ON bot_runs TO tiewtrade_api")
    for table in (
        "bot_strategy_configurations",
        "bot_basket_triggers",
        "bot_strategy_exit_guards",
        "bot_strategy_execution_receipts",
    ):
        op.execute(f"SELECT tiewtrade_make_append_only('{table}'::regclass)")


def downgrade() -> None:
    op.execute("LOCK TABLE " + ",".join(TABLES) + " IN ACCESS EXCLUSIVE MODE")
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM bot_strategy_configurations)
        OR EXISTS(SELECT 1 FROM bot_strategy_baskets)
        OR EXISTS(SELECT 1 FROM bot_strategy_progress) THEN
        RAISE EXCEPTION 'F-21 history prevents destructive downgrade';
      END IF;
    END $$""")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("ALTER TABLE bot_order_links DROP CONSTRAINT bot_order_link_run_ref")
    op.execute("DROP TRIGGER bot_price_recovery ON market_price_feed")
    op.execute("DROP FUNCTION mark_bot_price_recovery()")
    op.execute("ALTER TABLE market_price_feed DROP COLUMN bot_recovery_at")
    op.execute("REVOKE SELECT(configuration) ON bot_runs FROM tiewtrade_api")
    op.execute("""REVOKE INSERT(source,base,quote,timeframe,desired_start,desired_end,requested_at),
      UPDATE(desired_start,desired_end,requested_at,refresh_requested_at)
      ON market_candle_demand FROM tiewtrade_engine""")
    op.execute("DROP TRIGGER bot_candle_recovery ON market_candle_demand")
    op.execute("DROP FUNCTION mark_bot_candle_recovery()")
    op.execute("ALTER TABLE market_candle_demand DROP COLUMN bot_recovery_at")
