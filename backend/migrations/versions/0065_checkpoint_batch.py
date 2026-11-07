"""Batch existing checkpoint writes under unchanged invoker authority and transaction."""

from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None

_FUNCTION = """CREATE FUNCTION public.paper_persist_checkpoint_v1(
 p_wallet uuid,p_episode uuid,p_base text,p_quote text,p_id uuid,p_order uuid,
 p_kind text,p_recorded timestamptz,p_evidence uuid,p_payload jsonb,p_rows jsonb,
 p_occurred timestamptz,p_sequence bigint,p_revision bigint
) RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER
SET search_path=pg_catalog AS $$
DECLARE v_user uuid; v_event_sequence bigint;
BEGIN
 v_user:=public.tiewtrade_current_user_id();
 IF v_user IS NULL
   OR current_setting('tiewtrade.paper_writer_version',true) IS DISTINCT FROM 'F15_V1'
   OR current_setting('tiewtrade.protection_writer_version',true) IS DISTINCT FROM 'F17_V1'
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='checkpoint writer scope unavailable'; END IF;
 -- Same owner key/order as Python; defensive reentrant lock protects direct ENGINE invocation.
 PERFORM pg_advisory_xact_lock(hashtextextended('paper-wallet:'||v_user::text,0));
 PERFORM 1 FROM public.paper_wallet_state s
 JOIN public.paper_order_activity a ON a.wallet_id=s.wallet_id AND a.user_id=s.user_id
 WHERE s.wallet_id=p_wallet AND s.user_id=v_user AND s.active_episode_id=p_episode
   AND a.episode_id=p_episode AND a.availability='READY'
   AND a.source_sequence=p_sequence-1 AND a.revision=p_revision-1
   AND NOT EXISTS(SELECT 1 FROM public.paper_wallet_episode_closures c WHERE c.episode_id=p_episode)
 FOR UPDATE OF s,a;
 IF NOT FOUND THEN
   RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='checkpoint source metadata mismatch';
 END IF;
 IF p_payload IS NULL OR p_rows IS NULL OR jsonb_typeof(p_rows) IS DISTINCT FROM 'array'
   OR (p_payload#>>'{matching,owner}') IS DISTINCT FROM v_user::text
   OR (p_payload#>>'{matching,episode}') IS DISTINCT FROM p_episode::text
   OR (p_payload#>>'{matching,base}') IS DISTINCT FROM p_base
   OR (p_payload#>>'{matching,quote}') IS DISTINCT FROM p_quote
   OR (p_payload->>'decision_sequence') IS DISTINCT FROM p_sequence::text
   OR NOT EXISTS(SELECT 1 FROM public.paper_orders o WHERE o.id=p_order
      AND o.user_id=v_user AND o.wallet_id=p_wallet AND o.episode_id=p_episode
      AND o.base=p_base AND o.quote=p_quote)
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_rows) r
      WHERE NOT EXISTS(SELECT 1 FROM public.paper_orders o WHERE o.id=(r->>'order_id')::uuid
        AND o.user_id=v_user AND o.wallet_id=p_wallet AND o.episode_id=p_episode
        AND o.base=p_base AND o.quote=p_quote))
 THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='checkpoint identity mismatch'; END IF;
 SELECT coalesce(max(sequence),0)+1 INTO v_event_sequence FROM public.paper_order_events
            WHERE order_id=p_order;

 INSERT INTO public.paper_order_events
        (id,order_id,user_id,episode_id,base,quote,sequence,event_kind,
         input_recorded_at,input_evidence_id,payload,occurred_at)
        VALUES(p_id,p_order,v_user,p_episode,p_base,p_quote,v_event_sequence,p_kind,
         p_recorded,p_evidence,CAST(p_payload AS jsonb),p_occurred);

 WITH projected AS (INSERT INTO public.paper_order_projections
        (order_id,user_id,episode_id,base,quote,status,filled_quantity,spent,resting,
         queue_ahead,revision,last_event_id)
        SELECT r.order_id,v_user,p_episode,p_base,p_quote,r.status,r.filled,r.spent,r.resting,
          r.queue_ahead,p_revision,
          (SELECT e.id FROM public.paper_order_events e WHERE e.order_id=r.order_id
           ORDER BY e.sequence DESC LIMIT 1)
        FROM jsonb_to_recordset(CAST(p_rows AS jsonb)) AS r(
          order_id uuid,status text,filled numeric,spent numeric,resting boolean,
          queue_ahead numeric,reserved_quote numeric,reserved_base numeric)
        ON CONFLICT(order_id) DO UPDATE SET status=EXCLUDED.status,
          filled_quantity=EXCLUDED.filled_quantity,spent=EXCLUDED.spent,
          resting=EXCLUDED.resting,queue_ahead=EXCLUDED.queue_ahead,
          revision=EXCLUDED.revision,last_event_id=EXCLUDED.last_event_id
          RETURNING order_id)
        UPDATE public.paper_order_projections SET revision=p_revision WHERE episode_id=p_episode
        AND (base,quote)<>(p_base,p_quote)
        AND status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED');

 WITH reserved AS (INSERT INTO public.paper_reservations
        (order_id,user_id,episode_id,base,quote,quote_reserved,base_reserved,revision)
        SELECT r.order_id,v_user,p_episode,p_base,p_quote,
          r.reserved_quote,r.reserved_base,p_revision
        FROM jsonb_to_recordset(CAST(p_rows AS jsonb)) AS r(
          order_id uuid,status text,filled numeric,spent numeric,resting boolean,
          queue_ahead numeric,reserved_quote numeric,reserved_base numeric)
        ON CONFLICT(order_id) DO UPDATE SET quote_reserved=EXCLUDED.quote_reserved,
          base_reserved=EXCLUDED.base_reserved,revision=EXCLUDED.revision
          RETURNING order_id)
        UPDATE public.paper_reservations SET revision=p_revision WHERE episode_id=p_episode
        AND (base,quote)<>(p_base,p_quote)
        AND order_id IN (SELECT order_id FROM public.paper_order_projections
          WHERE episode_id=p_episode
          AND status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED'));

 UPDATE public.paper_order_activity SET source_sequence=p_sequence,revision=p_revision,
        observed_at=clock_timestamp() WHERE episode_id=p_episode;

 UPDATE public.paper_wallet_state SET revision=revision+1 WHERE wallet_id=p_wallet;
END $$"""
_SIGNATURE = (
    "uuid,uuid,text,text,uuid,uuid,text,timestamptz,uuid,jsonb,jsonb,timestamptz,bigint,bigint"
)


def upgrade() -> None:
    op.execute(_FUNCTION)
    op.execute(
        f"REVOKE ALL ON FUNCTION public.paper_persist_checkpoint_v1({_SIGNATURE}) FROM PUBLIC"
    )
    op.execute(
        f"GRANT EXECUTE ON FUNCTION public.paper_persist_checkpoint_v1({_SIGNATURE}) "
        "TO tiewtrade_engine"
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION public.paper_persist_checkpoint_v1({_SIGNATURE})")
