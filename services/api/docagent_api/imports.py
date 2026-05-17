from __future__ import annotations

from pathlib import Path
from typing import Any

from docagent_conversion import ConversionLayout, convert_resource_bytes


def import_text_input(
    workspace_root: Path,
    name: str,
    content: str,
    created_at: str,
) -> dict[str, Any]:
    text = content if content.endswith("\n") else f"{content}\n"
    return convert_resource_bytes(
        ConversionLayout(
            root=workspace_root,
            original_dir="inputs/original",
            markdown_dir="inputs/markdown",
            assets_dir="inputs/assets",
            reports_dir="inputs/reports",
        ),
        original_filename=name,
        content=text.encode("utf-8"),
        mime_type="text/plain",
        created_at=created_at,
    )
