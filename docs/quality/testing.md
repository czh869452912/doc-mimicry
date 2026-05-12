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

## Phase 0 Foundation

Run foundation tests with:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests -q
```

These tests cover contract models, workspace creation, workspace validation, checkpoints, Markdown import stubs, and semantic timeline mapping.

GitHub Actions runs Python on 3.12 and installs the repository with the `dev`
extra before running package, API, mock runtime, and OpenHands adapter tests.

## Phase 1 Interactive Skeleton

Run backend and runtime tests:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests -q
```

Run frontend checks:

```powershell
cd apps/web
npm install
npm run build
```

GitHub Actions runs the Python test command and a separate web build job.

## Phase 2 Authoring Loop

Run backend/runtime tests:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

Run frontend build:

```powershell
cd apps/web
npm run build
```

Manual demo path:

1. `.\start-dev.cmd`
2. create a PRD task
3. add text input
4. start loop
5. approve outline
6. revise selected draft passage
7. run checklist
8. export Markdown artifact

## Phase 3 Runtime Adapter

Run runtime adapter tests:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/timeline/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests -q
```

OpenHands smoke is opt-in:

```powershell
$env:DOCAGENT_RUNTIME = "openhands"
$env:OPENHANDS_BASE_URL = "http://127.0.0.1:8001"
$env:DATABASE_URL = "postgresql+psycopg2://docagent:docagent@localhost:5432/docagent"
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/runtime/openhands_smoke.py
```

Docker Compose smoke is mock-safe:

```powershell
python tools/runtime/compose_smoke.py --runtime mock
```
