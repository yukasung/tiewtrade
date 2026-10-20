"""Index immutable matching checkpoints and extend typed order decision audit."""

# ruff: noqa: E501 -- keep reviewed DDL predicates as complete clauses

from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE paper_order_events DROP CONSTRAINT paper_order_events_event_kind_check")
    op.execute("""ALTER TABLE paper_order_events ADD CONSTRAINT paper_order_events_event_kind_check
      CHECK(event_kind IN ('ACCEPTED','REJECTED','FILL','CANCELED','EXPIRED','QUEUE_REBASED',
                          'CORRECTED','INPUT_APPLIED'))""")
    op.execute("""CREATE UNIQUE INDEX paper_matching_decision_sequence
      ON paper_order_events(episode_id,((payload->>'decision_sequence')::bigint))
      WHERE payload ? 'matching'""")
    op.execute("""CREATE INDEX paper_matching_checkpoint
      ON paper_order_events(episode_id,base,quote,((payload->>'decision_sequence')::bigint) DESC)
      WHERE payload ? 'matching'""")
    op.execute("""ALTER TABLE paper_order_events ADD CONSTRAINT paper_matching_checkpoint_shape
      CHECK(NOT (payload ? 'matching') OR (
        jsonb_typeof(payload->'matching')='object'
        AND coalesce((payload->>'decision_sequence')::bigint>0,false)
        AND coalesce(payload->>'matching_digest' ~ '^[0-9a-f]{64}$',false)))""")
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false',
        'WHEN ''PAPER_ORDER_DECISION'' THEN (
          actor_kind=''SYSTEM'' AND actor_id IS NULL AND mode=''PAPER''
          AND subject_kind=''PAPER_ORDER_ACTIVITY'' AND subject_id=details->>''episode_id''
          AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''episode_id'',''decision_id'',''kind'']
          AND details-ARRAY[''episode_id'',''decision_id'',''kind'']=''{}''::jsonb
          AND details->>''episode_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
          AND details->>''decision_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
          AND details->>''kind'' IN (''ACCEPT'',''CANCEL'',''INPUT'',''REBASE'',
                                    ''REJECT'',''CORRECTION'',''CONFLICT'')
        ) IS TRUE ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||changed;
    END $$""")


def downgrade() -> None:
    op.execute("ALTER TABLE paper_order_events NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM paper_order_events
      WHERE payload ? 'matching' OR event_kind='INPUT_APPLIED') THEN
        RAISE EXCEPTION 'matching decision history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE paper_order_events FORCE ROW LEVEL SECURITY")
    op.execute("DROP INDEX paper_matching_checkpoint")
    op.execute("DROP INDEX paper_matching_decision_sequence")
    op.execute("ALTER TABLE paper_order_events DROP CONSTRAINT paper_matching_checkpoint_shape")
    op.execute("ALTER TABLE paper_order_events DROP CONSTRAINT paper_order_events_event_kind_check")
    op.execute("""ALTER TABLE paper_order_events ADD CONSTRAINT paper_order_events_event_kind_check
      CHECK(event_kind IN ('ACCEPTED','REJECTED','FILL','CANCELED','EXPIRED','QUEUE_REBASED','CORRECTED'))""")
    op.execute("""DO $$ DECLARE definition text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape ' ||
        regexp_replace(definition,'WHEN ''PAPER_ORDER_DECISION''.*ELSE false','ELSE false') || ' NOT VALID';
    END $$""")
