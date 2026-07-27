from threading import Event

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.paper_session_setup import (
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionUnavailableError,
    PaperSessionValidationError,
)
from tiewtrade.ui.main_window import MainWindow


def test_created_spot_session_replaces_form_with_durable_overview(
    qtbot: QtBot,
) -> None:
    created = configured_spot_session()
    window = MainWindow(
        create_session=lambda values: PaperSessionCreateOutcome(created, True)
    )
    qtbot.addWidget(window)
    window.show()
    window.setup.available_capital.setText("200000")

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")
    assert window.overview.state_value.text() == (
        "Configured — Market Data Not Started"
    )
    assert window.overview.market_value.text() == "Spot"
    assert window.overview.session_id_value.text() == str(created.config.session_id)
    assert window.overview.timeframe_value.text() == "5m"
    assert window.overview.available_capital_value.text() == "200000 USDT"
    assert window.overview.spot_reserve_ratio_value.text() == "20%"


def test_repeated_submit_while_worker_is_running_calls_create_once(
    qtbot: QtBot,
) -> None:
    started = Event()
    release = Event()
    created = configured_spot_session()
    calls: list[PaperSessionSetupValues] = []

    def create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        calls.append(values)
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test did not release worker")
        return PaperSessionCreateOutcome(created, True)

    window = MainWindow(create_session=create)
    qtbot.addWidget(window)
    window.show()
    window.setup.available_capital.setText("200000")

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(started.is_set)
    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    assert len(calls) == 1
    release.set()
    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")


def test_validation_failure_restores_form_and_shows_field_error(qtbot: QtBot) -> None:
    def reject(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        raise PaperSessionValidationError(
            "available_capital", "Available Capital must be positive"
        )

    window = MainWindow(create_session=reject)
    qtbot.addWidget(window)
    window.show()

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: (
            window.setup.available_capital_error.text()
            == "Available Capital must be positive"
        )
    )
    assert window.current_page_name == "Session Setup"
    assert window.setup.create_button.isEnabled() is True


def test_persistence_failure_shows_unavailable_state_and_allows_retry(
    qtbot: QtBot,
) -> None:
    def unavailable(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        raise PaperSessionUnavailableError("Session storage is unavailable")

    window = MainWindow(create_session=unavailable)
    qtbot.addWidget(window)
    window.show()

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.unavailable_message.isVisible())
    assert window.unavailable_message.text() == "Session storage is unavailable"
    assert window.current_page_name == "Session Setup"
    assert window.setup.create_button.isEnabled() is True


def test_main_window_starts_on_setup_without_placeholder_navigation(
    qtbot: QtBot,
) -> None:
    def operation(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        return PaperSessionCreateOutcome(configured_spot_session(), True)

    window = MainWindow(create_session=operation)
    qtbot.addWidget(window)

    assert window.current_page_name == "Session Setup"
    assert window.navigation_items == ("Session",)
