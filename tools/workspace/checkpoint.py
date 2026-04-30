from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "packages" / "workspace"))

from docagent_workspace import checkpoint_draft


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--summary", default="Checkpoint")
    args = parser.parse_args()

    version = checkpoint_draft(Path(args.workspace), summary=args.summary)
    print(version.version_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
