from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from docagent_contracts import RawRuntimeEvent


class DocAgentState:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "timelines").mkdir(parents=True, exist_ok=True)
        (self.root / "raw-events").mkdir(parents=True, exist_ok=True)
        (self.root / "workspaces").mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[dict[str, Any]]:
        return [_normalized_task(task) for task in self._read_map("tasks.json").values()]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        task = self._read_map("tasks.json").get(task_id)
        return _normalized_task(task) if task is not None else None

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

    def append_raw_runtime_event(self, session_id: str, event: RawRuntimeEvent) -> None:
        event_dict = asdict(event)
        event_dict["runtime"] = event.runtime.value
        with self._raw_events_path(session_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event_dict, ensure_ascii=False) + "\n")

    def list_raw_runtime_events(self, session_id: str) -> list[dict[str, Any]]:
        path = self._raw_events_path(session_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

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

    def _raw_events_path(self, session_id: str) -> Path:
        return self.root / "raw-events" / f"{session_id}.jsonl"


def _normalized_task(task: dict[str, Any]) -> dict[str, Any]:
    next_task = dict(task)
    description = str(next_task.get("description") or next_task.get("brief") or "")
    first_line = next((line.strip() for line in description.splitlines() if line.strip()), "Untitled workspace")
    next_task["description"] = description
    next_task["brief"] = str(next_task.get("brief") or description)
    next_task["title"] = str(next_task.get("title") or first_line[:80])
    return next_task
