from __future__ import annotations

from concurrent.futures import Future
from threading import Event

from docagent_api.background import BackgroundRuntimeRunner


class ImmediateExecutor:
    def __init__(self) -> None:
        self.shutdown_called = False

    def submit(self, operation):
        future: Future[None] = Future()
        try:
            operation()
        except BaseException as exc:
            future.set_exception(exc)
        else:
            future.set_result(None)
        return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        self.shutdown_called = True


def test_background_runner_completes_submitted_work() -> None:
    runner = BackgroundRuntimeRunner(max_workers=1)
    completed = Event()

    runner.submit("session-1", lambda: completed.set())

    assert completed.wait(timeout=2)
    runner.shutdown()


def test_background_runner_tracks_running_session_ids() -> None:
    runner = BackgroundRuntimeRunner(max_workers=1)
    release = Event()

    runner.submit("session-1", lambda: release.wait(timeout=2))

    assert "session-1" in runner.running_session_ids()
    release.set()
    runner.shutdown()


def test_background_runner_does_not_track_already_completed_work() -> None:
    runner = BackgroundRuntimeRunner(executor=ImmediateExecutor())

    runner.submit("session-1", lambda: None)

    assert "session-1" not in runner.running_session_ids()
