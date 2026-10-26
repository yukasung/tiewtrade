"""API runtime heap lifecycle checks; no database or network access."""

import gc

import pytest

from tiewtrade.services.api import app as api_app


@pytest.fixture(autouse=True)
def reset_heap_ownership() -> None:
    api_app._heap_users = 0
    api_app._owns_frozen_heap = False


def test_runtime_heap_is_frozen_once_and_released_after_last_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(gc, "get_freeze_count", lambda: 0)
    monkeypatch.setattr(gc, "collect", lambda: calls.append("collect"))
    monkeypatch.setattr(gc, "freeze", lambda: calls.append("freeze"))
    monkeypatch.setattr(gc, "unfreeze", lambda: calls.append("unfreeze"))

    api_app._retain_stable_heap()
    api_app._retain_stable_heap()
    api_app._release_stable_heap()
    assert calls == ["collect", "freeze"]
    api_app._release_stable_heap()

    assert calls == ["collect", "freeze", "unfreeze"]
    assert api_app._heap_users == 0
    assert api_app._owns_frozen_heap is False


def test_runtime_heap_does_not_take_ownership_of_an_existing_freeze(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(gc, "get_freeze_count", lambda: 1)
    monkeypatch.setattr(gc, "collect", lambda: calls.append("collect"))
    monkeypatch.setattr(gc, "freeze", lambda: calls.append("freeze"))
    monkeypatch.setattr(gc, "unfreeze", lambda: calls.append("unfreeze"))

    api_app._retain_stable_heap()
    api_app._release_stable_heap()

    assert calls == []
    assert api_app._heap_users == 0
    assert api_app._owns_frozen_heap is False
