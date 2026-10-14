# ruff: noqa: E501
"""Add native UTC week/month candle schedules without rewriting observations."""

from datetime import UTC, datetime, timedelta

from alembic import op
from sqlalchemy import text

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

_ENUM = "('1m','5m','15m','1h','4h','1d','1w','1M')"
_OLD_ENUM = "('1m','5m','15m','1h','4h','1d')"
_TF_TABLES = (
    "market_candles",
    "market_candle_demand",
    "market_candle_preview",
    "indicator_build_jobs",
    "indicator_generations",
)


def _definition(signature: str) -> str:
    value = (
        op.get_bind()
        .execute(
            text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
            {"signature": f"public.{signature}"},
        )
        .scalar_one()
    )
    if value is None:
        raise RuntimeError(f"missing function: {signature}")
    return value


def _replace_function(signature: str, replacements: tuple[tuple[str, str], ...]) -> None:
    definition = _definition(signature)
    for before, after in replacements:
        if definition.count(before) != 1:
            raise RuntimeError(f"unexpected function definition: {signature}")
        definition = definition.replace(before, after)
    op.execute(definition)


def _drop_check_containing(table: str, fragments: tuple[str, ...]) -> None:
    rows = (
        op.get_bind()
        .execute(
            text(
                """SELECT conname,pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE conrelid=CAST(:table AS regclass) AND contype='c'"""
            ),
            {"table": f"public.{table}"},
        )
        .mappings()
    )
    matches = [
        row["conname"]
        for row in rows
        if all(fragment.lower() in row["definition"].lower() for fragment in fragments)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"unexpected check constraint on {table}: {fragments}")
    name = matches[0].replace('"', '""')
    op.execute(f'ALTER TABLE public.{table} DROP CONSTRAINT "{name}"')


_FLOOR = """CREATE FUNCTION market_timeframe_floor(p_timeframe text,p_moment timestamptz)
RETURNS timestamptz LANGUAGE plpgsql IMMUTABLE STRICT
SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE seconds integer;
BEGIN
  IF NOT isfinite(p_moment) THEN RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='TIMEFRAME_INVALID'; END IF;
  IF p_timeframe='1w' THEN
    RETURN date_trunc('week',p_moment AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
  ELSIF p_timeframe='1M' THEN
    RETURN date_trunc('month',p_moment AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';
  END IF;
  seconds:=CASE p_timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
    WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400 END;
  IF seconds IS NULL THEN RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='TIMEFRAME_INVALID'; END IF;
  RETURN date_bin(make_interval(secs=>seconds),p_moment,'1970-01-01 UTC'::timestamptz);
END $$"""

_ADVANCE = """CREATE FUNCTION market_timeframe_advance(
  p_timeframe text,p_open timestamptz,p_slots integer) RETURNS timestamptz
LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE seconds integer;
BEGIN
  IF p_open IS DISTINCT FROM public.market_timeframe_floor(p_timeframe,p_open) THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='TIMEFRAME_UNALIGNED';
  END IF;
  IF p_timeframe='1M' THEN RETURN p_open+make_interval(months=>p_slots); END IF;
  seconds:=CASE p_timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
    WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400
    WHEN '1w' THEN 604800 END;
  IF seconds IS NULL THEN RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='TIMEFRAME_INVALID'; END IF;
  RETURN p_open+make_interval(secs=>seconds*p_slots);
END $$"""

_SLOTS = """CREATE FUNCTION market_timeframe_slots(
  p_timeframe text,p_start timestamptz,p_end timestamptz) RETURNS integer
LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE seconds integer; result bigint;
BEGIN
  IF p_start IS DISTINCT FROM public.market_timeframe_floor(p_timeframe,p_start)
    OR p_end IS DISTINCT FROM public.market_timeframe_floor(p_timeframe,p_end) OR p_end<p_start THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='TIMEFRAME_UNALIGNED';
  END IF;
  IF p_timeframe='1M' THEN
    result:=(extract(year FROM p_end)::integer-extract(year FROM p_start)::integer)*12
      +extract(month FROM p_end)::integer-extract(month FROM p_start)::integer;
  ELSE
    seconds:=CASE p_timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
      WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400
      WHEN '1w' THEN 604800 END;
    IF seconds IS NULL THEN RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='TIMEFRAME_INVALID'; END IF;
    result:=extract(epoch FROM p_end-p_start)::bigint/seconds;
  END IF;
  IF result>2147483647 THEN RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='TIMEFRAME_RANGE'; END IF;
  RETURN result::integer;
END $$"""

