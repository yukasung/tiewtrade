"""Add the typed successful Paper-wallet reset audit event."""

# ruff: noqa: E501 -- keep the reviewed audit predicate as one complete clause

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

_READINESS_TABLES = (
    "paper_wallet_state",
    "paper_position_activity",
    "paper_position_events",
    "paper_position_projections",
    "paper_order_activity",
    "paper_order_initializations",
    "paper_orders",
    "paper_order_projections",
    "paper_reservations",
    "paper_order_commands",
    "paper_order_dispatch",
)


def upgrade() -> None:
    for table in _READINESS_TABLES:
        op.execute(f"""CREATE POLICY {table}_reset_reader ON {table}
          FOR SELECT TO tiewtrade_migrator
          USING(user_id=public.tiewtrade_current_user_id())""")
    op.execute("""CREATE FUNCTION paper_wallet_reset_readiness(target_episode uuid)
      RETURNS TABLE(
        position_availability text,position_sequence bigint,position_revision bigint,
        position_proof text,order_availability text,order_revision bigint,order_proof text,
        initialized_position_proof text,initialized_order_proof text,
        position_record_count bigint,position_max_sequence bigint,position_pair_count bigint,
        position_projection_count bigint,position_revision_mismatch bigint,
        open_position_count bigint,order_count bigint,order_projection_count bigint,
        reservation_count bigint,active_order_count bigint,active_reservation_count bigint,
        order_projection_mismatch bigint,reservation_revision_mismatch bigint,
        pending_order_command_count bigint)
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT pa.availability,pa.source_sequence,pa.revision,pa.source_proof,
        oa.availability,oa.revision,oa.source_proof,oi.position_proof,oi.source_proof,
        (SELECT count(pe.id) FROM public.paper_position_events pe
         WHERE pe.episode_id=target_episode AND pe.user_id=public.tiewtrade_current_user_id()
           AND pe.event_kind='RECORD'),
        (SELECT coalesce(max(pe.source_sequence),0) FROM public.paper_position_events pe
         WHERE pe.episode_id=target_episode AND pe.user_id=public.tiewtrade_current_user_id()
           AND pe.event_kind='RECORD'),
        (SELECT count(DISTINCT (pe.base,pe.quote)) FROM public.paper_position_events pe
         WHERE pe.episode_id=target_episode AND pe.user_id=public.tiewtrade_current_user_id()
           AND pe.event_kind='RECORD'),
        (SELECT count(pp.episode_id) FROM public.paper_position_projections pp
         WHERE pp.episode_id=target_episode AND pp.user_id=public.tiewtrade_current_user_id()),
        (SELECT count(pp.episode_id) FROM public.paper_position_projections pp
         WHERE pp.episode_id=target_episode AND pp.user_id=public.tiewtrade_current_user_id()
           AND (pp.revision<>pa.revision OR pp.last_sequence<>pa.source_sequence)),
        (SELECT count(pp.episode_id) FROM public.paper_position_projections pp
         WHERE pp.episode_id=target_episode AND pp.user_id=public.tiewtrade_current_user_id()
           AND (pp.held_quantity<>0 OR pp.total_cost<>0)),
        (SELECT count(po.id) FROM public.paper_orders po
         WHERE po.episode_id=target_episode AND po.user_id=public.tiewtrade_current_user_id()),
        (SELECT count(op.order_id) FROM public.paper_order_projections op
         WHERE op.episode_id=target_episode AND op.user_id=public.tiewtrade_current_user_id()),
        (SELECT count(pr.order_id) FROM public.paper_reservations pr
         WHERE pr.episode_id=target_episode AND pr.user_id=public.tiewtrade_current_user_id()),
        (SELECT count(op.order_id) FROM public.paper_order_projections op
         WHERE op.episode_id=target_episode AND op.user_id=public.tiewtrade_current_user_id()
           AND op.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED')),
        (SELECT count(pr.order_id) FROM public.paper_reservations pr
         WHERE pr.episode_id=target_episode AND pr.user_id=public.tiewtrade_current_user_id()
           AND (pr.quote_reserved<>0 OR pr.base_reserved<>0)),
        (SELECT count(op.order_id) FROM public.paper_order_projections op
         WHERE op.episode_id=target_episode AND op.user_id=public.tiewtrade_current_user_id()
           AND op.revision<>oa.revision),
        (SELECT count(pr.order_id) FROM public.paper_reservations pr
         WHERE pr.episode_id=target_episode AND pr.user_id=public.tiewtrade_current_user_id()
           AND pr.revision<>oa.revision),
        (SELECT count(oc.id) FROM public.paper_order_commands oc
         JOIN public.paper_order_dispatch od ON od.command_id=oc.id
         WHERE oc.episode_id=target_episode AND oc.user_id=public.tiewtrade_current_user_id()
           AND od.state<>'TERMINAL')
      FROM public.paper_wallet_state ws
      LEFT JOIN public.paper_position_activity pa ON pa.episode_id=ws.active_episode_id
      LEFT JOIN public.paper_order_activity oa ON oa.episode_id=ws.active_episode_id
      LEFT JOIN public.paper_order_initializations oi ON oi.episode_id=ws.active_episode_id
      WHERE ws.user_id=public.tiewtrade_current_user_id()
        AND ws.active_episode_id=target_episode
      $$""")
    op.execute("REVOKE ALL ON FUNCTION paper_wallet_reset_readiness(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION paper_wallet_reset_readiness(uuid) TO tiewtrade_api,tiewtrade_engine"
    )
    op.execute("""DO $$ DECLARE definition text; changed text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      changed:=replace(definition,'ELSE false',
        'WHEN ''PAPER_WALLET_RESET'' THEN
          actor_kind=''USER'' AND actor_id=owner_user_id AND mode=''PAPER''
          AND subject_kind=''PAPER_WALLET'' AND outcome=''SUCCEEDED'' AND failure_code IS NULL
          AND details ?& ARRAY[''command_id'',''previous_episode_id'',''episode_id'',''amount'',''currency'']
          AND details-ARRAY[''command_id'',''previous_episode_id'',''episode_id'',''amount'',''currency'']=''{}''::jsonb
          AND details->>''currency''=''USDT''
          AND details->>''command_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
          AND details->>''previous_episode_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
          AND details->>''episode_id'' ~ ''^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$''
        ELSE false');
      IF changed=definition THEN RAISE EXCEPTION 'audit extension point missing'; END IF;
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape '||changed;
    END $$""")


def downgrade() -> None:
    op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM audit_events
      WHERE action='PAPER_WALLET_RESET') THEN
        RAISE EXCEPTION 'Paper reset audit history prevents downgrade'; END IF; END $$""")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute("""DO $$ DECLARE definition text; BEGIN
      SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
        WHERE conrelid='audit_events'::regclass AND conname='audit_events_action_shape';
      ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_shape;
      EXECUTE 'ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_shape ' ||
        regexp_replace(definition,'WHEN ''PAPER_WALLET_RESET''.*ELSE false','ELSE false') ||
        ' NOT VALID';
    END $$""")
    op.execute("DROP FUNCTION IF EXISTS paper_wallet_reset_readiness(uuid)")
    for table in reversed(_READINESS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_reset_reader ON {table}")
