# Workbench Alignment Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the main gaps found in the May 17 project review so DocAgent keeps moving toward a document-version Claude Code workbench rather than a form-heavy management console or split event system.

**Architecture:** Keep the current ACP-first backend and Markdown-only workspace contract. Add small shared helpers instead of new subsystems: one helper for semantic event persistence, one backend manifest/content path for skill-pack resources, one management resource read model, and one durable artifact naming policy.

**Tech Stack:** FastAPI, SQLAlchemy-backed `DocAgentState`, shared `docagent_contracts` models, React 19, TanStack Query, Vitest, pytest, existing conversion package.

---

## Review Drivers

This plan addresses these concrete findings from the repository review:

- Some product events are written only to `/timeline`, while the authoring UI treats ACP events as the durable interaction log.
- Skill Creator receives resource rows but not the converted Markdown content or conversion warnings, so it is not reliably material-driven.
- The management UI accepts uploads but does not show resource rows, converted Markdown, or conversion warnings before use.
- The full management workbench is duplicated inside the Settings drawer and the dedicated management route.
- DOCX/PDF export filenames are fixed and can overwrite earlier artifacts.
- A completed markdown import/export plan contains unchecked boxes, making repo state misleading for future agents.

## Scope

In scope:

- Backend event persistence changes for existing product-generated semantic events.
- Skill Creator prompt input improvements using already-converted resource Markdown and reports.
- Skill-pack resource list and detail endpoints.
- Management UI resource/warning/converted-Markdown visibility.
- Settings drawer simplification to a management route link.
- Unique DOCX/PDF artifact filenames.
- Documentation and plan-state cleanup.

Out of scope:

- Replacing the MVP converter with Docling, Pandoc, LibreOffice, or OCR.
- A new RAG system.
- Full artifact database tables.
- Full visual redesign of the workbench.
- Removing the legacy `doc-types` fallback path.

## File Map

- Modify `services/api/docagent_api/routes/_shared.py`: add one semantic-event persistence helper and reuse it from existing helpers.
- Modify `services/api/docagent_api/routes/tasks.py`: mirror input conversion events into ACP projections.
- Modify `services/api/docagent_api/app.py`: mirror startup recovery error events into ACP projections.
- Modify `services/api/docagent_api/skill_packs.py`: add safe resource summary/detail helpers that read conversion warnings and converted Markdown from the draft pack workspace.
- Modify `services/api/docagent_api/routes/skill_packs.py`: add resource list/detail routes and use enriched manifests for Skill Creator sessions.
- Modify `services/api/docagent_api/response_models.py`: add resource warnings and `SkillPackResourceDetailResponse`.
- Modify `services/api/docagent_api/routes/sessions.py`: write unique DOCX/PDF artifact filenames.
- Modify `apps/web/src/types.ts`: add resource detail type and optional warnings/report fields.
- Modify `apps/web/src/api.ts`: add skill-pack resource list/detail clients.
- Modify `apps/web/src/shell/state/useSkillPacks.ts`: add resource and resource-detail query hooks; invalidate them after uploads.
- Modify `apps/web/src/shell/management/SkillPackManager.tsx`: render resources, warnings, and converted Markdown preview.
- Modify `apps/web/src/shell/SettingsDrawer.tsx`: replace embedded manager with a link to `/management/skill-packs`.
- Modify frontend tests under `apps/web/src/shell/**/__tests__`.
- Modify backend tests under `services/api/tests`.
- Modify `docs/product/ui-surfaces.md`, `docs/architecture/event-model.md`, `docs/index.md`, and `docs/superpowers/completed/2026-05-17-markdown-import-export-pipeline.md`.

## Task 1: Mirror Product Semantic Events Into ACP

**Files:**
- Modify: `services/api/docagent_api/routes/_shared.py`
- Modify: `services/api/docagent_api/routes/tasks.py`
- Modify: `services/api/docagent_api/app.py`
- Test: `services/api/tests/test_imports.py`
- Test: `services/api/tests/test_phase3_api.py`

- [x] **Step 1: Add failing test for input conversion ACP projection**

`services/api/tests/test_imports.py` already imports `Path`, `TestClient`, and `create_app`; append only this test function:

```python
def test_file_input_conversion_is_mirrored_to_acp_events(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use the uploaded notes"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/tasks/{task['id']}/inputs/files",
        files={"file": ("notes.txt", b"Converted material", "text/plain")},
    )

    assert response.status_code == 200
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/projection"
        and event["projection"]["timeline_kind"] == "convert_input"
        and "inputs/markdown/notes.md" in event["projection"]["paths"]
        for event in acp_events
    )
```