_BOUNDS = """CREATE OR REPLACE FUNCTION indicator_calculation_bounds(
  p_timeframe text,p_as_of timestamptz)
RETURNS TABLE(calculation_start timestamptz,calculation_end timestamptz)
LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE cutoff timestamptz;
BEGIN
  IF p_timeframe NOT IN ('1m','5m','15m','1h','4h','1d','1w','1M')
    OR NOT isfinite(p_as_of) THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_BOUNDS_INVALID';
  END IF;
  cutoff:=p_as_of-CASE WHEN p_timeframe IN ('1w','1M') THEN interval '5 years'
    ELSE interval '365 days' END;
  calculation_start:=public.market_timeframe_floor(p_timeframe,cutoff);
  IF calculation_start<cutoff THEN
    calculation_start:=public.market_timeframe_advance(p_timeframe,calculation_start,1);
  END IF;
  calculation_end:=public.market_timeframe_floor(p_timeframe,p_as_of);
  RETURN NEXT;
END $$"""

_OLD_BOUNDS = """CREATE OR REPLACE FUNCTION indicator_calculation_bounds(
  p_timeframe text,p_as_of timestamptz)
RETURNS TABLE(calculation_start timestamptz,calculation_end timestamptz)
LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public SET TimeZone='UTC' AS $$
DECLARE width interval;
BEGIN
  width:=make_interval(secs=>CASE p_timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300
    WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400 END);
  IF width IS NULL OR NOT isfinite(p_as_of) THEN
    RAISE EXCEPTION USING ERRCODE='TT015',MESSAGE='INDICATOR_BOUNDS_INVALID';
  END IF;
  calculation_start:=date_bin(width,p_as_of-interval '365 days','1970-01-01 UTC');
  IF calculation_start<p_as_of-interval '365 days' THEN calculation_start:=calculation_start+width; END IF;
  calculation_end:=date_bin(width,p_as_of,'1970-01-01 UTC');
  RETURN NEXT;
END $$"""


def _replace_timeframe_checks(values: str) -> None:
    for table in _TF_TABLES:
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {table}_timeframe_check")
        op.execute(
            f"ALTER TABLE public.{table} ADD CONSTRAINT {table}_timeframe_check "
            f"CHECK(timeframe IN {values})"
        )


