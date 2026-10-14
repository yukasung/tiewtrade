"""Allow prepared indicators to use the approved five-year 1w/1M window."""

from alembic import op
from sqlalchemy import text

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

_TRANSITION = "transition_indicator_rollout(indicator_rollout_mode,uuid,indicator_rollout_mode)"


def _replace_ready_count(before: str, after: str) -> None:
    connection = op.get_bind()
    definition: str | None = connection.execute(
        text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
        {"signature": f"public.{_TRANSITION}"},
    ).scalar_one()
    if definition is None or definition.count(before) != 1:
        raise RuntimeError("unexpected indicator rollout transition definition")
    op.execute(definition.replace(before, after))


def upgrade() -> None:
    op.execute("SELECT public.begin_indicator_source_maintenance()")
    _replace_ready_count("ready_count<>30", "ready_count<>40")
    op.execute("""ALTER TABLE public.indicator_build_jobs
      DROP CONSTRAINT indicator_build_jobs_check,
      ADD CONSTRAINT indicator_build_jobs_check CHECK (
        (desired_start IS NULL AND desired_end IS NULL) OR
        (desired_start IS NOT NULL AND desired_end IS NOT NULL
         AND desired_start<desired_end AND
         ((timeframe IN ('1w','1M') AND desired_start>=desired_end-interval '5 years') OR
          (timeframe NOT IN ('1w','1M') AND desired_end-desired_start<=interval '365 days'))))""")
    op.execute("""ALTER TABLE public.indicator_generations
      DROP CONSTRAINT indicator_generations_check,
      ADD CONSTRAINT indicator_generations_check CHECK (
        calculation_start<calculation_end AND calculation_end<=as_of AND
        ((timeframe IN ('1w','1M')
          AND calculation_start>=calculation_end-interval '5 years') OR
         (timeframe NOT IN ('1w','1M')
          AND calculation_end-calculation_start<=interval '365 days')))""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM public.indicator_build_jobs
        WHERE desired_end-desired_start>interval '365 days') OR
        EXISTS (SELECT 1 FROM public.indicator_generations
        WHERE calculation_end-calculation_start>interval '365 days') THEN
        RAISE EXCEPTION 'LONG_INDICATOR_WINDOW_DOWNGRADE_NOT_DRAINED';
      END IF;
    END $$""")
    op.execute("SELECT public.begin_indicator_source_maintenance()")
    _replace_ready_count("ready_count<>40", "ready_count<>30")
    op.execute("""ALTER TABLE public.indicator_generations
      DROP CONSTRAINT indicator_generations_check,
      ADD CONSTRAINT indicator_generations_check CHECK (
        calculation_start<calculation_end AND calculation_end<=as_of
        AND calculation_end-calculation_start<=interval '365 days')""")
    op.execute("""ALTER TABLE public.indicator_build_jobs
      DROP CONSTRAINT indicator_build_jobs_check,
      ADD CONSTRAINT indicator_build_jobs_check CHECK (
        (desired_start IS NULL AND desired_end IS NULL) OR
        (desired_start IS NOT NULL AND desired_end IS NOT NULL
         AND desired_start<desired_end
         AND desired_end-desired_start<=interval '365 days'))""")
