# Runtime Adapters

Runtime-specific notes and adapter expectations.

The product should not couple directly to one agent runtime. OpenHands is the first candidate, but the adapter boundary should allow replacement.

Expected operations:

- create session
- send ACP prompt
- stream ACP updates
- cancel
- get state

## Phase 3 Runtime Selection

`services/api` selects runtime adapters through `DOCAGENT_RUNTIME`.

- `mock`: deterministic local and CI adapter.
- `openhands`: OpenHands Agent Server / SDK adapter.

Runtime-specific payloads must stay inside their adapter package. The product
backend consumes `RuntimeOperationResult`, ACP updates, optional semantic
projections, raw event references, and stable session states.

## ACP Boundary

New adapters should implement `send_prompt(session_id, prompt, metadata)` and
return `acp_updates`. Product actions such as start loop, approve outline,
revise selection, run checklist, and export are prompts with metadata; they are
not new adapter methods.

The old operation-specific methods and streaming variants are compatibility
fallbacks for legacy adapters. Do not build new behavior on them unless a
temporary migration wrapper is unavoidable.

