"""Partitioned public candle observations and durable demand (F-09)."""

from datetime import UTC, datetime, timedelta

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE market_candles (
        source text NOT NULL CHECK (source = 'primary_spot'),
        base tiewtrade_unit_code NOT NULL,
        quote tiewtrade_unit_code NOT NULL,
        timeframe text NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','1d')),
        open_at timestamptz NOT NULL,
        end_at timestamptz NOT NULL,
        open tiewtrade_money_amount NOT NULL CHECK (open > 0),
        high tiewtrade_money_amount NOT NULL CHECK (high > 0),
        low tiewtrade_money_amount NOT NULL CHECK (low > 0),
        close tiewtrade_money_amount NOT NULL CHECK (close > 0),
        volume tiewtrade_money_amount NOT NULL CHECK (volume >= 0),
        finality text NOT NULL CHECK (finality IN ('UNCONFIRMED','OPEN','CLOSED')),
        observed_at timestamptz NOT NULL,
        fetch_started_at timestamptz NOT NULL,
        last_checked_at timestamptz NOT NULL,
        ingestion_generation bigint NOT NULL CHECK (ingestion_generation > 0),
        PRIMARY KEY (source,base,quote,timeframe,open_at),
        CHECK (quote='USDT' AND base IN ('BTC','ETH','SOL','XRP','DOGE')),
        CHECK (base <> quote AND base = upper(btrim(base)) AND quote = upper(btrim(quote))),
        CHECK (high >= open AND high >= close AND low <= open AND low <= close AND high >= low),
        CHECK (extract(epoch FROM end_at - open_at) = CASE timeframe
            WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
            WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400 END),
        CHECK (mod(extract(epoch FROM open_at), CASE timeframe
            WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
            WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400 END) = 0),
        CHECK (fetch_started_at <= last_checked_at)
    ) PARTITION BY RANGE (open_at)""")
    op.execute("""CREATE TABLE market_candle_demand (
        source text NOT NULL DEFAULT 'primary_spot' CHECK (source = 'primary_spot'),
        base tiewtrade_unit_code NOT NULL,
        quote tiewtrade_unit_code NOT NULL,
        timeframe text NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','1d')),
        desired_start timestamptz NOT NULL,
        desired_end timestamptz NOT NULL,
        refresh_requested_at timestamptz,
        requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        leased_start timestamptz,
        leased_end timestamptz,
        status text NOT NULL DEFAULT 'PENDING'
          CHECK (status IN ('PENDING','RUNNING','COMPLETE','UNAVAILABLE','FAILED')),
        phase text NOT NULL DEFAULT 'FORWARD' CHECK (phase IN ('FORWARD','REPAIR','REFRESH')),
        cursor timestamptz,
        repair_cursor timestamptz,
        repair_pass integer NOT NULL DEFAULT 0 CHECK (repair_pass BETWEEN 0 AND 2),
        refresh_as_of timestamptz,
        refresh_cursor timestamptz,
        refresh_served_at timestamptz,
        generation bigint NOT NULL DEFAULT 0 CHECK (generation >= 0),
        worker text,
        token uuid,
        lease_until timestamptz,
        fetch_unit_id uuid,
        fetch_start timestamptz,
        fetch_end timestamptz,
        fetch_started_at timestamptz,
        attemptcount integer NOT NULL DEFAULT 0 CHECK (attemptcount BETWEEN 0 AND 3),
        next_attempt_at timestamptz NOT NULL DEFAULT '-infinity',
        checked_at timestamptz,
        failure_code text CHECK (failure_code IN ('SOURCE_FAILURE','PARTITION_UNAVAILABLE',
            'GAP_REPAIR_EXHAUSTED','REFRESH_INCOMPLETE','SOURCE_PROTOCOL','SOURCE_REJECTED')),
        PRIMARY KEY (source,base,quote,timeframe),
        CHECK (quote='USDT' AND base IN ('BTC','ETH','SOL','XRP','DOGE')),
        CHECK (base <> quote AND base = upper(btrim(base)) AND quote = upper(btrim(quote))),
        CHECK (desired_start < desired_end),
        CHECK (desired_end - desired_start <= interval '365 days'),
        CHECK ((fetch_unit_id IS NULL AND fetch_start IS NULL AND fetch_end IS NULL)
          OR (fetch_unit_id IS NOT NULL AND fetch_start IS NOT NULL AND fetch_end IS NOT NULL
              AND fetch_start < fetch_end)),
        CHECK ((token IS NULL AND worker IS NULL AND lease_until IS NULL)
          OR (token IS NOT NULL AND worker IS NOT NULL AND lease_until IS NOT NULL))
    )""")
    for table in ("market_candles", "market_candle_demand"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO tiewtrade_market_data")
        op.execute(f"GRANT SELECT ON {table} TO tiewtrade_api")
    columns = (
        "source,base,quote,timeframe,desired_start,desired_end,refresh_requested_at,requested_at"
    )
    op.execute(f"GRANT INSERT ({columns}) ON market_candle_demand TO tiewtrade_api")
    op.execute("""GRANT UPDATE (desired_start,desired_end,refresh_requested_at,requested_at)
        ON market_candle_demand TO tiewtrade_api""")
    now = datetime.now(UTC)
    start = (now - timedelta(days=365)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_year = now.year + (now.month + 12) // 12
    end_month = (now.month + 12) % 12 + 1
    stop = now.replace(year=end_year, month=end_month, day=1)
    while start < stop:
        next_month = start.replace(year=start.year + start.month // 12, month=start.month % 12 + 1)
        name = f"market_candles_{start:%Y%m}"
        op.execute(f"""CREATE TABLE {name} PARTITION OF market_candles
          FOR VALUES FROM ('{start.isoformat()}') TO ('{next_month.isoformat()}')""")
        op.execute(f"GRANT SELECT ON {name} TO tiewtrade_api")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {name} TO tiewtrade_market_data")
        start = next_month


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM market_candles) OR EXISTS (SELECT 1 FROM market_candle_demand)
        THEN RAISE EXCEPTION 'market data populated; downgrade refused'; END IF;
    END $$""")
    op.execute("DROP TABLE market_candle_demand")
    op.execute("DROP TABLE market_candles")
