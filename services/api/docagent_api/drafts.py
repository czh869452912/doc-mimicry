from __future__ import annotations

from pathlib import Path


def read_draft(workspace_root: Path) -> str:
    path = workspace_root / "draft" / "draft.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_draft(workspace_root: Path, markdown: str) -> None:
    path = workspace_root / "draft" / "draft.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = markdown if markdown.endswith("\n") else f"{markdown}\n"
    path.write_text(text, encoding="utf-8")
