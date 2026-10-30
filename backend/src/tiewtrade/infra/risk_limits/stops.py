"""Owner-fenced stop enrollment and durable F15 cancellation recovery."""

import json
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from tiewtrade.core.orders import OrderType, TradingMode
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    RiskLimitDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.paper_orders.dispatch import complete_command, submit_cancel
from tiewtrade.infra.paper_orders.requests import get_request, request_audit
from tiewtrade.infra.risk_limits.dispatch import lock_risk_owner

_TERMINAL = ("CANCELED", "FILLED", "REJECTED", "ALREADY_TERMINAL")

# Only risk-increasing NEW commands are discarded. Every existing active F15
# MARKET/LIMIT remainder is canceled. TP/SL are not F15 supported order types and
# must never be enrolled by widening this predicate when those contracts arrive.
_CANDIDATES = """WITH candidates AS (
 SELECT 'REQUEST'::text kind,r.id,r.order_id FROM paper_order_requests r
 WHERE r.episode_id=:episode AND r.action='NEW' AND r.payload->>'side'='BUY'
   AND r.recorded_at<=:cut AND NOT EXISTS(SELECT 1 FROM paper_order_request_results x
     WHERE x.request_id=r.id AND x.risk_recorded_at<=:cut)
 UNION ALL
 SELECT 'COMMAND',c.id,c.order_id FROM paper_order_commands c
 WHERE c.episode_id=:episode AND c.action='NEW' AND c.payload->'intent'->>'side'='BUY'
   AND c.risk_recorded_at<=:cut AND NOT EXISTS(SELECT 1 FROM paper_order_command_results x
     WHERE x.command_id=c.id AND x.risk_recorded_at<=:cut)
   AND NOT EXISTS(SELECT 1 FROM paper_orders o JOIN risk_order_lifecycle l ON l.order_id=o.id
     WHERE o.command_id=c.id AND l.recorded_at<=:cut)
 UNION ALL
 SELECT 'ORDER',o.id,o.id FROM paper_orders o JOIN LATERAL(
   SELECT status FROM risk_order_lifecycle l WHERE l.order_id=o.id AND l.recorded_at<=:cut
   ORDER BY l.recorded_at DESC,l.sequence DESC LIMIT 1) p ON true
 WHERE o.episode_id=:episode AND o.kind IN ('MARKET','LIMIT')
   AND p.status NOT IN ('FILLED','CANCELED','EXPIRED','REJECTED'))
 SELECT kind,id,order_id FROM candidates c WHERE NOT EXISTS(
   SELECT 1 FROM risk_stop_targets t WHERE t.stop_id=:stop AND t.target_kind=c.kind
   AND t.target_id=c.id) ORDER BY kind,id LIMIT :limit"""


async def _effect(
    session: UserSession,
    target: Any,
    *,
    state: str,
    attempt: int,
    details: dict[str, object],
    delay_seconds: int = 0,
) -> None:
    await session.execute(
        """INSERT INTO risk_stop_effects
        (stop_id,user_id,mode,target_kind,target_id,state,attempt,next_attempt_at,details)
        VALUES(:stop,:owner,'PAPER',:kind,:target,:state,:attempt,
          clock_timestamp()+make_interval(secs=>:delay),CAST(:details AS jsonb))""",
        {
            "stop": target["stop_id"],
            "owner": session.user_id,
            "kind": target["target_kind"],
            "target": target["target_id"],
            "state": state,
            "attempt": attempt,
            "delay": delay_seconds,
            "details": json.dumps(details),
        },
    )


