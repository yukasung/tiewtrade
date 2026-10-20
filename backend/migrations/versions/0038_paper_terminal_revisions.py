"""Retain terminal order revisions without weakening active reset coherence.

Old workers remain compatible: they may still advance terminal revisions.
Downgrade refuses historical revisions the previous readiness contract cannot read.
"""

from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

_OLD_PROJECTION = "op.revision<>oa.revision"
_OLD_RESERVATION = "pr.revision<>oa.revision"
_NEW_PROJECTION = """(op.revision>oa.revision OR
             (op.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')
              AND op.revision<>oa.revision))"""
_NEW_RESERVATION = """(pr.revision>oa.revision OR NOT EXISTS (
             SELECT 1 FROM public.paper_order_projections projection
             WHERE projection.order_id=pr.order_id
               AND projection.episode_id=pr.episode_id
               AND projection.user_id=pr.user_id
               AND projection.revision=pr.revision
               AND (projection.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')
                    OR (pr.quote_reserved=0 AND pr.base_reserved=0))))"""


def _replace_predicates(*, reverse: bool = False) -> None:
    # Patch only the reviewed predicates, preserving signature, owner, ACL and RLS.
    pairs = ((_OLD_PROJECTION, _NEW_PROJECTION), (_OLD_RESERVATION, _NEW_RESERVATION))
    for old, new in pairs:
        if reverse:
            old, new = new, old
        op.execute(f"""DO $migration$ DECLARE definition text; changed text; BEGIN
          SELECT pg_get_functiondef('paper_wallet_reset_readiness(uuid)'::regprocedure)
            INTO definition;
          changed:=replace(definition,$old${old}$old$,$new${new}$new$);
          IF changed=definition THEN
            RAISE EXCEPTION 'Paper reset readiness revision predicate missing';
          END IF;
          EXECUTE changed;
        END $migration$""")


def upgrade() -> None:
    _replace_predicates()


def downgrade() -> None:
    tables = ("paper_order_activity", "paper_order_projections", "paper_reservations")
    # Transactional DDL locks also prevent a writer creating divergence after the check.
    for table in tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(
      SELECT 1 FROM paper_order_projections p
      LEFT JOIN paper_order_activity a ON a.episode_id=p.episode_id
      WHERE a.revision IS NULL OR p.revision<>a.revision
      UNION ALL
      SELECT 1 FROM paper_reservations r
      LEFT JOIN paper_order_activity a ON a.episode_id=r.episode_id
      WHERE a.revision IS NULL OR r.revision<>a.revision
    ) THEN RAISE EXCEPTION 'historical Paper order revisions prevent downgrade';
    END IF; END $$""")
    for table in reversed(tables):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    _replace_predicates(reverse=True)
