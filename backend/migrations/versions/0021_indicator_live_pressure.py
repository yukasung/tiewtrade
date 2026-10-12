"""Separate live eviction pressure from reusable allocated PostgreSQL pages."""

from pathlib import Path

from alembic import op
from alembic.util import load_python_file

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

GC = load_python_file(Path(__file__).parent, "0020_indicator_recovery_gc.py").GC
LIVE = """  -- Allocated files include reusable/dead pages. They are an operational disk
  -- measurement, not evidence that live cache still needs eviction. Charge live
  -- tuple bytes plus conservative heap/index/TOAST reserves, including retained
  -- request identities, so DELETE reduces pressure without waiting for VACUUM.
  pressure:=(
    (SELECT coalesce(sum(pg_column_size(payload)::bigint+512+
      ((pg_column_size(payload)::bigint+1995)/1996)*128),0)
      FROM public.indicator_checkpoints)+
    (SELECT coalesce(sum(pg_column_size(live_generation)::bigint+1024),0)
      FROM public.indicator_generations live_generation)+
    (SELECT coalesce(sum(pg_column_size(live_head)::bigint+512),0)
      FROM public.indicator_heads live_head)+
    (SELECT coalesce(sum(pg_column_size(live_request)::bigint+256),0)
      FROM public.indicator_retry_requests live_request))>3221225472;
"""
ALLOCATED = """  pressure:=(pg_total_relation_size('public.indicator_checkpoints')+
    pg_total_relation_size('public.indicator_generations')+
    pg_total_relation_size('public.indicator_heads')+
    pg_total_relation_size('public.indicator_retry_requests'))>3221225472;
"""


def upgrade() -> None:
    assert GC.count(ALLOCATED) == 1
    op.execute(
        GC.replace(ALLOCATED, LIVE).replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
    )


def downgrade() -> None:
    op.execute(GC.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
