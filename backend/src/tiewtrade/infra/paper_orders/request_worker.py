"""Atomic inbox-to-F15 transfer under the shared wallet lock and claim fence."""

from tiewtrade.core.manual_trading import ManualUseRequiredError
from tiewtrade.core.orders import (
    AdmissionPolicy,
    OrderConflictError,
    OrderError,
    SourceUnavailableError,
    UnsupportedOrderError,
)
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.audit import AuditAction
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.paper_orders.codec import intent_from_payload
from tiewtrade.infra.paper_orders.dispatch import submit_cancel, submit_order
from tiewtrade.infra.paper_orders.manual_policy import manual_policy_for
from tiewtrade.infra.paper_orders.request_dispatch import (
    ClaimedRequest,
    finish_request_claim,
    require_request_claim,
)
from tiewtrade.infra.paper_orders.requests import get_request, request_audit
from tiewtrade.infra.paper_orders.storage import lock_pair_catalog


async def process_request(
    session: UserSession, claim: ClaimedRequest, *, policy: AdmissionPolicy | None
) -> None:
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
        return
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
    if failure is None:
        await session.execute("SAVEPOINT manual_transfer")
        try:
            if receipt.action == "NEW":
                intent = intent_from_payload(receipt.payload)
                if intent.side is ExecutionSide.BUY:
                    fence = await lock_pair_catalog(session, intent.pair)
                    revision = receipt.admitted_catalog_revision
                    if (
                        revision is None
                        or (
                            fence.latest_removed_revision is not None
                            and fence.latest_removed_revision > revision
                        )
                        or not fence.snapshot.supports(intent.pair.base, intent.pair.quote)
                    ):
                        failure = "CATALOG_PAIR_REMOVED"
                if failure is None:
                    checked = await manual_policy_for(session, intent, delegate=policy)
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
            if isinstance(error, ManualUseRequiredError):
                failure = "MANUAL_USE_REQUIRED"
            elif isinstance(error, UnsupportedOrderError):
                failure = "ORDER_UNSUPPORTED"
            elif isinstance(error, OrderConflictError):
                failure = "ORDER_CONFLICT"
            else:
                failure = "ORDER_SAFETY_UNAVAILABLE"
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
