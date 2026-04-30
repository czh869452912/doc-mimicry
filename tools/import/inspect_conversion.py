from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    print(f"status: {report['status']}")
    print(f"engine: {report['engine']}")
    print(f"markdown: {report['markdown_path']}")
    for warning in report.get("warnings", []):
        print(f"warning[{warning['type']}]: {warning['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
