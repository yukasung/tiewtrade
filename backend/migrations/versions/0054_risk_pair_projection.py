"""Permit atomic rebuild of the mutable risk pair cache, never financial history."""

from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT DELETE ON risk_limit_pairs TO tiewtrade_engine")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON risk_limit_pairs FROM tiewtrade_engine")
