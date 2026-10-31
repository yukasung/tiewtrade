"""Allow the monitor scanner to observe public price replay progress, never funds."""

from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT(cursor) ON risk_owner_state TO tiewtrade_engine_scan")
    op.execute("GRANT SELECT(watermark) ON risk_price_publication TO tiewtrade_engine_scan")


def downgrade() -> None:
    op.execute("REVOKE SELECT(cursor) ON risk_owner_state FROM tiewtrade_engine_scan")
    op.execute("REVOKE SELECT(watermark) ON risk_price_publication FROM tiewtrade_engine_scan")
