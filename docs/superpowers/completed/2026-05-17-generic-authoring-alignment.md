# Generic Authoring Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn the current PRD-shaped authoring demo into a doc-type-agnostic authoring path while tightening Skill Pack warning safety and E2E reliability.

**Architecture:** Keep the existing ACP-first runtime boundary and Markdown workspace contract. Make document-type specificity flow from `PromptBundle.doc_type_id`, task metadata, and published skill-pack snapshots instead of hardcoded PRD strings. Keep management safety gates explicit in the UI and backend.

**Tech Stack:** FastAPI, Pydantic, Python runtime adapters, pytest, React, TanStack Query, Vitest, Playwright, Testcontainers Postgres.

---

## Review Context

This plan follows the May 17, 2026 review and external `claude -p` review. The confirmed issues are:

- Markdown export prompt and API response are hardcoded to `artifacts/prd-draft.md`.
- `MockRuntimeAdapter` does not store `doc_type_id` for authoring sessions and emits PRD-specific draft headings, timeline paths, checklist language, and export paths.
- E2E tests assert PRD-specific output instead of generic authoring mechanics.
- Skill Pack publish UI auto-acknowledges all validation warnings by passing `validationWarnings` directly to the backend.
- `_source_copy_warnings` skips resources with `status == "warning"`.
- The E2E API runner leaves `.local/e2e/docagent-*` directories behind after runs.

## File Structure

- Modify `services/api/docagent_api/routes/sessions.py`: generate Markdown export artifact paths from `task["doc_type_id"]`; send a matching runtime prompt; return the actual path.
- Modify `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`: store `doc_type_id`; derive skill/example paths, draft heading, style/structure wording, checklist wording, and Markdown export path from doc type.
- Modify `agent/runtime-adapters/mock/tests/test_authoring_loop.py`: add non-PRD authoring tests and update export expectations.
- Modify `agent/runtime-adapters/mock/tests/test_adapter.py`: add non-PRD first-message coverage and keep ACP event family coverage generic.
- Modify `services/api/tests/test_phase2_api.py`: update Markdown export expectation away from `prd-draft.md`.
- Modify or add `services/api/tests/test_phase3_api.py`: add API-level non-PRD export coverage if an existing helper is convenient; otherwise create a focused test in `services/api/tests/test_authoring_pack_binding.py`.
- Modify `apps/web/tests/core-loop.spec.ts`: remove PRD-specific UI assertions except where explicitly testing PRD content; assert generic draft/artifact behavior.
- Modify `apps/web/tests/workbench-shell.spec.ts`: reduce PRD naming in test titles/descriptions where it is not material.
- Modify `apps/web/src/shell/management/SkillPackManager.tsx`: add explicit per-warning acknowledgment state and disable publish until every warning is checked.
- Modify `apps/web/src/shell/state/useSkillPacks.ts`: rename mutation variable from `warnings` to `acknowledgedWarnings` for clarity.
- Modify `apps/web/src/api.ts`: no wire change required, but keep parameter name as `acknowledged_warnings` at the boundary.
- Modify or add `apps/web/src/shell/management/__tests__/SkillPackManager.test.tsx`: cover warning acknowledgment behavior.
- Modify `services/api/docagent_api/skill_packs.py`: include `warning` resources in source-copy checks.
- Modify `services/api/tests/test_skill_packs.py`: add warning-status resource copy-detection coverage.
- Modify `tools/runtime/e2e_api_server.py`: clean its generated state root on shutdown.
- Modify `tests/test_dev_entrypoint.py`: extend the E2E runner contract test to assert cleanup behavior.

---

### Task 1: Dynamic Markdown Export Path

**Files:**
- Modify: `services/api/docagent_api/routes/sessions.py`
- Modify: `services/api/tests/test_phase2_api.py`
- Test: `services/api/tests/test_authoring_pack_binding.py`

- [x] **Step 1: Add a failing API test for non-PRD Markdown export**

Add this test to `services/api/tests/test_authoring_pack_binding.py`:

