"""Atomic inbox-to-F15 transfer under the shared wallet lock and claim fence."""

from enum import Enum
from uuid import UUID

from tiewtrade.core.manual_trading import ManualUseRequiredError
from tiewtrade.core.orders import (
    AdmissionPolicy,
    OrderConflictError,
    OrderError,
    OrderIntent,
    SourceUnavailableError,
    UnsupportedOrderError,
)
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.risk_limits import RiskUnavailableError
from tiewtrade.infra.audit import AuditAction
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.paper_orders.codec import intent_from_payload
from tiewtrade.infra.paper_orders.dispatch import submit_cancel, submit_order
from tiewtrade.infra.paper_orders.manual_policy import manual_policy_for
from tiewtrade.infra.paper_orders.request_dispatch import (
    ClaimedRequest,
    defer_request_claim,
    finish_request_claim,
    require_request_claim,
)
from tiewtrade.infra.paper_orders.requests import get_request, request_audit
from tiewtrade.infra.paper_orders.storage import LockedPairCatalog, lock_pair_catalog
from tiewtrade.infra.risk_limits.policy import TransactionalRiskPolicy
from tiewtrade.infra.risk_limits.stops import queued_opening_stopped


class RequestOutcome(Enum):
    PROCESSED = "PROCESSED"
    DEFERRED = "DEFERRED"


def _catalog_current(fence: LockedPairCatalog, revision: int | None, intent: OrderIntent) -> bool:
    return (
        revision is not None
        and (fence.latest_removed_revision is None or fence.latest_removed_revision <= revision)
        and fence.snapshot.supports(intent.pair.base, intent.pair.quote)
    )


async def _pending_price_replay(session: UserSession, wallet_id: UUID, episode_id: UUID) -> bool:
    # The engine replay holds the publication fence and owner lock through commit.
    # Successful bounded progress records its cursor as the evaluation watermark.
    # An integrity/source exception instead records the captured current watermark;
    # never turn that failure, missing policy, wrong use or a latch into this retry.
    return bool(
        (
            await session.execute(
                """SELECT EXISTS(SELECT 1 FROM risk_owner_state o
        JOIN risk_limit_settings s USING(user_id,mode)
        JOIN risk_limit_evaluations e USING(user_id,mode)
        JOIN user_trading_preferences u USING(user_id)
        JOIN paper_wallet_state w USING(user_id)
        CROSS JOIN risk_price_publication p CROSS JOIN risk_protocol_control c
        WHERE o.mode='PAPER' AND o.wallet_id=:wallet AND o.episode_id=:episode
          AND w.wallet_id=o.wallet_id AND w.active_episode_id=o.episode_id
          AND s.amount IS NOT NULL AND NOT s.latched AND NOT e.latched AND u.use='MANUAL'
          AND e.setting_revision=s.revision AND e.reason='RISK_SOURCE_UNAVAILABLE'
          AND e.replay_pending AND o.replay_pending
          AND e.source_revision=o.source_revision AND e.price_watermark=o.cursor
          AND o.cursor<p.watermark AND c.publication_enabled
          AND c.financial_enabled AND c.admission_enabled)""",
                {"wallet": wallet_id, "episode": episode_id},
            )
        ).scalar_one()
    )


def _failure_code(error: OrderError) -> str:
    if isinstance(error, ManualUseRequiredError):
        return "MANUAL_USE_REQUIRED"
    if isinstance(error, UnsupportedOrderError):
        return "ORDER_UNSUPPORTED"
    if isinstance(error, OrderConflictError):
        return "ORDER_CONFLICT"
    return "ORDER_SAFETY_UNAVAILABLE"