async def _request(session: UserSession, target: Any, episode_id: UUID) -> str:
    receipt = await get_request(session, target["target_id"])
    if receipt is None:
        raise ValueError("stop target request missing")
    result = (
        await session.execute(
            "SELECT state,command_id FROM paper_order_request_results WHERE request_id=:id",
            {"id": receipt.request_id},
        )
    ).one_or_none()
    if result is not None:
        if result.state == "TRANSFERRED":
            return await _command(
                session,
                {**dict(target), "target_id": result.command_id},
                episode_id,
            )
        return "ALREADY_TERMINAL"
    await session.execute(
        """INSERT INTO paper_order_request_results
        (request_id,user_id,episode_id,order_id,action,state,failure_code)
        VALUES(:id,:owner,:episode,:order,'NEW','REJECTED','ORDER_SAFETY_UNAVAILABLE')""",
        {
            "id": receipt.request_id,
            "owner": session.user_id,
            "episode": receipt.episode_id,
            "order": receipt.order_id,
        },
    )
    await request_audit(
        session,
        receipt,
        action=AuditAction.PAPER_ORDER_REQUEST_REJECTED,
        failure_code="ORDER_SAFETY_UNAVAILABLE",
    )
    await session.execute(
        """UPDATE paper_order_request_dispatch SET state='TERMINAL',worker=NULL,
        claim_id=NULL,lease_until=NULL WHERE request_id=:id""",
        {"id": receipt.request_id},
    )
    return "REJECTED"


async def _command(session: UserSession, target: Any, episode_id: UUID) -> str:
    accepted = (
        await session.execute(
            "SELECT 1 FROM paper_orders WHERE command_id=:id",
            {"id": target["target_id"]},
        )
    ).first()
    if accepted is not None:
        return "CANCEL_PENDING"
    exists = (
        await session.execute(
            "SELECT 1 FROM paper_order_command_results WHERE command_id=:id",
            {"id": target["target_id"]},
        )
    ).first()
    if exists is not None:
        return "ALREADY_TERMINAL"
    await complete_command(
        session,
        command_id=target["target_id"],
        episode_id=episode_id,
        succeeded=False,
        failure_code="ORDER_SAFETY_UNAVAILABLE",
        snapshot={
            "order_id": str(target["order_id"]),
            "reason": "RISK_LOSS_LIMIT_REACHED",
            "stop_id": str(target["stop_id"]),
        },
    )
    await session.execute(
        """UPDATE paper_order_dispatch SET state='TERMINAL',worker=NULL,claim_id=NULL,
        lease_until=NULL WHERE command_id=:id""",
        {"id": target["target_id"]},
    )
    return "REJECTED"


async def _order(session: UserSession, target: Any, stop: Any) -> tuple[str, dict[str, object]]:
    order = (
        await session.execute(
            """SELECT p.status,p.filled_quantity::text AS filled,p.spent::text AS spent
        FROM paper_order_projections p WHERE p.order_id=:id AND p.episode_id=:episode""",
            {"id": target["order_id"], "episode": stop["episode_id"]},
        )
    ).one_or_none()
    if order is None:
        raise ValueError("stop target order projection missing")
    details: dict[str, object] = {
        "filled_quantity": order.filled,
        "spent": order.spent,
        "order_status": order.status,
    }
    if order.status in ("FILLED", "CANCELED"):
        return str(order.status), details
    if order.status in ("EXPIRED", "REJECTED"):
        return "ALREADY_TERMINAL", details
    command = await submit_cancel(
        session,
        wallet_id=UUID(str(stop["wallet_id"])),
        episode_id=UUID(str(stop["episode_id"])),
        order_id=UUID(str(target["order_id"])),
        idempotency_key=uuid5(
            NAMESPACE_URL, f"tiewtrade:risk-stop:{stop['id']}:{target['order_id']}"
        ),
    )
    details["cancel_command_id"] = str(command.command_id)
    return "CANCEL_PENDING", details


