from pytestqt.qtbot import QtBot

from tiewtrade.ui.background_task import BackgroundTask


def test_background_task_emits_success_before_finished(qtbot: QtBot) -> None:
    task = BackgroundTask(lambda: "result")
    events: list[object] = []
    task.signals.succeeded.connect(lambda value: events.append(value))
    task.signals.finished.connect(lambda: events.append("finished"))

    task.run()

    assert events == ["result", "finished"]


def test_background_task_emits_failure_before_finished(qtbot: QtBot) -> None:
    error = RuntimeError("failed")

    def fail() -> object:
        raise error

    task = BackgroundTask(fail)
    events: list[object] = []
    task.signals.failed.connect(lambda value: events.append(value))
    task.signals.finished.connect(lambda: events.append("finished"))

    task.run()

    assert events == [error, "finished"]
