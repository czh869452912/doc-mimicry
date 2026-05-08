from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock


class BackgroundRuntimeRunner:
    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="docagent-runtime")
        self._lock = RLock()
        self._running: dict[str, Future[None]] = {}

    def submit(self, session_id: str, operation: Callable[[], None]) -> Future[None]:
        def wrapped() -> None:
            try:
                operation()
            finally:
                with self._lock:
                    self._running.pop(session_id, None)

        future = self._executor.submit(wrapped)
        with self._lock:
            self._running[session_id] = future
        return future

    def running_session_ids(self) -> set[str]:
        with self._lock:
            return set(self._running)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