- [x] **Step 2: Add failing test for startup recovery ACP projection**

`services/api/tests/test_phase3_api.py` already imports `Path`, `TestClient`, `create_app`, and `DocAgentState`; append only this test function:

```python
def test_startup_recovery_error_is_mirrored_to_acp_events(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Recover me"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    state = DocAgentState(state_root)
    row = state.get_session(session["id"])
    row["status"] = "running_chat"
    state.save_session(row)

    recovered = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))

    assert recovered.get(f"/sessions/{session['id']}").json()["status"] == "failed"
    acp_events = recovered.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/projection"
        and event["projection"]["timeline_kind"] == "error"
        and "interrupted" in event["projection"]["summary"].lower()
        for event in acp_events
    )
```

- [x] **Step 3: Run focused tests and verify failure**

Run:

```powershell
python -m pytest services/api/tests/test_imports.py::test_file_input_conversion_is_mirrored_to_acp_events services/api/tests/test_phase3_api.py::test_startup_recovery_error_is_mirrored_to_acp_events -q
```

Expected: FAIL because the semantic events are present in `/timeline` but not mirrored into `/events`.

- [x] **Step 4: Extract one shared helper**

`append_events` already mirrors semantic events into both the compatibility timeline and ACP projections. This step does not change its behavior; it extracts the single-event behavior into a named helper so direct callers in `tasks.py` and `app.py` can use the same path in Steps 5-6.

In `services/api/docagent_api/routes/_shared.py`, add this helper above `append_events`:

```python
def append_semantic_event(
    state: DocAgentState,
    session_id: str,
    event: SemanticTimelineEvent,
) -> None:
    state.append_timeline_event(session_id, asdict(event))
    append_acp_projection_event(state, session_id, event)
```

Then replace `append_events` with:

```python
def append_events(state: DocAgentState, session_id: str, events: list[SemanticTimelineEvent]) -> None:
    for event in events:
        append_semantic_event(state, session_id, event)
```

- [x] **Step 5: Use the helper in task input routes**

In `services/api/docagent_api/routes/tasks.py`, add `append_semantic_event` to the `_shared` import:

```python
from docagent_api.routes._shared import (
    append_runtime_result,
    append_semantic_event,
    manual_event,
    require_task,
)
```

In both `add_text_input` and `add_file_input`, replace:

```python
state.append_timeline_event(latest["id"], asdict(event))
```

with:

```python
append_semantic_event(state, latest["id"], event)
```

If `asdict` becomes unused in this file after the replacement, remove it from the imports.

- [x] **Step 6: Use the helper in startup recovery**

In `services/api/docagent_api/app.py`, import `append_semantic_event`:

```python
from docagent_api.routes._shared import append_semantic_event, manual_event
```

In `_recover_interrupted_sessions`, replace:

```python
state.append_timeline_event(session["id"], asdict(failure))
```

with:

```python
append_semantic_event(state, session["id"], failure)
```

If `asdict` becomes unused in this file after the replacement, remove it from the imports.

- [x] **Step 7: Run focused tests and verify pass**

Run:

```powershell
python -m pytest services/api/tests/test_imports.py::test_file_input_conversion_is_mirrored_to_acp_events services/api/tests/test_phase3_api.py::test_startup_recovery_error_is_mirrored_to_acp_events -q
```

Expected: PASS.

- [x] **Step 8: Commit Task 1**

```powershell
git add services/api/docagent_api/routes/_shared.py services/api/docagent_api/routes/tasks.py services/api/docagent_api/app.py services/api/tests/test_imports.py services/api/tests/test_phase3_api.py
git commit -m "fix: mirror product events to acp log"
```

## Task 2: Make Skill Creator Actually Read Converted Materials

**Files:**
- Modify: `services/api/docagent_api/skill_packs.py`
- Modify: `services/api/docagent_api/routes/skill_packs.py`
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Test: `services/api/tests/test_skill_creator_sessions.py`
- Test: `agent/runtime-adapters/mock/tests/test_adapter.py`

- [x] **Step 1: Add failing backend prompt-bundle test**

`services/api/tests/test_skill_creator_sessions.py` already imports `Path`, `TestClient`, and `create_app`. Add only these missing imports near the top:

```python
from typing import Any

from docagent_contracts import PromptBundle, RuntimeOperationResult, RuntimeSessionState
```

Then append this helper adapter and test:

