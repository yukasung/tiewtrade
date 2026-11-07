"""Extend native candle schedules and catalog readiness with three-minute bars."""

import re
from pathlib import Path

from alembic import op
from alembic.util import load_python_file
from sqlalchemy import text

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

# Reuse immutable migration helpers rather than duplicating checked DDL replacement.
_catalog = load_python_file(Path(__file__).parent, "0040_supported_symbol_catalog.py")
_calendar = load_python_file(Path(__file__).parent, "0026_week_month_timeframes.py")
_OLD_VALUES = "('1m','5m','15m','1h','4h','1d','1w','1M')"
_NEW_VALUES = "('1m','3m','5m','15m','1h','4h','1d','1w','1M')"
_STATE_TABLES = (
    "indicator_heads",
    "indicator_numeric_failures",
    "indicator_source_changes",
    "indicator_generations",
    "indicator_build_jobs",
    "market_candle_preview",
    "market_candle_demand",
    "market_candles",
    "supported_symbol_timeframe_readiness",
)
_ACTIVATE = (
    "activate_supported_symbol(uuid,text,text,bigint,uuid,text,"
    "timestamp with time zone,timestamp with time zone,jsonb,text)"
)


def _lock() -> None:
    # Same stopped-writer/table-lock boundary as 0030; no source facts are changed.
    tables = ("indicator_build_slot", "market_candle_feed_state", *_STATE_TABLES)
    op.execute(
        "LOCK TABLE " + ",".join(f"public.{t}" for t in tables) + " IN ACCESS EXCLUSIVE MODE"
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.indicator_build_slot WHERE state<>'IDLE') THEN
        RAISE EXCEPTION 'INDICATOR_WRITER_NOT_DRAINED';
      END IF;
    END $$""")


def _functions(adding: bool) -> None:
    replacements: dict[str, tuple[tuple[str, str], ...]] = {
        "market_timeframe_floor(text,timestamptz)": (
            ("WHEN '1m' THEN 60 WHEN '5m'", "WHEN '1m' THEN 60 WHEN '3m' THEN 180 WHEN '5m'"),
        ),
        "market_timeframe_advance(text,timestamptz,integer)": (
            ("WHEN '1m' THEN 60 WHEN '5m'", "WHEN '1m' THEN 60 WHEN '3m' THEN 180 WHEN '5m'"),
        ),
        "market_timeframe_slots(text,timestamptz,timestamptz)": (
            ("WHEN '1m' THEN 60 WHEN '5m'", "WHEN '1m' THEN 60 WHEN '3m' THEN 180 WHEN '5m'"),
        ),
        "indicator_calculation_bounds(text,timestamptz)": ((_OLD_VALUES, _NEW_VALUES),),
        "seed_indicator_build_jobs()": (
            ("VALUES('1m',60),('5m',300)", "VALUES('1m',60),('3m',180),('5m',300)"),
        ),
        "record_supported_symbol_timeframe_readiness(text,text,bigint,text,timestamptz)": (
            (_OLD_VALUES, _NEW_VALUES),
        ),
        _ACTIVATE: (("ready_timeframe_count<>8", "ready_timeframe_count<>9"),),
        "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)": (
            ("count(*)*8", "count(*)*9"),
        ),
        "claim_indicator_build_job(uuid)": (
            ("f.base<eligible.base)*8", "f.base<eligible.base)*9"),
            ("f.base<j.base)*8", "f.base<j.base)*9"),
            ("('ACTIVE','PREPARING'))*8)-1", "('ACTIVE','PREPARING'))*9)-1"),
            ("('ACTIVE','PREPARING'))*8))", "('ACTIVE','PREPARING'))*9))"),
            (
                "CASE eligible.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1\n"
                "                WHEN '15m' THEN 2 WHEN '1h' THEN 3 WHEN '4h' THEN 4\n"
                "                WHEN '1d' THEN 5 WHEN '1w' THEN 6 ELSE 7 END",
                "CASE eligible.timeframe WHEN '1m' THEN 0 WHEN '3m' THEN 1 WHEN '5m' THEN 2\n"
                "                WHEN '15m' THEN 3 WHEN '1h' THEN 4 WHEN '4h' THEN 5\n"
                "                WHEN '1d' THEN 6 WHEN '1w' THEN 7 ELSE 8 END",
            ),
            (
                "CASE j.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1 WHEN '15m' THEN 2\n"
                "             WHEN '1h' THEN 3 WHEN '4h' THEN 4 WHEN '1d' THEN 5\n"
                "             WHEN '1w' THEN 6 ELSE 7 END",
                "CASE j.timeframe WHEN '1m' THEN 0 WHEN '3m' THEN 1 WHEN '5m' THEN 2\n"
                "             WHEN '15m' THEN 3 WHEN '1h' THEN 4 WHEN '4h' THEN 5\n"
                "             WHEN '1d' THEN 6 WHEN '1w' THEN 7 ELSE 8 END",
            ),
        ),
    }
    for signature, pairs in replacements.items():
        selected = pairs if adding else tuple((after, before) for before, after in pairs)
        _catalog._replace_function(signature, selected)


def _checks(adding: bool) -> None:
    values = _NEW_VALUES if adding else _OLD_VALUES
    _calendar._replace_timeframe_checks(values)
    op.execute(
        "ALTER TABLE public.supported_symbol_timeframe_readiness "
        "DROP CONSTRAINT supported_symbol_timeframe_value"
    )
    op.execute(
        "ALTER TABLE public.supported_symbol_timeframe_readiness "
        f"ADD CONSTRAINT supported_symbol_timeframe_value CHECK(timeframe IN {values})"
    )
    op.execute(
        "ALTER TABLE public.supported_symbol_readiness "
        "DROP CONSTRAINT supported_symbol_ready_timeframes"
    )
    maximum = 9 if adding else 8
    op.execute(
        "ALTER TABLE public.supported_symbol_readiness "
        "ADD CONSTRAINT supported_symbol_ready_timeframes "
        f"CHECK(ready_timeframe_count BETWEEN 0 AND {maximum})"
    )
    before = "WHEN '1m'::text THEN 60"
    after = "WHEN '1m'::text THEN 60 WHEN '3m'::text THEN 180"
    for table in ("market_candles", "market_candle_preview"):
        name = f"{table}_schedule_check"
        definition: str = (
            op.get_bind()
            .execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conrelid=CAST(:table AS regclass) AND conname=:name"
                ),
                {"table": f"public.{table}", "name": name},
            )
            .scalar_one()
        )
        if adding:
            count = definition.count(before)
            definition = definition.replace(before, after)
        else:
            definition, count = re.subn(r"WHEN '3m'::text THEN 180\s*", "", definition)
        if count != 3:
            raise RuntimeError(f"unexpected candle schedule constraint: {table}")
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {name} " + definition)


def upgrade() -> None:
    _lock()
    op.execute("SELECT public.begin_indicator_source_maintenance()")
    _functions(True)
    _checks(True)


def downgrade() -> None:
    _lock()
    connection = op.get_bind()
    for table in _STATE_TABLES:
        if connection.execute(
            text(f"SELECT EXISTS(SELECT 1 FROM public.{table} WHERE timeframe='3m')")
        ).scalar_one():
            raise RuntimeError("THREE_MINUTE_DOWNGRADE_NOT_DRAINED")
    if connection.execute(
        text("""SELECT EXISTS(
      SELECT 1 FROM public.market_candle_feed_state,
      LATERAL jsonb_object_keys(metadata) AS k(value) WHERE k.value LIKE '%/3m')""")
    ).scalar_one():
        raise RuntimeError("THREE_MINUTE_DOWNGRADE_NOT_DRAINED")
    # Guard before maintenance: maintenance removes heads, which are part of inventory.
    op.execute("SELECT public.begin_indicator_source_maintenance()")
    _checks(False)
    _functions(False)
