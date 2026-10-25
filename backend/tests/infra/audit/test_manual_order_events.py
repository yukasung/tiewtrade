from dataclasses import replace
from uuid import uuid4

import pytest

from tiewtrade.infra.audit import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditMode,
    AuditOutcome,
    PaperOrderRequestDetails,
    SubjectKind,
)


def test_request_event_has_immutable_typed_actor_scope() -> None:
    owner, episode, request = uuid4(), uuid4(), uuid4()
    event = AuditEvent(
        owner_user_id=owner,
        actor_kind=ActorKind.USER,
        actor_id=owner,
        action=AuditAction.PAPER_ORDER_REQUESTED,
        subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
        subject_id=str(episode),
        mode=AuditMode.PAPER,
        outcome=AuditOutcome.SUCCEEDED,
        details=PaperOrderRequestDetails(request, episode, "NEW"),
    )
    for changes in [
        {"mode": AuditMode.LIVE},
        {"actor_id": uuid4()},
        {"subject_id": str(uuid4())},
        {"failure_code": "ORDER_CONFLICT"},
        {"outcome": AuditOutcome.REJECTED},
    ]:
        with pytest.raises(AuditEventError):
            replace(event, **changes)  # type: ignore[arg-type]
    with pytest.raises(AuditEventError):
        PaperOrderRequestDetails(request, episode, "AMEND")


def test_transfer_and_reject_outcomes_are_not_user_acceptance() -> None:
    owner, episode, request = uuid4(), uuid4(), uuid4()
    transferred = AuditEvent(
        owner_user_id=owner,
        actor_kind=ActorKind.SYSTEM,
        subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
        subject_id=str(episode),
        mode=AuditMode.PAPER,
        action=AuditAction.PAPER_ORDER_REQUEST_TRANSFERRED,
        outcome=AuditOutcome.SUCCEEDED,
        details=PaperOrderRequestDetails(request, episode, "CANCEL", uuid4()),
    )
    with pytest.raises(AuditEventError):
        replace(transferred, details=PaperOrderRequestDetails(request, episode, "CANCEL"))
    rejected = AuditEvent(
        owner_user_id=owner,
        actor_kind=ActorKind.SYSTEM,
        subject_kind=SubjectKind.PAPER_ORDER_ACTIVITY,
        subject_id=str(episode),
        mode=AuditMode.PAPER,
        action=AuditAction.PAPER_ORDER_REQUEST_REJECTED,
        outcome=AuditOutcome.REJECTED,
        failure_code="CATALOG_PAIR_REMOVED",
        details=PaperOrderRequestDetails(request, episode, "NEW"),
    )
    with pytest.raises(AuditEventError):
        replace(rejected, failure_code="ARBITRARY_REASON")
