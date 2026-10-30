"""Owner-only risk reads and non-financial monitor scheduling hints."""

from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # F16 already grants only these projection columns. Its engine-only F14
    # policy otherwise silently hides held exposure from the API reader.
    op.execute("""CREATE POLICY paper_position_risk_reader ON paper_position_projections
      FOR SELECT TO tiewtrade_api USING(user_id=tiewtrade_current_user_id())""")
    op.execute("""GRANT SELECT(user_id,mode,updated_at) ON risk_limit_settings
      TO tiewtrade_engine_scan""")


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT(user_id,mode,updated_at) ON risk_limit_settings FROM tiewtrade_engine_scan"
    )
    op.execute("DROP POLICY paper_position_risk_reader ON paper_position_projections")
