"""Risk setting persistence under the existing owner financial lock."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from tiewtrade.core.money import Money
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.risk_limits import (
    RiskScope,
    RiskSetting,
    RiskUnavailableError,
    change_limit,
    reset_risk,
)
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
from tiewtrade.infra.risk_limits.books import authoritative_book
from tiewtrade.infra.risk_limits.boundaries import financial_boundary
from tiewtrade.infra.risk_limits.dispatch import RiskClaim, finish_claim, require_claim
from tiewtrade.infra.risk_limits.monitor import initialize_monitor, replay_monitor
from tiewtrade.infra.risk_limits.prices import price_watermark, read_frame
from tiewtrade.infra.risk_limits.records import RiskAction, RiskReceipt
from tiewtrade.infra.risk_limits.requests import authorization_for, receipt_by_id


async def read_setting(session: UserSession, scope: RiskScope) -> RiskSetting:
    checked = require_user_session(session)
    if scope.owner_id != checked.user_id:
        raise ValueError("risk setting owner mismatch")
    row = (
        await checked.execute(
            """SELECT revision,amount,latched FROM risk_limit_settings
            WHERE user_id=:owner AND mode=:mode""",
            {"owner": checked.user_id, "mode": scope.mode.value},
        )
    ).one_or_none()
    return _setting_from_row(scope, row)


def _setting_from_row(scope: RiskScope, row: Any) -> RiskSetting:
    return (
        RiskSetting(scope, 0, None)
        if row is None or row.revision is None
        else RiskSetting(scope, int(row.revision), Money.of(row.amount, "USDT"), bool(row.latched))
    )


async def read_monitor_owner(session: UserSession) -> tuple[RiskSetting, bool] | None:
    """Read the same owner/wallet/setting/initialization cut under the caller's lock."""
    checked = require_user_session(session)
    row = (
        await checked.execute(
            """SELECT w.wallet_id,w.active_episode_id,s.revision,s.amount,s.latched,
              o.source_revision
            FROM paper_wallet_state w
            LEFT JOIN risk_limit_settings s ON s.user_id=w.user_id AND s.mode='PAPER'
            LEFT JOIN risk_owner_state o ON o.user_id=w.user_id AND o.mode='PAPER'
            WHERE w.user_id=:owner""",
            {"owner": checked.user_id},
        )
    ).one_or_none()
    return decode_monitor_owner(checked.user_id, None if row is None else row._mapping)


def decode_monitor_owner(owner_id: UUID, row: Any) -> tuple[RiskSetting, bool] | None:
    if row is None:
        return None
    scope = RiskScope(
        owner_id,
        TradingMode.PAPER,
        UUID(str(row["wallet_id"])),
        UUID(str(row["active_episode_id"])),
    )
    setting = (
        RiskSetting(
            scope, int(row["revision"]), Money.of(row["amount"], "USDT"), bool(row["latched"])
        )
        if row["revision"] is not None
        else RiskSetting(scope, 0, None)
    )
    return setting, row["source_revision"] not in (None, 0)


async def _audit_result(
    session: UserSession,
    receipt: RiskReceipt,
    *,
    event_id: UUID,
    setting: RiskSetting,
    failure: str | None,
) -> None:
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=(
                AuditAction.RISK_LIMIT_REJECTED
                if failure
                else AuditAction.RISK_LIMIT_RESET
                if receipt.submission.action is RiskAction.RESET
                else AuditAction.RISK_LIMIT_SET
            ),
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.RISK_LIMIT,
            subject_id=str(session.user_id),
            outcome=AuditOutcome.REJECTED if failure else AuditOutcome.SUCCEEDED,
            details=RiskLimitDetails(event_id, receipt.receipt_id, setting.revision, setting.limit),
            mode=AuditMode(receipt.submission.scope.mode.value),
            failure_code=failure,
        ),
    )


async def process_request(session: UserSession, claim: RiskClaim) -> None:
    await require_claim(session, claim)
    receipt = await receipt_by_id(session, claim.due.mode, claim.due.request_id)
    if receipt is None:
        raise ValueError("claimed risk inbox record missing")
    scope = receipt.submission.scope
    active = (
        None
        if scope.episode_id is None
        else (
            await session.execute(
                """SELECT 1 FROM paper_wallet_state WHERE active_episode_id=:episode
        AND wallet_id=:wallet""",
                {"episode": scope.episode_id, "wallet": scope.wallet_id},
            )
        ).first()
    )
    applied = (
        await session.execute(
            "SELECT 1 FROM risk_limit_results WHERE request_id=:id",
            {"id": receipt.receipt_id},
        )
    ).first()
    if scope.episode_id is None or active is None or applied is not None:
        await _process_request(session, claim)
    else:
        async with financial_boundary(
            session,
            episode_id=scope.episode_id,
            kind="RESET" if receipt.submission.action is RiskAction.RESET else "SETTING",
        ):
            await _process_request(session, claim)