```python

class CapturingSkillCreatorAdapter:
    def __init__(self) -> None:
        self.bundle: PromptBundle | None = None

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        self.bundle = prompt_bundle
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_prompt(self, session_id: str, prompt: str, metadata: dict[str, Any] | None = None) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)


def test_skill_creator_prompt_includes_converted_resource_markdown_and_warnings(tmp_path: Path) -> None:
    adapter = CapturingSkillCreatorAdapter()
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=adapter,
    ))
    assert client.post("/skill-packs", json={"id": "memo", "title": "Memo"}).status_code == 200
    assert client.post(
        "/skill-packs/memo/resources/text",
        json={
            "group": "examples",
            "name": "board-memo.txt",
            "content": "Executive summary first. Élan 中文. Then decision context. Then risks.",
        },
    ).status_code == 200

    response = client.post(
        "/skill-packs/memo/skill-creator/sessions",
        json={"message": "Generate the memo skill"},
    )

    assert response.status_code == 200
    assert adapter.bundle is not None
    assert "Executive summary first" in adapter.bundle.task_instruction
    assert "Élan 中文" in adapter.bundle.task_instruction
    assert "resources/markdown/examples/board-memo.md" in adapter.bundle.task_instruction
    assert "warnings" in adapter.bundle.task_instruction
```

- [x] **Step 2: Add failing mock-runtime material-use test**

`agent/runtime-adapters/mock/tests/test_adapter.py` already imports `Path`, `PromptBundle`, and `MockRuntimeAdapter`; append only this test function:

```python
def test_mock_skill_creator_resource_notes_include_prompt_manifest(tmp_path: Path) -> None:
    adapter = MockRuntimeAdapter()
    bundle = PromptBundle(
        system_prompt="system",
        task_instruction=(
            "Resource manifest:\n"
            "{\n"
            '  "resources": [\n'
            '    {"original_filename": "board-memo.txt", "markdown_excerpt": "Executive summary first. Élan 中文."}\n'
            "  ]\n"
            "}\n"
        ),
        workspace_root=tmp_path,
        doc_type_id="",
        pack_id="memo",
        metadata={"session_scope": "pack-management", "pack_id": "memo"},
    )
    adapter.create_session("creator-1", bundle)

    adapter.send_prompt("creator-1", "Generate the memo skill", {"action": "skill_creator_generate"})

    notes = (tmp_path / "notes" / "resources.md").read_text(encoding="utf-8")
    assert "Executive summary first" in notes
    assert "Élan 中文" in notes
```

- [x] **Step 3: Run tests and verify failure**

Run:

```powershell
python -m pytest services/api/tests/test_skill_creator_sessions.py::test_skill_creator_prompt_includes_converted_resource_markdown_and_warnings agent/runtime-adapters/mock/tests/test_adapter.py::test_mock_skill_creator_resource_notes_include_prompt_manifest -q
```

Expected: FAIL because Skill Creator currently receives only resource metadata rows and the mock runtime does not preserve the prompt bundle instruction.

- [x] **Step 4: Add enriched resource manifest helpers**

In `services/api/docagent_api/skill_packs.py`, add:

```python
def list_resource_summaries(state: DocAgentState, pack_id: str) -> list[dict[str, Any]]:
    root = draft_root(state, pack_id)
    summaries: list[dict[str, Any]] = []
    for resource in state.list_skill_pack_resources(pack_id):
        summary = dict(resource)
        summary["warnings"] = _resource_warnings(root, resource)
        summaries.append(summary)
    return summaries


def list_resource_details(state: DocAgentState, pack_id: str) -> list[dict[str, Any]]:
    root = draft_root(state, pack_id)
    details: list[dict[str, Any]] = []
    for resource in state.list_skill_pack_resources(pack_id):
        details.append(_resource_detail(root, resource))
    return details


def _resource_detail(root: Path, resource: dict[str, Any]) -> dict[str, Any]:
    detail = dict(resource)
    markdown_path = resource.get("markdown_path")
    markdown = ""
    conversion_report = _resource_report(root, resource)
    warnings = list(conversion_report.get("warnings") or [])
    if markdown_path:
        markdown_file = _resolve_resource_path(root, markdown_path)
        if markdown_file.is_file():
            markdown = markdown_file.read_text(encoding="utf-8")
    detail["markdown"] = markdown
    # Cap each resource before serializing the complete prompt bundle.
    detail["markdown_excerpt"] = _word_excerpt(markdown, 800)
    detail["warnings"] = warnings
    detail["conversion_report"] = conversion_report
    return detail


def _resource_warnings(root: Path, resource: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_resource_report(root, resource).get("warnings") or [])


def _resource_report(root: Path, resource: dict[str, Any]) -> dict[str, Any]:
    report_path = resource.get("conversion_report_path")
    if not report_path:
        return {}
    report_file = _resolve_resource_path(root, report_path)
    if not report_file.is_file():
        return {}
    return json.loads(report_file.read_text(encoding="utf-8"))


def _resolve_resource_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Resource path escapes pack workspace")
    return target


def _word_excerpt(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])
```

