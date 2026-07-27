from pathlib import Path

from pytest import MonkeyPatch

import tiewtrade.desktop_main as desktop_main
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)


def test_desktop_composition_supplies_migrated_create_and_load_operations(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def capture_desktop(
        *,
        create_session: object,
        load_active: object,
    ) -> int:
        captured["create_session"] = create_session
        captured["load_active"] = load_active
        return 0

    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    result = desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3")

    assert result == 0
    create_session = captured["create_session"]
    load_active = captured["load_active"]
    assert callable(create_session)
    assert callable(load_active)
    assert load_active() is None
    outcome = create_session(
        PaperSessionSetupValues(
            market_type="spot",
            symbol="BTCUSDT",
            timeframe="5m",
            available_capital="200000",
            max_entries="10",
            fee_percent="0",
            slippage_bps="0",
            spot_trading_capital_percent="80",
            futures_leverage=None,
        )
    )

    assert isinstance(outcome, PaperSessionCreateOutcome)
    assert outcome.created is True
    active = load_active()
    assert isinstance(active, ConfiguredPaperSession)
    assert active.config.session_id == outcome.session.config.session_id


def test_desktop_composition_defers_database_directory_creation_to_load_worker(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    mkdir_calls: list[Path] = []
    original_mkdir = Path.mkdir

    def capture_desktop(
        *,
        create_session: object,
        load_active: object,
    ) -> int:
        captured["create_session"] = create_session
        captured["load_active"] = load_active
        return 0

    def record_mkdir(path: Path, *args: object, **kwargs: object) -> None:
        mkdir_calls.append(path)
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(Path, "mkdir", record_mkdir)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", capture_desktop)

    result = desktop_main.run_desktop()

    assert result == 0
    assert mkdir_calls == []

    load_active = captured["load_active"]
    assert callable(load_active)
    assert load_active() is None
    assert (tmp_path / "Library" / "Application Support" / "TiewTrade") in mkdir_calls
