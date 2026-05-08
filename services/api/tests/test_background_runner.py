from __future__ import annotations

from threading import Event

from docagent_api.background import BackgroundRuntimeRunner


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
