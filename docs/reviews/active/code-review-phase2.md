# Code Review — Phase 2 Authoring Loop

**Date:** 2026-05-06
**Scope:** Full 3-phase implementation (Phase 0 foundation → Phase 1 interactive skeleton → Phase 2 authoring loop)
**Commits reviewed:** `480fe67` → `be19e97`
**Reviewer:** superpowers:code-reviewer subagent

---

## Summary

The implementation substantially follows the 3-phase plan. Architecture boundaries are respected: no Pydantic in contracts, file-backed state under `.local/docagent`, the adapter boundary is clean, and all WorkbenchPage controls call real API methods. The test suite covers all planned adapter methods and API endpoints.

Two critical issues must be fixed before Phase 3 planning begins. Five important issues should be resolved in the first Phase 3 cleanup pass before new feature work starts.

---

## Confirmed Correct

- **WorkbenchPage controls** — Every interactive control calls a real API method. No non-functional or placeholder buttons exist. `ManagementPage` third column is correctly marked as intentionally passive (out of scope for Phase 2).
- **`revise_selection` logic** — Selected text is replaced, instruction appears in replacement, checkpoint is created before write, event kinds match test expectations.
- **Workspace endpoint** — `GET /tasks/{task_id}/workspace` correctly uses `list_workspace_files` from `docagent_api.workspace_files`.

---

## Critical Issues

These must be fixed before Phase 3 planning. Any Phase 3 logic built on these contracts will be incorrect.

### C1 — `SessionRecord` status Literal does not include Phase 2 states

**File:** `services/api/docagent_api/models.py:17`

The `SessionRecord` TypedDict declares:

```python
status: Literal["idle", "running", "paused", "completed", "failed"]
```

But `app.py` writes two Phase 2 states that are absent from this Literal:

```python
session["status"] = "await_outline_approval"   # app.py line ~188
session["status"] = "draft_ready"              # app.py line ~204
```

Python does not enforce TypedDict Literals at runtime so there is no immediate crash, but any Phase 3 code that pattern-matches on `session["status"]` will silently miss these states.

**Fix:** Add `"await_outline_approval"` and `"draft_ready"` to the Literal.

---

### C2 — `revise_selection` endpoint produces unhandled 500 on missing draft

**File:** `services/api/docagent_api/app.py` — `revise_selection` endpoint

`adapter.revise_selection` calls `checkpoint_draft` as its first action. `checkpoint_draft` raises `FileNotFoundError` if `draft/draft.md` does not exist. The endpoint has no `try/except` around the adapter call. A client that calls `POST /sessions/{id}/revision/selection` before the draft has been generated (i.e. before `outline/approve`) receives an unhandled 500 instead of a meaningful 4xx response.

All tests follow the correct sequence, so this path is invisible in the test suite.

**Fix:** Wrap the adapter call in `try/except FileNotFoundError` and raise `HTTPException(status_code=400, detail="Draft does not exist. Approve the outline first.")`.

---

## Important Issues

These should be resolved in the first Phase 3 cleanup pass before new feature work begins.

### I1 — Hardcoded timestamps throughout `app.py` and `adapter.py`

**Files:** `services/api/docagent_api/app.py`, `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`

At least four locations in `app.py` and all `_event` calls in `adapter.py` use `"2026-04-30T00:00:00Z"`. `checkpoint.py` defaults to `"1970-01-01T00:00:00Z"`. Timeline ordering, audit logs, and session filtering will be broken if all records share the same timestamp.

`tools/import/convert_to_markdown.py` already shows the correct pattern:

