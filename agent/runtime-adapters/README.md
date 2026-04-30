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

