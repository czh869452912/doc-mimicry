# Runtime Adapters

Runtime-specific notes and adapter expectations.

The product should not couple directly to one agent runtime. OpenHands is the first candidate, but the adapter boundary should allow replacement.

Expected operations:

- create session
- send message
- stream events
- pause
- resume
- cancel
- approve action
- reject action
- get state

## Phase 3 Runtime Selection

`services/api` selects runtime adapters through `DOCAGENT_RUNTIME`.

- `mock`: deterministic local and CI adapter.
- `openhands`: OpenHands Agent Server / SDK adapter.

Runtime-specific payloads must stay inside their adapter package. The product backend consumes `RuntimeOperationResult`, semantic timeline events, raw event references, and stable session states.