- [x] **Step 5: Use enriched manifest in Skill Creator routes**

In `services/api/docagent_api/routes/skill_packs.py`, import `list_resource_details`:

```python
from docagent_api.skill_packs import (
    PACK_GROUPS,
    add_file_resource,
    add_text_resource,
    draft_root,
    is_valid_pack_id,
    list_resource_details,
    publish_skill_pack_snapshot,
    resolve_artifact_path,
    validate_skill_pack_draft,
    write_skill_pack_artifact,
)
```

Replace `_resource_manifest` with:

```python
def _resource_manifest(state: DocAgentState, pack_id: str) -> dict[str, object]:
    return {"resources": list_resource_details(state, pack_id)}
```

No route should use `list_resource_summaries` yet; Task 3 adds the lightweight management list endpoint.

- [x] **Step 6: Preserve Skill Creator prompt bundle in mock runtime**

In `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`, add `import json` near the top, then update `create_session` so the session dict includes `task_instruction`:

```python
session: dict[str, object] = {
    "workspace_root": prompt_bundle.workspace_root,
    "state": RuntimeSessionState.IDLE,
    "session_scope": session_scope,
    "task_instruction": prompt_bundle.task_instruction,
}
```

Change `_run_skill_creator_action` to read the instruction:

```python
task_instruction = str(session.get("task_instruction") or "")
resource_notes = _skill_creator_resource_notes(pack_id, prompt, task_instruction)
```

Replace `_skill_creator_resource_notes` with:

```python
def _skill_creator_resource_notes(pack_id: str, prompt: str, task_instruction: str) -> str:
    excerpt = _extract_first_markdown_excerpt(task_instruction)
    observed = f"\n\n## Observed Resource Signals\n\n{excerpt}\n" if excerpt else ""
    return (
        f"# Resource Notes for {pack_id}\n\n"
        "Skill Creator should summarize converted resources before using them as guidance.\n\n"
        f"Latest instruction: {prompt}\n"
        f"{observed}"
    )


def _extract_first_markdown_excerpt(task_instruction: str) -> str:
    marker = "Resource manifest:\n"
    start = task_instruction.find(marker)
    if start == -1:
        return ""
    start += len(marker)
    end = task_instruction.find("\n\nCurrent artifacts:", start)
    manifest_text = task_instruction[start:end if end != -1 else len(task_instruction)]
    try:
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError:
        return ""
    resources = manifest.get("resources", [])
    if not isinstance(resources, list):
        return ""
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        excerpt = resource.get("markdown_excerpt")
        if isinstance(excerpt, str):
            return excerpt
    return ""
```

- [x] **Step 7: Run focused tests and verify pass**

Run:

```powershell
python -m pytest services/api/tests/test_skill_creator_sessions.py::test_skill_creator_prompt_includes_converted_resource_markdown_and_warnings agent/runtime-adapters/mock/tests/test_adapter.py::test_mock_skill_creator_resource_notes_include_prompt_manifest -q
```

Expected: PASS.

- [x] **Step 8: Commit Task 2**

```powershell
git add services/api/docagent_api/skill_packs.py services/api/docagent_api/routes/skill_packs.py services/api/tests/test_skill_creator_sessions.py agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py agent/runtime-adapters/mock/tests/test_adapter.py
git commit -m "feat: feed converted materials to skill creator"
```

## Task 3: Show Skill Pack Resources, Warnings, And Converted Markdown

This task depends on Task 2's `list_resource_details` and `list_resource_summaries` helpers. Keep the list endpoint lightweight: it should expose resource metadata plus conversion warnings, while the detail endpoint is the only route that returns full converted Markdown and conversion report bodies.

