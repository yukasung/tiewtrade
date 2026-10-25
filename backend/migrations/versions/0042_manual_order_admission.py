"""Owner-scoped account-use reads for the engine and independent order throttles."""

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON market_execution_state,market_execution_buffer TO tiewtrade_api")
    op.execute("""CREATE POLICY trading_preferences_engine_reader ON user_trading_preferences
        FOR SELECT TO tiewtrade_engine USING(user_id=tiewtrade_current_user_id())""")
    op.execute("GRANT SELECT(user_id,use) ON user_trading_preferences TO tiewtrade_engine")
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind CHECK(bucket_kind IN
        ('API_KEY_ADD','API_KEY_RETRY','PRICE_STREAM_HANDSHAKE','PAPER_WALLET_MUTATION',
         'PAPER_ORDER_NEW','PAPER_ORDER_CANCEL'))""")


def downgrade() -> None:
    # Refuse rather than silently dropping rate-limit history during rolling deployments.
    op.execute("LOCK TABLE paper_order_requests,api_throttle IN ACCESS EXCLUSIVE MODE")
    op.execute("ALTER TABLE paper_order_requests NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM api_throttle
        WHERE bucket_kind IN ('PAPER_ORDER_NEW','PAPER_ORDER_CANCEL'))
        OR EXISTS(SELECT 1 FROM paper_order_requests)
        THEN RAISE EXCEPTION 'manual order admission history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE paper_order_requests FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute("""ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind CHECK(bucket_kind IN
        ('API_KEY_ADD','API_KEY_RETRY','PRICE_STREAM_HANDSHAKE','PAPER_WALLET_MUTATION'))""")
    op.execute("REVOKE SELECT ON market_execution_state,market_execution_buffer FROM tiewtrade_api")
    op.execute("REVOKE SELECT(user_id,use) ON user_trading_preferences FROM tiewtrade_engine")
    op.execute("DROP POLICY trading_preferences_engine_reader ON user_trading_preferences")
