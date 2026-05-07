# Runtime Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workbench timeline events appear while runtime operations are still running by streaming adapter events into persisted session timelines.

**Architecture:** Add an optional callback-based streaming capability beside the existing synchronous `RuntimeAdapter` methods. The API starts selected workbench operations in a background runner, persists user/action events immediately, appends streamed raw and semantic events as they arrive, and falls back to the current synchronous result path for adapters without streaming support.

**Tech Stack:** Python dataclasses/protocols, FastAPI, file-backed `DocAgentState`, OpenHands SDK adapter bridge, React/Vitest timeline polling.

---

## File Map

- Modify `packages/contracts/docagent_contracts/runtime.py`: define `RuntimeEventSink` and `StreamingRuntimeAdapter` protocol.
- Modify `packages/contracts/docagent_contracts/__init__.py`: export the new streaming types.
- Modify `packages/contracts/tests/test_runtime_contracts.py`: cover event sink typing and streaming protocol shape.
- Modify `services/api/docagent_api/state.py`: serialize state mutations with a reentrant lock.
- Modify `services/api/docagent_api/app.py`: accept an injectable adapter for tests and add background streaming operation runner.
- Modify `services/api/tests/test_state.py`: prove concurrent timeline appends keep all events.
- Modify `services/api/tests/test_api.py`: cover background message acceptance and partial timeline visibility.
- Modify `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`: add `send_message_stream` polling bridge.
- Modify `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`: implement streaming send/start/approve/revise/checklist/export operations.
- Modify `agent/runtime-adapters/openhands/tests/test_openhands_client.py`: test stream bridge against a fake blocking conversation.
- Modify `agent/runtime-adapters/openhands/tests/test_openhands_adapter.py`: test adapter emits raw events through sink.
- Modify `apps/web/src/api.ts`: let workbench calls request background mode.
- Modify `apps/web/src/shell/panes/ConversationPane.tsx`: stop waiting for workspace/timeline refresh before showing message accepted.
- Modify `apps/web/src/shell/__tests__/AppShell.test.tsx`: assert send-message flow remains responsive.

---

### Task 1: State Locking

**Files:**
- Modify: `services/api/docagent_api/state.py`
- Test: `services/api/tests/test_state.py`

- [ ] **Step 1: Write the failing concurrent append test**

Add this test to `services/api/tests/test_state.py`:

```python
from concurrent.futures import ThreadPoolExecutor


def test_state_keeps_all_concurrent_timeline_appends(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)

    def append_event(index: int) -> None:
        state.append_timeline_event(
            "session-001",
            {
                "id": f"event-{index:03d}",
                "session_id": "session-001",
                "kind": "update_draft",
                "summary": f"Event {index}",
            },
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append_event, range(40)))

    events = state.list_timeline_events("session-001")
    assert len(events) == 40
    assert {event["id"] for event in events} == {f"event-{index:03d}" for index in range(40)}
```

- [ ] **Step 2: Run the focused state test and verify it fails**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_state.py::test_state_keeps_all_concurrent_timeline_appends -q
```

Expected: FAIL with fewer than 40 events or a JSON read/write race.

- [ ] **Step 3: Add an internal reentrant lock**

In `services/api/docagent_api/state.py`, import `RLock` and initialize it:

```python
from threading import RLock
```

```python
class DocAgentState:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = RLock()
        self.root.mkdir(parents=True, exist_ok=True)
