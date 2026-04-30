# Testing Strategy

Testing will be added as implementation begins.

## Phase 0 Priorities

- Workspace initialization creates required directories.
- Workspace validation detects missing required context files.
- Timeline mapper converts raw file/tool events to semantic events.
- Checkpoint script saves current draft versions safely.
- Export script fails clearly when inputs are missing.
- GitHub Actions currently checks required repository structure and docs.
- GitHub Actions should run foundation tests once Phase 0 test modules exist.

## Test Shape

- Unit tests for packages and tools.
- Contract tests for API schemas.
- Integration tests for workspace happy path.
- Manual agent-loop smoke tests until runtime integration stabilizes.
