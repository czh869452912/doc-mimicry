from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock
from typing import Protocol


class BackgroundExecutor(Protocol):
    def submit(self, operation: Callable[[], None]) -> Future[None]:
        ...

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        ...


class BackgroundRuntimeRunner:
    def __init__(self, max_workers: int = 4, executor: BackgroundExecutor | None = None) -> None:
        self._executor = executor or ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="docagent-runtime")
        self._lock = RLock()
        self._running: dict[str, Future[None]] = {}

    def submit(self, session_id: str, operation: Callable[[], None]) -> Future[None]:
        placeholder: Future[None] = Future()
        with self._lock:
            self._running[session_id] = placeholder

        def wrapped() -> None:
            try:
                operation()
            finally:
                with self._lock:
                    self._running.pop(session_id, None)

        future = self._executor.submit(wrapped)
        with self._lock:
            if self._running.get(session_id) is placeholder:
                if future.done():
                    self._running.pop(session_id, None)
                else:
                    self._running[session_id] = future
        return future

    def running_session_ids(self) -> set[str]:
        with self._lock:
            return set(self._running)

    def is_running(self, session_id: str) -> bool:
        with self._lock:
            future = self._running.get(session_id)
            return future is not None and not future.done()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
