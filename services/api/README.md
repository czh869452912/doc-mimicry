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
.\start-dev.cmd
```

The local development stack is Docker Compose based. It starts Postgres, Redis,
the FastAPI API, the Celery worker, and the web app. Use:

```powershell
docker compose logs -f api worker
```

to inspect backend logs.

## Runtime Configuration

Default:

```powershell
$env:DOCAGENT_RUNTIME = "mock"
```

OpenHands opt-in:

```powershell
.\start-dev.cmd -Runtime openhands
```

When running API or worker directly on the host, use `OPENHANDS_BASE_URL=http://127.0.0.1:8001`.
When running through Docker Compose, the containers must reach the host server through
`OPENHANDS_CONTAINER_BASE_URL=http://host.docker.internal:8001`; `start-dev.cmd` sets this
default for the compose stack. The API and worker image uses Python 3.12 because the OpenHands
SDK packages require Python 3.12 or newer.

Normal CI and local development should keep `mock` unless OpenHands Agent Server is configured and running.
