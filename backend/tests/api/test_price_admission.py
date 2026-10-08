import pytest

from tiewtrade.services.api.price_admission import ProcessBudget


def test_reservations_never_queue_and_physical_survives_handshake() -> None:
    budget = ProcessBudget(physical_limit=2, pending_limit=1)
    first = budget.reserve()
    assert first is not None
    assert budget.reserve() is None
    first.accepted()
    second = budget.reserve()
    assert second is not None
    second.accepted()
    assert budget.reserve() is None
    first.close()
    first.close()
    third = budget.reserve()
    assert third is not None
    third.close()
    second.close()
    assert (budget.physical, budget.pending) == (0, 0)


def test_settings_validate_process_budgets() -> None:
    import pytest

    from tiewtrade.services.api.settings import PriceSettings

    settings = PriceSettings()
    assert (settings.physical_limit, settings.pending_limit) == (100, 16)
    with pytest.raises(ValueError):
        PriceSettings(physical_limit=0)
    with pytest.raises(ValueError):
        PriceSettings(pending_limit=101)


def test_origin_configuration_rejects_wildcards(monkeypatch: pytest.MonkeyPatch) -> None:
    import pytest

    from tiewtrade.services.api.settings import price_origins

    monkeypatch.setenv("TIEWTRADE_PRICE_ORIGINS", "https://*.example.com")
    with pytest.raises(ValueError):
        price_origins()


def test_default_physical_boundary_100_and_pending_boundary_16() -> None:
    from tiewtrade.services.api.price_admission import Reservation

    budget = ProcessBudget()
    accepted: list[Reservation] = []
    for _ in range(84):
        reservation = budget.reserve()
        assert reservation is not None
        reservation.accepted()
        accepted.append(reservation)
    pending: list[Reservation] = []
    for _ in range(16):
        reservation = budget.reserve()
        assert reservation is not None
        pending.append(reservation)
    assert (budget.physical, budget.pending) == (100, 16)
    assert budget.reserve() is None
    pending[0].close()
    replacement = budget.reserve()
    assert replacement is not None
    replacement.accepted()
    assert (budget.physical, budget.pending) == (100, 15)
    assert budget.reserve() is None
    for reservation in [*accepted, *pending, replacement]:
        reservation.close()
    assert (budget.physical, budget.pending) == (0, 0)


def test_default_pending_boundary_16_rejects_17_without_waiting() -> None:
    from tiewtrade.services.api.price_admission import Reservation

    budget = ProcessBudget()
    reservations: list[Reservation] = []
    for _ in range(16):
        reservation = budget.reserve()
        assert reservation is not None
        reservations.append(reservation)
    assert budget.reserve() is None
    assert budget.physical == 16
    reservations[0].accepted()
    next_reservation = budget.reserve()
    assert next_reservation is not None
    assert budget.pending == 16
    for reservation in [*reservations, next_reservation]:
        reservation.close()
    assert (budget.physical, budget.pending) == (0, 0)