**Files:**
- Modify: `services/api/docagent_api/routes/skill_packs.py`
- Modify: `services/api/docagent_api/response_models.py`
- Modify: `services/api/tests/test_skill_pack_routes.py`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/shell/state/useSkillPacks.ts`
- Modify: `apps/web/src/shell/management/SkillPackManager.tsx`
- Modify: `apps/web/src/shell/management/__tests__/ManagementPage.test.tsx`

- [x] **Step 1: Add failing API resource read test**

`services/api/tests/test_skill_pack_routes.py` already imports `Path`, `TestClient`, and `create_app`; append only this test function:

```python
def test_skill_pack_resource_detail_exposes_markdown_and_warnings(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo"})
    resource = client.post(
        "/skill-packs/memo/resources/text",
        json={"group": "examples", "name": "memo.txt", "content": "Memo pattern"},
    ).json()

    list_response = client.get("/skill-packs/memo/resources")
    detail_response = client.get(f"/skill-packs/memo/resources/{resource['id']}")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [resource["id"]]
    assert "warnings" in list_response.json()[0]
    assert "markdown" not in list_response.json()[0]
    assert "conversion_report" not in list_response.json()[0]
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["markdown"] == "Memo pattern\n"
    assert detail["conversion_report"]["source_path"] == "resources/original/examples/memo.txt"
    assert detail["warnings"] == []
```

- [x] **Step 2: Add failing frontend management test**

In `apps/web/src/shell/management/__tests__/ManagementPage.test.tsx`, extend the existing API mock:

```tsx
vi.mock("../../../api", () => ({
  api: {
    addSkillPackFileResource: vi.fn(),
    getSkillPackArtifact: vi.fn(),
    getSkillPackResource: vi.fn(),
    listSkillPacks: vi.fn(),
    listSkillPackResources: vi.fn(),
  },
}));
```

Add these defaults to the existing `beforeEach`:

```tsx
vi.mocked(api.listSkillPackResources).mockResolvedValue([]);
vi.mocked(api.getSkillPackResource).mockRejectedValue(new Error("404"));
```

Then append this test:

```tsx
it("shows resource conversion warnings and converted markdown", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listSkillPacks).mockResolvedValue([
    { id: "memo", title: "Memo", description: "", draft_status: "draft", latest_version_id: null },
  ]);
  vi.mocked(api.listSkillPackResources).mockResolvedValue([
    {
      id: "resource-1",
      pack_id: "memo",
      group: "examples",
      original_filename: "memo.docx",
      source_path: "resources/original/examples/memo.docx",
      markdown_path: "resources/markdown/examples/memo.md",
      conversion_report_path: "resources/reports/examples/memo.conversion.json",
      status: "warning",
      summary: "",
      warnings: [{ type: "docx_format_loss", message: "DOCX layout was reduced.", location: null }],
    },
  ]);
  vi.mocked(api.getSkillPackResource).mockResolvedValue({
    id: "resource-1",
    pack_id: "memo",
    group: "examples",
    original_filename: "memo.docx",
    source_path: "resources/original/examples/memo.docx",
    markdown_path: "resources/markdown/examples/memo.md",
    conversion_report_path: "resources/reports/examples/memo.conversion.json",
    status: "warning",
    summary: "",
    warnings: [{ type: "docx_format_loss", message: "DOCX layout was reduced.", location: null }],
    markdown: "# Converted memo",
    conversion_report: { status: "succeeded_with_warnings" },
  });

  renderManagementPage();
  await screen.findByText("memo.docx");
  expect(screen.getByText("DOCX layout was reduced.")).toBeTruthy();

  await user.click(screen.getByRole("button", { name: /view converted memo.docx/i }));

  expect(await screen.findByText("# Converted memo")).toBeTruthy();
});
```

- [x] **Step 3: Run tests and verify failure**

Run:

```powershell
python -m pytest services/api/tests/test_skill_pack_routes.py::test_skill_pack_resource_detail_exposes_markdown_and_warnings -q
cd apps/web
npm run test:unit -- --run src/shell/management/__tests__/ManagementPage.test.tsx
cd ..\..
```

Expected: backend route test fails with 404; frontend test fails because clients/hooks/UI do not exist.

- [x] **Step 4: Add response models**

In `services/api/docagent_api/response_models.py`, add this field to the existing `SkillPackResourceResponse`:

```python
warnings: list[dict[str, Any]] = Field(default_factory=list)
```

Then add:

```python
class SkillPackResourceDetailResponse(SkillPackResourceResponse):
    markdown: str = ""
    conversion_report: dict[str, Any] = Field(default_factory=dict)
```

- [x] **Step 5: Add resource read routes**

In `services/api/docagent_api/routes/skill_packs.py`, import `SkillPackResourceDetailResponse` and make sure `SkillPackResourceResponse`, `list_resource_summaries`, and `list_resource_details` are imported. Then add these routes after the file resource route:

```python
    @router.get("/skill-packs/{pack_id}/resources", response_model=list[SkillPackResourceResponse])
    def list_pack_resources(pack_id: str) -> list[dict[str, Any]]:
        _require_pack(state, pack_id)
        try:
            return list_resource_summaries(state, pack_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/skill-packs/{pack_id}/resources/{resource_id}", response_model=SkillPackResourceDetailResponse)
    def get_pack_resource(pack_id: str, resource_id: str) -> dict[str, Any]:
        _require_pack(state, pack_id)
        try:
            for resource in list_resource_details(state, pack_id):
                if resource["id"] == resource_id:
                    return resource
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail="Skill pack resource not found")
```

- [x] **Step 6: Add frontend types and clients**

In `apps/web/src/types.ts`, update `SkillPackResource`:

```ts
export interface SkillPackResource {
  id: string;
  pack_id: string;
  group: "examples" | "specs" | "checklists" | "export-references";
  original_filename: string;
  source_path: string;
  markdown_path?: string | null;
  conversion_report_path: string;
  status: "ready" | "warning" | "failed" | "unsupported";
  summary: string;
  warnings?: Array<{ type: string; message: string; location: string | null }>;
}

