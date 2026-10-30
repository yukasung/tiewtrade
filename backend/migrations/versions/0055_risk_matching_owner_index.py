"""Bound owner-scoped checkpoint reads during integrated risk monitoring."""

from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # RLS adds user_id to every ENGINE read. With the episode-only index the
    # planner can choose a bitmap scan and detoast/sort every old checkpoint.
    # Pin all equality keys before the existing immutable decision sequence so
    # the unchanged LIMIT 1 query reads only its newest matching checkpoint.
    op.execute("""CREATE INDEX paper_matching_owner_checkpoint
      ON paper_order_events(user_id,episode_id,base,quote,
        ((payload->>'decision_sequence')::bigint) DESC)
      WHERE payload ? 'matching'""")


def downgrade() -> None:
    op.execute("DROP INDEX paper_matching_owner_checkpoint")
