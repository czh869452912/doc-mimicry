from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


WORKSPACE_DIRS = [
    "inputs/original",
    "inputs/markdown",
    "inputs/assets",
    "inputs/reports",
    "context",
    "draft/sections",
    "versions",
    "reviews",
    "artifacts",
    "logs",
]


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    brief: Path
    user_intent: Path
    style_notes: Path
    structure_notes: Path
    outline: Path
    current_draft: Path


def workspace_paths(root: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=root,
        brief=root / "brief.md",
        user_intent=root / "context" / "user_intent.md",
        style_notes=root / "context" / "style_notes.md",
        structure_notes=root / "context" / "structure_notes.md",
        outline=root / "draft" / "outline.md",
        current_draft=root / "draft" / "draft.md",
    )


def create_workspace(root: Path, brief: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel_dir in WORKSPACE_DIRS:
        (root / rel_dir).mkdir(parents=True, exist_ok=True)
    brief_text = brief if brief.endswith("\n") else f"{brief}\n"
    (root / "brief.md").write_text(brief_text, encoding="utf-8")
