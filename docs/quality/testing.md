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

GitHub Actions runs the same command in `.github/workflows/ci.yml` on push to `main` and pull requests.

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
