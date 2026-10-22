"""Restrict the development market catalog to BTC/USDT and ETH/USDT."""

from alembic import op
from sqlalchemy import text

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

_TRANSITION = "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)"
_SEED = "seed_indicator_build_jobs()"
_CLAIM = "claim_indicator_build_job(uuid)"
_SUPPORTED = "('BTC','ETH')"
_LEGACY = "('BTC','ETH','SOL','XRP','DOGE')"
_SUPPORTED_ROWS = {
    table: f"SELECT * FROM public.{table} WHERE base IN ('BTC','ETH')"
    for table in (
        "market_candles",
        "market_candle_demand",
        "market_latest_prices",
        "market_candle_preview",
        "indicator_build_jobs",
        "indicator_generations",
        "indicator_heads",
        "indicator_source_changes",
    )
} | {
    "indicator_retry_requests": """SELECT r.* FROM public.indicator_retry_requests r
      JOIN public.indicator_build_jobs j ON j.id=r.job_id WHERE j.base IN ('BTC','ETH')""",
    "indicator_checkpoints": """SELECT c.* FROM public.indicator_checkpoints c
      JOIN public.indicator_generations g ON g.id=c.generation_id
      WHERE g.base IN ('BTC','ETH')""",
}


def _replace_function_fragments(signature: str, replacements: tuple[tuple[str, str], ...]) -> None:
    connection = op.get_bind()
    definition: str | None = connection.execute(
        text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
        {"signature": f"public.{signature}"},
    ).scalar_one()
    if definition is None:
        raise RuntimeError(f"missing function: {signature}")
    for before, after in replacements:
        if definition.count(before) != 1:
            raise RuntimeError(f"unexpected function definition: {signature}")
        definition = definition.replace(before, after)
    op.execute(definition)


def _replace_pair_constraint(table: str, name: str, bases: str) -> None:
    op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT {name}")
    op.execute(
        f"ALTER TABLE public.{table} ADD CONSTRAINT {name} CHECK (quote='USDT' AND base IN {bases})"
    )


def _supported_digests() -> dict[str, tuple[int, str]]:
    connection = op.get_bind()
    result: dict[str, tuple[int, str]] = {}
    for name, query in _SUPPORTED_ROWS.items():
        count, digest = connection.execute(
            text(f"""WITH rows AS ({query}) SELECT count(*),
              coalesce(md5(string_agg(md5(row_to_json(rows)::text),''
                ORDER BY md5(row_to_json(rows)::text))),md5('')) FROM rows""")
        ).one()
        result[name] = (int(count), str(digest))
    return result


def upgrade() -> None:
    op.execute("""LOCK TABLE public.indicator_build_slot,
      public.indicator_heads, public.indicator_retry_requests,
      public.indicator_checkpoints, public.indicator_generations,
      public.indicator_build_jobs, public.indicator_source_changes,
      public.market_candle_preview, public.market_candle_feed_state,
      public.market_candle_demand, public.market_candles,
      public.market_latest_prices, public.market_price_feed
      IN ACCESS EXCLUSIVE MODE""")
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM public.indicator_build_slot WHERE state<>'IDLE') THEN
        RAISE EXCEPTION 'INDICATOR_WRITER_NOT_DRAINED';
      END IF;
    END $$""")
    supported_before = _supported_digests()
    op.execute("SELECT public.begin_indicator_source_maintenance()")

    op.execute("DELETE FROM public.indicator_heads WHERE base NOT IN ('BTC','ETH')")
    op.execute("""DELETE FROM public.indicator_retry_requests r USING
      public.indicator_build_jobs j WHERE r.job_id=j.id AND j.base NOT IN ('BTC','ETH')""")
    op.execute("""UPDATE public.indicator_build_jobs SET current_candidate=NULL
      WHERE base NOT IN ('BTC','ETH')""")
    op.execute("DELETE FROM public.indicator_generations WHERE base NOT IN ('BTC','ETH')")
    op.execute("DELETE FROM public.indicator_build_jobs WHERE base NOT IN ('BTC','ETH')")
    op.execute("DELETE FROM public.market_candle_preview WHERE base NOT IN ('BTC','ETH')")
    op.execute("DELETE FROM public.market_candle_demand WHERE base NOT IN ('BTC','ETH')")
    op.execute("DELETE FROM public.market_candles WHERE base NOT IN ('BTC','ETH')")
    # Candle DELETE triggers publish source-change rows; clear those after source removal.
    op.execute("DELETE FROM public.indicator_source_changes WHERE base NOT IN ('BTC','ETH')")
    op.execute("DELETE FROM public.market_latest_prices WHERE base NOT IN ('BTC','ETH')")
    op.execute("""UPDATE public.market_candle_feed_state
      SET connected=false,bootstrapped=false,metadata='{}'::jsonb,
          failure_code=NULL""")
    op.execute("UPDATE public.market_price_feed SET connected=false")

    # Flush the deferrable job -> current generation FK before altering either table.
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")

    for table, name in (
        ("market_candles", "market_candles_check"),
        ("market_candle_demand", "market_candle_demand_check"),
        ("market_latest_prices", "market_latest_prices_check"),
        ("market_candle_preview", "market_candle_preview_check1"),
        ("indicator_build_jobs", "indicator_build_jobs_base_check"),
        ("indicator_generations", "indicator_generations_base_check"),
    ):
        _replace_pair_constraint(table, name, _SUPPORTED)
    _replace_function_fragments(_TRANSITION, (("ready_count<>40", "ready_count<>16"),))
    _replace_function_fragments(
        _SEED,
        (
            (
                "FROM (VALUES('BTC'),('DOGE'),('ETH'),('SOL'),('XRP')) b(base)",
                "FROM (VALUES('BTC'),('ETH')) b(base)",
            ),
        ),
    )
    _replace_function_fragments(
        _CLAIM,
        (
            (
                "CASE eligible.base WHEN 'BTC' THEN 0 WHEN 'DOGE' THEN 1\n"
                "                WHEN 'ETH' THEN 2 WHEN 'SOL' THEN 3 ELSE 4 END)*6",
                "CASE eligible.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
            ),
            (
                "CASE eligible.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1\n"
                "                WHEN '15m' THEN 2 WHEN '1h' THEN 3 WHEN '4h' THEN 4 ELSE 5 END",
                "CASE eligible.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1\n"
                "                WHEN '15m' THEN 2 WHEN '1h' THEN 3 WHEN '4h' THEN 4\n"
                "                WHEN '1d' THEN 5 WHEN '1w' THEN 6 ELSE 7 END",
            ),
            ("-s.dispatch_cursor+29,30)", "-s.dispatch_cursor+15,16)"),
            (
                "CASE j.base WHEN 'BTC' THEN 0 WHEN 'DOGE' THEN 1\n"
                "            WHEN 'ETH' THEN 2 WHEN 'SOL' THEN 3 ELSE 4 END)*6",
                "CASE j.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
            ),
            (
                "CASE j.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1 WHEN '15m' THEN 2\n"
                "             WHEN '1h' THEN 3 WHEN '4h' THEN 4 ELSE 5 END",
                "CASE j.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1 WHEN '15m' THEN 2\n"
                "             WHEN '1h' THEN 3 WHEN '4h' THEN 4 WHEN '1d' THEN 5\n"
                "             WHEN '1w' THEN 6 ELSE 7 END",
            ),
        ),
    )

    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM public.market_candles WHERE base NOT IN ('BTC','ETH'))
        OR EXISTS (SELECT 1 FROM public.market_candle_demand WHERE base NOT IN ('BTC','ETH'))
        OR EXISTS (SELECT 1 FROM public.market_latest_prices WHERE base NOT IN ('BTC','ETH'))
        OR EXISTS (SELECT 1 FROM public.market_candle_preview WHERE base NOT IN ('BTC','ETH'))
        OR EXISTS (SELECT 1 FROM public.indicator_build_jobs WHERE base NOT IN ('BTC','ETH'))
        OR EXISTS (SELECT 1 FROM public.indicator_generations WHERE base NOT IN ('BTC','ETH'))
        OR EXISTS (SELECT 1 FROM public.indicator_heads WHERE base NOT IN ('BTC','ETH'))
        OR EXISTS (SELECT 1 FROM public.indicator_source_changes WHERE base NOT IN ('BTC','ETH'))
      THEN RAISE EXCEPTION 'UNSUPPORTED_PAIR_DATA_REMAINS'; END IF;
    END $$""")
    if _supported_digests() != supported_before:
        raise RuntimeError("supported pair data changed during catalog migration")