def upgrade() -> None:
    _replace_timeframe_checks(_ENUM)
    for statement in (_FLOOR, _ADVANCE, _SLOTS):
        op.execute(statement)
    _drop_check_containing("market_candles", ("end_at - open_at", "extract(epoch"))
    _drop_check_containing("market_candles", ("extract(epoch from open_at)", "mod"))
    op.execute("""ALTER TABLE public.market_candles ADD CONSTRAINT market_candles_schedule_check
      CHECK(open_at=CASE timeframe
        WHEN '1w' THEN date_trunc('week',open_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        WHEN '1M' THEN date_trunc('month',open_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
        ELSE to_timestamp(floor(extract(epoch FROM open_at)/(CASE timeframe
          WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
          WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END))*(CASE timeframe
          WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
          WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END)) END
      AND end_at=CASE timeframe WHEN '1M' THEN open_at+interval '1 month'
        WHEN '1w' THEN open_at+interval '7 days' ELSE open_at+make_interval(secs=>CASE timeframe
          WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
          WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END) END) NOT VALID""")
    op.execute(
        "ALTER TABLE public.market_candles VALIDATE CONSTRAINT market_candles_schedule_check"
    )

    _drop_check_containing("market_candle_demand", ("desired_end", "desired_start", "365 days"))
    op.execute("""ALTER TABLE public.market_candle_demand
      ADD CONSTRAINT market_candle_demand_retention_check CHECK(
        (timeframe='1w' AND desired_start>=date_trunc(
          'week',(desired_end-interval '5 years') AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')
        OR (timeframe='1M' AND desired_start>=date_trunc(
          'month',(desired_end-interval '5 years') AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')
        OR (timeframe NOT IN ('1w','1M')
          AND desired_end-desired_start<=interval '365 days'))""")
    op.execute("""ALTER TABLE public.market_candle_preview
      ADD CONSTRAINT market_candle_preview_schedule_check CHECK(
        open_at=CASE timeframe
          WHEN '1w' THEN date_trunc('week',open_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
          WHEN '1M' THEN date_trunc('month',open_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
          ELSE to_timestamp(floor(extract(epoch FROM open_at)/(CASE timeframe
            WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
            WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END))*(CASE timeframe
            WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
            WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END)) END
        AND end_at=CASE timeframe WHEN '1M' THEN open_at+interval '1 month'
          WHEN '1w' THEN open_at+interval '7 days' ELSE open_at+make_interval(secs=>CASE timeframe
            WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
            WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END) END) NOT VALID""")
    op.execute(
        "ALTER TABLE public.market_candle_preview VALIDATE CONSTRAINT market_candle_preview_schedule_check"
    )

    now = datetime.now(UTC)
    start = now.replace(year=now.year - 5, day=1, hour=0, minute=0, second=0, microsecond=0)
    stop = now.replace(year=now.year + 1, month=now.month % 12 + 1, day=1)
    if now.month == 12:
        stop = stop.replace(year=now.year + 2, month=1)
    while start < stop:
        following = start.replace(year=start.year + start.month // 12, month=start.month % 12 + 1)
        name = f"market_candles_{start:%Y%m}"
        op.execute(f"""CREATE TABLE IF NOT EXISTS public.{name} PARTITION OF public.market_candles
          FOR VALUES FROM ('{start.isoformat()}') TO ('{following.isoformat()}')""")
        op.execute(f"GRANT SELECT ON public.{name} TO tiewtrade_api")
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON public.{name} TO tiewtrade_market_data")
        start = following

    op.execute(_BOUNDS)
    _replace_function(
        "seed_indicator_build_jobs()",
        (("('4h',14400),('1d',86400)", "('4h',14400),('1d',86400),('1w',604800),('1M',NULL)"),),
    )
    _replace_function(
        "append_indicator_checkpoint(uuid,bigint,uuid,uuid,uuid,uuid,timestamptz,jsonb)",
        (
            ("; seconds integer; expected timestamptz", "; expected timestamptz"),
            (
                "seconds:=CASE g.timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300\n            WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END;\n          expected:=least(g.calculation_start+make_interval(secs=>seconds*1000)*g.checkpoint_count,\n            g.calculation_end);",
                "expected:=least(public.market_timeframe_advance(g.timeframe,g.calculation_start,\n            1000*g.checkpoint_count),g.calculation_end);",
            ),
        ),
    )
    _replace_function(
        "publish_indicator_generation(uuid,bigint,uuid,uuid,uuid,uuid,boolean)",
        (
            ("seconds integer; expected_count integer", "expected_count integer"),
            (
                "seconds:=CASE g.timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300\n      WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END;\n    expected_count:=ceil(extract(epoch FROM (g.calculation_end-g.calculation_start))\n      /(seconds*1000))::integer+1;",
                "expected_count:=ceil(public.market_timeframe_slots(g.timeframe,g.calculation_start,\n      g.calculation_end)/1000.0)::integer+1;",
            ),
            (
                "g.calculation_start+make_interval(secs=>seconds*1000)*n,g.calculation_end",
                "public.market_timeframe_advance(g.timeframe,g.calculation_start,1000*n),\n            g.calculation_end",
            ),
        ),
    )
    for signature in (
        "market_timeframe_floor(text,timestamptz)",
        "market_timeframe_advance(text,timestamptz,integer)",
        "market_timeframe_slots(text,timestamptz,timestamptz)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION public.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION public.{signature} TO tiewtrade_indicator_builder")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.market_candles WHERE timeframe IN ('1w','1M'))
        OR EXISTS(SELECT 1 FROM public.market_candle_demand WHERE timeframe IN ('1w','1M'))
        OR EXISTS(SELECT 1 FROM public.market_candle_preview WHERE timeframe IN ('1w','1M'))
        OR EXISTS(SELECT 1 FROM public.indicator_build_jobs WHERE timeframe IN ('1w','1M'))
        OR EXISTS(SELECT 1 FROM public.indicator_generations WHERE timeframe IN ('1w','1M'))
      THEN RAISE EXCEPTION 'WEEK_MONTH_DOWNGRADE_NOT_DRAINED'; END IF;
    END $$""")
    now = datetime.now(UTC)
    start = now.replace(year=now.year - 5, day=1, hour=0, minute=0, second=0, microsecond=0)
    original_start = (now - timedelta(days=365)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    while start < original_start:
        following = start.replace(year=start.year + start.month // 12, month=start.month % 12 + 1)
        name = f"market_candles_{start:%Y%m}"
        op.execute(f"""DO $$ BEGIN
          IF to_regclass('public.{name}') IS NOT NULL
            AND EXISTS(SELECT 1 FROM public.{name}) THEN
            RAISE EXCEPTION 'WEEK_MONTH_DOWNGRADE_HISTORY_NOT_DRAINED';
          END IF;
        END $$""")
        op.execute(f"DROP TABLE IF EXISTS public.{name}")
        start = following
    _replace_function(
        "publish_indicator_generation(uuid,bigint,uuid,uuid,uuid,uuid,boolean)",
        (
            ("expected_count integer", "seconds integer; expected_count integer"),
            (
                "expected_count:=ceil(public.market_timeframe_slots(g.timeframe,g.calculation_start,\n      g.calculation_end)/1000.0)::integer+1;",
                "seconds:=CASE g.timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300\n      WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END;\n    expected_count:=ceil(extract(epoch FROM (g.calculation_end-g.calculation_start))\n      /(seconds*1000))::integer+1;",
            ),
            (
                "public.market_timeframe_advance(g.timeframe,g.calculation_start,1000*n),\n            g.calculation_end",
                "g.calculation_start+make_interval(secs=>seconds*1000)*n,g.calculation_end",
            ),
        ),
    )
    _replace_function(
        "append_indicator_checkpoint(uuid,bigint,uuid,uuid,uuid,uuid,timestamptz,jsonb)",
        (
            ("; expected timestamptz", "; seconds integer; expected timestamptz"),
            (
                "expected:=least(public.market_timeframe_advance(g.timeframe,g.calculation_start,\n            1000*g.checkpoint_count),g.calculation_end);",
                "seconds:=CASE g.timeframe WHEN '1m' THEN 60 WHEN '5m' THEN 300\n            WHEN '15m' THEN 900 WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END;\n          expected:=least(g.calculation_start+make_interval(secs=>seconds*1000)*g.checkpoint_count,\n            g.calculation_end);",
            ),
        ),
    )
    _replace_function(
        "seed_indicator_build_jobs()",
        (("('4h',14400),('1d',86400),('1w',604800),('1M',NULL)", "('4h',14400),('1d',86400)"),),
    )
    op.execute(_OLD_BOUNDS)
    op.execute(
        "ALTER TABLE public.market_candle_demand DROP CONSTRAINT market_candle_demand_retention_check"
    )
    op.execute("""ALTER TABLE public.market_candle_demand ADD CONSTRAINT
      market_candle_demand_retention_check CHECK(desired_end-desired_start<=interval '365 days')""")
    for signature in (
        "market_timeframe_slots(text,timestamptz,timestamptz)",
        "market_timeframe_advance(text,timestamptz,integer)",
        "market_timeframe_floor(text,timestamptz)",
    ):
        op.execute(f"DROP FUNCTION public.{signature}")

    op.execute(
        "ALTER TABLE public.market_candle_preview DROP CONSTRAINT market_candle_preview_schedule_check"
    )
    op.execute("ALTER TABLE public.market_candles DROP CONSTRAINT market_candles_schedule_check")
    op.execute("""ALTER TABLE public.market_candles ADD CONSTRAINT market_candles_span_check
      CHECK(extract(epoch FROM end_at-open_at)=CASE timeframe
        WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
        WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400 END)""")
    op.execute("""ALTER TABLE public.market_candles ADD CONSTRAINT market_candles_alignment_check
      CHECK(mod(extract(epoch FROM open_at),CASE timeframe
        WHEN '1m' THEN 60 WHEN '5m' THEN 300 WHEN '15m' THEN 900
        WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 WHEN '1d' THEN 86400 END)=0)""")
    _replace_timeframe_checks(_OLD_ENUM)
