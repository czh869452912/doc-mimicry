from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote


RESOURCE_GROUPS = ["examples", "specs", "checklists", "export-references"]


def is_valid_doc_type_id(doc_type_id: str) -> bool:
    decoded = unquote(doc_type_id)
    return bool(decoded) and all(part not in decoded for part in ("..", "/", "\\"))


def list_doc_types(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    return [summarize_doc_type(path) for path in sorted(root.iterdir()) if path.is_dir()]


def get_doc_type(root: Path, doc_type_id: str) -> dict[str, Any] | None:
    if not is_valid_doc_type_id(doc_type_id):
        return None
    path = root / doc_type_id
    if not path.exists() or not path.is_dir():
        return None
    detail = summarize_doc_type(path)
    skill_path = path / "SKILL.md"
    detail["skill_markdown"] = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
    return detail


def summarize_doc_type(path: Path) -> dict[str, Any]:
    return {
        "id": path.name,
        "title": path.name.upper(),
        "has_skill": (path / "SKILL.md").exists(),
        "resource_groups": {
            group: _list_group(path / group)
            for group in RESOURCE_GROUPS
        },
    }


def _list_group(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        item.relative_to(path).as_posix()
        for item in sorted(path.rglob("*"))
        if item.is_file() and item.name != ".gitkeep"
    ]
