"""Persist a bounded recent-candle pass without moving deep-history progress."""

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE market_candle_demand
        ADD COLUMN recent_cursor timestamptz,
        ADD COLUMN recent_end timestamptz,
        ADD COLUMN fetch_recent boolean NOT NULL DEFAULT false,
        ADD CONSTRAINT market_candle_recent_progress CHECK (
            (recent_cursor IS NULL AND recent_end IS NULL AND NOT fetch_recent)
            OR (recent_cursor IS NOT NULL AND recent_end IS NOT NULL
                AND recent_cursor <= recent_end))""")


def downgrade() -> None:
    # An outstanding recent fetch cannot be interpreted by the old worker.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM market_candle_demand WHERE fetch_recent) THEN
            RAISE EXCEPTION 'finish recent candle fetches before downgrade';
        END IF;
    END $$""")
    op.execute("""ALTER TABLE market_candle_demand
        DROP CONSTRAINT market_candle_recent_progress,
        DROP COLUMN fetch_recent, DROP COLUMN recent_end, DROP COLUMN recent_cursor""")
