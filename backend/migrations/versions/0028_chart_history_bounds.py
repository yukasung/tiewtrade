# ruff: noqa: E501
"""Separate discoverable candle history from indicator retention."""

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE market_candle_demand
      ADD COLUMN history_start timestamptz,
      ADD COLUMN history_checked_at timestamptz,
      ADD CONSTRAINT market_history_bounds CHECK (
        (history_start IS NULL AND history_checked_at IS NULL) OR
        (history_start IS NOT NULL AND history_start >= '1970-01-01 UTC'::timestamptz
         AND history_start < desired_end AND history_checked_at IS NOT NULL)),
      DROP CONSTRAINT market_candle_demand_retention_check,
      ADD CONSTRAINT market_candle_demand_retention_check CHECK (
        (timeframe IN ('1w','1M') AND desired_start >= '1970-01-01 UTC'::timestamptz)
        OR (timeframe NOT IN ('1w','1M') AND desired_end-desired_start<=interval '365 days'))""")
    op.execute("""CREATE FUNCTION ensure_history_partition(p_base text,p_tf text,p_at timestamptz)
      RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      DECLARE lo timestamptz; hi timestamptz; name text;
      BEGIN
        IF p_tf NOT IN ('1w','1M') OR NOT EXISTS (
          SELECT 1 FROM public.market_candle_demand WHERE base=p_base AND quote='USDT'
          AND timeframe=p_tf AND history_start IS NOT NULL
          AND p_at>=history_start AND p_at<=clock_timestamp()) THEN
          RAISE EXCEPTION 'history partition outside discovered bounds';
        END IF;
        lo := date_trunc('month',p_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
        hi := (lo AT TIME ZONE 'UTC' + interval '1 month') AT TIME ZONE 'UTC';
        name := 'market_candles_' || to_char(lo AT TIME ZONE 'UTC','YYYYMM');
        PERFORM pg_advisory_xact_lock(728,extract(year FROM lo)::int*12+extract(month FROM lo)::int);
        IF to_regclass('public.' || name) IS NULL THEN
          EXECUTE format('CREATE TABLE public.%I PARTITION OF public.market_candles FOR VALUES FROM (%L) TO (%L)',name,lo,hi);
          EXECUTE format('GRANT SELECT ON public.%I TO tiewtrade_api',name);
          EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO tiewtrade_market_data',name);
        END IF;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION ensure_history_partition(text,text,timestamptz) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION ensure_history_partition(text,text,timestamptz) TO tiewtrade_market_data"
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM market_candle_demand WHERE history_start IS NOT NULL) THEN
        RAISE EXCEPTION 'discovered history exists; downgrade refused';
      END IF;
    END $$""")
    op.execute("DROP FUNCTION ensure_history_partition(text,text,timestamptz)")
    op.execute("""ALTER TABLE market_candle_demand DROP CONSTRAINT market_history_bounds,
      DROP COLUMN history_start, DROP COLUMN history_checked_at""")
    op.execute("""ALTER TABLE market_candle_demand
      DROP CONSTRAINT market_candle_demand_retention_check,
      ADD CONSTRAINT market_candle_demand_retention_check CHECK (
        (timeframe='1w' AND desired_start>=date_trunc(
          'week',(desired_end-interval '5 years') AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')
        OR (timeframe='1M' AND desired_start>=date_trunc(
          'month',(desired_end-interval '5 years') AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')
        OR (timeframe NOT IN ('1w','1M') AND desired_end-desired_start<=interval '365 days'))""")
