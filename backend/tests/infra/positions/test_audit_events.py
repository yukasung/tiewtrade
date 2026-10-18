from uuid import uuid4

import pytest

from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditMode,
    AuditOutcome,
    PaperPositionConflictDetails,
    PaperPositionDetails,
    SubjectKind,
)


def test_applied_position_event_has_exact_typed_details() -> None:
    owner, event_id, execution_id, episode_id = uuid4(), uuid4(), uuid4(), uuid4()
    event = AuditEvent(
        owner_user_id=owner,
        action=AuditAction.PAPER_POSITION_APPLIED,
        actor_kind=ActorKind.SYSTEM,
        subject_kind=SubjectKind.PAPER_POSITION_EVENT,
        subject_id=str(event_id),
        outcome=AuditOutcome.SUCCEEDED,
        mode=AuditMode.PAPER,
        details=PaperPositionDetails(
            event_id,
            execution_id,
            episode_id,
            "BTC",
            "USDT",
            Quantity.of("1.25", "BTC"),
            Money.of("100.5", "USDT"),
        ),
    )

    assert event.details.as_details()["quantity"] == "1.25"


def test_initialization_conflict_uses_episode_activity_without_fake_pair() -> None:
    owner, episode_id, initialization_id = uuid4(), uuid4(), uuid4()
    event = AuditEvent(
        owner_user_id=owner,
        action=AuditAction.PAPER_POSITION_CONFLICTED,
        actor_kind=ActorKind.SYSTEM,
        subject_kind=SubjectKind.PAPER_POSITION_ACTIVITY,
        subject_id=str(episode_id),
        outcome=AuditOutcome.FAILED,
        failure_code="POSITION_SOURCE_UNKNOWN",
        mode=AuditMode.PAPER,
        details=PaperPositionConflictDetails(
            episode_id=episode_id, initialization_id=initialization_id
        ),
    )

    assert event.details.as_details() == {
        "initialization_id": str(initialization_id),
        "episode_id": str(episode_id),
    }


def test_conflict_subject_must_match_the_declared_detail_shape() -> None:
    owner, episode_id, initialization_id = uuid4(), uuid4(), uuid4()
    with pytest.raises(AuditEventError):
        AuditEvent(
            owner_user_id=owner,
            action=AuditAction.PAPER_POSITION_CONFLICTED,
            actor_kind=ActorKind.SYSTEM,
            subject_kind=SubjectKind.PAPER_POSITION_EVENT,
            subject_id=str(initialization_id),
            outcome=AuditOutcome.FAILED,
            failure_code="POSITION_SOURCE_UNKNOWN",
            mode=AuditMode.PAPER,
            details=PaperPositionConflictDetails(
                episode_id=episode_id, initialization_id=initialization_id
            ),
        )
