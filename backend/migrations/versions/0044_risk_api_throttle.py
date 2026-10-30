"""An independent API token bucket for risk mutations; no TOTP quota changes."""

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

_PRIOR = (
    "API_KEY_ADD",
    "API_KEY_RETRY",
    "PRICE_STREAM_HANDSHAKE",
    "PAPER_WALLET_MUTATION",
    "PAPER_ORDER_NEW",
    "PAPER_ORDER_CANCEL",
)


def upgrade() -> None:
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute(
        f"ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind "
        f"CHECK(bucket_kind IN {(*_PRIOR, 'RISK_LIMIT_MUTATION')!r})"
    )


def downgrade() -> None:
    op.execute("LOCK TABLE api_throttle IN ACCESS EXCLUSIVE MODE")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM api_throttle
      WHERE bucket_kind='RISK_LIMIT_MUTATION') THEN
      RAISE EXCEPTION 'risk throttle history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE api_throttle DROP CONSTRAINT api_throttle_kind")
    op.execute(
        "ALTER TABLE api_throttle ADD CONSTRAINT api_throttle_kind "
        f"CHECK(bucket_kind IN {_PRIOR!r})"
    )
