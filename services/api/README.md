# API Service

FastAPI product backend.

Owns:

- Task and session lifecycle.
- Document type configuration.
- Resource upload and import conversion orchestration.
- Workspace initialization.
- Runtime adapter integration.
- Versions, artifacts, audit records.
- ACP event storage and semantic projection enrichment.

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

The backend exposes ACP session events through `/sessions/{session_id}/events`
and `/sessions/{session_id}/events/stream`. Runtime adapters accept prompts plus
metadata and return ACP updates. Document actions are represented as ACP prompts
or commands with product metadata, not as product-facing runtime methods.

For external ACP clients, the API also exposes a thin JSON-RPC WebSocket gateway
at `/sessions/{session_id}/acp/ws`. It supports the minimal client loop:
`initialize`, `session/new`, `session/prompt`, and `session/cancel`, and streams
persisted DocAgent ACP events back as `session/update` notifications.

Default:

```powershell
$env:DOCAGENT_RUNTIME = "mock-acp"
```

OpenHands opt-in:

```powershell
.\start-dev.cmd -Runtime openhands-acp
```

Canonical runtime names are `mock-acp` and `openhands-acp`; `mock` and
`openhands` remain temporary aliases during migration.

When running API or worker directly on the host, use `DOCAGENT_ACP_RUNTIME_URL=http://127.0.0.1:8001`.
When running through Docker Compose, `start-dev.cmd -Runtime openhands-acp` starts the `openhands`
service with the shared workspace volume and sets container traffic to
`DOCAGENT_ACP_CONTAINER_RUNTIME_URL=http://openhands:8001`. The API and worker image uses Python 3.12
because the OpenHands SDK packages require Python 3.12 or newer.

Normal CI and local development should keep `mock-acp` unless OpenHands Agent Server is configured and running.

OpenHands runs through LiteLLM Proxy by default in Docker Compose:

```powershell
$env:LLM_BASE_URL = "http://litellm:4000"
$env:LLM_MODEL = "docagent/default"
$env:LLM_API_KEY = "sk-docagent-local"
```

Configure provider-backed LiteLLM aliases in `config/litellm.yaml` using `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `DOCAGENT_LITELLM_*_MODEL`, and provider-specific
`DOCAGENT_LITELLM_*_API_KEY` variables. Runtime
configuration should target LiteLLM aliases; direct provider endpoints are not
the supported product contract.

## Smoke Tests

The OpenHands smoke script is an adapter/full-chain smoke, not a unit test. It
uses `DOCAGENT_RUNTIME=openhands-acp`, `DOCAGENT_ACP_RUNTIME_URL`, and live LLM settings:

```powershell
$env:DOCAGENT_RUNTIME = "openhands-acp"
$env:DOCAGENT_ACP_RUNTIME_URL = "http://127.0.0.1:8001"
$env:DATABASE_URL = "postgresql+psycopg2://docagent:docagent@localhost:5432/docagent"
python tools/runtime/openhands_smoke.py
```

For Docker Compose routing and container health without a real runtime, use:

```powershell
python tools/runtime/compose_smoke.py --runtime mock-acp
```

The compose smoke checks the ACP event endpoint, which is the supported
authoring timeline contract.

Check Docker Compose wiring, including LiteLLM, with:

```powershell
docker compose config
python -m pytest tests/test_litellm_compose.py -q
```

Check Alembic migration drift recovery with:

```powershell
python -m pytest services/api/tests/test_acp_events_migration.py -q
```