async def process_request(
    session: UserSession, claim: ClaimedRequest, *, policy: AdmissionPolicy | None
) -> RequestOutcome:
    session = require_user_session(session)
    await require_request_claim(session, claim)
    receipt = await get_request(session, claim.request_id)
    if receipt is None:
        raise OrderConflictError("claimed request missing")
    previous = (
        await session.execute(
            "SELECT 1 FROM paper_order_request_results WHERE request_id=:id",
            {"id": claim.request_id},
        )
    ).first()
    if previous is not None:
        await finish_request_claim(session, claim)
        return RequestOutcome.PROCESSED
    active = (
        await session.execute(
            """SELECT 1 FROM paper_wallet_state s
        WHERE s.wallet_id=:wallet AND s.active_episode_id=:episode AND NOT EXISTS(
          SELECT 1 FROM paper_wallet_episode_closures c WHERE c.episode_id=:episode)""",
            {"wallet": receipt.wallet_id, "episode": receipt.episode_id},
        )
    ).first()
    failure = None if active is not None else "EPISODE_CONFLICT"
    command = None
    if (
        failure is None
        and receipt.action == "NEW"
        and receipt.payload.get("side") == "BUY"
        and await queued_opening_stopped(
            session, episode_id=receipt.episode_id, recorded_at=receipt.recorded_at
        )
    ):
        failure = "ORDER_SAFETY_UNAVAILABLE"
    prechecked: AdmissionPolicy | None = None
    if failure is None and receipt.action == "NEW" and isinstance(policy, TransactionalRiskPolicy):
        intent = intent_from_payload(receipt.payload)
        opening_fence = (
            await lock_pair_catalog(session, intent.pair)
            if intent.side is ExecutionSide.BUY
            else None
        )
        try:
            prechecked = await manual_policy_for(session, intent, delegate=policy)
            prechecked.check(intent)
        except SourceUnavailableError:
            raise
        except RiskUnavailableError as error:
            if (
                opening_fence is not None
                and _catalog_current(opening_fence, receipt.admitted_catalog_revision, intent)
                and await _pending_price_replay(session, receipt.wallet_id, receipt.episode_id)
            ):
                await require_request_claim(session, claim)
                await defer_request_claim(session, claim)
                return RequestOutcome.DEFERRED
            failure = _failure_code(error)
        except OrderError as error:
            failure = _failure_code(error)
    if failure is None:
        await session.execute("SAVEPOINT manual_transfer")
        try:
            if receipt.action == "NEW":
                intent = intent_from_payload(receipt.payload)
                if intent.side is ExecutionSide.BUY:
                    fence = await lock_pair_catalog(session, intent.pair)
                    revision = receipt.admitted_catalog_revision
                    if not _catalog_current(fence, revision, intent):
                        failure = "CATALOG_PAIR_REMOVED"
                if failure is None:
                    checked = prechecked or await manual_policy_for(
                        session, intent, delegate=policy
                    )
                    checked.check(intent)
                    command = await submit_order(
                        session,
                        wallet_id=receipt.wallet_id,
                        intent=intent,
                        admitted_catalog_revision=receipt.admitted_catalog_revision,
                    )
            else:
                command = await submit_cancel(
                    session,
                    wallet_id=receipt.wallet_id,
                    episode_id=receipt.episode_id,
                    order_id=receipt.order_id,
                    idempotency_key=receipt.idempotency_key,
                )
        except SourceUnavailableError:
            raise
        except OrderError as error:
            await session.execute("ROLLBACK TO SAVEPOINT manual_transfer")
            failure = _failure_code(error)
        await session.execute("RELEASE SAVEPOINT manual_transfer")
    await require_request_claim(session, claim)
    await session.execute(
        """INSERT INTO paper_order_request_results
        (request_id,user_id,episode_id,order_id,action,state,command_id,failure_code)
        VALUES(:id,:owner,:episode,:order,:action,:state,:command,:failure)""",
        {
            "id": receipt.request_id,
            "owner": session.user_id,
            "episode": receipt.episode_id,
            "order": receipt.order_id,
            "action": receipt.action,
            "state": "TRANSFERRED" if failure is None else "REJECTED",
            "command": None if command is None else command.command_id,
            "failure": failure,
        },
    )
    await request_audit(
        session,
        receipt,
        action=AuditAction.PAPER_ORDER_REQUEST_TRANSFERRED
        if failure is None
        else AuditAction.PAPER_ORDER_REQUEST_REJECTED,
        command_id=None if command is None else command.command_id,
        failure_code=failure,
    )
    await finish_request_claim(session, claim)
    return RequestOutcome.PROCESSED
