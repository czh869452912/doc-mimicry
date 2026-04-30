from __future__ import annotations

from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml"}


def list_workspace_files(workspace_root: Path) -> list[dict[str, Any]]:
    if not workspace_root.exists():
        return []
    files: list[dict[str, Any]] = []
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace_root).as_posix()
        files.append({
            "path": relative,
            "group": _group_for(relative),
            "kind": _kind_for(path),
        })
    return files


def read_workspace_text_file(workspace_root: Path, relative_path: str) -> str:
    path = _resolve_inside(workspace_root, relative_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(relative_path)
    if path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError("not a text file")
    return path.read_text(encoding="utf-8")


def _resolve_inside(workspace_root: Path, relative_path: str) -> Path:
    root = workspace_root.resolve()
    path = (workspace_root / relative_path).resolve()
    if root != path and root not in path.parents:
        raise ValueError("path is outside workspace")
    return path


def _group_for(relative_path: str) -> str:
    if relative_path == "brief.md":
        return "brief"
    return relative_path.split("/", 1)[0]


def _kind_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".txt", ".json", ".yaml", ".yml"}:
        return "text"
    return "binary"
