from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "packages" / "workspace"))

from docagent_workspace import validate_workspace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    result = validate_workspace(Path(args.workspace))
    if result.valid:
        print("valid")
        return 0

    print("invalid")
    for path in result.missing_files:
        print(f"missing: {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
