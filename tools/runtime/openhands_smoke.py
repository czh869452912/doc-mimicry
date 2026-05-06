from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def main() -> int:
    client = TestClient(create_app(repo_root=Path("."), runtime_name="openhands"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    print("created task")
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    print("created session")
    client.post(
        f"/tasks/{task['id']}/inputs/text",
        json={"name": "research.txt", "content": "Users need funnel visibility."},
    )
    client.post(f"/sessions/{session['id']}/loop/start").raise_for_status()
    print("started loop")
    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    ).raise_for_status()
    print("approved outline")
    draft = client.get(f"/tasks/{task['id']}/draft").json()["markdown"]
    selected = "Build onboarding analytics" if "Build onboarding analytics" in draft else draft.splitlines()[0]
    client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": selected, "instruction": "Make this more specific."},
    ).raise_for_status()
    print("revised selection")
    client.post(f"/sessions/{session['id']}/checklist/run").raise_for_status()
    print("ran checklist")
    client.post(f"/sessions/{session['id']}/artifacts/export-markdown").raise_for_status()
    print("exported markdown")
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