async def _process_request(session: UserSession, claim: RiskClaim) -> None:
    checked = require_user_session(session)
    await require_claim(checked, claim)
    receipt = await receipt_by_id(checked, claim.due.mode, claim.due.request_id)
    if receipt is None or receipt.authorization_only:
        raise ValueError("claimed risk inbox record missing")
    previous = (
        await checked.execute(
            "SELECT 1 FROM risk_limit_results WHERE request_id=:id",
            {"id": receipt.receipt_id},
        )
    ).first()
    if previous is not None:
        await finish_claim(checked, claim)
        return
    value = receipt.submission
    setting = await read_setting(checked, value.scope)
    failure = None
    if setting.revision != value.expected_revision:
        failure = "RISK_REVISION_CONFLICT"
    elif value.scope.episode_id is not None:
        active = (
            await checked.execute(
                """SELECT 1 FROM paper_wallet_state s WHERE s.user_id=:owner
                  AND s.wallet_id=:wallet AND s.active_episode_id=:episode
                  AND NOT EXISTS(SELECT 1 FROM paper_wallet_episode_closures c
                    WHERE c.episode_id=:episode)""",
                {
                    "owner": checked.user_id,
                    "wallet": value.scope.wallet_id,
                    "episode": value.scope.episode_id,
                },
            )
        ).first()
        if active is None:
            failure = "RISK_SCOPE_CONFLICT"
    if (
        failure is None
        and value.scope.mode is TradingMode.LIVE
        and value.action is RiskAction.INCREASE
    ):
        proof = await authorization_for(checked, value)
        if proof is None or proof.authorization_id != receipt.authorization_id:
            failure = "RISK_AUTHORIZATION_REQUIRED"
    protocol = (
        bool(
            (
                await checked.execute("SELECT publication_enabled FROM risk_protocol_control")
            ).scalar_one()
        )
        and value.scope.episode_id is not None
    )
    if failure is None and protocol and setting.limit is not None:
        try:
            evaluation = await replay_monitor(checked, setting)
            setting = await read_setting(checked, value.scope)
            if setting.revision != value.expected_revision:
                failure = "RISK_REVISION_CONFLICT"
            elif evaluation.reason.value == "RISK_SOURCE_UNAVAILABLE":
                failure = "RISK_SOURCE_UNAVAILABLE"
        except RiskUnavailableError:
            failure = "RISK_SOURCE_UNAVAILABLE"
    if failure is None:
        if value.action is RiskAction.RESET and not protocol:
            failure = "RISK_SOURCE_UNAVAILABLE"
        elif (value.action is RiskAction.SET and setting.limit is not None) or (
            value.action in (RiskAction.DECREASE, RiskAction.INCREASE) and setting.limit is None
        ):
            failure = "RISK_REVISION_CONFLICT"
        elif value.amount is None and value.action is not RiskAction.RESET:
            failure = "RISK_INPUT_INVALID"
        elif (
            setting.limit is not None
            and value.amount is not None
            and (
                (value.action is RiskAction.DECREASE and not value.amount < setting.limit)
                or (value.action is RiskAction.INCREASE and not value.amount > setting.limit)
            )
        ):
            failure = "RISK_REVISION_CONFLICT"
    event_id = uuid4()
    baseline_id = None
    if failure is None and value.action is RiskAction.RESET:
        try:
            book, source_proof = await authoritative_book(checked, value.scope)
            watermark = await price_watermark(checked)
            frame = await read_frame(checked, watermark)
            now: datetime = (await checked.execute("SELECT clock_timestamp()")).scalar_one()
            setting, baseline = reset_risk(
                setting,
                book,
                frame.prices,
                reset_id=event_id,
                now=now,
                source_ready=True,
            )
            baseline_id = baseline.reset_id
            await checked.execute(
                """INSERT INTO risk_limit_baselines
                (id,user_id,mode,request_id,source_revision,wallet_id,episode_id,source_proof,snapshot)
                VALUES(:id,:owner,:mode,:request,:revision,:wallet,:episode,:proof,
                  CAST(:snapshot AS jsonb))""",
                {
                    "id": baseline_id,
                    "owner": checked.user_id,
                    "mode": value.scope.mode.value,
                    "request": receipt.receipt_id,
                    "revision": book.source_revision,
                    "wallet": value.scope.wallet_id,
                    "episode": value.scope.episode_id,
                    "proof": source_proof,
                    "snapshot": json.dumps(
                        {
                            "source_sequence": max(
                                (p.position.last_sequence for p in book.pairs), default=0
                            ),
                            "price_watermark": watermark,
                            "reset_at": now.isoformat(),
                        }
                    ),
                },
            )
        except RiskUnavailableError:
            failure = "RISK_SOURCE_UNAVAILABLE"
    if failure is None:
        if value.action is not RiskAction.RESET:
            assert value.amount is not None
            setting = change_limit(setting, value.amount)
        assert setting.limit is not None
        await checked.execute(
            """INSERT INTO risk_limit_settings(user_id,mode,revision,amount,latched)
              VALUES(:owner,:mode,:revision,:amount,:latched)
              ON CONFLICT(user_id,mode) DO UPDATE SET revision=EXCLUDED.revision,
                amount=EXCLUDED.amount,latched=EXCLUDED.latched,updated_at=clock_timestamp()""",
            {
                "owner": checked.user_id,
                "mode": value.scope.mode.value,
                "revision": setting.revision,
                "amount": setting.limit.amount,
                "latched": setting.latched,
            },
        )
        if baseline_id is not None:
            await checked.execute(
                "UPDATE risk_limit_settings SET baseline_id=:id WHERE mode=:mode",
                {"id": baseline_id, "mode": value.scope.mode.value},
            )
        await checked.execute(
            """INSERT INTO risk_limit_events
              (id,user_id,mode,revision,kind,request_id,amount,latched,details)
              VALUES(:id,:owner,:mode,:revision,:kind,:request,:amount,:latched,'{}')""",
            {
                "id": event_id,
                "owner": checked.user_id,
                "mode": value.scope.mode.value,
                "revision": setting.revision,
                "kind": value.action.value,
                "request": receipt.receipt_id,
                "amount": setting.limit.amount,
                "latched": setting.latched,
            },
        )
        await checked.execute(
            """INSERT INTO risk_limit_evaluations
              (user_id,mode,setting_revision,reason,latched,replay_pending)
              VALUES(:owner,:mode,:revision,'RISK_SOURCE_UNAVAILABLE',:latched,true)
              ON CONFLICT(user_id,mode) DO UPDATE SET setting_revision=EXCLUDED.setting_revision,
                reason=EXCLUDED.reason,loss=NULL,latched=EXCLUDED.latched,evaluated_at=clock_timestamp(),
                source_revision=NULL,price_watermark=NULL,input_ready_at=NULL,replay_pending=true""",
            {
                "owner": checked.user_id,
                "mode": value.scope.mode.value,
                "revision": setting.revision,
                "latched": setting.latched,
            },
        )
        if protocol:
            try:
                if value.action in (RiskAction.SET, RiskAction.RESET):
                    await initialize_monitor(checked, setting)
                else:
                    await replay_monitor(checked, setting)
            except RiskUnavailableError:
                # Preserve the unavailable projection above. An amount change
                # never turns a missing source into zero loss or clears a latch.
                pass
    await _audit_result(checked, receipt, event_id=event_id, setting=setting, failure=failure)
    setting = await read_setting(checked, value.scope)
    await checked.execute(
        """INSERT INTO risk_limit_results
          (request_id,user_id,mode,state,failure_code,revision,snapshot)
          VALUES(:request,:owner,:mode,:state,:failure,:revision,CAST(:snapshot AS jsonb))""",
        {
            "request": receipt.receipt_id,
            "owner": checked.user_id,
            "mode": value.scope.mode.value,
            "state": "APPLIED" if failure is None else "REJECTED",
            "failure": failure,
            "revision": setting.revision if setting.revision else None,
            "snapshot": json.dumps(
                {
                    "amount": None if setting.limit is None else setting.limit.as_parts()["amount"],
                    "revision": setting.revision,
                    "latched": setting.latched,
                }
            ),
        },
    )
    await finish_claim(checked, claim)
