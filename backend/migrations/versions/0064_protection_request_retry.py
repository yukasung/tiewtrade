"""Keep replacement retry deadlines durable while the previous revision stays armed."""

from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE paper_protection_request_progress (
        request_id uuid PRIMARY KEY, user_id uuid NOT NULL, episode_id uuid NOT NULL,
        attempt integer NOT NULL DEFAULT 1 CHECK(attempt BETWEEN 1 AND 4),
        next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(request_id,user_id,episode_id)
          REFERENCES paper_protection_requests(id,user_id,episode_id))""")
    op.execute("ALTER TABLE paper_protection_request_progress ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE paper_protection_request_progress FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY paper_protection_request_progress_self
        ON paper_protection_request_progress FOR ALL
        USING(user_id=tiewtrade_current_user_id())
        WITH CHECK(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT,INSERT ON paper_protection_request_progress TO tiewtrade_engine")
    op.execute("""GRANT UPDATE(attempt,next_attempt_at)
        ON paper_protection_request_progress TO tiewtrade_engine""")
    op.execute("""GRANT SELECT(request_id,next_attempt_at)
        ON paper_protection_request_progress TO tiewtrade_engine_scan""")


def downgrade() -> None:
    # Keep the same protected boundary even if a caller stops at revision0063.
    # Owner visibility and locks make the all-owner emptiness proof atomic.
    tables = (
        "paper_protection_request_progress",
        "paper_protection_requests",
        "paper_protection_results",
        "paper_protections",
        "paper_protection_events",
        "paper_protection_exits",
        "paper_protection_exit_progress",
        "paper_order_requests",
        "audit_events",
    )
    op.execute(
        "LOCK TABLE paper_protection_protocol," + ",".join(tables) + " IN ACCESS EXCLUSIVE MODE"
    )
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
        IF (SELECT enabled FROM paper_protection_protocol WHERE singleton) THEN
            RAISE EXCEPTION 'active protection protocol prevents downgrade';
        END IF;
        END $$""")
    for table in tables[:-2]:
        op.execute(f"""DO $$ BEGIN IF EXISTS(SELECT 1 FROM {table}) THEN
            RAISE EXCEPTION 'protection history prevents downgrade'; END IF; END $$""")
    op.execute("""DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM paper_order_requests
            WHERE protection IS NOT NULL OR protection_allocations<>'[]'::jsonb)
            OR EXISTS(SELECT 1 FROM audit_events WHERE action='PROTECTION_EVENT') THEN
            RAISE EXCEPTION 'protection intent or audit history prevents downgrade';
        END IF;
        END $$""")
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("DROP TABLE paper_protection_request_progress")
