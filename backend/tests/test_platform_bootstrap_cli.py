from __future__ import annotations

import sys
from uuid import UUID

import pytest

from tiewtrade.services.platform_bootstrap import main as command


def test_bootstrap_requires_interactive_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    with pytest.raises(SystemExit, match="interactive terminal required"):
        command.main(["--user-id", "00000000-0000-0000-0000-000000000001"])


def test_bootstrap_requires_exact_uuid_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "00000000-0000-0000-0000-000000000002")

    with pytest.raises(SystemExit, match="confirmation did not match"):
        command.main(["--user-id", "00000000-0000-0000-0000-000000000001"])


def test_bootstrap_invokes_only_confirmed_user(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = UUID("00000000-0000-0000-0000-000000000001")
    observed: list[UUID] = []

    async def capture(user_id: UUID) -> None:
        observed.append(user_id)

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: str(expected))
    monkeypatch.setattr(command, "_bootstrap", capture)

    command.main(["--user-id", str(expected)])

    assert observed == [expected]
