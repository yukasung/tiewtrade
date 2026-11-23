"""Owned Paper test configurations and first-fill ATR protection anchors."""

from alembic import op

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE bot_test_strategy_configurations (
      id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
      mode text NOT NULL CHECK(mode='PAPER'), idempotency_key uuid NOT NULL,
      fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
      configuration jsonb NOT NULL CHECK((jsonb_typeof(configuration)='object') IS TRUE),
      CHECK((configuration->'version'='1'::jsonb) IS TRUE),
      CHECK((jsonb_typeof(configuration->'fields')='array'
        AND jsonb_array_length(configuration->'fields')=5) IS TRUE),
      CHECK((configuration->'fields'->0->>0='strategy_name'
        AND configuration->'fields'->0->>1='paper-green-atr-test') IS TRUE),
      CHECK((configuration->'fields'->1->>0='base'
        AND configuration->'fields'->1->>1 IN ('BTC','ETH')) IS TRUE),
      CHECK((configuration->'fields'->2->>0='quote'
        AND configuration->'fields'->2->>1='USDT') IS TRUE),
      CHECK((configuration->'fields'->3->>0='timeframe'
        AND configuration->'fields'->3->>1 IN
          ('1m','3m','5m','15m','1h','4h','1d','1w','1M')) IS TRUE),
      CHECK((configuration->'fields'->4->>0='capital_per_entry'
        AND configuration->'fields'->4->1->'money'->>'currency'='USDT'
        AND (configuration->'fields'->4->1->'money'->>'amount')::tiewtrade_money_amount>0) IS TRUE),
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,mode,idempotency_key))""")
    op.execute("""CREATE TABLE bot_test_entry_anchors (
      order_id uuid PRIMARY KEY, command_id uuid NOT NULL, run_id uuid NOT NULL,
      user_id uuid NOT NULL, mode text NOT NULL CHECK(mode='PAPER'), episode_id uuid NOT NULL,
      atr tiewtrade_money_amount NOT NULL CHECK(atr>0),
      execution_id uuid, anchor_price tiewtrade_money_amount CHECK(anchor_price>0),
      take_profit tiewtrade_money_amount CHECK(take_profit>0),
        stop_loss tiewtrade_money_amount CHECK(stop_loss>0),
      failure_code text CHECK(failure_code='PROTECTION_SETUP_REJECTED'),
      CHECK((execution_id IS NULL AND anchor_price IS NULL AND take_profit IS NULL
        AND stop_loss IS NULL AND failure_code IS NULL)
        OR (execution_id IS NOT NULL AND anchor_price IS NOT NULL AND
          ((take_profit IS NOT NULL AND stop_loss IS NOT NULL
        AND stop_loss<take_profit AND failure_code IS NULL)
            OR (failure_code IS NOT NULL AND take_profit IS NULL AND stop_loss IS NULL)))),
      FOREIGN KEY(command_id,user_id,episode_id,order_id)
        REFERENCES bot_order_links(command_id,user_id,episode_id,order_id),
      FOREIGN KEY(command_id,run_id) REFERENCES bot_order_links(command_id,run_id),
      FOREIGN KEY(run_id,user_id,mode,episode_id)
        REFERENCES bot_runs(id,user_id,mode,episode_id))""")
    for table in ("bot_test_strategy_configurations", "bot_test_entry_anchors"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY {table}_owner ON {table} FOR ALL
          USING(user_id=tiewtrade_current_user_id())
          WITH CHECK(user_id=tiewtrade_current_user_id())"""
        )
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api,tiewtrade_engine")
    op.execute("GRANT INSERT ON bot_test_strategy_configurations TO tiewtrade_api")
    op.execute("SELECT tiewtrade_make_append_only('bot_test_strategy_configurations'::regclass)")
    op.execute("GRANT INSERT ON bot_test_entry_anchors TO tiewtrade_engine")
    op.execute(
        "GRANT "
        "UPDATE(execution_id,anchor_price,take_profit,stop_loss,failure_code) "
        "ON bot_test_entry_anchors TO tiewtrade_engine"
    )
    op.execute("""CREATE FUNCTION guard_test_entry_anchor() RETURNS trigger LANGUAGE plpgsql
      SET search_path=pg_catalog,public AS $$ BEGIN
      IF OLD.execution_id IS NOT NULL THEN
        RAISE EXCEPTION 'first-fill anchor is immutable' USING ERRCODE='42501';
      END IF;
      RETURN NEW; END $$""")
    op.execute("REVOKE ALL ON FUNCTION guard_test_entry_anchor() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER immutable_test_entry_anchor BEFORE UPDATE ON "
        "bot_test_entry_anchors FOR EACH ROW EXECUTE FUNCTION "
        "guard_test_entry_anchor()"
    )


def downgrade() -> None:
    op.execute(
        "LOCK TABLE bot_test_strategy_configurations,bot_test_entry_anchors IN "
        "ACCESS EXCLUSIVE MODE"
    )
    op.execute("ALTER TABLE bot_test_strategy_configurations NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE bot_test_entry_anchors NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM bot_test_strategy_configurations)
        OR EXISTS(SELECT 1 FROM bot_test_entry_anchors) THEN
      RAISE EXCEPTION 'Paper test history prevents destructive downgrade'; END IF; END $$""")
    op.execute("DROP TABLE bot_test_entry_anchors")
    op.execute("DROP FUNCTION guard_test_entry_anchor()")
    op.execute("DROP TABLE bot_test_strategy_configurations")
