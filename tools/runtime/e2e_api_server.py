from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from testcontainers.postgres import PostgresContainer


ROOT = Path(__file__).resolve().parents[2]

for relative in [
    "packages/contracts",
    "packages/conversion",
    "packages/workspace",
    "packages/timeline",
    "tools/import",
    "services/api",
    "agent/runtime-adapters/mock",
    "agent/runtime-adapters/openhands",
]:
    sys.path.insert(0, str(ROOT / relative))


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the DocAgent API for Playwright E2E tests.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    os.environ.setdefault("DOCAGENT_RUNTIME", "mock-acp")
    os.environ.setdefault("DOCAGENT_QUEUE", "inline")
    os.environ.setdefault("DOCAGENT_REPO_ROOT", str(ROOT))

    with TemporaryDirectory(prefix="docagent-e2e-") as state_root, PostgresContainer("postgres:16-alpine") as postgres:
        os.environ.setdefault("DOCAGENT_STATE_ROOT", state_root)
        os.environ["DATABASE_URL"] = postgres.get_connection_url()

        import uvicorn

        from docagent_api.app import create_app

        uvicorn.run(
            create_app(
                state_root=Path(os.environ["DOCAGENT_STATE_ROOT"]),
                repo_root=ROOT,
                runtime_name=os.environ["DOCAGENT_RUNTIME"],
            ),
            host=args.host,
            port=args.port,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