export interface SkillPackResourceDetail extends SkillPackResource {
  markdown: string;
  conversion_report: Record<string, unknown>;
}
```

In `apps/web/src/api.ts`, import `SkillPackResourceDetail` and add:

```ts
  listSkillPackResources: (packId: string) =>
    request<SkillPackResource[]>(`/skill-packs/${packId}/resources`),
  getSkillPackResource: (packId: string, resourceId: string) =>
    request<SkillPackResourceDetail>(`/skill-packs/${packId}/resources/${resourceId}`),
```

- [x] **Step 7: Add query hooks and invalidation**

In `apps/web/src/shell/state/useSkillPacks.ts`, add:

```ts
export function useSkillPackResources(packId: string | null) {
  return useQuery({
    queryKey: ["skillPackResources", packId],
    queryFn: () => api.listSkillPackResources(packId ?? ""),
    enabled: Boolean(packId),
  });
}

export function useSkillPackResource(packId: string | null, resourceId: string | null) {
  return useQuery({
    queryKey: ["skillPackResource", packId, resourceId],
    queryFn: () => api.getSkillPackResource(packId ?? "", resourceId ?? ""),
    enabled: Boolean(packId && resourceId),
  });
}
```

Update `useAddSkillPackTextResource` and `useAddSkillPackFileResource` `onSuccess` handlers to invalidate both:

```ts
onSuccess: (_resource, _variables) => {
  void queryClient.invalidateQueries({ queryKey: ["skillPacks"] });
  void queryClient.invalidateQueries({ queryKey: ["skillPackResources", packId] });
},
```

- [x] **Step 8: Render resource list and preview in SkillPackManager**

In `PackWorkSurface`, add state and hooks:

```tsx
const resourcesQuery = useSkillPackResources(packId);
const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
const resourceDetail = useSkillPackResource(packId, selectedResourceId);
const resources = resourcesQuery.data ?? [];
```

After the "Add material" button, render:

```tsx
<div className="skill-pack-resource-list" aria-label="Pack resources">
  {resources.map((resource) => (
    <article className="skill-pack-resource-row" key={resource.id}>
      <div>
        <strong>{resource.original_filename}</strong>
        <p className="muted">{resource.group} · {resource.status}</p>
        {(resource.warnings ?? []).map((warning) => (
          <p className="status-warning" key={`${resource.id}-${warning.type}`}>{warning.message}</p>
        ))}
      </div>
      <Button
        size="sm"
        variant="outline"
        type="button"
        aria-label={`View converted ${resource.original_filename}`}
        disabled={!resource.markdown_path}
        onClick={() => setSelectedResourceId(resource.id)}
      >
        <FileText size={14} />
        View converted
      </Button>
    </article>
  ))}
</div>
{resourceDetail.data ? (
  <section className="skill-pack-resource-preview">
    <h4>{resourceDetail.data.original_filename}</h4>
    <pre>{resourceDetail.data.markdown}</pre>
  </section>
) : null}
```

Import `useSkillPackResources` and `useSkillPackResource`.

- [x] **Step 9: Run focused tests and verify pass**

Run:

```powershell
python -m pytest services/api/tests/test_skill_pack_routes.py::test_skill_pack_resource_detail_exposes_markdown_and_warnings -q
cd apps/web
npm run test:unit -- --run src/shell/management/__tests__/ManagementPage.test.tsx
cd ..\..
```

Expected: PASS.

- [x] **Step 10: Commit Task 3**

```powershell
git add services/api/docagent_api/routes/skill_packs.py services/api/docagent_api/response_models.py services/api/tests/test_skill_pack_routes.py apps/web/src/types.ts apps/web/src/api.ts apps/web/src/shell/state/useSkillPacks.ts apps/web/src/shell/management/SkillPackManager.tsx apps/web/src/shell/management/__tests__/ManagementPage.test.tsx
git commit -m "feat: show skill pack resource conversions"
```

## Task 4: Keep Settings Drawer Lightweight And Management Dedicated

**Files:**
- Modify: `apps/web/src/shell/SettingsDrawer.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`
- Modify: `docs/product/ui-surfaces.md`

- [x] **Step 1: Add failing settings drawer boundary test**

In `apps/web/src/shell/__tests__/AppShell.test.tsx`, replace the existing test named `"creates a material-driven skill pack from the settings drawer"` with:

```tsx
it("links to dedicated skill pack management from the settings drawer", async () => {
  const { router } = renderAppShell("/?task=task-1&session=session-1");
  await userEvent.click(await screen.findByRole("button", { name: /open settings/i }));

  const link = await screen.findByRole("link", { name: /open skill pack management/i });
  expect(link.getAttribute("href")).toBe("/management/skill-packs");

  await userEvent.click(link);
  await waitFor(() => expect(router.state.location.pathname).toBe("/management/skill-packs"));
});
```

- [x] **Step 2: Run test and verify failure**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/__tests__/AppShell.test.tsx
cd ..\..
```

