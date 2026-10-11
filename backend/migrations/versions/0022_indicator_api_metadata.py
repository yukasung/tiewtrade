"""Expose immutable READY candidate ordering to the read-only API view."""

from pathlib import Path

from alembic import op
from alembic.util import load_python_file

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE OR REPLACE VIEW indicator_ready_generations AS
      SELECT g.id,g.source,g.base,g.quote,g.timeframe,g.formula_version,
      g.calculation_start,g.calculation_end,g.as_of,g.source_epoch,g.source_fence,
      g.dataset_revision,g.checkpoint_count,g.codec_version,g.expires_at,g.prepared_at,
      g.candidate_sequence FROM indicator_generations g WHERE g.status='READY'""")
    op.execute("""CREATE OR REPLACE VIEW indicator_numeric_failures AS SELECT
      g.id,j.source,j.base,j.quote,j.timeframe,j.formula_version,
      g.calculation_start,g.calculation_end,g.as_of,g.source_epoch,g.source_fence,
      g.codec_version,coalesce(g.candidate_sequence,j.generation_sequence) AS candidate_sequence,
      g.expires_at,g.failure_code,j.desired_start,j.desired_end,
      (g.id IS NOT NULL) AS manifest_available
      FROM indicator_build_jobs j LEFT JOIN indicator_generations g
        ON g.id=j.current_candidate AND g.status='FAILED_NUMERIC'
      WHERE j.failed_calculation_key IS NOT NULL""")


def downgrade() -> None:
    # Drop dependents only within this migration transaction and restore their grants.
    op.execute("DROP VIEW indicator_ready_generations")
    op.execute("""CREATE VIEW indicator_ready_generations AS
      SELECT g.id,g.source,g.base,g.quote,g.timeframe,g.formula_version,
      g.calculation_start,g.calculation_end,g.as_of,g.source_epoch,g.source_fence,
      g.dataset_revision,g.checkpoint_count,g.codec_version,g.expires_at,g.prepared_at
      FROM indicator_generations g WHERE g.status='READY'""")
    op.execute("GRANT SELECT ON indicator_ready_generations TO tiewtrade_api")
    op.execute("DROP VIEW indicator_numeric_failures")
    previous = load_python_file(Path(__file__).parent, "0015_prepared_indicator_source.py")
    op.execute(
        next(
            sql
            for sql in previous.SCHEMA
            if sql.startswith("CREATE VIEW indicator_numeric_failures")
        )
    )
    op.execute("GRANT SELECT ON indicator_numeric_failures TO tiewtrade_api")
