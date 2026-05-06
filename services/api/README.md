# API Service

FastAPI product backend.

Owns:

- Task and session lifecycle.
- Document type configuration.
- Resource upload and import conversion orchestration.
- Workspace initialization.
- Runtime adapter integration.
- Versions, artifacts, audit records.
- Semantic timeline enrichment.

Does not own:

- Fixed document writing workflows.
- Agent drafting decisions.
- Best-practice semantic retrieval as the default writing path.

## Format Boundary

The API should expose converted Markdown resources to the agent runtime. Original binary files are retained for audit and re-conversion, but should not be the normal agent input.

## Phase 1 Local Run

```powershell
uvicorn docagent_api.app:app --reload --app-dir services/api
```

## Runtime Configuration

Default:

```powershell
$env:DOCAGENT_RUNTIME = "mock"
```

OpenHands opt-in:

```powershell
$env:DOCAGENT_RUNTIME = "openhands"
$env:OPENHANDS_BASE_URL = "http://127.0.0.1:8001"
```

Normal CI and local development should keep `mock` unless OpenHands Agent Server is installed and running.
