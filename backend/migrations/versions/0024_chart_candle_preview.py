"""Bounded public candle previews; no changes to durable indicator sources."""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE market_candle_feed_state (
      source text PRIMARY KEY CHECK(source='primary_spot'), owner uuid NOT NULL,
      epoch bigint NOT NULL CHECK(epoch>0), lease_until timestamptz NOT NULL,
      connected boolean NOT NULL DEFAULT false, bootstrapped boolean NOT NULL DEFAULT false,
      failure_code text, metadata jsonb NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(metadata)='object'
        AND octet_length(metadata::text)<=16384))""")
    op.execute("""INSERT INTO market_candle_feed_state(source,owner,epoch,lease_until)
      VALUES('primary_spot','00000000-0000-0000-0000-000000000000',1,clock_timestamp())""")
    op.execute("""CREATE TABLE market_candle_preview (
      source text NOT NULL REFERENCES market_candle_feed_state(source),
      base tiewtrade_unit_code NOT NULL, quote tiewtrade_unit_code NOT NULL,
      timeframe text NOT NULL CHECK(timeframe IN ('1m','5m','15m','1h','4h','1d')),
      open_at timestamptz NOT NULL, end_at timestamptz NOT NULL CHECK(end_at>open_at),
      open tiewtrade_money_amount NOT NULL CHECK(open>0),
      high tiewtrade_money_amount NOT NULL CHECK(high>0),
      low tiewtrade_money_amount NOT NULL CHECK(low>0),
      close tiewtrade_money_amount NOT NULL CHECK(close>0),
      volume tiewtrade_money_amount NOT NULL CHECK(volume>=0),
      finality text NOT NULL CHECK(finality IN ('OPEN','UNCONFIRMED')),
      event_at timestamptz NOT NULL, received_at timestamptz NOT NULL,
      epoch bigint NOT NULL CHECK(epoch>0), revision bigint NOT NULL CHECK(revision>0),
      CHECK(quote='USDT' AND base IN ('BTC','ETH','SOL','XRP','DOGE')),
      CHECK(low<=open AND low<=close AND high>=open AND high>=close AND low<=high),
      PRIMARY KEY(source,base,quote,timeframe,open_at))""")
    for table in ("market_candle_feed_state", "market_candle_preview"):
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO tiewtrade_market_data")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api")


def downgrade() -> None:
    op.execute("DROP TABLE market_candle_preview")
    op.execute("DROP TABLE market_candle_feed_state")
