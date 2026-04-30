from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_BEFORE_DRAFTING = [
    "context/user_intent.md",
    "context/style_notes.md",
    "context/structure_notes.md",
    "draft/outline.md",
]


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    missing_files: list[str]


def validate_workspace(root: Path) -> ValidationResult:
    missing = [path for path in REQUIRED_BEFORE_DRAFTING if not (root / path).is_file()]
    return ValidationResult(valid=not missing, missing_files=missing)
