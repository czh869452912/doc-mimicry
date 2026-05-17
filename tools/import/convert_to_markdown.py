from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "conversion"))

from docagent_conversion import ConversionLayout, convert_resource_bytes


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def convert_file(source: Path, output_root: Path) -> Path:
    layout = ConversionLayout(
        root=output_root,
        original_dir="original",
        markdown_dir="markdown",
        assets_dir="assets",
        reports_dir="reports",
    )
    result = convert_resource_bytes(
        layout,
        original_filename=source.name,
        content=source.read_bytes(),
        mime_type="application/octet-stream",
        created_at=_now(),
    )
    return output_root / result["conversion_report_path"]


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