```

Wrap all public methods that read or mutate persisted state with `with self._lock:`. Keep private helpers lock-free so nested calls remain readable:

```python
    def append_timeline_event(self, session_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            events = self.list_timeline_events(session_id)
            events.append(event)
            self._timeline_path(session_id).write_text(
                json.dumps(events, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
```

Apply the same pattern to `list_tasks`, `get_task`, `save_task`, `list_sessions`, `get_session`, `save_session`, `list_timeline_events`, `append_raw_runtime_event`, `list_raw_runtime_events`, and `workspace_root`.

- [ ] **Step 4: Run state tests**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_state.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/api/docagent_api/state.py services/api/tests/test_state.py
git commit -m "Make DocAgent state writes thread safe"
```

---

### Task 2: Streaming Runtime Contract

**Files:**
- Modify: `packages/contracts/docagent_contracts/runtime.py`
- Modify: `packages/contracts/docagent_contracts/__init__.py`
- Test: `packages/contracts/tests/test_runtime_contracts.py`

- [ ] **Step 1: Write the failing contract test**

Add this test to `packages/contracts/tests/test_runtime_contracts.py`:

```python
from docagent_contracts import RuntimeEventSink, StreamingRuntimeAdapter


def test_runtime_event_sink_receives_raw_event() -> None:
    received: list[RawRuntimeEvent] = []

    def sink(event: RawRuntimeEvent) -> None:
        received.append(event)

    event = RawRuntimeEvent(
        id="raw-2",
        session_id="session-1",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="openhands-1",
        kind="message",
        payload={"content": "hello"},
        created_at=utc_now(),
    )

    typed_sink: RuntimeEventSink = sink
    typed_sink(event)

    assert received == [event]
```

- [ ] **Step 2: Run the focused contract test and verify it fails**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest packages/contracts/tests/test_runtime_contracts.py::test_runtime_event_sink_receives_raw_event -q
```

Expected: FAIL because `RuntimeEventSink` is not exported.

- [ ] **Step 3: Add streaming protocol types**

In `packages/contracts/docagent_contracts/runtime.py`, import `Callable` and add:

```python
RuntimeEventSink = Callable[[RawRuntimeEvent], None]


class StreamingRuntimeAdapter(RuntimeAdapter, Protocol):
    def send_message_stream(self, session_id: str, message: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        ...

    def start_loop_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        ...

    def approve_outline_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        ...

    def revise_selection_stream(
        self,
        session_id: str,
        selection: str,
        instruction: str,
        sink: RuntimeEventSink,
    ) -> RuntimeOperationResult:
        ...

    def run_checklist_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        ...

    def export_markdown_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        ...
```

In `packages/contracts/docagent_contracts/__init__.py`, import and add `RuntimeEventSink` and `StreamingRuntimeAdapter` to `__all__`.

- [ ] **Step 4: Run contract tests**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest packages/contracts/tests/test_runtime_contracts.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add packages/contracts/docagent_contracts/runtime.py packages/contracts/docagent_contracts/__init__.py packages/contracts/tests/test_runtime_contracts.py
git commit -m "Add streaming runtime adapter contract"
```

---

### Task 3: API Background Runner

**Files:**
- Modify: `services/api/docagent_api/app.py`
- Test: `services/api/tests/test_api.py`

- [ ] **Step 1: Add fake streaming adapter test**

Add these imports to `services/api/tests/test_api.py`:

```python
from threading import Event
import time
from typing import Any

from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeEventSink,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
)
```

Add this fake adapter and helper:

```python
class StreamingFakeAdapter:
    def __init__(self) -> None:
        self.first_event_sent = Event()
        self.finish = Event()

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_message(self, session_id: str, message: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def send_message_stream(
        self,
        session_id: str,
        message: str,
        sink: RuntimeEventSink,
    ) -> RuntimeOperationResult:
        sink(_raw(session_id, "stream-1", {"kind": "file_written", "path": "draft/partial.md"}))
        self.first_event_sent.set()
        assert self.finish.wait(timeout=2)
        sink(_raw(session_id, "stream-2", {"kind": "file_written", "path": "draft/final.md"}))
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def start_loop(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)

    def approve_outline(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def revise_selection(self, session_id: str, selection: str, instruction: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def run_checklist(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def export_markdown(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.COMPLETED)

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return RuntimeSessionState.IDLE


def _raw(session_id: str, raw_id: str, payload: dict[str, Any]) -> RawRuntimeEvent:
    return RawRuntimeEvent(
        id=raw_id,
        session_id=session_id,
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="runtime-001",
        kind=str(payload.get("kind", "event")),
        payload=payload,
        created_at="2026-05-07T00:00:00Z",
    )
```

Add this test:

```python
def test_background_message_streams_partial_timeline_before_completion(tmp_path: Path) -> None:
    adapter = StreamingFakeAdapter()
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_adapter=adapter))

    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build billing controls"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/messages?background=true",
        json={"message": "Start the PRD"},
    )

    assert response.status_code == 202
    assert response.json()["accepted"] is True
    assert adapter.first_event_sent.wait(timeout=2)

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    kinds = [event["kind"] for event in timeline]
    assert "user_message" in kinds
    assert "update_draft" in kinds
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "running_revision"

    adapter.finish.set()
    deadline = time.time() + 2
    while time.time() < deadline:
        if client.get(f"/sessions/{session['id']}").json()["status"] == "draft_ready":
            break
        time.sleep(0.05)

    assert client.get(f"/sessions/{session['id']}").json()["status"] == "draft_ready"
```

- [ ] **Step 2: Run the focused API test and verify it fails**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_api.py::test_background_message_streams_partial_timeline_before_completion -q
```

Expected: FAIL because `create_app` does not accept `runtime_adapter` and background mode does not exist.

- [ ] **Step 3: Add adapter injection**

In `services/api/docagent_api/app.py`, change `create_app` signature:

```python
def create_app(
    state_root: Path | None = None,
    repo_root: Path | None = None,
    runtime_name: str | None = None,
    runtime_adapter: Any | None = None,
) -> FastAPI:
```

Set adapter with:

```python
    adapter = runtime_adapter or create_runtime_adapter(runtime_name)
```

- [ ] **Step 4: Add background operation helpers**

In `services/api/docagent_api/app.py`, import `Thread`:

```python
from threading import Thread
```

Add helpers near `_run_runtime_operation`:

```python
def _start_background_runtime_operation(
    state: DocAgentState,
    task_id: str,
    session: dict[str, Any],
    running_state: RuntimeSessionState,
    operation: Any,
    previous_state_on_failure: RuntimeSessionState | None = None,
) -> dict[str, Any]:
    previous_state = previous_state_on_failure or RuntimeSessionState(session["status"])
    _prepare_transition(state, session, running_state)

    def worker() -> None:
        try:
            result = operation()
        except Exception as exc:
            failure = _manual_event(
                task_id,
                session["id"],
                f"runtime-failed-{uuid4().hex[:8]}",
                TimelineActor.SYSTEM,
                SemanticEventKind.USER_MESSAGE,
                f"Runtime operation failed: {exc}",
                [],
            )
            state.append_timeline_event(session["id"], asdict(failure))
            _set_session_state(state, session, previous_state)
            return
        _append_runtime_result(state, task_id, session["id"], result)
        _set_session_state(state, session, result.next_state)

    Thread(target=worker, daemon=True).start()
    return {"session_id": session["id"], "accepted": True, "status": running_state.value}
```

Add raw event sink helper:

```python
def _runtime_event_sink(state: DocAgentState, task_id: str, session_id: str) -> Any:
    def sink(raw_event: Any) -> None:
        state.append_raw_runtime_event(session_id, raw_event)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            semantic = map_openhands_raw_event(raw_event, task_id)
            if semantic is not None:
                state.append_timeline_event(session_id, asdict(semantic))

    return sink
```

Adjust `_append_runtime_result` to avoid double-appending streamed raw events by allowing empty `raw_events` from streaming methods. Do not add de-duplication yet.

- [ ] **Step 5: Wire background send-message endpoint**

Change endpoint signature:

```python
    @app.post("/sessions/{session_id}/messages", status_code=200)
    def send_message(
        session_id: str,
        request: SendMessageRequest,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
```

Before invoking runtime, append the user message immediately:

```python
        user_event = _manual_event(
            task["id"], session_id, f"user-{uuid4().hex[:8]}",
            TimelineActor.USER, SemanticEventKind.USER_MESSAGE,
            request.message, [],
        )
        state.append_timeline_event(session_id, asdict(user_event))
```

When `background` is true, return background response and set status code 202 with a `Response` parameter:

```python
        if background:
            stream_method = getattr(adapter, "send_message_stream", None)
            if callable(stream_method):
                operation = lambda: stream_method(
                    session_id,
                    request.message,
                    _runtime_event_sink(state, task["id"], session_id),
                )
            else:
                operation = lambda: adapter.send_message(session_id, request.message)
            response.status_code = 202
            return _start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_REVISION,
                operation,
            )
```

For the synchronous branch, keep the existing behavior but remove the old `if not result.events` manual user event block because the user event is now appended before the runtime operation.

- [ ] **Step 6: Run focused API test**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_api.py::test_background_message_streams_partial_timeline_before_completion -q
```

Expected: PASS.

- [ ] **Step 7: Run API test suite**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_api.py services/api/tests/test_state.py -q
```

Expected: PASS. If `test_task_session_message_timeline_and_draft_roundtrip` now has one extra user event in sync mode, update its expected `event_count` and timeline order only after confirming the new immediate user event is intentional.

- [ ] **Step 8: Commit**

```powershell
git add services/api/docagent_api/app.py services/api/tests/test_api.py
git commit -m "Stream background message events into timelines"
```

---

### Task 4: OpenHands Streaming Bridge

**Files:**
- Modify: `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`
- Modify: `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`
- Test: `agent/runtime-adapters/openhands/tests/test_openhands_client.py`
- Test: `agent/runtime-adapters/openhands/tests/test_openhands_adapter.py`

- [ ] **Step 1: Write OpenHands client stream test**

Add this test to `agent/runtime-adapters/openhands/tests/test_openhands_client.py`:

```python
from threading import Event
import time


def test_openhands_client_streams_events_while_run_blocks() -> None:
    class State:
        def __init__(self) -> None:
            self.events: list[object] = []

    class Conversation:
        def __init__(self) -> None:
            self.state = State()
            self.started = Event()
            self.finish = Event()

        def send_message(self, message: str) -> None:
            self.state.events.append({"kind": "user", "content": message})

        def run(self) -> None:
            self.state.events.append({"kind": "agent", "content": "partial"})
            self.started.set()
            assert self.finish.wait(timeout=2)
            self.state.events.append({"kind": "file_written", "path": "draft/final.md"})

    client = OpenHandsAgentServerClient(base_url="http://example.test")
    conversation = Conversation()
    client._conversations["runtime-001"] = conversation

    stream = client.send_message_stream("runtime-001", "hello", poll_interval_seconds=0.01)
    first = next(stream)
    assert first["kind"] == "user"

    assert conversation.started.wait(timeout=2)
    second = next(stream)
    assert second["kind"] == "agent"

    conversation.finish.set()
    remaining = list(stream)
    assert remaining[-1]["path"] == "draft/final.md"
```

- [ ] **Step 2: Run the focused client test and verify it fails**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest agent/runtime-adapters/openhands/tests/test_openhands_client.py::test_openhands_client_streams_events_while_run_blocks -q
```

Expected: FAIL because `send_message_stream` does not exist.

- [ ] **Step 3: Implement client stream bridge**

In `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`, import `Thread` and `time`:

```python
from threading import Thread
import time
```

Add to `OpenHandsClient` protocol:

```python
    def send_message_stream(self, runtime_session_id: str, message: str) -> Any:
        ...
```

Add to `OpenHandsAgentServerClient`:

```python
    def send_message_stream(
        self,
        runtime_session_id: str,
        message: str,
        poll_interval_seconds: float = 0.1,
    ) -> Any:
        conversation = self._conversation(runtime_session_id)
        before_count = len(getattr(conversation.state, "events", []))
        error: list[BaseException] = []

        conversation.send_message(message)

        def run() -> None:
            try:
                conversation.run()
            except BaseException as exc:
                error.append(exc)

        worker = Thread(target=run, daemon=True)
        worker.start()
        next_index = before_count
        while worker.is_alive():
            events = getattr(conversation.state, "events", [])
            while next_index < len(events):
                yield _event_to_payload(events[next_index])
                next_index += 1
            time.sleep(poll_interval_seconds)

        worker.join()
        events = getattr(conversation.state, "events", [])
        while next_index < len(events):
            yield _event_to_payload(events[next_index])
            next_index += 1
        if error:
            raise error[0]
```

- [ ] **Step 4: Write adapter stream test**

Add to `FakeOpenHandsClient` in `agent/runtime-adapters/openhands/tests/test_openhands_adapter.py`:

```python
    def send_message_stream(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        self.messages.append(message)
        yield {"kind": "file_written", "path": "draft/streamed.md"}
```

Add test:

```python
def test_openhands_adapter_streams_raw_events_to_sink(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())
    adapter.create_session("session-001", _prompt_bundle(tmp_path))
    streamed = []

    result = adapter.send_message_stream("session-001", "Revise", streamed.append)

    assert result.next_state == RuntimeSessionState.DRAFT_READY
    assert result.raw_events == []
    assert streamed[0].payload["path"] == "draft/streamed.md"
    assert result.changed_paths == ["draft/streamed.md"]
```

- [ ] **Step 5: Implement adapter stream methods**

In `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`, import `RuntimeEventSink` and add a shared helper:

```python
    def _stream_result(
        self,
        session_id: str,
        next_state: RuntimeSessionState,
        raw_payloads: Any,
        sink: RuntimeEventSink,
    ) -> RuntimeOperationResult:
        runtime_session_id = self._runtime_session_id(session_id)
        changed_paths: list[str] = []
        for payload in raw_payloads:
            raw_event = self._raw_event(
                session_id,
                runtime_session_id,
                payload.get("kind", payload.get("type", "event")),
                payload,
            )
            if "path" in raw_event.payload:
                changed_paths.append(str(raw_event.payload["path"]))
            sink(raw_event)
        self._states[session_id] = next_state
        return RuntimeOperationResult(session_id=session_id, next_state=next_state, changed_paths=changed_paths)
```

Add `send_message_stream`, `start_loop_stream`, `approve_outline_stream`, `revise_selection_stream`, `run_checklist_stream`, and `export_markdown_stream`. Each should call `self.client.send_message_stream(...)` with the same prompt text used by the synchronous method, then pass the iterable to `_stream_result`.

- [ ] **Step 6: Run OpenHands tests**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest agent/runtime-adapters/openhands/tests -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py agent/runtime-adapters/openhands/tests/test_openhands_client.py agent/runtime-adapters/openhands/tests/test_openhands_adapter.py
git commit -m "Stream OpenHands runtime events"
```

---

### Task 5: Frontend Background Message Flow

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
- Test: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Update frontend API response type**

In `apps/web/src/api.ts`, change `sendMessage`:

```ts
  sendMessage: (sessionId: string, message: string) =>
    request<{ accepted?: boolean; event_count?: number; status?: string }>(
      `/sessions/${sessionId}/messages?background=true`,
      {
        method: "POST",
        body: JSON.stringify({ message }),
      },
    ),
```

- [ ] **Step 2: Make conversation submission responsive**

In `apps/web/src/shell/panes/ConversationPane.tsx`, after `await api.sendMessage(session.id, input);`, remove immediate `await refreshWorkspace();` and keep `await refreshTimeline();` so the user message appears quickly. Set status to `"Working..."` if the response is accepted:

```ts
        const result = await api.sendMessage(session.id, input);
        await refreshTimeline();
        if (result.accepted) {
          setStatus("Working...");
          return;
        }
        await refreshWorkspace();
```

Keep slash command behavior unchanged for this task.

- [ ] **Step 3: Update or add frontend test**

In `apps/web/src/shell/__tests__/AppShell.test.tsx`, update the mocked `sendMessage` to resolve with `{ accepted: true, status: "running_revision" }` where needed. Add an assertion that a submitted message calls `api.getTimeline` after `sendMessage` without requiring a workspace refresh first.

- [ ] **Step 4: Run focused frontend tests**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useTimeline.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/api.ts apps/web/src/shell/panes/ConversationPane.tsx apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "Use background message streaming in workbench"
```

---

### Task 6: Extend Background Mode to Other Runtime Operations

**Files:**
- Modify: `services/api/docagent_api/app.py`
- Modify: `apps/web/src/api.ts`
- Test: `services/api/tests/test_api.py`

- [ ] **Step 1: Add helper for stream method fallback**

In `services/api/docagent_api/app.py`, add:

```python
def _stream_or_sync(adapter: Any, stream_name: str, sync_operation: Any, stream_operation: Any) -> Any:
    stream_method = getattr(adapter, stream_name, None)
    if callable(stream_method):
        return stream_operation(stream_method)
    return sync_operation
```

- [ ] **Step 2: Add `background` query support to start/checklist/export**

For `start_loop`, `run_checklist`, and `export_markdown`, add `background: bool = Query(default=False)` and `response: Response`. If background is true, use `_start_background_runtime_operation` with the corresponding stream method name and sink. Return 202 accepted. Keep sync behavior unchanged when `background=false`.

- [ ] **Step 3: Add `background` query support to approve/revise**

For `approve_outline` and `revise_selection`, keep their pre-runtime file/selection validation synchronous. After validation and transition preparation, use background runner when requested. On background failure, restore the same previous state each endpoint currently restores.

- [ ] **Step 4: Update frontend API runtime calls**

In `apps/web/src/api.ts`, append `?background=true` to `startLoop`, `approveOutline`, `reviseSelection`, `runChecklist`, and `exportMarkdown`. Keep response type as `LoopActionResult` if compatible, or widen it to include `{ accepted?: boolean; status?: string }`.

- [ ] **Step 5: Run API and frontend smoke tests**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_api.py -q
cd apps\web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/api/docagent_api/app.py services/api/tests/test_api.py apps/web/src/api.ts
git commit -m "Enable background runtime operations"
```

---

### Task 7: Full Verification

**Files:**
- No code changes expected unless verification reveals a defect.

- [ ] **Step 1: Run backend test suite**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests packages/contracts/tests agent/runtime-adapters/openhands/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend unit tests**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/__tests__/WorkspacePane.test.tsx src/shell/__tests__/useTimeline.test.tsx src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd apps\web
npm run build
```

Expected: PASS.

- [ ] **Step 4: Run end-to-end smoke tests**

Run:

```powershell
cd apps\web
npm run test:e2e
```

Expected: PASS.

- [ ] **Step 5: Review git status**

Run:

```powershell
git status --short
```

Expected: only intended tracked changes are present; `.claude/` may remain untracked and should not be committed.

