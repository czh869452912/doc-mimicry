from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DocAgentState:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "timelines").mkdir(parents=True, exist_ok=True)
        (self.root / "workspaces").mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[dict[str, Any]]:
        return list(self._read_map("tasks.json").values())

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._read_map("tasks.json").get(task_id)

    def save_task(self, task: dict[str, Any]) -> None:
        tasks = self._read_map("tasks.json")
        tasks[task["id"]] = task
        self._write_map("tasks.json", tasks)

    def list_sessions(self) -> list[dict[str, Any]]:
        return list(self._read_map("sessions.json").values())

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._read_map("sessions.json").get(session_id)

    def save_session(self, session: dict[str, Any]) -> None:
        sessions = self._read_map("sessions.json")
        sessions[session["id"]] = session
        self._write_map("sessions.json", sessions)

    def append_timeline_event(self, session_id: str, event: dict[str, Any]) -> None:
        events = self.list_timeline_events(session_id)
        events.append(event)
        self._timeline_path(session_id).write_text(
            json.dumps(events, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def list_timeline_events(self, session_id: str) -> list[dict[str, Any]]:
        path = self._timeline_path(session_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def workspace_root(self, task_id: str) -> Path:
        return self.root / "workspaces" / task_id

    def _read_map(self, filename: str) -> dict[str, Any]:
        path = self.root / filename
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_map(self, filename: str, data: dict[str, Any]) -> None:
        (self.root / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _timeline_path(self, session_id: str) -> Path:
        return self.root / "timelines" / f"{session_id}.json"
