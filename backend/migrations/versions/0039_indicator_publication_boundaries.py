"""Compute publication checkpoint boundaries once, even with fresh-ID statistics."""

from alembic import op
from sqlalchemy import text

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

_SIGNATURE = "public.publish_indicator_generation(uuid,bigint,uuid,uuid,uuid,uuid,boolean)"
_OLD = """EXISTS(SELECT 1 FROM generate_series(0,expected_count-1) n
        WHERE NOT EXISTS(SELECT 1 FROM public.indicator_checkpoints cp
          WHERE cp.generation_id=p_generation AND cp.next_open_at=least(
            public.market_timeframe_advance(g.timeframe,g.calculation_start,1000*n),
            g.calculation_end)))"""
_NEW = """EXISTS(
        WITH expected AS MATERIALIZED (
          SELECT least(public.market_timeframe_advance(
            g.timeframe,g.calculation_start,1000*n),g.calculation_end) AS next_open_at
          FROM generate_series(0,expected_count-1) n
        )
        SELECT 1 FROM expected e
        WHERE NOT EXISTS(SELECT 1 FROM public.indicator_checkpoints cp
          WHERE cp.generation_id=p_generation AND cp.next_open_at=e.next_open_at))"""


def _replace(before: str, after: str) -> None:
    # Follow 0026's targeted replacement: retain owner, ACL, locks and all guards.
    definition: str = (
        op.get_bind()
        .execute(
            text("SELECT pg_get_functiondef(CAST(:signature AS regprocedure))"),
            {"signature": _SIGNATURE},
        )
        .scalar_one()
    )
    if definition.count(before) != 1:
        raise RuntimeError("unexpected indicator publication completeness predicate")
    op.execute(definition.replace(before, after))


def upgrade() -> None:
    _replace(_OLD, _NEW)


def downgrade() -> None:
    _replace(_NEW, _OLD)
