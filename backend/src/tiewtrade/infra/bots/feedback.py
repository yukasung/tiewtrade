"""Read unconsumed immutable Paper execution facts for a bot run."""

from dataclasses import dataclass
from uuid import UUID

from tiewtrade.core.orders import OrderStatus
from tiewtrade.core.strategies import ExecutionFeedback
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders.codec import execution_from_payload


@dataclass(frozen=True, slots=True)
class PaperFeedback:
    input_identity: str
    value: ExecutionFeedback


def status_feedback_payload(value: ExecutionFeedback | None) -> dict[str, str | int] | None:
    """Retain a verified disposition if later cancellation changes the projection."""
    if value is None or value.execution is not None or value.status is None:
        return None
    return {
        "order_id": str(value.order_id),
        "revision": value.revision,
        "status": value.status.value,
    }


async def restore_status_feedback(
    session: UserSession, run_id: UUID, input_identity: str, payload: object
) -> PaperFeedback | None:
    """Decode the immutable failure snapshot and require the same run/order lineage."""
    if not isinstance(payload, dict) or payload.keys() != {"order_id", "revision", "status"}:
        return None
    try:
        value = ExecutionFeedback(
            UUID(payload["order_id"]), payload["revision"], OrderStatus(payload["status"])
        )
        if status_feedback_payload(value) != payload:
            return None
    except (ValueError, TypeError, AttributeError):
        return None
    linked = (
        await session.execute(
            """SELECT EXISTS(SELECT 1 FROM bot_order_links
           WHERE run_id=:run AND order_id=:order AND user_id=:owner AND mode='PAPER')""",
            {"run": run_id, "order": value.order_id, "owner": session.user_id},
        )
    ).scalar_one()
    return PaperFeedback(input_identity, value) if linked else None


async def next_paper_feedback(
    session: UserSession, run_id: UUID, *, input_identity: str | None = None
) -> PaperFeedback | None:
    row = (
        await session.execute(
            """WITH candidates AS (
              SELECT 'order:'||e.id::text AS identity,e.order_id,e.sequence AS rev,
                     e.event_kind,e.payload,e.occurred_at,0 AS phase
              FROM bot_order_links b JOIN paper_order_events e
                ON (e.order_id,e.user_id,e.episode_id)=(b.order_id,b.user_id,b.episode_id)
              WHERE b.run_id=:run AND b.user_id=:owner AND b.mode='PAPER'
                AND e.event_kind IN ('ACCEPTED','FILL','CANCELED','EXPIRED','REJECTED')
              UNION ALL
              SELECT 'reject:'||r.command_id::text,b.order_id,1,'REJECTED',
                NULL::jsonb,r.completed_at,0
              FROM bot_order_links b JOIN paper_order_command_results r
                ON (r.command_id,r.user_id,r.episode_id)=(b.command_id,b.user_id,b.episode_id)
              WHERE b.run_id=:run AND b.user_id=:owner AND b.mode='PAPER' AND r.state='REJECTED'
                AND NOT EXISTS (SELECT 1 FROM paper_order_events e
                  WHERE e.order_id=b.order_id AND e.user_id=b.user_id
                    AND e.episode_id=b.episode_id AND e.event_kind='REJECTED')
              UNION ALL
              SELECT 'state:'||e.id::text,b.order_id,e.sequence,p.status,NULL::jsonb,
                     e.occurred_at,1
              FROM bot_order_links b JOIN paper_order_projections p
                ON (p.order_id,p.user_id,p.episode_id)=(b.order_id,b.user_id,b.episode_id)
              JOIN LATERAL (
                SELECT f.id,f.sequence,f.occurred_at FROM paper_order_events f
                WHERE f.order_id=b.order_id AND f.user_id=b.user_id
                  AND f.episode_id=b.episode_id AND f.event_kind='FILL'
                ORDER BY f.sequence DESC LIMIT 1
              ) e ON true
              WHERE b.run_id=:run AND b.user_id=:owner AND b.mode='PAPER'
                AND p.status IN ('PARTIALLY_FILLED','FILLED'))
            , first_per_order AS (
              SELECT DISTINCT ON (c.order_id) c.* FROM candidates c
              WHERE (CAST(:input AS text) IS NULL OR c.identity=:input) AND NOT EXISTS(
                SELECT 1 FROM bot_decisions d
                WHERE d.run_id=:run AND d.input_identity=c.identity)
              ORDER BY c.order_id,c.rev,c.phase,c.identity)
            SELECT * FROM first_per_order
            ORDER BY occurred_at,order_id,rev,phase,identity LIMIT 1""",
            {"run": run_id, "owner": session.user_id, "input": input_identity},
        )
    ).one_or_none()
    if row is None:
        return None
    execution = None
    if row.event_kind == "FILL":
        execution = execution_from_payload(row.payload["execution"])
        # This event proves the fill, not the final disposition of the order.
        status = None
    else:
        status = OrderStatus(row.event_kind)
    return PaperFeedback(
        row.identity,
        ExecutionFeedback(UUID(str(row.order_id)), row.rev * 2 + row.phase, status, execution),
    )
