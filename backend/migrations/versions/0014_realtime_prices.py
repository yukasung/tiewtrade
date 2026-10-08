"""Durable fenced realtime observations and RLS connection slots."""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE market_price_feed (
      source text PRIMARY KEY CHECK(source='primary_spot'),
      generation bigint NOT NULL CHECK(generation>0), owner uuid NOT NULL,
      lease_until timestamptz NOT NULL, connected boolean NOT NULL DEFAULT false,
      last_failure_code text)""")
    op.execute("""CREATE TABLE market_latest_prices (
      source text NOT NULL REFERENCES market_price_feed(source),
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      amount tiewtrade_money_amount CHECK(amount>0), trade_id bigint CHECK(trade_id>=0),
      trade_at timestamptz, received_at timestamptz, observation_kind text
        CHECK(observation_kind IN ('STREAM','SNAPSHOT')),
      reconciled_generation bigint NOT NULL DEFAULT 0 CHECK(reconciled_generation>=0),
      revision bigint NOT NULL DEFAULT 1 CHECK(revision>0),
      effective_readiness text NOT NULL DEFAULT 'MISSING'
        CHECK(effective_readiness IN ('MISSING','RECOVERING','STALE','READY')),
      reason text, unavailable_since timestamptz, order_ambiguous_at timestamptz,
      PRIMARY KEY(source,base,quote),
      CHECK(quote='USDT' AND base IN ('BTC','ETH','SOL','XRP','DOGE')),
      CHECK((amount IS NULL AND trade_id IS NULL AND trade_at IS NULL
        AND received_at IS NULL AND observation_kind IS NULL) OR
        (amount IS NOT NULL AND trade_id IS NOT NULL AND trade_at IS NOT NULL
        AND received_at IS NOT NULL AND observation_kind IS NOT NULL)))""")
    # Persist initial absence even if the first producer never starts. The expired
    # marker cannot own a writer lease; normal fenced takeover creates generation 2.
    op.execute("""WITH initial AS (
      INSERT INTO market_price_feed
        (source,generation,owner,lease_until,connected,last_failure_code)
      VALUES ('primary_spot',1,'00000000-0000-0000-0000-000000000000',
        clock_timestamp(),false,'MISSING')
      RETURNING source,lease_until
    ) INSERT INTO market_latest_prices(source,base,quote,reason,unavailable_since)
      SELECT initial.source,pair.base,'USDT','MISSING',initial.lease_until
      FROM initial CROSS JOIN
        (VALUES ('BTC'),('ETH'),('SOL'),('XRP'),('DOGE')) AS pair(base)""")
    for table in ("market_price_feed", "market_latest_prices"):
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO tiewtrade_market_data")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api,tiewtrade_engine")
    op.execute("""CREATE TABLE market_price_connections (
      user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      slot smallint NOT NULL CHECK(slot BETWEEN 1 AND 3),
      connection_id uuid UNIQUE NOT NULL, lease_until timestamptz NOT NULL,
      PRIMARY KEY(user_id,slot))""")
    op.execute("ALTER TABLE market_price_connections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE market_price_connections FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY market_price_connections_self ON market_price_connections
      FOR ALL TO tiewtrade_api USING(user_id=tiewtrade_current_user_id())
      WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON market_price_connections TO tiewtrade_api")
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind
      CHECK(bucket_kind IN ('API_KEY_ADD','API_KEY_RETRY','PRICE_STREAM_HANDSHAKE'))""")


def downgrade() -> None:
    op.execute("DELETE FROM api_throttle WHERE bucket_kind='PRICE_STREAM_HANDSHAKE'")
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind
      CHECK(bucket_kind IN ('API_KEY_ADD','API_KEY_RETRY'))""")
    op.execute("DROP TABLE market_price_connections")
    op.execute("DROP TABLE market_latest_prices")
    op.execute("DROP TABLE market_price_feed")