```python
def test_markdown_export_uses_task_doc_type_path(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n",
        "summary": "Initial memo skill",
    })
    version = client.post("/skill-packs/memo/publish", json={"publish_note": "Memo v1"}).json()
    task = client.post("/tasks", json={
        "doc_type_id": "memo",
        "pack_version_id": version["id"],
        "brief": "Write a board memo",
    }).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    )

    response = client.post(f"/sessions/{session['id']}/artifacts/export-markdown")

    assert response.status_code == 200
    assert response.json()["artifact_path"] == "artifacts/memo-draft.md"
    workspace = client.get(f"/tasks/{task['id']}/workspace").json()
    assert "artifacts/memo-draft.md" in [file["path"] for file in workspace["files"]]
```

- [x] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest services/api/tests/test_authoring_pack_binding.py::test_markdown_export_uses_task_doc_type_path -q
```

Expected: fail because the response returns `artifacts/prd-draft.md`.

- [x] **Step 3: Implement path helper and dynamic prompt**

In `services/api/docagent_api/routes/sessions.py`, replace the module constant:

```python
EXPORT_MARKDOWN_PROMPT = "Export the current draft to artifacts/prd-draft.md."
```

with helpers near the other prompt constants:

```python
def _artifact_stem(task: dict[str, Any]) -> str:
    return str(task["doc_type_id"]).replace("/", "-").replace("\\", "-")


def _markdown_artifact_relative(task: dict[str, Any]) -> str:
    return f"artifacts/{_artifact_stem(task)}-draft.md"


def _export_markdown_prompt(task: dict[str, Any]) -> str:
    return f"Export the current draft to {_markdown_artifact_relative(task)}."
```

Then in `export_markdown`, compute once after `task = require_task(...)`:

```python
artifact_relative = _markdown_artifact_relative(task)
export_prompt = _export_markdown_prompt(task)
```

Replace every `EXPORT_MARKDOWN_PROMPT` inside `export_markdown` with `export_prompt`. Return the computed path:

```python
return {"session_id": session_id, "artifact_path": artifact_relative, "event_count": len(result.events)}
```

Keep `_export_draft_artifact` using the same stem helper:

```python
stem = _artifact_stem(task)
```

- [x] **Step 4: Update existing PRD expectation**

In `services/api/tests/test_phase2_api.py`, update:

```python
assert export_response.json()["artifact_path"] == "artifacts/prd-draft.md"
```

to:

```python
assert export_response.json()["artifact_path"] == "artifacts/prd-draft.md"
```

This assertion stays the same for PRD, but keep it intentionally after the helper change to document compatibility.

- [x] **Step 5: Run focused API export tests**

Run:

```powershell
python -m pytest services/api/tests/test_phase2_api.py::test_phase2_prd_authoring_loop services/api/tests/test_authoring_pack_binding.py::test_markdown_export_uses_task_doc_type_path -q
```

Expected: both pass.

---

### Task 2: Generic Mock Runtime Authoring

**Files:**
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Modify: `agent/runtime-adapters/mock/tests/test_authoring_loop.py`
- Modify: `agent/runtime-adapters/mock/tests/test_adapter.py`

- [x] **Step 1: Add failing mock tests for non-PRD behavior**

In `agent/runtime-adapters/mock/tests/test_authoring_loop.py`, add:

```python
def test_non_prd_outline_uses_doc_type_paths_and_generic_language(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Write a board memo about renewals\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace, doc_type_id="memo"))
    result = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})

    assert (workspace / "context" / "style_notes.md").read_text(encoding="utf-8").startswith("# Style Notes")
    assert "PRD" not in (workspace / "context" / "style_notes.md").read_text(encoding="utf-8")
    assert result.events[0].paths == ["doc-types/memo/SKILL.md"]
    assert result.events[1].paths == ["doc-types/memo/examples/markdown"]
    assert result.events[0].summary == "Read memo skill"
    assert result.events[1].summary == "Analyze memo examples"


