# Runtime Adapters

Runtime-specific notes and adapter expectations.

The product should not couple directly to one agent runtime. OpenHands is the first candidate, but the adapter boundary should allow replacement.

Formal operations:

- create session
- send ACP prompt
- stream ACP updates
- cancel
- get state

## Phase 3 Runtime Selection

`services/api` selects runtime adapters through `DOCAGENT_RUNTIME`.

- `mock-acp`: deterministic local and CI adapter.
- `openhands-acp`: OpenHands Agent Server / SDK adapter.

`mock` and `openhands` may be accepted as temporary runtime-name aliases by
factory code, but docs, plans, and new automation should use the ACP names.

Runtime-specific payloads must stay inside their adapter package or ACP shim.
The product backend consumes ACP updates, optional projection metadata, raw audit
references, and stable session states.

## ACP Boundary

Adapters implement `send_prompt(session_id, prompt, metadata)` and return
`acp_updates`. Product actions such as start loop, approve outline,
revise selection, run checklist, and export are prompts with metadata; they are
not new adapter methods.

Runtime-specific implementation details may exist inside an adapter, but they
must be normalized into ACP updates before leaving the adapter package. Do not
build new product behavior on private runtime methods.

