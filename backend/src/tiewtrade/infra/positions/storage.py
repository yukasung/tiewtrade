"""Transaction-bound Paper position writer and snapshot reader (F-14)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import RowMapping

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import (
    ExecutionFact,
    ExecutionSide,
    FeeEffect,
    InsufficientPositionError,
    InvalidPositionInputError,
    PositionAvailability,
    PositionPair,
    PositionSequenceError,
    PositionState,
    rebuild_correction,
    unrealized_pnl,
)
from tiewtrade.core.realtime_prices import MAX_PRICE_AGE
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    PaperPositionConflictDetails,
    PaperPositionDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db import (
    money_from_columns,
    money_to_columns,
    quantity_from_columns,
    quantity_to_columns,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.catalog import PAIRS
from tiewtrade.infra.positions.records import (
    PairEconomicEffects,
    PositionActivity,
    PositionEventKind,
    PositionIntegrityError,
    PositionSnapshot,
    PositionValuation,
    PositionWriteResult,
    PositionWriteStatus,
    ValuedPositionSnapshot,
)

_PROOF = re.compile(r"^[0-9a-f]{64}$")


def _activity(row: Mapping[str, Any] | RowMapping) -> PositionActivity:
    return PositionActivity(
        episode_id=row["episode_id"],
        wallet_id=row["wallet_id"],
        user_id=row["user_id"],
        mode=row["mode"],
        availability=PositionAvailability(row["availability"]),
        source_sequence=int(row["source_sequence"]),
        revision=int(row["revision"]),
        source_proof=row["source_proof"],
        observed_at=row["observed_at"],
        failure_code=row["failure_code"],
    )


async def _lock_active(session: UserSession, episode_id: UUID) -> RowMapping:
    await session.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))",
        {"scope": f"paper-wallet:{session.user_id}"},
    )
    row = (
        (
            await session.execute(
                """SELECT a.* FROM paper_wallet_state s
                JOIN paper_position_activity a
                  ON a.wallet_id=s.wallet_id AND a.user_id=s.user_id
                 AND a.episode_id=s.active_episode_id
                WHERE s.user_id=:owner AND s.active_episode_id=:episode
                FOR UPDATE OF s,a""",
                {"owner": session.user_id, "episode": episode_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise PositionIntegrityError("active Paper episode is unavailable")
    return row


def _fact_payload(fact: ExecutionFact | None) -> dict[str, object] | None:
    if fact is None:
        return None
    quantity = fact.gross_quantity.as_parts()
    quote = fact.quote_amount.as_parts()
    fee: dict[str, str] | None = None
    if fact.fee is not None:
        parts = fact.fee.amount.as_parts()
        fee = {
            "amount": parts["amount" if type(fact.fee.amount) is Money else "quantity"],
            "unit": parts["currency" if type(fact.fee.amount) is Money else "asset"],
        }
    return {
        "execution_id": str(fact.execution_id),
        "base": fact.pair.base,
        "quote": fact.pair.quote,
        "side": fact.side.value,
        "quantity": quantity["quantity"],
        "quote_amount": quote["amount"],
        "fee": fee,
        "source_sequence": fact.source_sequence,
        "occurred_at": fact.occurred_at.astimezone(UTC).isoformat(),
    }


def _fingerprint(
    kind: PositionEventKind, fact: ExecutionFact | None, supersedes_event_id: UUID | None
) -> str:
    payload = _fact_payload(fact)
    if kind is PositionEventKind.VOID and payload is not None:
        payload = {
            key: payload[key] for key in ("execution_id", "base", "quote", "source_sequence")
        }
    canonical = json.dumps(
        {
            "kind": kind.value,
            "supersedes": None if supersedes_event_id is None else str(supersedes_event_id),
            "fact": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _initialization_fingerprint(initialization_id: UUID, proof: str) -> str:
    return hashlib.sha256(f"{initialization_id}:{proof}".encode()).hexdigest()


async def read_position_activity(session: UserSession, episode_id: UUID) -> PositionActivity | None:
    checked = require_user_session(session)
    row = (
        (
            await checked.execute(
                "SELECT * FROM paper_position_activity WHERE episode_id=:episode",
                {"episode": episode_id},
            )
        )
        .mappings()
        .first()
    )
    return None if row is None else _activity(row)


async def initialize_position_source(
    session: UserSession, episode_id: UUID, initialization_id: UUID, source_proof: str
) -> PositionActivity:
    """Make the new empty Paper source authoritative; retry is proof-idempotent."""
    checked = require_user_session(session)
    if type(initialization_id) is not UUID or _PROOF.fullmatch(source_proof) is None:
        raise PositionIntegrityError("invalid position source proof")
    row = await _lock_active(checked, episode_id)
    current = _activity(row)
    if current.availability is PositionAvailability.READY and row["source_proof"] == source_proof:
        return current
    if current.availability is PositionAvailability.UNKNOWN:
        updated = (
            (
                await checked.execute(
                    """UPDATE paper_position_activity
                    SET availability='READY',source_proof=:proof,revision=revision+1,
                        observed_at=clock_timestamp(),failure_code=NULL
                    WHERE episode_id=:episode RETURNING *""",
                    {"episode": episode_id, "proof": source_proof},
                )
            )
            .mappings()
            .one()
        )
        return _activity(updated)
    fingerprint = _initialization_fingerprint(initialization_id, source_proof)
    return await _record_source_conflict(
        checked, current, initialization_id, fingerprint, "POSITION_SOURCE_UNKNOWN"
    )


async def _record_source_conflict(
    session: UserSession,
    current: PositionActivity,
    initialization_id: UUID,
    fingerprint: str,
    failure_code: str,
) -> PositionActivity:
    inserted = (
        await session.execute(
            """INSERT INTO paper_position_conflicts
            (id,initialization_id,user_id,wallet_id,episode_id,fingerprint,failure_code)
            VALUES (:id,:initialization,:owner,:wallet,:episode,:fingerprint,:failure)
            ON CONFLICT (user_id,episode_id,fingerprint) DO NOTHING RETURNING id""",
            {
                "id": uuid4(),
                "initialization": initialization_id,
                "owner": session.user_id,
                "wallet": current.wallet_id,
                "episode": current.episode_id,
                "fingerprint": fingerprint,
                "failure": failure_code,
            },
        )
    ).first()
    if inserted is None:
        latest = await read_position_activity(session, current.episode_id)
        if latest is None:
            raise PositionIntegrityError("position activity disappeared")
        return latest
    revision = current.revision + 1
    await session.execute(
        """UPDATE paper_position_projections SET revision=:revision
        WHERE episode_id=:episode""",
        {"episode": current.episode_id, "revision": revision},
    )
    updated = (
        (
            await session.execute(
                """UPDATE paper_position_activity SET availability='CONFLICTED',
                revision=:revision,observed_at=clock_timestamp(),failure_code=:failure
                WHERE episode_id=:episode RETURNING *""",
                {
                    "episode": current.episode_id,
                    "failure": failure_code,
                    "revision": revision,
                },
            )
        )
        .mappings()
        .one()
    )
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PAPER_POSITION_CONFLICTED,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.PAPER_POSITION_ACTIVITY,
            subject_id=str(current.episode_id),
            outcome=AuditOutcome.FAILED,
            failure_code=failure_code,
            mode=AuditMode.PAPER,
            details=PaperPositionConflictDetails(
                episode_id=current.episode_id, initialization_id=initialization_id
            ),
        ),
    )
    return _activity(updated)


async def _event_rows(session: UserSession, episode_id: UUID) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            """SELECT * FROM paper_position_events WHERE episode_id=:episode
            ORDER BY recorded_at,id""",
            {"episode": episode_id},
        )
    ).mappings()
    return [dict(row) for row in rows]


def _row_fact(row: Mapping[str, Any]) -> ExecutionFact:
    pair = PositionPair(row["base"], row["quote"])
    fee = None
    if row["fee_amount"] is not None:
        amount = (
            money_from_columns(row["fee_amount"], row["fee_unit"])
            if row["fee_unit"] == pair.quote
            else quantity_from_columns(row["fee_amount"], row["fee_unit"])
        )
        fee = FeeEffect(amount)
    return ExecutionFact(
        execution_id=UUID(str(row["execution_id"])),
        pair=pair,
        side=ExecutionSide(row["side"]),
        gross_quantity=quantity_from_columns(row["gross_quantity"], pair.base),
        quote_amount=money_from_columns(row["quote_amount"], pair.quote),
        fee=fee,
        source_sequence=int(row["source_sequence"]),
        occurred_at=row["occurred_at"],
    )


def _effective_slots(
    rows: list[dict[str, Any]], pair: PositionPair, source_sequence: int
) -> tuple[ExecutionFact | None, ...]:
    by_id = {row["id"]: row for row in rows}
    children: dict[UUID, dict[str, Any]] = {}
    roots: dict[int, dict[str, Any]] = {}
    for row in rows:
        if row["event_kind"] == PositionEventKind.RECORD.value:
            sequence = int(row["source_sequence"])
            if sequence in roots:
                raise PositionIntegrityError("duplicate source sequence")
            roots[sequence] = row
        else:
            parent = row["supersedes_event_id"]
            if parent not in by_id or parent in children:
                raise PositionIntegrityError("invalid correction chain")
            children[parent] = row
    if set(roots) != set(range(1, source_sequence + 1)):
        raise PositionIntegrityError("incomplete position source stream")
    slots: list[ExecutionFact | None] = [None] * source_sequence
    for sequence, root in roots.items():
        leaf = root
        seen: set[UUID] = set()
        while leaf["id"] in children:
            if leaf["id"] in seen:
                raise PositionIntegrityError("cyclic correction chain")
            seen.add(leaf["id"])
            leaf = children[leaf["id"]]
        if (leaf["base"], leaf["quote"]) == (pair.base, pair.quote):
            slots[sequence - 1] = (
                None if leaf["event_kind"] == PositionEventKind.VOID.value else _row_fact(leaf)
            )
    return tuple(slots)


def _candidate_row(
    event_id: UUID,
    kind: PositionEventKind,
    fact: ExecutionFact,
    supersedes_event_id: UUID | None,
    fingerprint: str,
) -> dict[str, Any]:
    fee_amount = None if fact.fee is None else fact.fee.amount.amount
    fee_unit = None
    if fact.fee is not None:
        fee_value = fact.fee.amount
        if isinstance(fee_value, Money):
            fee_unit = fee_value.currency
        else:
            assert isinstance(fee_value, Quantity)
            fee_unit = fee_value.asset
    return {
        "id": event_id,
        "execution_id": fact.execution_id,
        "event_kind": kind.value,
        "source_sequence": fact.source_sequence,
        "request_fingerprint": fingerprint,
        "supersedes_event_id": supersedes_event_id,
        "base": fact.pair.base,
        "quote": fact.pair.quote,
        "side": None if kind is PositionEventKind.VOID else fact.side.value,
        "gross_quantity": None if kind is PositionEventKind.VOID else fact.gross_quantity.amount,
        "quote_amount": None if kind is PositionEventKind.VOID else fact.quote_amount.amount,
        "fee_amount": None if kind is PositionEventKind.VOID else fee_amount,
        "fee_unit": None if kind is PositionEventKind.VOID else fee_unit,
        "occurred_at": None if kind is PositionEventKind.VOID else fact.occurred_at,
        "recorded_at": datetime.max.replace(tzinfo=fact.occurred_at.tzinfo),
    }


def _event_parameters(
    row: Mapping[str, Any], owner: UUID, wallet_id: UUID, episode_id: UUID
) -> dict[str, object]:
    return dict(row) | {"owner": owner, "wallet": wallet_id, "episode": episode_id}


async def apply_position_event(
    session: UserSession,
    episode_id: UUID,
    event_id: UUID,
    kind: PositionEventKind,
    fact: ExecutionFact | None = None,
    supersedes_event_id: UUID | None = None,
) -> PositionWriteResult:
    """Validate and stage one event; the caller owns commit/rollback."""
    checked = require_user_session(session)
    if type(event_id) is not UUID or not isinstance(kind, PositionEventKind):
        raise PositionIntegrityError("invalid position event identity")
    if not isinstance(fact, ExecutionFact):
        raise PositionIntegrityError("position event requires an execution identity")
    if (fact.pair.base, fact.pair.quote) not in PAIRS:
        raise PositionIntegrityError("unsupported Paper position pair")
    if kind is PositionEventKind.RECORD and supersedes_event_id is not None:
        raise PositionIntegrityError("record cannot supersede another event")
    if kind is not PositionEventKind.RECORD and type(supersedes_event_id) is not UUID:
        raise PositionIntegrityError("correction must identify its predecessor")

    activity_row = await _lock_active(checked, episode_id)
    current = _activity(activity_row)
    rows = await _event_rows(checked, episode_id)
    by_id = {row["id"]: row for row in rows}
    target = None if supersedes_event_id is None else by_id.get(supersedes_event_id)
    fingerprint = _fingerprint(kind, fact, supersedes_event_id)

    prior_conflict = (
        (
            await checked.execute(
                """SELECT failure_code FROM paper_position_conflicts
                WHERE episode_id=:episode AND fingerprint=:fingerprint""",
                {"episode": episode_id, "fingerprint": fingerprint},
            )
        )
        .mappings()
        .first()
    )
    if prior_conflict is not None:
        return PositionWriteResult(
            PositionWriteStatus.CONFLICTED,
            event_id,
            current,
            failure_code=prior_conflict["failure_code"],
        )

    existing = by_id.get(event_id)
    if existing is not None:
        if existing["request_fingerprint"] == fingerprint:
            return PositionWriteResult(PositionWriteStatus.REPLAYED, event_id, current)
        return await _record_event_conflict(
            checked, current, event_id, fact.pair, fingerprint, "POSITION_DUPLICATE_CONFLICT"
        )
    matching = next((row for row in rows if row["request_fingerprint"] == fingerprint), None)
    if matching is not None:
        return PositionWriteResult(PositionWriteStatus.REPLAYED, matching["id"], current)
    if current.availability is not PositionAvailability.READY:
        return await _record_event_conflict(
            checked, current, event_id, fact.pair, fingerprint, "POSITION_SOURCE_UNKNOWN"
        )

    if kind is PositionEventKind.RECORD:
        duplicate = next(
            (
                row
                for row in rows
                if row["event_kind"] == "RECORD"
                and (
                    row["execution_id"] == fact.execution_id
                    or int(row["source_sequence"]) == fact.source_sequence
                )
            ),
            None,
        )
        if duplicate is not None:
            if duplicate["request_fingerprint"] == fingerprint:
                return PositionWriteResult(PositionWriteStatus.REPLAYED, duplicate["id"], current)
            return await _record_event_conflict(
                checked,
                current,
                event_id,
                fact.pair,
                fingerprint,
                "POSITION_DUPLICATE_CONFLICT",
            )
        if fact.source_sequence != current.source_sequence + 1:
            return await _record_event_conflict(
                checked,
                current,
                event_id,
                fact.pair,
                fingerprint,
                "POSITION_SEQUENCE_GAP",
            )
    else:
        if target is None or target["id"] in {row["supersedes_event_id"] for row in rows}:
            return await _record_event_conflict(
                checked,
                current,
                event_id,
                fact.pair,
                fingerprint,
                "POSITION_CORRECTION_CONFLICT",
            )
        if (
            target["execution_id"] != fact.execution_id
            or int(target["source_sequence"]) != fact.source_sequence
            or (target["base"], target["quote"]) != (fact.pair.base, fact.pair.quote)
        ):
            return await _record_event_conflict(
                checked,
                current,
                event_id,
                fact.pair,
                fingerprint,
                "POSITION_CORRECTION_CONFLICT",
            )

    candidate = _candidate_row(event_id, kind, fact, supersedes_event_id, fingerprint)
    next_sequence = current.source_sequence + (kind is PositionEventKind.RECORD)
    before_slots = _effective_slots(rows, fact.pair, current.source_sequence)
    before_for_diff = before_slots + ((None,) if kind is PositionEventKind.RECORD else ())
    try:
        after_slots = _effective_slots([*rows, candidate], fact.pair, next_sequence)
        correction = rebuild_correction(fact.pair, before_for_diff, after_slots)
    except InsufficientPositionError:
        return await _record_event_conflict(
            checked, current, event_id, fact.pair, fingerprint, "POSITION_INSUFFICIENT"
        )
    except (InvalidPositionInputError, PositionSequenceError):
        failure = (
            "POSITION_CORRECTION_CONFLICT"
            if kind is not PositionEventKind.RECORD
            else "POSITION_EXECUTION_INVALID"
        )
        return await _record_event_conflict(
            checked, current, event_id, fact.pair, fingerprint, failure
        )

    await checked.execute(
        """INSERT INTO paper_position_events
        (id,execution_id,user_id,wallet_id,episode_id,event_kind,source_sequence,
         request_fingerprint,supersedes_event_id,base,quote,side,gross_quantity,
         quote_amount,fee_amount,fee_unit,occurred_at)
        VALUES (:id,:execution_id,:owner,:wallet,:episode,:event_kind,:source_sequence,
         :request_fingerprint,:supersedes_event_id,:base,:quote,:side,:gross_quantity,
         :quote_amount,:fee_amount,:fee_unit,:occurred_at)""",
        _event_parameters(candidate, checked.user_id, current.wallet_id, episode_id),
    )
    state = correction.state
    revision = current.revision + 1
    quantity_amount, _ = quantity_to_columns(state.held_quantity)
    cost_amount, _ = money_to_columns(state.total_cost)
    pnl_amount, _ = money_to_columns(state.realized_pnl)
    await checked.execute(
        """UPDATE paper_position_projections
        SET last_sequence=:sequence,revision=:revision
        WHERE episode_id=:episode AND (base<>:base OR quote<>:quote)""",
        {
            "episode": episode_id,
            "base": fact.pair.base,
            "quote": fact.pair.quote,
            "sequence": next_sequence,
            "revision": revision,
        },
    )
    await checked.execute(
        """INSERT INTO paper_position_projections
        (episode_id,wallet_id,user_id,base,quote,held_quantity,total_cost,realized_pnl,
         last_sequence,revision,last_event_id)
        VALUES (:episode,:wallet,:owner,:base,:quote,:quantity,:cost,:pnl,
                :sequence,:revision,:event)
        ON CONFLICT (episode_id,base,quote) DO UPDATE SET
          held_quantity=EXCLUDED.held_quantity,total_cost=EXCLUDED.total_cost,
          realized_pnl=EXCLUDED.realized_pnl,last_sequence=EXCLUDED.last_sequence,
          revision=EXCLUDED.revision,last_event_id=EXCLUDED.last_event_id""",
        {
            "episode": episode_id,
            "wallet": current.wallet_id,
            "owner": checked.user_id,
            "base": fact.pair.base,
            "quote": fact.pair.quote,
            "quantity": quantity_amount,
            "cost": cost_amount,
            "pnl": pnl_amount,
            "sequence": next_sequence,
            "revision": revision,
            "event": event_id,
        },
    )
    for effect in correction.compensating_effects.external_asset_effects:
        amount, asset = quantity_to_columns(effect)
        await checked.execute(
            """INSERT INTO paper_position_external_fees
            (id,event_id,user_id,wallet_id,episode_id,amount,asset)
            VALUES (:id,:event,:owner,:wallet,:episode,:amount,:asset)""",
            {
                "id": uuid4(),
                "event": event_id,
                "owner": checked.user_id,
                "wallet": current.wallet_id,
                "episode": episode_id,
                "amount": amount,
                "asset": asset,
            },
        )
    updated = (
        (
            await checked.execute(
                """UPDATE paper_position_activity SET source_sequence=:sequence,
                revision=:revision,observed_at=clock_timestamp(),failure_code=NULL
                WHERE episode_id=:episode RETURNING *""",
                {"episode": episode_id, "sequence": next_sequence, "revision": revision},
            )
        )
        .mappings()
        .one()
    )
    audit_quantity = (
        fact.gross_quantity
        if kind is PositionEventKind.RECORD
        else correction.compensating_effects.base_delta
    )
    audit_quote = (
        fact.quote_amount
        if kind is PositionEventKind.RECORD
        else correction.compensating_effects.quote_cash_delta
    )
    await record_event(
        checked,
        AuditEvent(
            owner_user_id=checked.user_id,
            action=(
                AuditAction.PAPER_POSITION_APPLIED
                if kind is PositionEventKind.RECORD
                else AuditAction.PAPER_POSITION_CORRECTED
            ),
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.PAPER_POSITION_EVENT,
            subject_id=str(event_id),
            outcome=AuditOutcome.SUCCEEDED,
            mode=AuditMode.PAPER,
            details=PaperPositionDetails(
                event_id,
                fact.execution_id,
                episode_id,
                fact.pair.base,
                fact.pair.quote,
                audit_quantity,
                audit_quote,
            ),
        ),
    )
    effects = PairEconomicEffects(
        fact.pair,
        correction.compensating_effects.base_delta,
        correction.compensating_effects.quote_cash_delta,
        correction.compensating_effects.external_asset_effects,
    )
    return PositionWriteResult(PositionWriteStatus.APPLIED, event_id, _activity(updated), effects)


async def _record_event_conflict(
    session: UserSession,
    current: PositionActivity,
    event_id: UUID,
    pair: PositionPair,
    fingerprint: str,
    failure_code: str,
) -> PositionWriteResult:
    inserted = (
        await session.execute(
            """INSERT INTO paper_position_conflicts
            (id,attempted_event_id,user_id,wallet_id,episode_id,fingerprint,
             failure_code,base,quote)
            VALUES (:id,:event,:owner,:wallet,:episode,:fingerprint,:failure,:base,:quote)
            ON CONFLICT (user_id,episode_id,fingerprint) DO NOTHING RETURNING id""",
            {
                "id": uuid4(),
                "event": event_id,
                "owner": session.user_id,
                "wallet": current.wallet_id,
                "episode": current.episode_id,
                "fingerprint": fingerprint,
                "failure": failure_code,
                "base": pair.base,
                "quote": pair.quote,
            },
        )
    ).first()
    if inserted is None:
        latest = await read_position_activity(session, current.episode_id)
        if latest is None:
            raise PositionIntegrityError("position activity disappeared")
        return PositionWriteResult(
            PositionWriteStatus.CONFLICTED, event_id, latest, failure_code=failure_code
        )
    revision = current.revision + 1
    await session.execute(
        """UPDATE paper_position_projections SET revision=:revision
        WHERE episode_id=:episode""",
        {"episode": current.episode_id, "revision": revision},
    )
    updated = (
        (
            await session.execute(
                """UPDATE paper_position_activity SET availability='CONFLICTED',
                revision=:revision,observed_at=clock_timestamp(),failure_code=:failure
                WHERE episode_id=:episode RETURNING *""",
                {
                    "episode": current.episode_id,
                    "failure": failure_code,
                    "revision": revision,
                },
            )
        )
        .mappings()
        .one()
    )
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PAPER_POSITION_CONFLICTED,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.PAPER_POSITION_EVENT,
            subject_id=str(event_id),
            outcome=AuditOutcome.FAILED,
            failure_code=failure_code,
            mode=AuditMode.PAPER,
            details=PaperPositionConflictDetails(
                episode_id=current.episode_id,
                event_id=event_id,
                base=pair.base,
                quote=pair.quote,
            ),
        ),
    )
    return PositionWriteResult(
        PositionWriteStatus.CONFLICTED,
        event_id,
        _activity(updated),
        failure_code=failure_code,
    )


def _validate_projection_completeness(
    row: Mapping[str, Any] | RowMapping, activity: PositionActivity
) -> None:
    if (
        int(row["source_record_count"]) != activity.source_sequence
        or int(row["projection_count"]) != int(row["source_pair_count"])
        or int(row["source_max_sequence"]) != activity.source_sequence
    ):
        raise PositionIntegrityError("position projection is incomplete")


async def read_position_snapshot(session: UserSession, episode_id: UUID) -> PositionSnapshot | None:
    """Read activity and projections from one PostgreSQL statement snapshot."""
    checked = require_user_session(session)
    rows = list(
        (
            await checked.execute(
                """SELECT a.*,p.base,p.quote,p.held_quantity,p.total_cost,p.realized_pnl,
                          p.last_sequence,p.revision AS projection_revision,
                          statement_timestamp() AS snapshot_at,
                          count(p.base) OVER () AS projection_count,
                          (SELECT count(*) FROM paper_position_events e
                           WHERE e.episode_id=a.episode_id AND e.event_kind='RECORD')
                            AS source_record_count,
                          (SELECT coalesce(max(e.source_sequence),0)
                           FROM paper_position_events e
                           WHERE e.episode_id=a.episode_id AND e.event_kind='RECORD')
                            AS source_max_sequence,
                          (SELECT count(DISTINCT (e.base,e.quote))
                           FROM paper_position_events e
                           WHERE e.episode_id=a.episode_id AND e.event_kind='RECORD')
                            AS source_pair_count
                FROM paper_position_activity a
                LEFT JOIN paper_position_projections p ON p.episode_id=a.episode_id
                WHERE a.episode_id=:episode ORDER BY p.base,p.quote""",
                {"episode": episode_id},
            )
        ).mappings()
    )
    if not rows:
        return None
    activity = _activity(rows[0])
    _validate_projection_completeness(rows[0], activity)
    positions = tuple(
        PositionState(
            pair=PositionPair(row["base"], row["quote"]),
            held_quantity=quantity_from_columns(row["held_quantity"], row["base"]),
            total_cost=money_from_columns(row["total_cost"], row["quote"]),
            realized_pnl=money_from_columns(row["realized_pnl"], row["quote"]),
            last_sequence=int(row["last_sequence"]),
        )
        for row in rows
        if row["base"] is not None
    )
    if any(
        int(row["projection_revision"]) != activity.revision
        or int(row["last_sequence"]) != activity.source_sequence
        for row in rows
        if row["base"] is not None
    ):
        raise PositionIntegrityError("position projection does not match activity revision")
    return PositionSnapshot(activity, positions, rows[0]["snapshot_at"])


async def read_valued_position_snapshot(
    session: UserSession, episode_id: UUID
) -> ValuedPositionSnapshot | None:
    """Read positions and fresh reconciled prices from one database statement snapshot."""
    checked = require_user_session(session)
    rows = list(
        (
            await checked.execute(
                """SELECT a.*,p.base,p.quote,p.held_quantity,p.total_cost,p.realized_pnl,
                          p.last_sequence,p.revision AS projection_revision,
                          m.amount AS price_amount,m.trade_at AS price_at,
                          m.reconciled_generation,m.revision AS price_revision,
                          m.effective_readiness,
                          f.generation AS feed_generation,f.lease_until,f.connected,
                          statement_timestamp() AS snapshot_at,
                          count(p.base) OVER () AS projection_count,
                          (SELECT count(*) FROM paper_position_events e
                           WHERE e.episode_id=a.episode_id AND e.event_kind='RECORD')
                            AS source_record_count,
                          (SELECT coalesce(max(e.source_sequence),0)
                           FROM paper_position_events e
                           WHERE e.episode_id=a.episode_id AND e.event_kind='RECORD')
                            AS source_max_sequence,
                          (SELECT count(DISTINCT (e.base,e.quote))
                           FROM paper_position_events e
                           WHERE e.episode_id=a.episode_id AND e.event_kind='RECORD')
                            AS source_pair_count
                FROM paper_position_activity a
                LEFT JOIN paper_position_projections p ON p.episode_id=a.episode_id
                LEFT JOIN market_latest_prices m
                  ON m.source='primary_spot' AND m.base=p.base AND m.quote=p.quote
                LEFT JOIN market_price_feed f ON f.source=m.source
                WHERE a.episode_id=:episode ORDER BY p.base,p.quote""",
                {"episode": episode_id},
            )
        ).mappings()
    )
    if not rows:
        return None
    activity = _activity(rows[0])
    _validate_projection_completeness(rows[0], activity)
    snapshot_at: datetime = rows[0]["snapshot_at"]
    valuations: list[PositionValuation] = []
    for row in rows:
        if row["base"] is None:
            continue
        if (
            int(row["projection_revision"]) != activity.revision
            or int(row["last_sequence"]) != activity.source_sequence
        ):
            raise PositionIntegrityError("position projection does not match activity revision")
        state = PositionState(
            pair=PositionPair(row["base"], row["quote"]),
            held_quantity=quantity_from_columns(row["held_quantity"], row["base"]),
            total_cost=money_from_columns(row["total_cost"], row["quote"]),
            realized_pnl=money_from_columns(row["realized_pnl"], row["quote"]),
            last_sequence=int(row["last_sequence"]),
        )
        reason: str | None = None
        pnl: Money | None = None
        if activity.availability is not PositionAvailability.READY:
            reason = "POSITION_SOURCE_UNKNOWN"
        elif state.held_quantity.amount == 0:
            pnl = unrealized_pnl(state, None)
        elif row["price_amount"] is None:
            reason = "PRICE_MISSING"
        elif not row["connected"]:
            reason = "PRICE_DISCONNECTED"
        elif row["lease_until"] is None or row["lease_until"] <= snapshot_at:
            reason = "PRICE_PRODUCER_UNAVAILABLE"
        elif row["reconciled_generation"] != row["feed_generation"]:
            reason = "PRICE_UNRECONCILED"
        elif row["price_at"] is None or row["price_at"] > snapshot_at:
            reason = "PRICE_INVALID_TIME"
        elif snapshot_at - row["price_at"] > MAX_PRICE_AGE:
            reason = "PRICE_STALE"
        elif row["effective_readiness"] != "READY":
            reason = "PRICE_UNAVAILABLE"
        else:
            pnl = unrealized_pnl(state, money_from_columns(row["price_amount"], row["quote"]))
        valuations.append(
            PositionValuation(
                state,
                pnl,
                reason,
                row["price_at"],
                None if row["price_revision"] is None else int(row["price_revision"]),
            )
        )
    return ValuedPositionSnapshot(activity, tuple(valuations), snapshot_at)
