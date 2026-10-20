"""Prove an existing capital-only episode before adopting it into the F-15 writer."""

import hashlib
import json
from uuid import UUID

from tiewtrade.core.orders import OrderConflictError, SimulationProfile
from tiewtrade.core.positions import PositionAvailability
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditMode,
    AuditOutcome,
    PaperOrderSourceDetails,
    SubjectKind,
    record_event,
)
from tiewtrade.infra.db.session import UserSession, require_user_session
from tiewtrade.infra.market_data.order_book_codec import canonical
from tiewtrade.infra.paper_orders.records import OrderSourceInitialization
from tiewtrade.infra.paper_orders.storage import (
    increment_wallet_revision,
    lock_active_episode,
    pin_execution_profile,
)
from tiewtrade.infra.paper_wallet import get_wallet
from tiewtrade.infra.positions import initialize_position_source, read_position_snapshot


async def enable_financial_writer(session: UserSession) -> None:
    """Transaction-local protocol marker; owner RLS and wallet locking still apply."""
    session = require_user_session(session)
    await session.execute("SELECT set_config('tiewtrade.paper_writer_version','F15_V1',true)")


async def initialize_order_source(
    session: UserSession,
    *,
    wallet_id: UUID,
    episode_id: UUID,
    initialization_id: UUID,
) -> OrderSourceInitialization:
    """Adopt only a proven empty economic baseline; caller commits all sources and audit."""
    session = require_user_session(session)
    if type(initialization_id) is not UUID:
        raise OrderConflictError("initialization identity required")
    await lock_active_episode(session, wallet_id, episode_id)
    existing = (
        (
            await session.execute(
                "SELECT * FROM paper_order_initializations WHERE episode_id=:episode",
                {"episode": episode_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        baseline_value = existing["baseline"]
        if isinstance(baseline_value, str):
            baseline_value = json.loads(baseline_value)
        if (
            hashlib.sha256(canonical(baseline_value).encode()).hexdigest()
            != existing["source_proof"]
        ):
            raise OrderConflictError("initialization baseline proof is inconsistent")
        # An immutable receipt does not assert current source readiness after a conflict.
        return OrderSourceInitialization(
            episode_id,
            wallet_id,
            existing["initialization_id"],
            existing["source_proof"],
            existing["position_proof"],
            existing["initialized_at"],
        )
    wallet = await get_wallet(session)
    if wallet is None or wallet.wallet_id != wallet_id or wallet.episode_id != episode_id:
        raise OrderConflictError("active capital baseline unavailable")
    params = {"episode": episode_id}
    # Missing activity is not an empty source. F-13 creates the F-14 UNKNOWN row.
    position = await read_position_snapshot(session, episode_id)
    if (
        position is None
        or position.activity.availability
        not in (PositionAvailability.UNKNOWN, PositionAvailability.READY)
        or position.positions
        or position.activity.source_sequence != 0
    ):
        raise OrderConflictError("position baseline is not provably empty")
    if position.activity.availability is PositionAvailability.UNKNOWN and (
        position.activity.revision != 1
        or position.activity.source_proof is not None
        or position.activity.observed_at is not None
        or position.activity.failure_code is not None
    ):
        raise OrderConflictError("unknown position baseline is inconsistent")
    for table in (
        "paper_position_events",
        "paper_position_external_fees",
        "paper_position_conflicts",
        "paper_order_commands",
        "paper_orders",
        "paper_order_events",
        "paper_order_projections",
        "paper_reservations",
        "paper_execution_inputs",
        "paper_execution_input_keys",
    ):
        if (
            await session.execute(
                f"SELECT EXISTS(SELECT 1 FROM {table} WHERE episode_id=:episode)", params
            )
        ).scalar_one():
            raise OrderConflictError("existing economic history prevents empty adoption")
    if (
        await session.execute(
            "SELECT count(*) FROM paper_wallet_ledger WHERE episode_id=:episode", params
        )
    ).scalar_one() != 1 or wallet.balance != wallet.initial_capital:
        raise OrderConflictError("capital-only ledger baseline required")
    activity = (
        (
            await session.execute(
                "SELECT * FROM paper_order_activity WHERE episode_id=:episode FOR UPDATE", params
            )
        )
        .mappings()
        .one_or_none()
    )
    if activity is not None and (
        activity["availability"] != "UNKNOWN"
        or activity["source_sequence"] != 0
        or activity["revision"] != 0
        or activity["initialization_id"] is not None
        or activity["source_proof"] is not None
        or activity["observed_at"] is not None
        or activity["failure_code"] is not None
    ):
        raise OrderConflictError("order source baseline is inconsistent")
    profile = SimulationProfile()
    baseline = canonical(
        {
            "episode_id": str(episode_id),
            "wallet_id": str(wallet_id),
            "capital": wallet.initial_capital.as_parts(),
            "position_sequence": 0,
            "order_sequence": 0,
            "fee_version": profile.fee_version,
            "model_version": profile.liquidity_version,
            "prior_position_proof": position.activity.source_proof,
        }
    )
    proof = hashlib.sha256(baseline.encode()).hexdigest()
    await enable_financial_writer(session)
    await pin_execution_profile(
        session, wallet_id=wallet_id, episode_id=episode_id, profile=profile
    )
    if position.activity.availability is PositionAvailability.UNKNOWN:
        initialized = await initialize_position_source(
            session, episode_id, initialization_id, proof
        )
        if initialized.availability is not PositionAvailability.READY:
            raise OrderConflictError("position initialization did not become ready")
        position_proof = initialized.source_proof
    else:
        position_proof = position.activity.source_proof
    if position_proof is None:
        raise OrderConflictError("position proof unavailable")
    common = {
        **params,
        "wallet": wallet_id,
        "user": session.user_id,
        "initialization": initialization_id,
        "proof": proof,
    }
    await session.execute(
        """INSERT INTO paper_order_activity(episode_id,wallet_id,user_id)
        VALUES(:episode,:wallet,:user) ON CONFLICT(episode_id) DO NOTHING""",
        common,
    )
    await session.execute(
        """UPDATE paper_order_activity SET availability='READY',revision=1,
        initialization_id=:initialization,source_proof=:proof,observed_at=clock_timestamp()
        WHERE episode_id=:episode""",
        common,
    )
    row = (
        await session.execute(
            """INSERT INTO paper_order_initializations
                (episode_id,wallet_id,user_id,initialization_id,source_proof,position_proof,baseline)
                VALUES(:episode,:wallet,:user,:initialization,:proof,:position_proof,
                       CAST(:baseline AS jsonb)) RETURNING initialized_at""",
            {**common, "position_proof": position_proof, "baseline": baseline},
        )
    ).one()
    await increment_wallet_revision(session, wallet_id)
    await record_event(
        session,
        AuditEvent(
            owner_user_id=session.user_id,
            action=AuditAction.PAPER_ORDER_SOURCE_INITIALIZED,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
            subject_id=str(episode_id),
            outcome=AuditOutcome.SUCCEEDED,
            mode=AuditMode.PAPER,
            details=PaperOrderSourceDetails(episode_id, initialization_id, proof),
        ),
    )
    return OrderSourceInitialization(
        episode_id, wallet_id, initialization_id, proof, position_proof, row.initialized_at
    )
