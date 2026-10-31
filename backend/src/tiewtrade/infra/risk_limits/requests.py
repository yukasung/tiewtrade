"""Durable authorization/intake. The API cannot write the applied risk state."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import RowMapping

from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import RiskScope
from tiewtrade.infra.db.errors import ValueRejectedError
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.risk_limits.records import (
    RiskAction,
    RiskAuthorizationError,
    RiskConflictError,
    RiskReceipt,
    RiskSubmission,
)


def _decode(row: Mapping[str, Any] | RowMapping, *, authorization_only: bool) -> RiskReceipt:
    scope = RiskScope(
        UUID(str(row["user_id"])),
        TradingMode(row["mode"]),
        None if row["wallet_id"] is None else UUID(str(row["wallet_id"])),
        None if row["episode_id"] is None else UUID(str(row["episode_id"])),
    )
    submission = RiskSubmission(
        scope,
        RiskAction(row["action"]),
        UUID(str(row["idempotency_key"])),
        int(row["expected_revision"]),
        None if row["amount"] is None else Money.of(row["amount"], "USDT"),
    )
    if row["fingerprint"] != submission.fingerprint:
        raise RiskConflictError("stored risk request fingerprint is inconsistent")
    recorded_at = row["recorded_at"]
    if not isinstance(recorded_at, datetime):
        raise RiskConflictError("stored risk receipt time is invalid")
    receipt_id = UUID(str(row["id"]))
    authorization_id = receipt_id if authorization_only else row["authorization_id"]
    return RiskReceipt(
        receipt_id,
        submission,
        recorded_at,
        None if authorization_id is None else UUID(str(authorization_id)),
        authorization_only,
    )


def _owner(session: UserSession, submission: RiskSubmission) -> UserSession:
    checked = require_user_session(session)
    if submission.scope.owner_id != checked.user_id:
        raise RiskConflictError("risk submission belongs to a different owner")
    return checked


async def receipt_by_key(session: UserSession, mode: TradingMode, key: UUID) -> RiskReceipt | None:
    checked = require_user_session(session)
    # A single statement cannot miss a receipt during authorization→inbox transfer.
    row = (
        (
            await checked.execute(
                """SELECT r.id,r.user_id,r.mode,r.action,r.idempotency_key,r.expected_revision,
              r.amount,r.wallet_id,r.episode_id,r.fingerprint,r.authorization_id,r.recorded_at,
              false AS authorization_only FROM risk_limit_requests r
            WHERE r.user_id=:owner AND r.mode=:mode AND r.idempotency_key=:key
            UNION ALL
            SELECT a.id,a.user_id,a.mode,a.action,a.idempotency_key,a.expected_revision,
              a.amount,a.wallet_id,a.episode_id,a.fingerprint,a.id AS authorization_id,
              a.recorded_at,true AS authorization_only
            FROM risk_limit_authorizations a
            WHERE a.user_id=:owner AND a.mode=:mode AND a.idempotency_key=:key
              AND NOT EXISTS(SELECT 1 FROM risk_limit_requests r WHERE r.user_id=a.user_id
                AND r.mode=a.mode AND r.idempotency_key=a.idempotency_key)
            LIMIT 1""",
                {"owner": checked.user_id, "mode": mode.value, "key": key},
            )
        )
        .mappings()
        .first()
    )
    return None if row is None else _decode(row, authorization_only=bool(row["authorization_only"]))


async def receipt_by_id(
    session: UserSession, mode: TradingMode, receipt_id: UUID
) -> RiskReceipt | None:
    checked = require_user_session(session)
    row = (
        await checked.execute(
            """SELECT idempotency_key FROM risk_limit_requests
            WHERE id=:id AND user_id=:owner AND mode=:mode
            UNION ALL SELECT idempotency_key FROM risk_limit_authorizations
            WHERE id=:id AND user_id=:owner AND mode=:mode LIMIT 1""",
            {"id": receipt_id, "owner": checked.user_id, "mode": mode.value},
        )
    ).scalar_one_or_none()
    return None if row is None else await receipt_by_key(checked, mode, UUID(str(row)))


async def authorize_increase(session: UserSession, submission: RiskSubmission) -> RiskReceipt:
    """Call in the AUTH transaction that consumed F-06 TOTP; never from API role."""
    checked = _owner(session, submission)
    if (
        submission.scope.mode is not TradingMode.LIVE
        or submission.action is not RiskAction.INCREASE
    ):
        raise RiskAuthorizationError("authorization is only for an exact Live increase action")
    # AUTH role intentionally cannot read the request inbox or applied settings.
    params: dict[str, object] = {
        "id": uuid4(),
        "owner": checked.user_id,
        "mode": submission.scope.mode.value,
        "action": submission.action.value,
        "key": submission.key,
        "revision": submission.expected_revision,
        "amount": None if submission.amount is None else submission.amount.amount,
        "wallet": submission.scope.wallet_id,
        "episode": submission.scope.episode_id,
        "fingerprint": submission.fingerprint,
    }
    await checked.execute(
        """INSERT INTO risk_limit_authorizations
        (id,user_id,mode,action,idempotency_key,expected_revision,amount,wallet_id,episode_id,fingerprint)
        VALUES(:id,:owner,:mode,:action,:key,:revision,:amount,:wallet,:episode,:fingerprint)
        ON CONFLICT(user_id,mode,idempotency_key) DO NOTHING""",
        params,
    )
    row = (
        (
            await checked.execute(
                """SELECT * FROM risk_limit_authorizations
            WHERE user_id=:owner AND mode=:mode AND idempotency_key=:key""",
                params,
            )
        )
        .mappings()
        .one()
    )
    receipt = _decode(row, authorization_only=True)
    if receipt.submission != submission:
        raise RiskConflictError("risk authorization key already used differently")
    return receipt


async def authorization_for(session: UserSession, submission: RiskSubmission) -> RiskReceipt | None:
    checked = _owner(session, submission)
    row = (
        (
            await checked.execute(
                """SELECT * FROM risk_limit_authorizations
            WHERE user_id=:owner AND mode=:mode AND idempotency_key=:key""",
                {
                    "owner": checked.user_id,
                    "mode": submission.scope.mode.value,
                    "key": submission.key,
                },
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    receipt = _decode(row, authorization_only=True)
    if receipt.submission != submission:
        raise RiskConflictError("risk authorization key already used differently")
    return receipt


async def submit_request(session: UserSession, submission: RiskSubmission) -> RiskReceipt:
    checked = _owner(session, submission)
    previous = await receipt_by_key(checked, submission.scope.mode, submission.key)
    if previous is not None and previous.submission != submission:
        raise RiskConflictError("risk request key already used differently")
    if previous is not None and not previous.authorization_only:
        return previous
    if (
        submission.scope.mode is TradingMode.LIVE
        and submission.action is RiskAction.INCREASE
        and previous is None
    ):
        raise RiskAuthorizationError("exact TOTP authorization receipt required")
    request_id = uuid4() if previous is None else previous.receipt_id
    try:
        result = (
            await checked.execute(
                """SELECT risk_submit_request(:id,:mode,:action,:key,:revision,:amount,
                  :wallet,:episode,:fingerprint,:authorization)""",
                {
                    "id": request_id,
                    "mode": submission.scope.mode.value,
                    "action": submission.action.value,
                    "key": submission.key,
                    "revision": submission.expected_revision,
                    "amount": None if submission.amount is None else submission.amount.amount,
                    "wallet": submission.scope.wallet_id,
                    "episode": submission.scope.episode_id,
                    "fingerprint": submission.fingerprint,
                    "authorization": None if previous is None else previous.authorization_id,
                },
            )
        ).scalar_one()
    except ValueRejectedError:
        raise RiskConflictError("risk scope, revision or authorization changed") from None
    receipt = await receipt_by_id(checked, submission.scope.mode, UUID(str(result)))
    if receipt is None or receipt.authorization_only:
        raise RiskConflictError("risk inbox receipt missing after submission")
    return receipt
