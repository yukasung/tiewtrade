"""Short diagnostics must never satisfy full workload prerequisites."""

from pathlib import Path

import pytest

from tests.services.indicator_builder.profile_capacity import SERIES, save
from tests.services.indicator_builder.profile_capacity_steady import phase_plan, run


@pytest.mark.parametrize(
    ("phase", "loaded", "smoke", "expected"),
    [
        ("steady", False, False, ("R2-C2", None, 3600)),
        ("dirty", False, False, ("R2-C3", "R2-C2", 3600)),
        ("steady", True, False, ("R2-C5-steady", "R2-C3", 3600)),
        ("dirty", True, False, ("R2-C5-dirty", "R2-C5-steady", 3600)),
        ("steady", False, True, ("SMOKE-steady", None, 300)),
        ("dirty", True, True, ("SMOKE-dirty", "SMOKE-steady", 300)),
    ],
)
def test_phase_scope(
    phase: str, loaded: bool, smoke: bool, expected: tuple[str, str | None, int]
) -> None:
    assert phase_plan(phase, loaded, smoke) == expected
    duration = expected[2]
    assert duration // 10 == (30 if smoke else 360)
    assert duration // 60 == (5 if smoke else 60)
    assert len(set(SERIES)) == 8
    assert {base for base, _ in SERIES} == {"BTC"}


@pytest.mark.parametrize(("phase", "loaded"), [("dirty", False), ("steady", True)])
def test_smoke_requires_approved_load_shape(phase: str, loaded: bool) -> None:
    with pytest.raises(AssertionError):
        phase_plan(phase, loaded, True)


async def test_smoke_result_cannot_unlock_full_dirty_gate(tmp_path: Path) -> None:
    c1, prior = tmp_path / "c1", tmp_path / "prior"
    c1.mkdir()
    prior.mkdir()
    save(c1 / "result.json", {"R2-C1": "PASSED"})
    save(prior / "result.json", {"SMOKE-steady": "PASSED"})
    with pytest.raises(KeyError, match="R2-C5-steady"):
        await run(tmp_path / "output", c1, "dirty", tmp_path / "metrics", prior)
    assert not (tmp_path / "output").exists()