def downgrade() -> None:
    # The protected candle source rejects constraint DDL outside the same
    # maintenance scope used by the forward catalog migration.
    op.execute("SELECT public.begin_indicator_source_maintenance()")
    for table, name in (
        ("market_candles", "market_candles_check"),
        ("market_candle_demand", "market_candle_demand_check"),
        ("market_latest_prices", "market_latest_prices_check"),
        ("market_candle_preview", "market_candle_preview_check1"),
        ("indicator_build_jobs", "indicator_build_jobs_base_check"),
        ("indicator_generations", "indicator_generations_base_check"),
    ):
        _replace_pair_constraint(table, name, _LEGACY)
    _replace_function_fragments(_TRANSITION, (("ready_count<>16", "ready_count<>40"),))
    _replace_function_fragments(
        _SEED,
        (
            (
                "FROM (VALUES('BTC'),('ETH')) b(base)",
                "FROM (VALUES('BTC'),('DOGE'),('ETH'),('SOL'),('XRP')) b(base)",
            ),
        ),
    )
    _replace_function_fragments(
        _CLAIM,
        (
            (
                "CASE eligible.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
                "CASE eligible.base WHEN 'BTC' THEN 0 WHEN 'DOGE' THEN 1\n"
                "                WHEN 'ETH' THEN 2 WHEN 'SOL' THEN 3 ELSE 4 END)*6",
            ),
            (
                "CASE eligible.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1\n"
                "                WHEN '15m' THEN 2 WHEN '1h' THEN 3 WHEN '4h' THEN 4\n"
                "                WHEN '1d' THEN 5 WHEN '1w' THEN 6 ELSE 7 END",
                "CASE eligible.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1\n"
                "                WHEN '15m' THEN 2 WHEN '1h' THEN 3 WHEN '4h' THEN 4 ELSE 5 END",
            ),
            ("-s.dispatch_cursor+15,16)", "-s.dispatch_cursor+29,30)"),
            (
                "CASE j.base WHEN 'BTC' THEN 0 ELSE 1 END)*8",
                "CASE j.base WHEN 'BTC' THEN 0 WHEN 'DOGE' THEN 1\n"
                "            WHEN 'ETH' THEN 2 WHEN 'SOL' THEN 3 ELSE 4 END)*6",
            ),
            (
                "CASE j.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1 WHEN '15m' THEN 2\n"
                "             WHEN '1h' THEN 3 WHEN '4h' THEN 4 WHEN '1d' THEN 5\n"
                "             WHEN '1w' THEN 6 ELSE 7 END",
                "CASE j.timeframe WHEN '1m' THEN 0 WHEN '5m' THEN 1 WHEN '15m' THEN 2\n"
                "             WHEN '1h' THEN 3 WHEN '4h' THEN 4 ELSE 5 END",
            ),
        ),
    )
