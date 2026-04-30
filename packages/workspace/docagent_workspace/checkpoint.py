from __future__ import annotations

import shutil
from pathlib import Path

from docagent_contracts import DraftVersion


def _next_version(root: Path) -> tuple[str, Path]:
    versions_dir = root / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(versions_dir.glob("v*.md"))
    next_index = len(existing) + 1
    version = f"v{next_index:03d}"
    return version, versions_dir / f"{version}.md"


def checkpoint_draft(root: Path, summary: str, created_at: str = "1970-01-01T00:00:00Z") -> DraftVersion:
    source = root / "draft" / "draft.md"
    if not source.is_file():
        raise FileNotFoundError("Cannot checkpoint missing draft/draft.md")

    version, target = _next_version(root)
    shutil.copyfile(source, target)
    return DraftVersion(
        id=version,
        task_id=root.name,
        version=version,
        source_path="draft/draft.md",
        version_path=f"versions/{version}.md",
        summary=summary,
        created_by="agent",
        created_at=created_at,
    )
