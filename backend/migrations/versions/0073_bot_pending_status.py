"""Index owner-scoped pending bot request status without activating execution."""

from alembic import op

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE INDEX bot_control_requests_status
      ON bot_control_requests(user_id,mode,requested_at DESC,id DESC)""")


def downgrade() -> None:
    op.execute("DROP INDEX bot_control_requests_status")
