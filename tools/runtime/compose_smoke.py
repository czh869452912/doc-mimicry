from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Docker Compose API/web stack.")
    parser.add_argument("--runtime", default="mock-acp", choices=["mock", "mock-acp", "openhands", "openhands-acp"])
    parser.add_argument("--api-url", default="http://127.0.0.1:18000")
    parser.add_argument("--web-url", default="http://127.0.0.1:5173")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--skip-up", action="store_true", help="Use already-running compose services.")
    args = parser.parse_args()

    env = os.environ.copy()
    runtime = {"mock": "mock-acp", "openhands": "openhands-acp"}.get(args.runtime, args.runtime)
    env["DOCAGENT_RUNTIME"] = runtime
    if runtime == "mock-acp":
        env.pop("DOCAGENT_ACP_RUNTIME_URL", None)
        env.pop("DOCAGENT_ACP_CONTAINER_RUNTIME_URL", None)
        env.pop("OPENHANDS_BASE_URL", None)
    else:
        env.setdefault("DOCAGENT_ACP_CONTAINER_RUNTIME_URL", "http://openhands:8001")
        env.setdefault("LLM_API_KEY", "sk-docagent-local")
        env.setdefault("LLM_MODEL", "openai/docagent/default")
        env.setdefault("LLM_BASE_URL", "http://litellm:4000")

    if not args.skip_up:
        subprocess.run(
            ["docker", "compose", "down", "--remove-orphans"],
            check=True,
            env=env,
        )
        up_command = ["docker", "compose"]
        if runtime == "openhands-acp":
            up_command.extend(["--profile", "openhands"])
        up_command.extend(["up", "-d", "--build", "postgres", "redis"])
        if runtime == "openhands-acp":
            up_command.extend(["litellm", "openhands"])
        up_command.extend(["api", "worker", "web"])
        subprocess.run(up_command, check=True, env=env)

    wait_for_json(f"{args.api_url}/health", args.timeout)
    wait_for_text(args.web_url, args.timeout)
    wait_for_json(f"{args.web_url}/api/health", args.timeout)
    task = post_json(
        f"{args.web_url}/api/tasks",
        {"doc_type_id": "prd", "brief": "Build onboarding analytics"},
    )
    session = post_json(f"{args.web_url}/api/tasks/{task['id']}/sessions", {})
    post_json(f"{args.web_url}/api/sessions/{session['id']}/loop/start?background=true", {})
    wait_for_workspace_file(
        f"{args.web_url}/api/tasks/{task['id']}/workspace",
        "draft/outline.md",
        args.timeout,
    )
    acp_events = wait_for_acp_events(f"{args.web_url}/api/sessions/{session['id']}/events", args.timeout)
    if not acp_events:
        raise RuntimeError("Expected at least one ACP event after background operation.")
    print("compose smoke ok")
    return 0


def wait_for_json(url: str, timeout_seconds: int) -> None:
    body = wait_for_text(url, timeout_seconds)
    if '"status":"ok"' not in body.replace(" ", ""):
        raise RuntimeError(f"Unexpected health response from {url}: {body[:200]}")


def post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "docagent-compose-smoke",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        if response.status >= 400:
            raise RuntimeError(f"POST {url} failed with {response.status}")
        return json.loads(response.read().decode("utf-8"))


def wait_for_workspace_file(url: str, path: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        workspace = json.loads(wait_for_text(url, 5))
        if any(file.get("path") == path for file in workspace.get("files", [])):
            return
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for workspace file {path}")


def wait_for_acp_events(url: str, timeout_seconds: int) -> list[dict[str, object]]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        events = json.loads(wait_for_text(url, 5))
        if events:
            return events
        time.sleep(2)
    return []


def wait_for_text(url: str, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            request = Request(url, headers={"User-Agent": "docagent-compose-smoke"})
            with urlopen(request, timeout=5) as response:
                if response.status < 400:
                    return response.read().decode("utf-8", errors="replace")
        except (OSError, URLError) as exc:
            last_error = exc
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