def test_non_prd_draft_and_export_use_doc_type_heading_and_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "brief.md").write_text("Write a board memo about renewals\n", encoding="utf-8")
    (workspace / "draft" / "outline.md").write_text("# Outline\n\n1. Context\n2. Recommendation\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace, doc_type_id="memo"))
    adapter.send_prompt("session-001", "Approve outline", {"action": "approve_outline"})
    export_events = adapter.send_prompt("session-001", "Export Markdown", {"action": "export_markdown"}).events

    draft = (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert "# Memo Draft" in draft
    assert "# PRD Draft" not in draft
    assert (workspace / "artifacts" / "memo-draft.md").exists()
    assert export_events[0].paths == ["artifacts/memo-draft.md"]
```

Change the helper signature in the same file:

```python
def _prompt_bundle(workspace: Path, doc_type_id: str = "prd") -> PromptBundle:
    return PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=workspace,
        doc_type_id=doc_type_id,
        metadata={"task_id": "task-001"},
    )
```

In `agent/runtime-adapters/mock/tests/test_adapter.py`, update `_prompt_bundle` the same way and add:

```python
def test_first_message_for_non_prd_uses_generic_heading_and_skill_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Create a board memo\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace, doc_type_id="memo"))
    result = adapter.send_prompt("session-001", "Start drafting", {"action": "send_message"})

    draft = (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert "# Memo Draft" in draft
    assert "# PRD Draft" not in draft
    assert result.events[1].paths == ["doc-types/memo/SKILL.md"]
```

- [x] **Step 2: Run failing mock tests**

Run:

```powershell
python -m pytest agent/runtime-adapters/mock/tests/test_authoring_loop.py::test_non_prd_outline_uses_doc_type_paths_and_generic_language agent/runtime-adapters/mock/tests/test_authoring_loop.py::test_non_prd_draft_and_export_use_doc_type_heading_and_path agent/runtime-adapters/mock/tests/test_adapter.py::test_first_message_for_non_prd_uses_generic_heading_and_skill_path -q
```

Expected: fail because the mock stores no `doc_type_id` and emits PRD-specific output.

- [x] **Step 3: Store doc type and add formatting helpers**

In `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`, in `create_session`, add `doc_type_id` to authoring sessions:

```python
        else:
            session["task_id"] = str(prompt_bundle.metadata["task_id"])
            session["doc_type_id"] = prompt_bundle.doc_type_id or "document"
```

Add helpers near `_read_text`:

```python
def _doc_type_id(session: dict[str, object]) -> str:
    return str(session.get("doc_type_id") or "document")


def _doc_type_title(doc_type_id: str) -> str:
    return doc_type_id.replace("-", " ").replace("_", " ").title()


def _draft_heading(doc_type_id: str) -> str:
    return f"# {_doc_type_title(doc_type_id)} Draft\n\n"


def _skill_path(doc_type_id: str) -> str:
    return f"doc-types/{doc_type_id}/SKILL.md"


def _examples_path(doc_type_id: str) -> str:
    return f"doc-types/{doc_type_id}/examples/markdown"


def _markdown_artifact_relative(doc_type_id: str) -> str:
    return f"artifacts/{doc_type_id.replace('/', '-').replace('\\\\', '-')}-draft.md"
```

- [x] **Step 4: Thread doc type through action methods**

Update `_send_message`, `_start_loop`, `_approve_outline`, `_run_checklist`, and `_export_markdown` to read:

```python
doc_type_id = _doc_type_id(session)
```

Pass `doc_type_id` into `_first_draft`, `_build_context_and_outline_events`, `_approve_outline_and_draft_events`, `_run_checklist_events`, and `_export_markdown_events`.

Update method signatures accordingly. Example:

```python
    def _build_context_and_outline_events(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        doc_type_id: str,
    ) -> list[SemanticTimelineEvent]:
```

- [x] **Step 5: Replace PRD-specific strings**

In `_first_draft`, replace the structure note with:

```python
"# Structure Notes\n\nUse a concise document structure with goals, audience, requirements, risks, and open questions when relevant.\n"
```

Replace the draft heading:

```python
_draft_heading(doc_type_id)
```

Replace the skill event:

```python
_event(task_id, session_id, "skill-1", TimelineActor.AGENT, SemanticEventKind.READ_SKILL, "Read document type skill", [_skill_path(doc_type_id)]),
```

In `_build_context_and_outline_events`, replace style/structure notes with:

```python
"# Style Notes\n\nUse concise prose, explicit bullets, and decision-ready sections.\n"
```

and:

```python
"# Structure Notes\n\nProblem, Goals, Audience, Requirements, Risks, Open Questions.\n"
```

Replace read/analyze events with:

```python
_event(task_id, session_id, "skill", TimelineActor.AGENT, SemanticEventKind.READ_SKILL, f"Read {doc_type_id} skill", [_skill_path(doc_type_id)]),
_event(task_id, session_id, "examples", TimelineActor.AGENT, SemanticEventKind.ANALYZE_EXAMPLES, f"Analyze {doc_type_id} examples", [_examples_path(doc_type_id)]),
```

In `_approve_outline_and_draft_events`, replace `"# PRD Draft\n\n"` with `_draft_heading(doc_type_id)`.

In `_run_checklist_events`, replace:

```python
result = "# Checklist Result\n\n- [x] Has draft content\n- [x] Has PRD heading\n"
```

with:

```python
result = "# Checklist Result\n\n- [x] Has draft content\n- [x] Has document heading\n"
```

Keep the `## Risks` check for now, but rename the result line to generic language:

```python
result += "- [x] Includes risks or caveats section\n"
```

and:

```python
result += "- [x] Includes risks or caveats section\n"
```

In `_export_markdown_events`, use:

```python
artifact_relative = _markdown_artifact_relative(doc_type_id)
artifact_path = workspace_root / artifact_relative
artifact_path.write_text(_read_text(workspace_root / "draft" / "draft.md"), encoding="utf-8")
return [_event(task_id, session_id, "export-md", TimelineActor.SYSTEM, SemanticEventKind.EXPORT_MARKDOWN, "Export Markdown artifact", [artifact_relative])]
```

- [x] **Step 6: Run mock adapter tests**

Run:

```powershell
python -m pytest agent/runtime-adapters/mock/tests -q
```

Expected: all mock tests pass.

---

### Task 3: API And E2E Non-PRD Coverage

**Files:**
- Modify: `apps/web/tests/core-loop.spec.ts`
- Modify: `apps/web/tests/workbench-shell.spec.ts`
- Modify: `services/api/tests/test_phase2_api.py`

- [x] **Step 1: Update generic E2E assertions**

In `apps/web/tests/core-loop.spec.ts`, replace:

```ts
await expect(page.getByText("PRD Draft")).toBeVisible({ timeout: 8_000 });
```

with:

```ts
await expect(page.getByRole("tab", { name: /draft/i })).toBeVisible({ timeout: 8_000 });
await expect(page.locator(".cm-content, .markdown-preview, .draft-preview").filter({ hasText: /Draft|Problem|Goals/i }).first()).toBeVisible({ timeout: 8_000 });
```

Replace:

```ts
await expect(page.getByText(/artifact · artifacts\/prd-draft\.md/i)).toBeVisible({ timeout: 8_000 });
```

with:

```ts
await expect(page.getByText(/artifact · artifacts\/[a-z0-9_-]+-draft\.md/i)).toBeVisible({ timeout: 8_000 });
```

Replace:

```ts
await expect(messageBox(page)).toContainText("PRD Draft");
```

with:

```ts
await expect(messageBox(page)).toContainText("Draft");
```

Keep PRD only in workspace titles if it is useful for human readability.

- [x] **Step 2: Reduce nonessential PRD labels in workbench shell**

In `apps/web/tests/workbench-shell.spec.ts`, rename generated titles:

```ts
const title = `First loop workspace ${Date.now()}`;
```

and:

```ts
await createDraftReadyWorkspace(page, `Assistant UI workspace ${Date.now()}`);
await createDraftReadyWorkspace(page, `Reload workspace ${Date.now()}`);
await createWorkspace(page, `Attachment workspace ${Date.now()}`);
```

Keep descriptions generic:

```ts
await page.getByLabel(/description/i).fill("Write a first usable document imitation loop.");
```

- [x] **Step 3: Add a backend second-doc-type loop test**

In `services/api/tests/test_phase2_api.py`, add:

```python
def test_phase2_non_prd_authoring_loop_uses_generic_doc_type_paths(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n",
        "summary": "Initial memo skill",
    })
    version = client.post("/skill-packs/memo/publish", json={"publish_note": "Memo v1"}).json()
    task = client.post("/tasks", json={
        "doc_type_id": "memo",
        "pack_version_id": version["id"],
        "brief": "Write a board memo",
    }).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    start_response = client.post(f"/sessions/{session['id']}/loop/start")
    assert start_response.status_code == 200
    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    approve_response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    )
    assert approve_response.status_code == 200

    draft = client.get(f"/tasks/{task['id']}/draft").json()["markdown"]
    assert "# Memo Draft" in draft
    assert "# PRD Draft" not in draft

    export_response = client.post(f"/sessions/{session['id']}/artifacts/export-markdown")
    assert export_response.status_code == 200
    assert export_response.json()["artifact_path"] == "artifacts/memo-draft.md"
```

- [x] **Step 4: Run focused backend and E2E tests**

Run:

```powershell
python -m pytest services/api/tests/test_phase2_api.py services/api/tests/test_authoring_pack_binding.py -q
npm run test:e2e -- tests/core-loop.spec.ts tests/workbench-shell.spec.ts
```

Expected: backend tests pass and Playwright passes.

---

### Task 4: Explicit Skill Pack Warning Acknowledgment

**Files:**
- Modify: `apps/web/src/shell/management/SkillPackManager.tsx`
- Modify: `apps/web/src/shell/state/useSkillPacks.ts`
- Add: `apps/web/src/shell/management/__tests__/SkillPackManager.test.tsx` if the directory does not exist
- Test: `apps/web/src/shell/management/__tests__/SkillPackManager.test.tsx`

- [x] **Step 1: Add a UI test for warning acknowledgment**

Create `apps/web/src/shell/management/__tests__/SkillPackManager.test.tsx` with:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import { SkillPackManager } from "../SkillPackManager";

vi.mock("../../../api", () => ({
  api: {
    listSkillPacks: vi.fn(),
    createSkillPack: vi.fn(),
    addSkillPackTextResource: vi.fn(),
    addSkillPackFileResource: vi.fn(),
    listSkillPackResources: vi.fn(),
    getSkillPackResource: vi.fn(),
    getSkillPackArtifact: vi.fn(),
    updateSkillPackArtifact: vi.fn(),
    createSkillCreatorSession: vi.fn(),
    generateSkillPack: vi.fn(),
    sendSkillCreatorMessage: vi.fn(),
    validateSkillPack: vi.fn(),
    publishSkillPack: vi.fn(),
  },
}));

function renderManager() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SkillPackManager />
    </QueryClientProvider>,
  );
}

