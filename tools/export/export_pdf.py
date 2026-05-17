from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "conversion"))

from docagent_conversion import export_markdown_to_pdf


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = export_markdown_to_pdf(Path(args.source), Path(args.output))
    print(result["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
