# Runtime Streaming Design

## Purpose

Workbench chat timeline updates must reflect model output and agent runtime events while an operation is still running. The current backend waits for each runtime adapter call to finish, persists all events at the end, and only then lets the frontend observe them. This makes timeline updates appear in delayed bursts.

This design adds an incremental streaming path without removing the existing synchronous runtime adapter contract.

## Goals

- Persist runtime events as they arrive so the existing timeline polling UI can render near-real-time progress.
- Keep existing synchronous adapters and tests compatible.
- Make the OpenHands adapter stream events even though its current SDK call blocks during `conversation.run()`.
- Prevent concurrent timeline/session writes from dropping events.
- Keep the first implementation focused on workbench operations, especially chat messages.

## Non-Goals

- No WebSocket or Server-Sent Events transport in this change. The frontend can continue polling the timeline endpoint.
- No token-level rendering guarantee. The first target is runtime event-level streaming.
- No redesign of the agent event schema.

## Architecture

The runtime contract gains an optional streaming capability. Existing methods still return `RuntimeOperationResult`; streaming-capable adapters additionally accept an event sink/callback that receives raw runtime events as they appear.

The API layer gains a background operation runner for workbench requests. A workbench request records the user/action event immediately, marks the session as running, starts the runtime call in a background thread, and returns without waiting for completion. The background runner appends mapped timeline events on each streamed raw event, then applies final changed paths and session state transitions when the operation finishes.

Adapters that do not implement streaming run through a compatibility wrapper: the background runner calls the synchronous method and appends its result at completion. This preserves current behavior while allowing streaming adapters to improve latency.

## OpenHands Adapter

OpenHands currently sends a message, runs `conversation.run()` synchronously, then reads `conversation.state.events`. The streaming bridge will:

1. Capture the event count before sending a message.
2. Send the message.
3. Run `conversation.run()` in a worker thread.
4. Poll `conversation.state.events` while the worker is alive.
5. Yield each newly observed event through the runtime event sink.
6. Yield any remaining events after completion and propagate runtime errors.

This is a pragmatic bridge around the blocking SDK interface and keeps the adapter boundary explicit.

## Backend State Safety

Streaming introduces overlapping reads and writes: frontend polling can read timeline files while the background runner appends events. `DocAgentState` should serialize session/timeline mutations with an internal lock so append operations cannot overwrite each other.

## Frontend Behavior

The frontend will call the workbench operation endpoints in background mode and keep using the existing timeline polling hook. Because events are persisted incrementally, the UI updates during the run. Workspace/draft refresh can remain completion-oriented for this change; timeline freshness is the primary target.

## Error Handling

- Operation start records an explicit running state before the runtime call begins.
- Streamed malformed raw events are preserved when possible and skipped only if they cannot be mapped safely.
- Runtime failures append a failure timeline event and move the session out of running state.
- Compatibility sync adapters retain their existing result/error behavior.

## Testing

- Contract/unit tests for streaming callback compatibility and sync fallback.
- API tests with a fake streaming adapter that emits multiple events with delays; verify timeline endpoint observes partial events before operation completion.
- API tests for concurrent appends to avoid event loss.
- OpenHands adapter unit tests using a fake conversation object with blocking `run()` and mutable `state.events`.
- Frontend tests verifying send-message returns immediately and timeline polling keeps updating from the backend.

