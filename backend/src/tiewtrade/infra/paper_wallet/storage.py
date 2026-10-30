"""Durable Paper-wallet commands and owner-scoped financial state."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from tiewtrade.core.money import Money, MoneyError
from tiewtrade.core.paper_wallet import (
    PAPER_CURRENCY,
    InitialCapitalTooSmallError,
    initial_capital,
    ledger_balance,
)
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    PaperWalletCreatedDetails,
    PaperWalletRejectedDetails,
    PaperWalletResetDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db import money_from_columns, money_to_columns
from tiewtrade.infra.db.session import ScanSession, UserSession, require_user_session
from tiewtrade.infra.paper_wallet.records import (
    ACTIVITY_UNKNOWN,
    RESET_UNSAFE,
    ClaimedPaperCommand,
    DuePaperCommand,
    PaperCommand,
    PaperCommandSnapshot,
    PaperCommandState,
    PaperWalletAction,
    PaperWalletIntegrityError,
    PaperWalletSnapshot,
)

_BACKOFF = (timedelta(seconds=1), timedelta(seconds=5), timedelta(seconds=30), timedelta(minutes=5))


def _fingerprint(action: PaperWalletAction, capital: str, expected: UUID | None) -> str:
    try:
        canonical_capital = Money.of(capital, PAPER_CURRENCY).as_parts()["amount"]
    except MoneyError:
        # Invalid input has no Money representation.  Retain its exact bounded
        # text so an identical rejected request is still replayable.
        canonical_capital = capital
    encoded = json.dumps(
        {
            "action": action.value,
            "initial_capital": canonical_capital,
            "expected_episode_id": str(expected) if expected else None,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


async def _admission_lock(
    session: UserSession, action: PaperWalletAction, idempotency_key: UUID
) -> None:
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))",
        {"scope": f"paper-admission:{session.user_id}:{action.value}:{idempotency_key}"},
    )


async def inspect_submission(
    session: UserSession,
    *,
    action: PaperWalletAction,
    idempotency_key: UUID,
    capital_text: str,
    expected_episode_id: UUID | None,
) -> PaperCommand | None:
    """Serialize one key and return an exact prior result without consuming quota."""
    session = require_user_session(session)
    await _admission_lock(session, action, idempotency_key)
    fingerprint = _fingerprint(action, capital_text, expected_episode_id)
    admission = (
        await session.execute(
            """SELECT id,failure_code FROM paper_wallet_admission_results
               WHERE user_id=:owner AND action=:action AND idempotency_key=:key
                 AND request_fingerprint=:fingerprint ORDER BY rejected_at LIMIT 1""",
            {
                "owner": session.user_id,
                "action": action.value,
                "key": idempotency_key,
                "fingerprint": fingerprint,
            },
        )
    ).first()
    if admission is not None:
        return PaperCommand(admission.id, PaperCommandState.REJECTED, admission.failure_code)
    command = (
        await session.execute(
            """SELECT id,request_fingerprint FROM paper_wallet_commands
               WHERE user_id=:owner AND action=:action AND idempotency_key=:key""",
            {"owner": session.user_id, "action": action.value, "key": idempotency_key},
        )
    ).first()
    if command is not None and command.request_fingerprint == fingerprint:
        return await get_command(session, command.id)
    return None


async def _record_rejection(
    session: UserSession,
    *,
    action: PaperWalletAction,
    idempotency_key: UUID,
    fingerprint: str,
    failure_code: str,
) -> PaperCommand:
    existing = (
        await session.execute(
            """SELECT id,failure_code FROM paper_wallet_admission_results
               WHERE user_id=:owner AND action=:action AND idempotency_key=:key
                 AND request_fingerprint=:fingerprint AND failure_code=:failure""",
            {
                "owner": session.user_id,
                "action": action.value,
                "key": idempotency_key,
                "fingerprint": fingerprint,
                "failure": failure_code,
            },
        )
    ).first()
    if existing is not None:
        return PaperCommand(existing.id, PaperCommandState.REJECTED, existing.failure_code)
    result_id = uuid4()
    await session.execute(
        """INSERT INTO paper_wallet_admission_results
           (id,user_id,action,idempotency_key,request_fingerprint,failure_code)
           VALUES (:id,:owner,:action,:key,:fingerprint,:failure)""",
        {
            "id": result_id,
            "owner": session.user_id,
            "action": action.value,
            "key": idempotency_key,
            "fingerprint": fingerprint,
            "failure": failure_code,
        },
    )
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=(
                AuditAction.PAPER_WALLET_CREATE_REJECTED
                if action is PaperWalletAction.CREATE
                else AuditAction.PAPER_WALLET_RESET_REJECTED
            ),
            actor_kind=ActorKind.USER,
            actor_id=session.user_id,
            subject_kind=SubjectKind.PAPER_WALLET_COMMAND,
            subject_id=str(result_id),
            outcome=AuditOutcome.REJECTED,
            failure_code=failure_code,
            details=PaperWalletRejectedDetails(),
            mode=AuditMode.PAPER,
        ),
    )
    return PaperCommand(result_id, PaperCommandState.REJECTED, failure_code)


async def admit_command(
    session: UserSession,
    *,
    action: PaperWalletAction,
    idempotency_key: UUID,
    capital_text: str,
    expected_episode_id: UUID | None,
) -> PaperCommand:
    """Create one immutable command or one audited admission rejection."""
    session = require_user_session(session)
    await _admission_lock(session, action, idempotency_key)
    fingerprint = _fingerprint(action, capital_text, expected_episode_id)
    occupied = (
        await session.execute(
            """SELECT 1 FROM paper_wallet_commands
               WHERE user_id=:owner AND action=:action AND idempotency_key=:key
               UNION ALL SELECT 1 FROM paper_wallet_admission_results
               WHERE user_id=:owner AND action=:action AND idempotency_key=:key LIMIT 1""",
            {"owner": session.user_id, "action": action.value, "key": idempotency_key},
        )
    ).first()
    if occupied is not None:
        return await _record_rejection(
            session,
            action=action,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            failure_code="IDEMPOTENCY_CONFLICT",
        )
    try:
        capital = initial_capital(capital_text)
    except InitialCapitalTooSmallError:
        return await _record_rejection(
            session,
            action=action,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            failure_code="INITIAL_CAPITAL_TOO_SMALL",
        )
    except MoneyError:
        return await _record_rejection(
            session,
            action=action,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            failure_code="INITIAL_CAPITAL_INVALID",
        )
    amount, currency = money_to_columns(capital)
    command_id = uuid4()
    await session.execute(
        """INSERT INTO paper_wallet_commands
           (id,user_id,action,idempotency_key,request_fingerprint,initial_capital,currency,expected_episode_id)
           VALUES (:id,:owner,:action,:key,:fingerprint,:amount,:currency,:episode)""",
        {
            "id": command_id,
            "owner": session.user_id,
            "action": action.value,
            "key": idempotency_key,
            "fingerprint": fingerprint,
            "amount": amount,
            "currency": currency,
            "episode": expected_episode_id,
        },
    )
    await session.execute(
        "INSERT INTO paper_wallet_command_dispatch(command_id,user_id) VALUES (:id,:owner)",
        {"id": command_id, "owner": session.user_id},
    )
    return PaperCommand(command_id, PaperCommandState.PENDING)


async def get_command(session: UserSession, command_id: UUID) -> PaperCommand | None:
    session = require_user_session(session)
    command = (
        await session.execute(
            "SELECT id FROM paper_wallet_commands WHERE id=:id AND user_id=:owner",
            {"id": command_id, "owner": session.user_id},
        )
    ).first()
    if command is None:
        return None
    result = (
        await session.execute(
            """SELECT state,failure_code,wallet_id,episode_id,
                      initial_capital,balance,currency
               FROM paper_wallet_command_results WHERE command_id=:id""",
            {"id": command_id},
        )
    ).first()
    if result is None:
        return PaperCommand(command_id, PaperCommandState.PENDING)
    snapshot = None
    if result.state == PaperCommandState.SUCCEEDED.value:
        snapshot = PaperCommandSnapshot(
            wallet_id=result.wallet_id,
            episode_id=result.episode_id,
            initial_capital=money_from_columns(result.initial_capital, result.currency),
            balance=money_from_columns(result.balance, result.currency),
        )
    return PaperCommand(
        command_id,
        PaperCommandState(result.state),
        result.failure_code,
        snapshot,
    )


async def get_wallet(session: UserSession) -> PaperWalletSnapshot | None:
    session = require_user_session(session)
    row = (
        await session.execute(
            """SELECT w.id wallet_id,s.active_episode_id,e.id episode_id,e.sequence,
                      e.initial_capital,e.currency,e.started_at,s.revision,
                      EXISTS(SELECT 1 FROM paper_wallet_episode_closures c
                             WHERE c.episode_id=s.active_episode_id) episode_closed,
                      rr.*,
                      clock_timestamp() snapshot_at
               FROM paper_wallets w LEFT JOIN paper_wallet_state s
                 ON s.wallet_id=w.id AND s.user_id=w.user_id
               LEFT JOIN paper_wallet_episodes e
                 ON e.id=s.active_episode_id AND e.wallet_id=w.id AND e.user_id=w.user_id
               LEFT JOIN LATERAL paper_wallet_reset_readiness(s.active_episode_id) rr ON true
               WHERE w.user_id=:owner""",
            {"owner": session.user_id},
        )
    ).first()
    if row is None:
        return None
    if (
        row.active_episode_id is None
        or row.episode_id is None
        or row.initial_capital is None
        or row.currency is None
        or row.sequence is None
        or row.started_at is None
        or row.revision is None
        or row.episode_closed
    ):
        raise PaperWalletIntegrityError("Paper wallet active episode is incomplete")
    amounts = (
        await session.execute(
            """SELECT kind,amount,currency FROM paper_wallet_ledger
               WHERE episode_id=:episode ORDER BY created_at,id""",
            {"episode": row.episode_id},
        )
    ).all()
    capital_entries = [item for item in amounts if item.kind == "EXTERNAL_CAPITAL"]
    if len(capital_entries) != 1:
        raise PaperWalletIntegrityError("Paper wallet episode has no unique external capital")
    entries = [money_from_columns(item.amount, item.currency) for item in amounts]
    stored_capital = money_from_columns(row.initial_capital, row.currency)
    ledger_capital = money_from_columns(capital_entries[0].amount, capital_entries[0].currency)
    if ledger_capital != stored_capital:
        raise PaperWalletIntegrityError("Paper wallet episode capital does not match its ledger")
    position_complete = (
        row.position_availability == "READY"
        and row.position_proof is not None
        and row.position_proof == row.initialized_position_proof
        and int(row.position_record_count) == int(row.position_sequence)
        and int(row.position_max_sequence) == int(row.position_sequence)
        and int(row.position_pair_count) == int(row.position_projection_count)
        and int(row.position_revision_mismatch) == 0
    )
    order_complete = (
        row.order_availability == "READY"
        and row.order_proof is not None
        and row.order_proof == row.initialized_order_proof
        and int(row.order_count) == int(row.order_projection_count)
        and int(row.order_count) == int(row.reservation_count)
        and int(row.order_projection_mismatch) == 0
        and int(row.reservation_revision_mismatch) == 0
    )
    reset_reason = (
        ACTIVITY_UNKNOWN
        if not position_complete or not order_complete
        else (
            RESET_UNSAFE
            if any(
                int(value) != 0
                for value in (
                    row.open_position_count,
                    row.active_order_count,
                    row.active_reservation_count,
                    row.pending_order_command_count,
                )
            )
            else None
        )
    )
    return PaperWalletSnapshot(
        wallet_id=row.wallet_id,
        episode_id=row.episode_id,
        sequence=row.sequence,
        initial_capital=stored_capital,
        balance=ledger_balance(entries),
        started_at=row.started_at,
        snapshot_at=row.snapshot_at,
        revision=row.revision,
        reset_available=reset_reason is None,
        reset_reason=reset_reason,
    )


async def due_hints(session: ScanSession, *, limit: int = 20) -> tuple[DuePaperCommand, ...]:
    rows = (
        await session.execute(
            """WITH due AS (
                 SELECT d.command_id,d.user_id,d.next_attempt_at,c.requested_at,
                        row_number() OVER (
                          PARTITION BY d.user_id
                          ORDER BY d.next_attempt_at,c.requested_at,d.command_id
                        ) AS owner_rank
                 FROM paper_wallet_command_dispatch d
                 JOIN paper_wallet_commands c ON c.id=d.command_id
                 WHERE d.next_attempt_at<=clock_timestamp()
                   AND (d.claim_expires_at IS NULL OR d.claim_expires_at<clock_timestamp())
                   AND NOT EXISTS(SELECT 1 FROM paper_wallet_command_results r
                                  WHERE r.command_id=d.command_id)
               )
               SELECT command_id,user_id FROM due WHERE owner_rank=1
               ORDER BY next_attempt_at,requested_at,command_id LIMIT :limit""",
            {"limit": limit},
        )
    ).all()
    return tuple(DuePaperCommand(row.command_id, row.user_id) for row in rows)


async def claim_command(
    session: UserSession, due: DuePaperCommand, *, worker: str
) -> ClaimedPaperCommand | None:
    claim_id = uuid4()
    row = (
        await session.execute(
            """UPDATE paper_wallet_command_dispatch SET claimed_by=:worker,claim_id=:claim,
                      claim_expires_at=clock_timestamp()+interval '30 seconds',attempts=attempts+1
               WHERE command_id=:id AND user_id=:owner
                 AND next_attempt_at<=clock_timestamp()
                 AND (claim_expires_at IS NULL OR claim_expires_at<clock_timestamp())
                 AND NOT EXISTS(SELECT 1 FROM paper_wallet_command_results r
                                WHERE r.command_id=paper_wallet_command_dispatch.command_id)
               RETURNING attempts""",
            {"worker": worker, "claim": claim_id, "id": due.command_id, "owner": due.user_id},
        )
    ).first()
    if row is None:
        return None
    command = (
        await session.execute(
            """SELECT action,initial_capital,currency,expected_episode_id
               FROM paper_wallet_commands WHERE id=:id""",
            {"id": due.command_id},
        )
    ).one()
    return ClaimedPaperCommand(
        due.command_id,
        due.user_id,
        claim_id,
        PaperWalletAction(command.action),
        money_from_columns(command.initial_capital, command.currency),
        command.expected_episode_id,
        row.attempts,
    )


async def _reject_claimed(session: UserSession, claimed: ClaimedPaperCommand, failure: str) -> None:
    await session.execute(
        """INSERT INTO paper_wallet_command_results(command_id,user_id,state,failure_code)
           VALUES (:id,:owner,'REJECTED',:failure)""",
        {"id": claimed.command_id, "owner": claimed.user_id, "failure": failure},
    )
    await record_event(
        session,
        AuditEvent(
            owner_user_id=claimed.user_id,
            action=(
                AuditAction.PAPER_WALLET_CREATE_REJECTED
                if claimed.action is PaperWalletAction.CREATE
                else AuditAction.PAPER_WALLET_RESET_REJECTED
            ),
            actor_kind=ActorKind.USER,
            actor_id=claimed.user_id,
            subject_kind=SubjectKind.PAPER_WALLET_COMMAND,
            subject_id=str(claimed.command_id),
            outcome=AuditOutcome.REJECTED,
            failure_code=failure,
            details=PaperWalletRejectedDetails(),
            mode=AuditMode.PAPER,
        ),
    )


async def _initialize_sources(
    session: UserSession, *, wallet_id: UUID, episode_id: UUID, initialization_id: UUID
) -> None:
    # The integration is transaction-bound; defer this import to avoid a module cycle.
    from tiewtrade.infra.paper_orders.initialization import initialize_order_source

    await initialize_order_source(
        session,
        wallet_id=wallet_id,
        episode_id=episode_id,
        initialization_id=initialization_id,
    )


async def _enable_f15_writer(session: UserSession) -> None:
    # The integration is transaction-bound; defer this import to avoid a module cycle.
    from tiewtrade.infra.paper_orders.initialization import enable_financial_writer

    await enable_financial_writer(session)


async def _process_reset(session: UserSession, claimed: ClaimedPaperCommand) -> PaperCommand:
    expected = claimed.expected_episode_id
    if expected is None:
        await _reject_claimed(session, claimed, "EPISODE_CONFLICT")
        return PaperCommand(claimed.command_id, PaperCommandState.REJECTED, "EPISODE_CONFLICT")
    expected = UUID(str(expected))
    state = (
        await session.execute(
            """SELECT wallet_id,active_episode_id,revision FROM paper_wallet_state
            WHERE user_id=:owner FOR UPDATE""",
            {"owner": session.user_id},
        )
    ).one_or_none()
    if state is None or UUID(str(state.active_episode_id)) != expected:
        await _reject_claimed(session, claimed, "EPISODE_CONFLICT")
        return PaperCommand(claimed.command_id, PaperCommandState.REJECTED, "EPISODE_CONFLICT")
    current = await get_wallet(session)
    if current is None or current.reset_reason is not None:
        failure = ACTIVITY_UNKNOWN if current is None else current.reset_reason
        assert failure is not None
        await _reject_claimed(session, claimed, failure)
        return PaperCommand(claimed.command_id, PaperCommandState.REJECTED, failure)

    from tiewtrade.infra.risk_limits.boundaries import financial_boundary

    episode_id = uuid5(NAMESPACE_URL, f"tiewtrade:paper-reset:{claimed.command_id}:episode")
    async with financial_boundary(
        session,
        episode_id=expected,
        kind="EPISODE",
        after_episode_id=episode_id,
    ):
        return await _reset_finances(
            session,
            claimed,
            expected=expected,
            wallet_id=UUID(str(state.wallet_id)),
            episode_id=episode_id,
            previous_sequence=current.sequence,
        )


async def _reset_finances(
    session: UserSession,
    claimed: ClaimedPaperCommand,
    *,
    expected: UUID,
    wallet_id: UUID,
    episode_id: UUID,
    previous_sequence: int,
) -> PaperCommand:
    await _enable_f15_writer(session)
    ledger_id = uuid5(NAMESPACE_URL, f"tiewtrade:paper-reset:{claimed.command_id}:capital")
    initialization_id = uuid5(NAMESPACE_URL, f"tiewtrade:paper-reset:{claimed.command_id}:sources")
    amount, currency = money_to_columns(claimed.initial_capital)
    await session.execute(
        """INSERT INTO paper_wallet_episode_closures
        (episode_id,wallet_id,user_id,reset_command_id)
        VALUES(:old_episode,:wallet,:owner,:command)""",
        {
            "old_episode": expected,
            "wallet": wallet_id,
            "owner": session.user_id,
            "command": claimed.command_id,
        },
    )
    await session.execute(
        """INSERT INTO paper_wallet_episodes
        (id,wallet_id,user_id,sequence,initial_capital,currency)
        VALUES(:episode,:wallet,:owner,:sequence,:amount,:currency)""",
        {
            "episode": episode_id,
            "wallet": wallet_id,
            "owner": session.user_id,
            "sequence": previous_sequence + 1,
            "amount": amount,
            "currency": currency,
        },
    )
    await session.execute(
        """INSERT INTO paper_position_activity(episode_id,wallet_id,user_id)
        VALUES(:episode,:wallet,:owner)""",
        {"episode": episode_id, "wallet": wallet_id, "owner": session.user_id},
    )
    await session.execute(
        """INSERT INTO paper_wallet_ledger
        (id,user_id,wallet_id,episode_id,kind,amount,currency,source_command_id)
        VALUES(:ledger,:owner,:wallet,:episode,'EXTERNAL_CAPITAL',:amount,:currency,:command)""",
        {
            "ledger": ledger_id,
            "owner": session.user_id,
            "wallet": wallet_id,
            "episode": episode_id,
            "amount": amount,
            "currency": currency,
            "command": claimed.command_id,
        },
    )
    moved = (
        await session.execute(
            """UPDATE paper_wallet_state SET active_episode_id=:episode,revision=revision+1
            WHERE wallet_id=:wallet AND active_episode_id=:old_episode
            RETURNING revision""",
            {"episode": episode_id, "wallet": wallet_id, "old_episode": expected},
        )
    ).one_or_none()
    if moved is None:
        raise PaperWalletIntegrityError("Paper reset lost the active episode fence")
    await _initialize_sources(
        session,
        wallet_id=wallet_id,
        episode_id=episode_id,
        initialization_id=initialization_id,
    )
    snapshot = await get_wallet(session)
    if snapshot is None or snapshot.episode_id != episode_id or not snapshot.reset_available:
        raise PaperWalletIntegrityError("new Paper episode sources are not ready")
    await session.execute(
        """INSERT INTO paper_wallet_command_results
        (command_id,user_id,state,wallet_id,episode_id,initial_capital,balance,currency)
        VALUES(:command,:owner,'SUCCEEDED',:wallet,:episode,:amount,:amount,:currency)""",
        {
            "command": claimed.command_id,
            "owner": session.user_id,
            "wallet": wallet_id,
            "episode": episode_id,
            "amount": amount,
            "currency": currency,
        },
    )
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PAPER_WALLET_RESET,
            actor_kind=ActorKind.USER,
            actor_id=session.user_id,
            subject_kind=SubjectKind.PAPER_WALLET,
            subject_id=str(wallet_id),
            outcome=AuditOutcome.SUCCEEDED,
            details=PaperWalletResetDetails(
                claimed.command_id, expected, episode_id, claimed.initial_capital
            ),
            mode=AuditMode.PAPER,
        ),
    )
    return PaperCommand(
        claimed.command_id,
        PaperCommandState.SUCCEEDED,
        snapshot=PaperCommandSnapshot(
            wallet_id=wallet_id,
            episode_id=episode_id,
            initial_capital=claimed.initial_capital,
            balance=claimed.initial_capital,
        ),
    )


async def process_claimed(session: UserSession, claimed: ClaimedPaperCommand) -> PaperCommand:
    """Apply a claimed command atomically under the per-owner financial lock."""
    session = require_user_session(session)
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))",
        {"scope": f"paper-wallet:{session.user_id}"},
    )
    owned = (
        await session.execute(
            """SELECT 1 FROM paper_wallet_command_dispatch
               WHERE command_id=:id AND claim_id=:claim AND claim_expires_at>clock_timestamp()""",
            {"id": claimed.command_id, "claim": claimed.claim_id},
        )
    ).first()
    if owned is None:
        return PaperCommand(claimed.command_id, PaperCommandState.PENDING)
    prior = await get_command(session, claimed.command_id)
    if prior is not None and prior.state is not PaperCommandState.PENDING:
        return prior
    if claimed.action is PaperWalletAction.RESET:
        return await _process_reset(session, claimed)
    exists = (
        await session.execute(
            "SELECT 1 FROM paper_wallets WHERE user_id=:owner",
            {"owner": session.user_id},
        )
    ).first()
    if exists is not None:
        await _reject_claimed(session, claimed, "WALLET_EXISTS")
        return PaperCommand(claimed.command_id, PaperCommandState.REJECTED, "WALLET_EXISTS")
    wallet_id, episode_id, ledger_id = uuid4(), uuid4(), uuid4()
    amount, currency = money_to_columns(claimed.initial_capital)
    await session.execute(
        "INSERT INTO paper_wallets(id,user_id) VALUES (:wallet,:owner)",
        {"wallet": wallet_id, "owner": session.user_id},
    )
    await session.execute(
        """INSERT INTO paper_wallet_episodes
           (id,wallet_id,user_id,sequence,initial_capital,currency)
           VALUES (:episode,:wallet,:owner,1,:amount,:currency)""",
        {
            "episode": episode_id,
            "wallet": wallet_id,
            "owner": session.user_id,
            "amount": amount,
            "currency": currency,
        },
    )
    await session.execute(
        """INSERT INTO paper_wallet_state(wallet_id,user_id,active_episode_id)
           VALUES (:wallet,:owner,:episode)""",
        {"wallet": wallet_id, "owner": session.user_id, "episode": episode_id},
    )
    await session.execute(
        """INSERT INTO paper_position_activity(episode_id,wallet_id,user_id)
           VALUES (:episode,:wallet,:owner)""",
        {"episode": episode_id, "wallet": wallet_id, "owner": session.user_id},
    )
    await session.execute(
        """INSERT INTO paper_wallet_ledger
           (id,user_id,wallet_id,episode_id,kind,amount,currency,source_command_id)
           VALUES (:id,:owner,:wallet,:episode,'EXTERNAL_CAPITAL',:amount,:currency,:command)""",
        {
            "id": ledger_id,
            "owner": session.user_id,
            "wallet": wallet_id,
            "episode": episode_id,
            "amount": amount,
            "currency": currency,
            "command": claimed.command_id,
        },
    )
    await _initialize_sources(
        session,
        wallet_id=wallet_id,
        episode_id=episode_id,
        initialization_id=uuid5(
            NAMESPACE_URL, f"tiewtrade:paper-create:{claimed.command_id}:sources"
        ),
    )
    await session.execute(
        """INSERT INTO paper_wallet_command_results
           (command_id,user_id,state,wallet_id,episode_id,initial_capital,balance,currency)
           VALUES (:command,:owner,'SUCCEEDED',:wallet,:episode,:amount,:amount,:currency)""",
        {
            "command": claimed.command_id,
            "owner": session.user_id,
            "wallet": wallet_id,
            "episode": episode_id,
            "amount": amount,
            "currency": currency,
        },
    )
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PAPER_WALLET_CREATED,
            actor_kind=ActorKind.USER,
            actor_id=session.user_id,
            subject_kind=SubjectKind.PAPER_WALLET,
            subject_id=str(wallet_id),
            outcome=AuditOutcome.SUCCEEDED,
            details=PaperWalletCreatedDetails(
                claimed.command_id, episode_id, claimed.initial_capital
            ),
            mode=AuditMode.PAPER,
        ),
    )
    return PaperCommand(
        claimed.command_id,
        PaperCommandState.SUCCEEDED,
        snapshot=PaperCommandSnapshot(
            wallet_id=wallet_id,
            episode_id=episode_id,
            initial_capital=claimed.initial_capital,
            balance=claimed.initial_capital,
        ),
    )


async def schedule_failure(
    session: UserSession, claimed: ClaimedPaperCommand, failure_code: str
) -> None:
    delay = _BACKOFF[min(claimed.attempts - 1, len(_BACKOFF) - 1)]
    await session.execute(
        """UPDATE paper_wallet_command_dispatch
           SET next_attempt_at=clock_timestamp()+CAST(:delay AS interval),
               claimed_by=NULL,claim_id=NULL,claim_expires_at=NULL,last_failure_code=:failure
           WHERE command_id=:id AND claim_id=:claim""",
        {
            "delay": delay,
            "failure": failure_code,
            "id": claimed.command_id,
            "claim": claimed.claim_id,
        },
    )
