"""Attach BOT brackets to authoritative F-20 decision links."""

from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None

_OLD = "((entry_request_id IS NULL) = (entry_order_id IS NULL))"
_NEW = """((entry_order_id IS NULL AND num_nonnulls(entry_request_id,entry_bot_command_id)=0)
       OR (entry_order_id IS NOT NULL AND num_nonnulls(entry_request_id,entry_bot_command_id)=1))"""


def upgrade() -> None:
    op.execute("""ALTER TABLE bot_order_links
      ADD COLUMN bracket jsonb CHECK(bracket IS NULL OR jsonb_typeof(bracket)='object'),
      ADD CONSTRAINT bot_order_link_protection_ref
        UNIQUE(command_id,user_id,episode_id,order_id)""")
    op.execute(f"""DO $$ DECLARE constraint_name text; BEGIN
      SELECT conname INTO STRICT constraint_name FROM pg_constraint
      WHERE conrelid='paper_protections'::regclass AND contype='c'
        AND pg_get_expr(conbin,conrelid)='{_OLD}';
      EXECUTE format('ALTER TABLE paper_protections DROP CONSTRAINT %I',constraint_name);
    END $$""")
    op.execute(f"""ALTER TABLE paper_protections
      ADD COLUMN entry_bot_command_id uuid UNIQUE,
      ADD CONSTRAINT protection_entry_source CHECK({_NEW}),
      ADD CONSTRAINT protection_bot_order_link
        FOREIGN KEY(entry_bot_command_id,user_id,episode_id,entry_order_id)
        REFERENCES bot_order_links(command_id,user_id,episode_id,order_id)""")


def downgrade() -> None:
    tables = ("paper_protections", "bot_order_links")
    op.execute("LOCK TABLE " + ",".join(tables) + " IN ACCESS EXCLUSIVE MODE")
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM paper_protections WHERE entry_bot_command_id IS NOT NULL)
        OR EXISTS(SELECT 1 FROM bot_order_links WHERE bracket IS NOT NULL) THEN
        RAISE EXCEPTION 'bot protection history prevents downgrade';
      END IF;
    END $$""")
    for table in tables:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""ALTER TABLE paper_protections DROP CONSTRAINT protection_bot_order_link,
      DROP CONSTRAINT protection_entry_source, DROP COLUMN entry_bot_command_id,
      ADD CONSTRAINT protection_manual_entry_source CHECK({_OLD})""")
    op.execute("""ALTER TABLE bot_order_links DROP CONSTRAINT bot_order_link_protection_ref,
      DROP COLUMN bracket""")
