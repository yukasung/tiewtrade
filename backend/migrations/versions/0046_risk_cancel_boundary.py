"""Keep reservation-only wallet revision updates independent of price replay."""

from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A cancellation changes order/reservation facts and the wallet's display
    # revision, but does not change any financial source. The other F18 table
    # guards still require a full boundary for ledger/position/episode writes.
    op.execute("""DROP TRIGGER paper_f18_writer_fence ON paper_wallet_state""")
    op.execute("""CREATE TRIGGER paper_f18_writer_fence_insert_delete
      BEFORE INSERT OR DELETE ON paper_wallet_state FOR EACH ROW
      EXECUTE FUNCTION risk_require_financial_boundary()""")
    op.execute("""CREATE TRIGGER paper_f18_writer_fence
      BEFORE UPDATE ON paper_wallet_state FOR EACH ROW
      WHEN (OLD.wallet_id IS DISTINCT FROM NEW.wallet_id
        OR OLD.user_id IS DISTINCT FROM NEW.user_id
        OR OLD.active_episode_id IS DISTINCT FROM NEW.active_episode_id)
      EXECUTE FUNCTION risk_require_financial_boundary()""")


def downgrade() -> None:
    op.execute("DROP TRIGGER paper_f18_writer_fence ON paper_wallet_state")
    op.execute("DROP TRIGGER paper_f18_writer_fence_insert_delete ON paper_wallet_state")
    op.execute("""CREATE TRIGGER paper_f18_writer_fence
      BEFORE INSERT OR UPDATE OR DELETE ON paper_wallet_state FOR EACH ROW
      EXECUTE FUNCTION risk_require_financial_boundary()""")