describe("SkillPackManager warning acknowledgment", () => {
  it("requires explicit warning acknowledgment before publish", async () => {
    const user = userEvent.setup();
    vi.mocked(api.listSkillPacks).mockResolvedValue([
      { id: "memo", title: "Memo", description: "", draft_status: "draft", latest_version_id: null },
    ]);
    vi.mocked(api.listSkillPackResources).mockResolvedValue([]);
    vi.mocked(api.getSkillPackArtifact).mockResolvedValue({
      pack_id: "memo",
      path: "SKILL.md",
      content: "# Memo\n",
    });
    vi.mocked(api.validateSkillPack).mockResolvedValue({
      status: "passed",
      errors: [],
      warnings: ["SKILL.md shares 25+ consecutive words with example.txt"],
    });
    vi.mocked(api.publishSkillPack).mockResolvedValue({
      id: "memo-v001",
      pack_id: "memo",
      version: "v001",
      publish_note: "",
      manifest: {},
      validation: {},
      created_at: "2026-05-17T00:00:00Z",
    });

    renderManager();

    await screen.findByText("Memo");
    await user.click(screen.getByRole("button", { name: /validate/i }));
    const publish = await screen.findByRole("button", { name: /publish/i });

    expect(publish).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /shares 25\+ consecutive words/i }));
    expect(publish).toBeEnabled();
    await user.click(publish);

    await waitFor(() => expect(api.publishSkillPack).toHaveBeenCalledWith(
      "memo",
      "",
      ["SKILL.md shares 25+ consecutive words with example.txt"],
    ));
  });
});
```

- [x] **Step 2: Run failing UI test**

Run:

```powershell
npm run test:unit -- --run src/shell/management/__tests__/SkillPackManager.test.tsx
```

Expected: fail because there are no checkboxes and Publish is enabled.

- [x] **Step 3: Implement acknowledged warning state**

In `PackWorkSurface` in `SkillPackManager.tsx`, add state:

```tsx
const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<string[]>([]);
```

Reset acknowledgments when validation warnings change:

```tsx
useEffect(() => {
  setAcknowledgedWarnings([]);
}, [packId, validationWarnings.join("\n")]);
```

Add helper values:

```tsx
const allWarningsAcknowledged = validationWarnings.every((warning) => acknowledgedWarnings.includes(warning));
const canPublish = !publishPack.isPending && validatePack.data?.status === "passed" && allWarningsAcknowledged;
```

Replace warning rendering:

```tsx
{validationWarnings.map((warning) => (
  <label className="skill-pack-warning-ack" key={warning}>
    <input
      type="checkbox"
      checked={acknowledgedWarnings.includes(warning)}
      onChange={(event) => {
        setAcknowledgedWarnings((current) =>
          event.target.checked
            ? [...new Set([...current, warning])]
            : current.filter((item) => item !== warning),
        );
      }}
    />
    <span>{warning}</span>
  </label>
))}
```

Update Publish button:

```tsx
disabled={!canPublish}
onClick={() => publishPack.mutate({ note: publishNote, acknowledgedWarnings })}
```

- [x] **Step 4: Rename mutation variable for clarity**

In `apps/web/src/shell/state/useSkillPacks.ts`, change:

```ts
mutationFn: ({ note, warnings }: { note: string; warnings: string[] }) => {
  if (!packId) throw new Error("Select a pack before publishing");
  return api.publishSkillPack(packId, note, warnings);
},
```

to:

```ts
mutationFn: ({ note, acknowledgedWarnings }: { note: string; acknowledgedWarnings: string[] }) => {
  if (!packId) throw new Error("Select a pack before publishing");
  return api.publishSkillPack(packId, note, acknowledgedWarnings);
},
```

- [x] **Step 5: Run management UI tests**

Run:

```powershell
npm run test:unit -- --run src/shell/management/__tests__/SkillPackManager.test.tsx
npm run test:unit -- --run
```

Expected: focused test and full unit suite pass. Existing jsdom `scrollTo` warnings may remain.

---

### Task 5: Source-Copy Warning Coverage For Warning Resources

**Files:**
- Modify: `services/api/docagent_api/skill_packs.py`
- Modify: `services/api/tests/test_skill_packs.py`

- [x] **Step 1: Add failing copy-detection test**

Add to `services/api/tests/test_skill_packs.py`:

```python
def test_validate_skill_pack_checks_warning_status_resources_for_source_copy(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    state.save_skill_pack({"id": "memo", "title": "Memo", "description": "", "draft_status": "draft"})
    root = state.skill_pack_root("memo")
    markdown = root / "examples" / "markdown" / "source.md"
    markdown.parent.mkdir(parents=True, exist_ok=True)
    copied_sentence = (
        "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike "
        "november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu"
    )
    markdown.write_text(copied_sentence, encoding="utf-8")
    (root / "SKILL.md").write_text(f"# Memo\n\n{copied_sentence}\n", encoding="utf-8")
    state.save_skill_pack_resource({
        "id": "resource-1",
        "pack_id": "memo",
        "group": "examples",
        "original_filename": "source.docx",
        "source_path": "examples/original/source.docx",
        "markdown_path": "examples/markdown/source.md",
        "conversion_report_path": "examples/reports/source.conversion.json",
        "status": "warning",
        "summary": "",
        "warnings": [{"type": "format_loss", "message": "DOCX formatting was simplified.", "location": None}],
    })

    result = validate_skill_pack_draft(state, "memo")

    assert any("shares 25+ consecutive words" in warning for warning in result["warnings"])
```

- [x] **Step 2: Run failing test**

Run:

```powershell
python -m pytest services/api/tests/test_skill_packs.py::test_validate_skill_pack_checks_warning_status_resources_for_source_copy -q
```

Expected: fail because `status == "warning"` is skipped.

- [x] **Step 3: Include warning resources in the check**

In `services/api/docagent_api/skill_packs.py`, change:

```python
if resource["group"] not in {"examples", "specs"} or resource["status"] != "ready":
    continue
```

to:

```python
if resource["group"] not in {"examples", "specs"} or resource["status"] not in {"ready", "warning"}:
    continue
```

- [x] **Step 4: Run skill pack tests**

Run:

```powershell
python -m pytest services/api/tests/test_skill_packs.py -q
```

Expected: all pass.

---

### Task 6: E2E Runner State Cleanup

**Files:**
- Modify: `tools/runtime/e2e_api_server.py`
- Modify: `tests/test_dev_entrypoint.py`

- [x] **Step 1: Extend runner contract test**

In `tests/test_dev_entrypoint.py`, update `test_playwright_e2e_uses_project_managed_api_runner` by adding:

```python
    assert "TemporaryDirectory" in runner
    assert "DOCAGENT_STATE_ROOT" in runner
```

- [x] **Step 2: Run failing contract test**

Run:

```powershell
python -m pytest tests/test_dev_entrypoint.py::test_playwright_e2e_uses_project_managed_api_runner -q
```

Expected: fail until the runner uses a managed temporary directory.

- [x] **Step 3: Use a temporary directory for E2E state**

In `tools/runtime/e2e_api_server.py`, add:

```python
from tempfile import TemporaryDirectory
```

Replace:

```python
os.environ.setdefault("DOCAGENT_STATE_ROOT", str(ROOT / ".local" / "e2e" / f"docagent-{uuid4().hex[:8]}"))

with PostgresContainer("postgres:16-alpine") as postgres:
```

with:

```python
with TemporaryDirectory(prefix="docagent-e2e-") as state_root, PostgresContainer("postgres:16-alpine") as postgres:
    os.environ.setdefault("DOCAGENT_STATE_ROOT", state_root)
```

Keep the existing `uuid4` import only if another assertion or path still needs it. If not, remove `from uuid import uuid4` and remove the old `"uuid4"` assertion from `tests/test_dev_entrypoint.py`.

- [x] **Step 4: Run E2E runner and focused Playwright tests**

Run:

```powershell
python -m pytest tests/test_dev_entrypoint.py::test_playwright_e2e_uses_project_managed_api_runner -q
npm run test:e2e -- tests/workbench-shell.spec.ts --grep "attachments"
```

Expected: contract test passes and attachment E2E passes.

---

## Final Verification

- [x] **Step 1: Run full Python tests**

```powershell
python -m pytest packages/conversion/tests tools/import/tests packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests -q
```

Expected: all tests pass.

- [x] **Step 2: Run frontend unit/type/build checks**

```powershell
npm run test:unit -- --run
npm run test
npm run build
```

Expected: all pass. The existing Vite large chunk warning is acceptable unless this work changes bundle shape substantially.

- [x] **Step 3: Run Playwright E2E**

```powershell
npm run test:e2e -- tests/core-loop.spec.ts tests/workbench-shell.spec.ts
```

Expected: all selected E2E tests pass.

- [x] **Step 4: Run diff hygiene**

```powershell
git diff --check -- . ':!.claude/settings.local.json'
```

Expected: no whitespace errors. CRLF warnings may appear on Windows and are acceptable.

---

## Rollback Notes

- If dynamic Markdown export breaks real runtime behavior, revert Task 1 only and keep Task 2 tests skipped until the prompt/response contract is reworked.
- If generic mock output causes too much E2E churn, keep PRD-specific text only in PRD-focused tests and add a separate non-PRD API test before touching Playwright again.
- If warning acknowledgment UI creates noisy tests, keep the backend gate intact and land a smaller UI checkbox test first.
- If `TemporaryDirectory` cleanup conflicts with Playwright server lifetime, keep `.local/e2e` but add cleanup of only directories older than one day in a later task.

## Self-Review

- Spec coverage: all confirmed findings map to tasks. Task 1 covers real-runtime export hardcoding. Task 2 covers mock PRD lock. Task 3 covers E2E PRD overfitting. Task 4 covers warning auto-ack. Task 5 covers warning-resource copy detection. Task 6 covers E2E state cleanup.
- Placeholder scan: no `TBD`, `TODO`, or vague “write tests” placeholders remain; every task includes specific files, code snippets, and commands.
- Type consistency: frontend publish variables use `acknowledgedWarnings` internally and `acknowledged_warnings` only at the API boundary. Python export helpers use `dict[str, Any]`, already imported in `sessions.py`.

