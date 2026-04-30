from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def import_text_input(
    workspace_root: Path,
    name: str,
    content: str,
    created_at: str,
) -> dict[str, Any]:
    stem = _safe_stem(name)
    original_path = workspace_root / "inputs" / "original" / f"{stem}.txt"
    markdown_path = workspace_root / "inputs" / "markdown" / f"{stem}.md"
    report_path = workspace_root / "inputs" / "reports" / f"{stem}.json"
    for path in [original_path.parent, markdown_path.parent, report_path.parent]:
        path.mkdir(parents=True, exist_ok=True)
    text = content if content.endswith("\n") else f"{content}\n"
    original_path.write_text(text, encoding="utf-8")
    markdown_path.write_text(text, encoding="utf-8")
    report = {
        "source_path": original_path.relative_to(workspace_root).as_posix(),
        "markdown_path": markdown_path.relative_to(workspace_root).as_posix(),
        "asset_dir": None,
        "engine": "manual",
        "status": "succeeded",
        "warnings": [],
        "features_detected": {
            "tables": 0,
            "images": 0,
            "formulas": 0,
            "footnotes": 0,
            "pages": None,
        },
        "created_at": created_at,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "id": f"input-{stem}",
        "status": "converted",
        "source_path": report["source_path"],
        "markdown_path": report["markdown_path"],
        "conversion_report_path": report_path.relative_to(workspace_root).as_posix(),
        "original_filename": name,
        "created_at": created_at,
    }


def _safe_stem(name: str) -> str:
    raw_stem = Path(name).stem or "input"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_stem).strip("-").lower()
    return stem or "input"