```python
def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

**Fix:** Apply `_now()` (or an equivalent utility) to all `created_at`/`updated_at` assignment sites in `app.py`, `adapter.py`, and `checkpoint.py`.

---

### I2 — `revise_selection` is a silent no-op when `selected_text` is not in the draft

**File:** `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py:175`

```python
draft_path.write_text(current.replace(selected_text, replacement, 1), encoding="utf-8")
```

If `selected_text` is not found, `str.replace` with `count=1` returns the original string unchanged. The file is re-written with its own content, a checkpoint is still created, and two events are still emitted. The operation silently "succeeds" with no effect. The test suite does not cover this case.

**Fix:** Check the replacement count and raise `ValueError` in the adapter (converted to `HTTPException(422)` at the endpoint) when the text is not found.

---

### I3 — Event IDs are not unique across repeated calls in the same session

**File:** `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`

`_event` produces IDs like `"{session_id}-skill"`, `"{session_id}-outline"`, etc. If `build_context_and_outline` is called twice in the same session, both calls emit the same event IDs. `DocAgentState.append_timeline_event` does no deduplication. The timeline JSON will contain duplicate `id` values.

**Fix:** Add a unique suffix (short UUID or monotonic counter) to the event ID suffix in `_event`.

---

### I4 — `httpx` and `pytest` missing from `pyproject.toml`

**File:** `pyproject.toml`

`fastapi.testclient.TestClient` requires `httpx`. The CI workflow explicitly installs it, but `pyproject.toml` only declares `fastapi` and `uvicorn`. A developer following the project dependencies will not get `httpx` or `pytest` and will see `ImportError` from the test suite.

**Fix:** Add an `[project.optional-dependencies]` dev group:

```toml
[project.optional-dependencies]
dev = ["pytest", "httpx"]
```

---

### I5 — `_revise` hardcodes `"versions/v001.md"` in checkpoint event path

**File:** `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py:86-88`

The Phase 1 `send_message → _revise` path hardcodes the checkpoint path in the emitted event:

```python
_event(..., SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint", ["versions/v001.md"]),
```

The Phase 2 `revise_selection` method correctly captures `checkpoint = checkpoint_draft(...)` and uses `checkpoint.version_path`. But `_revise` ignores the returned `DraftVersion` entirely. If called on a workspace with existing checkpoints, the event path will be wrong.

**Fix:** Capture the return value of `checkpoint_draft` in `_revise` and use `checkpoint.version_path` in the event.

---

## Minor Issues

These are acceptable for Phase 2 but should be noted for Phase 3.

| ID | Issue | File |
|----|-------|------|
| M1 | Sub-dataclasses of `WorkspaceLayout` (`InputPaths`, `ContextPaths`, `DraftPaths`, `ReviewPaths`, `LogPaths`) not exported from `contracts/__init__.py` | `packages/contracts/docagent_contracts/__init__.py` |
| M2 | `import_text_input` silently overwrites files on duplicate filename; resource `id` always collides on same stem | `services/api/docagent_api/imports.py` |
| M3 | `checkpoint_draft` defaults `created_at` to `"1970-01-01T00:00:00Z"` — callers never supply a real time, so all checkpoints share the epoch | `packages/workspace/docagent_workspace/checkpoint.py` |
| M4 | Draft preview in WorkbenchPage renders as raw line-by-line `<p>` elements — Markdown headings and bullets lose all formatting | `apps/web/src/pages/WorkbenchPage.tsx` |
| M5 | File-backed state uses read-modify-write with no file lock — unsafe under multiple uvicorn workers | `services/api/docagent_api/state.py` |
| M6 | Default `brief` textarea value is a hardcoded placeholder string rather than empty; users may accidentally create tasks with it | `apps/web/src/pages/WorkbenchPage.tsx` |

---

## Overall Assessment

**Ready as a Phase 2 baseline once C1 and C2 are fixed.**

The implementation correctly builds the controlled authoring loop, respects all architecture boundaries from the plan, and the API-first design is sound. C1 (Literal type mismatch) and C2 (unguarded 500) are the only issues that will actively cause Phase 3 work to be built on incorrect foundations. All other issues are isolated and straightforward to fix.

**Recommended action before Phase 3 planning:**
1. Fix C1 and C2 immediately.
2. Fix I1–I5 in a dedicated cleanup commit before any new Phase 3 feature work.
3. Note M1–M6 in the Phase 3 plan as known debt items.
