from __future__ import annotations

from uuid import uuid4

import pytest

from tiewtrade.infra.audit.events import (
    ActorKind,
    AuditAction,
    AuditEvent,
    AuditEventError,
    AuditOutcome,
    PlatformOwnerBootstrapDetails,
    SubjectKind,
)


def test_platform_owner_bootstrap_event_has_typed_non_free_form_shape() -> None:
    owner = uuid4()
    event = AuditEvent(
        owner_user_id=owner,
        action=AuditAction.PLATFORM_OWNER_BOOTSTRAPPED,
        actor_kind=ActorKind.SYSTEM,
        subject_kind=SubjectKind.PLATFORM_MEMBERSHIP,
        subject_id=str(owner),
        outcome=AuditOutcome.SUCCEEDED,
        details=PlatformOwnerBootstrapDetails(),
    )

    assert event.details.as_details() == {"role": "PLATFORM_OWNER"}


def test_platform_owner_bootstrap_rejects_human_actor() -> None:
    owner = uuid4()
    with pytest.raises(AuditEventError, match="invalid Platform Owner bootstrap"):
        AuditEvent(
            owner_user_id=owner,
            action=AuditAction.PLATFORM_OWNER_BOOTSTRAPPED,
            actor_kind=ActorKind.PLATFORM,
            actor_id=owner,
            subject_kind=SubjectKind.PLATFORM_MEMBERSHIP,
            subject_id=str(owner),
            outcome=AuditOutcome.SUCCEEDED,
            details=PlatformOwnerBootstrapDetails(),
        )
