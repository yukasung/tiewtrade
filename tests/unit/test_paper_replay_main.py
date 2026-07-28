import pytest
from pytest import MonkeyPatch

import tiewtrade.paper_replay_main as paper_replay_main


class ParsingStopped(RuntimeError):
    pass


class RecordingParser:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def parse_args(self, argv: object) -> object:
        self._events.append("parse")
        raise ParsingStopped


def test_replay_configures_decimal_context_before_argument_parsing(
    monkeypatch: MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        paper_replay_main,
        "configure_decimal_context",
        lambda: events.append("decimal"),
        raising=False,
    )
    monkeypatch.setattr(
        paper_replay_main,
        "_build_parser",
        lambda: RecordingParser(events),
    )

    with pytest.raises(ParsingStopped):
        paper_replay_main.main([])

    assert events == ["decimal", "parse"]
