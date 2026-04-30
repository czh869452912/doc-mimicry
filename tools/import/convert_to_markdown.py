from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _report_path(output_root: Path, source: Path) -> Path:
    reports = output_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports / f"{source.stem}.conversion.json"


def convert_file(source: Path, output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "markdown").mkdir(parents=True, exist_ok=True)
    (output_root / "assets").mkdir(parents=True, exist_ok=True)
    report_path = _report_path(output_root, source)

    suffix = source.suffix.lower()
    markdown_path: Path | None = None
    warnings: list[dict[str, str | None]] = []
    status = "succeeded"

    if suffix in {".md", ".markdown"}:
        markdown_path = output_root / "markdown" / f"{source.stem}.md"
        shutil.copyfile(source, markdown_path)
    elif suffix == ".txt":
        markdown_path = output_root / "markdown" / f"{source.stem}.md"
        markdown_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        status = "failed"
        warnings.append(
            {
                "type": "unsupported_format",
                "message": f"Phase 0 direct converter does not support {suffix or 'files without extension'}.",
                "location": None,
            }
        )

    report = {
        "source_path": str(source),
        "markdown_path": str(markdown_path) if markdown_path else None,
        "asset_dir": str(output_root / "assets" / source.stem) if markdown_path else None,
        "engine": "manual" if markdown_path else "unknown",
        "status": status,
        "warnings": warnings,
        "features_detected": {"tables": 0, "images": 0, "formulas": 0, "footnotes": 0, "pages": None},
        "created_at": _now(),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    report_path = convert_file(Path(args.source), Path(args.output_root))
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
