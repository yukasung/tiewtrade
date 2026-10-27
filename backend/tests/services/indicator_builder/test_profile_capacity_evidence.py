from datetime import UTC, datetime, timedelta

from tests.services.indicator_builder.profile_capacity_evidence import (
    failure_occurs_in_phase,
)


def test_phase_failure_scope_excludes_retained_pre_t0_miss() -> None:
    start = datetime(2026, 10, 25, 18, 17, tzinfo=UTC)
    end = start + timedelta(hours=1)

    assert not failure_occurs_in_phase(
        {
            "status": "READY",
            "deadline_missed_at": "2026-10-25 18:14:17+00:00",
            "failed_at": None,
        },
        start,
        end,
    )
    assert failure_occurs_in_phase(
        {
            "status": "READY",
            "deadline_missed_at": "2026-10-25 18:30:00+00:00",
            "failed_at": None,
        },
        start,
        end,
    )


def test_failed_status_without_timestamp_fails_closed() -> None:
    start = datetime(2026, 10, 25, 18, 17, tzinfo=UTC)

    assert failure_occurs_in_phase(
        {"status": "FAILED_TRANSIENT", "deadline_missed_at": None, "failed_at": None},
        start,
        start + timedelta(hours=1),
    )