async def consume_stop(session: UserSession, stop_id: UUID, *, limit: int = 20) -> None:
    checked = require_user_session(session)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("bounded risk stop round required")
    await lock_risk_owner(checked, TradingMode.PAPER)
    stop = (
        (
            await checked.execute(
                """SELECT r.*,p.target_set_complete FROM risk_stop_requests r
        JOIN risk_stop_progress p ON p.stop_id=r.id WHERE r.id=:id FOR UPDATE OF p""",
                {"id": stop_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if stop is None:
        raise ValueError("risk stop not found")
    if not stop["target_set_complete"]:
        candidates = (
            (
                await checked.execute(
                    _CANDIDATES,
                    {
                        "episode": stop["episode_id"],
                        "cut": stop["recorded_at"],
                        "stop": stop_id,
                        "limit": limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        for row in candidates:
            new_target = {
                "stop_id": stop_id,
                "target_kind": row["kind"],
                "target_id": row["id"],
                "order_id": row["order_id"],
            }
            await checked.execute(
                """INSERT INTO risk_stop_targets
                (stop_id,user_id,mode,target_kind,target_id,order_id)
                VALUES(:stop,:owner,'PAPER',:kind,:target,:order)""",
                {
                    "stop": stop_id,
                    "owner": checked.user_id,
                    "kind": row["kind"],
                    "target": row["id"],
                    "order": row["order_id"],
                },
            )
            await _effect(checked, new_target, state="PENDING", attempt=0, details={})
        if len(candidates) < limit:
            await checked.execute(
                "UPDATE risk_stop_progress SET target_set_complete=true WHERE stop_id=:id",
                {"id": stop_id},
            )
    targets = (
        (
            await checked.execute(
                """SELECT t.*,e.attempt,e.state FROM risk_stop_targets t JOIN LATERAL(
          SELECT attempt,state,next_attempt_at FROM risk_stop_effects e
          WHERE (e.stop_id,e.target_kind,e.target_id)=(t.stop_id,t.target_kind,t.target_id)
          ORDER BY sequence DESC LIMIT 1) e ON true
        WHERE t.stop_id=:stop AND e.state IN ('PENDING','CANCEL_PENDING','FAILED')
          AND e.next_attempt_at<=clock_timestamp()
        ORDER BY e.next_attempt_at,t.enrolled_sequence LIMIT :limit""",
                {"stop": stop_id, "limit": limit},
            )
        )
        .mappings()
        .all()
    )
    changed = False
    for target in targets:
        await checked.execute("SAVEPOINT risk_stop_target")
        details: dict[str, object] = {"reason": "RISK_LOSS_LIMIT_REACHED"}
        try:
            if target["target_kind"] == "REQUEST":
                state = await _request(checked, target, UUID(str(stop["episode_id"])))
                if state == "CANCEL_PENDING":
                    state, details = await _order(checked, target, stop)
            elif target["target_kind"] == "COMMAND":
                state = await _command(checked, target, UUID(str(stop["episode_id"])))
                if state == "CANCEL_PENDING":
                    state, details = await _order(checked, target, stop)
            else:
                state, details = await _order(checked, target, stop)
        except Exception:
            await checked.execute("ROLLBACK TO SAVEPOINT risk_stop_target")
            state = "FAILED"
            details = {"reason": "RISK_STOP_RETRY_PENDING"}
        await checked.execute("RELEASE SAVEPOINT risk_stop_target")
        attempt = int(target["attempt"]) + 1
        delay = min(30, 2 ** min(attempt, 5)) if state == "FAILED" else 0
        await _effect(
            checked, target, state=state, attempt=attempt, details=details, delay_seconds=delay
        )
        changed = changed or state != target["state"]
    await checked.execute(
        """WITH latest AS (SELECT DISTINCT ON (target_kind,target_id) * FROM risk_stop_effects
          WHERE stop_id=:stop ORDER BY target_kind,target_id,sequence DESC), counts AS (
          SELECT count(*) AS total,count(*) FILTER(WHERE state IN
            ('PENDING','CANCEL_PENDING','FAILED')) AS pending,
            count(*) FILTER(WHERE state='FAILED') AS failed,coalesce(max(sequence),0) AS revision
          FROM latest)
        UPDATE risk_stop_progress SET target_count=c.total,pending_count=c.pending,
          failed_count=c.failed,effects_revision=c.revision,
          alert_due=(c.pending>0 AND :cut<=clock_timestamp()-interval '1 minute'),
          due_at=clock_timestamp()+interval '200 milliseconds'
        FROM counts c WHERE stop_id=:stop""",
        {"stop": stop_id, "cut": stop["recorded_at"]},
    )
    if changed:
        from tiewtrade.core.risk_limits import RiskScope
        from tiewtrade.infra.risk_limits.storage import read_setting

        setting = await read_setting(
            checked,
            RiskScope(
                UUID(str(checked.user_id)),
                TradingMode.PAPER,
                UUID(str(stop["wallet_id"])),
                UUID(str(stop["episode_id"])),
            ),
        )
        await record_event(
            checked,
            AuditEvent(
                owner_user_id=checked.user_id,
                action=AuditAction.RISK_STOP_UPDATED,
                actor_kind=ActorKind.SYSTEM,
                subject_kind=SubjectKind.RISK_LIMIT,
                subject_id=str(checked.user_id),
                outcome=AuditOutcome.SUCCEEDED,
                mode=AuditMode.PAPER,
                details=RiskLimitDetails(
                    uuid5(
                        NAMESPACE_URL,
                        f"{stop_id}:{targets[-1]['target_id']}:{targets[-1]['attempt']}",
                    ),
                    None,
                    setting.revision,
                    setting.limit,
                    stop_id=UUID(str(stop_id)),
                ),
            ),
        )


async def queued_opening_stopped(
    session: UserSession,
    *,
    episode_id: UUID,
    recorded_at: Any,
) -> bool:
    return (
        await session.execute(
            """SELECT 1 FROM risk_stop_requests WHERE mode='PAPER' AND episode_id=:episode
        AND recorded_at>=:recorded LIMIT 1""",
            {"episode": episode_id, "recorded": recorded_at},
        )
    ).first() is not None


async def cancel_stopped_remainders(session: UserSession, wallet_id: UUID, state: Any) -> Any:
    from tiewtrade.core.paper_matching import cancel_order
    from tiewtrade.infra.paper_orders.matching_storage import persist_checkpoint

    active = [
        order.intent.order_id
        for order in state.orders
        if not order.status.terminal and order.intent.kind in (OrderType.MARKET, OrderType.LIMIT)
    ]
    if not active:
        return state
    # Probe the indexed lifecycle only for this checkpoint's active candidates.
    # Historical stops still apply after reset; completed order history is irrelevant.
    stopped = {
        UUID(str(row.order_id))
        for row in await session.execute(
            """SELECT candidate.order_id
        FROM unnest(CAST(:orders AS uuid[])) candidate(order_id)
        CROSS JOIN LATERAL(SELECT 1 FROM risk_order_lifecycle l
          JOIN risk_stop_requests s ON s.user_id=l.user_id
            AND s.episode_id=l.episode_id AND s.mode='PAPER'
          WHERE l.order_id=candidate.order_id AND l.episode_id=:episode
            AND l.recorded_at<=s.recorded_at LIMIT 1) stopped""",
            {"episode": state.scope.episode_id, "orders": active},
        )
    }
    anchor = None
    for order in state.orders:
        if order.intent.order_id in stopped and not order.status.terminal:
            state = cancel_order(state, order.intent.order_id, scope=state.scope)
            anchor = order.intent.order_id
    if anchor is not None:
        await persist_checkpoint(
            session,
            wallet_id=wallet_id,
            state=state,
            anchor_order_id=anchor,
            event_kind="CANCELED",
            decision_kind="CANCEL",
            occurred_at=(await session.execute("SELECT clock_timestamp()")).scalar_one(),
        )
    return state