Expected: FAIL because the Settings drawer still embeds the full manager instead of linking to the route.

- [x] **Step 3: Replace embedded manager with route link**

In `apps/web/src/shell/SettingsDrawer.tsx`, remove:

```tsx
import { SkillPackManager } from "./management/SkillPackManager";
```

Add:

```tsx
import { Link } from "@tanstack/react-router";
```

Replace the drawer section containing `<SkillPackManager />` with:

```tsx
<section className="drawer-section">
  <h2>Skill Packs</h2>
  <p className="muted">
    Manage reusable materials, generated SKILL.md guidance, validation, and published versions in the dedicated management surface.
  </p>
  <Link className="command-chip" to="/management/skill-packs" aria-label="Open skill pack management">
    Open skill pack management
  </Link>
</section>
```

The exact old block is currently:

```tsx
<section className="drawer-section">
  <SkillPackManager />
</section>
```

- [x] **Step 4: Update product UI doc**

In `docs/product/ui-surfaces.md`, under "UI Principles", ensure this sentence is present:

```markdown
- The settings drawer may summarize runtime and repository document-type details, but the full Skill Pack Management workflow belongs only on `/management/skill-packs`.
```

- [x] **Step 5: Run focused frontend test**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/__tests__/AppShell.test.tsx
cd ..\..
```

Expected: PASS.

- [x] **Step 6: Commit Task 4**

```powershell
git add apps/web/src/shell/SettingsDrawer.tsx apps/web/src/shell/__tests__/AppShell.test.tsx docs/product/ui-surfaces.md
git commit -m "fix: keep skill pack management on dedicated route"
```

## Task 5: Make DOCX/PDF Artifact Exports Durable

**Files:**
- Modify: `services/api/docagent_api/routes/sessions.py`
- Modify: `services/api/tests/test_phase3_api.py`

- [x] **Step 1: Add failing repeated-export test**

`services/api/tests/test_phase3_api.py` already imports `Path`, `TestClient`, and `create_app`; append only this test function:

```python
def test_repeated_docx_exports_create_distinct_artifacts(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Draft\n\nBody\n"})

    first = client.post(f"/sessions/{session['id']}/artifacts/export-docx").json()
    second = client.post(f"/sessions/{session['id']}/artifacts/export-docx").json()

    assert first["artifact_path"] != second["artifact_path"]
    assert (Path(task["workspace_root"]) / first["artifact_path"]).is_file()
    assert (Path(task["workspace_root"]) / second["artifact_path"]).is_file()
    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    export_paths = [
        path
        for event in timeline
        if event["kind"] == "export_docx"
        for path in event["paths"]
    ]
    assert first["artifact_path"] in export_paths
    assert second["artifact_path"] in export_paths
```

- [x] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest services/api/tests/test_phase3_api.py::test_repeated_docx_exports_create_distinct_artifacts -q
```

Expected: FAIL because both exports currently use the same artifact path.

- [x] **Step 3: Generate unique artifact names**

In `services/api/docagent_api/routes/sessions.py`, replace:

```python
stem = str(task["doc_type_id"]).replace("/", "-").replace("\\", "-")
artifact_relative = f"artifacts/{stem}-draft.{extension}"
```

with:

```python
stem = str(task["doc_type_id"]).replace("/", "-").replace("\\", "-")
artifact_relative = f"artifacts/{stem}-draft-{uuid4().hex[:8]}.{extension}"
```

The file already imports `uuid4`, so no new import is needed.

- [x] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest services/api/tests/test_phase3_api.py::test_repeated_docx_exports_create_distinct_artifacts services/api/tests/test_phase3_api.py::test_export_docx_route_creates_artifact_without_runtime_prompt services/api/tests/test_phase3_api.py::test_export_pdf_route_creates_artifact_without_runtime_prompt -q
```

Expected: PASS.

- [x] **Step 5: Commit Task 5**

```powershell
git add services/api/docagent_api/routes/sessions.py services/api/tests/test_phase3_api.py
git commit -m "fix: create unique exported artifact paths"
```

## Task 6: Reconcile Completed Plan And Current-Truth Docs

**Files:**
- Modify: `docs/superpowers/completed/2026-05-17-markdown-import-export-pipeline.md`
- Modify: `docs/index.md`
- Modify: `docs/architecture/event-model.md`
- Modify: `docs/product/ui-surfaces.md`

- [x] **Step 1: Add a clear completion note to the import/export plan**

At the top of `docs/superpowers/completed/2026-05-17-markdown-import-export-pipeline.md`, after the title, add:

```markdown
> Status reconciled on 2026-05-17. The implementation files, tests, routes, and UI commands described by this plan are present in the repository. Some original checklist boxes below were left unchecked during archival, so this note is the durable status marker for future agents.
```

- [x] **Step 2: Mark completed checkboxes safely**

First inspect the target file for code fences and unchecked task markers:

```powershell
rg -n "^```|^- \[ \] \*\*Step" docs/superpowers/completed/2026-05-17-markdown-import-export-pipeline.md
```

Confirm the task markers are not inside fenced code blocks. Then, using the editor or `apply_patch`, replace each task checkbox marker:

```markdown
OLD: - [ ] **Step
```

with:

```markdown
NEW: - [x] **Step
```

Do not change code blocks or historical command examples.

- [x] **Step 3: Verify no unchecked boxes remain in that completed plan**

Run:

```powershell
rg -n "^- \\[ \\]" docs/superpowers/completed/2026-05-17-markdown-import-export-pipeline.md
```

Expected: no output and exit code 1 from `rg` because there are no matches.

- [x] **Step 4: Update event-model doc with semantic event persistence rule**

In `docs/architecture/event-model.md`, add this paragraph under "Storage":

```markdown
Every product-created semantic event that affects user trust or workspace state must be persisted through the shared semantic-event helper so it appears in both the compatibility `/timeline` read model and the ACP event log consumed by the authoring UI.
```

- [x] **Step 5: Run documentation checks**

Run:

```powershell
rg -n "^- \\[ \\]" docs/superpowers/completed/2026-05-17-markdown-import-export-pipeline.md
rg -n "completed implementation plan" docs/index.md
Get-ChildItem -Recurse -File | Select-Object FullName | Out-Null
```

Expected: first `rg` has no output and exit code 1; second `rg` finds the completed import/export plan index entry; structure check exits 0.

- [x] **Step 6: Commit Task 6**

```powershell
git add docs/superpowers/completed/2026-05-17-markdown-import-export-pipeline.md docs/index.md docs/architecture/event-model.md docs/product/ui-surfaces.md
git commit -m "docs: reconcile alignment hardening guidance"
```

## Final Verification

Run the complete verification suite:

```powershell
python -m pytest packages/conversion/tests tools/import/tests packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests -q
cd apps/web
npm run test:unit -- --run
npm run test
npm run build
cd ..\..
docker compose config
Get-ChildItem -Recurse -File | Select-Object FullName | Out-Null
git diff --check -- . ':!.claude/settings.local.json'
git status --short --branch
```

Expected:

- All Python tests pass.
- Frontend unit tests, TypeScript check, and Vite build pass.
- `docker compose config` exits 0.
- Documentation structure check exits 0.
- `git diff --check` reports no whitespace errors.
- Worktree contains only intentional changes plus any pre-existing local files such as `.claude/settings.local.json`.

## Rollback Notes

- Task 1 is safe to revert independently if ACP projection duplication creates UI regressions; reverting restores previous timeline-only behavior.
- Task 2 can be reverted independently because it only enriches prompt context and mock output, not the stored resource layout.
- Task 3 can be partially reverted by removing the frontend resource preview while keeping backend resource read routes.
- Task 4 is UI-only and can be reverted without backend changes.
- Task 5 only changes future artifact names; existing artifact files remain valid.
- Task 6 is documentation-only.

## Open Questions For Execution

- Should Skill Creator resource excerpts use 800 words per resource, as planned here, or a total pack-level budget before `build_skill_creator_prompt_bundle` receives the manifest? This plan uses 800 words per resource plus the existing prompt-bundle budget for a conservative MVP.
- Should unique export names include human-readable UTC timestamps? This plan uses short UUID suffixes to avoid timezone formatting churn and keep paths compact.
