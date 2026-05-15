# Local Development

## One-Click Startup

The supported local development entrypoint on Windows is:

```powershell
.\start-dev.cmd
```

`start-dev.cmd` delegates to `scripts/dev.ps1`.

## Script Contract

The startup script must:

- start the Docker Compose local stack;
- start Postgres and Redis;
- start the FastAPI service;
- start the Celery worker;
- start the Vite web app;
- start the OpenHands Agent Server as a Compose service when `-Runtime openhands-acp` is selected;
- optionally prepare and start the external `acp-ui` client when `-ExternalAcpUi` is selected;
- keep API state and local runtime artifacts under Docker volumes or `.local/`;
- write startup logs under `.local/dev`;
- build the API and web Docker images when needed;
- set runtime environment variables for the API and worker containers;
- use Postgres for product state and Redis/Celery for background jobs;
- use `http://127.0.0.1:8000` for the API and `http://127.0.0.1:5173` for the web app;
- keep existing package-level run commands usable for CI and debugging.

The script must not:

- write generated files outside `.local/`, Docker volumes, `apps/web/node_modules/`, or ignored build/cache folders;
- replace package-specific test or build commands;
- hide API or web logs from developers;
- require a manually installed local Python virtualenv.

## Compose Runtime Environment Contract

The base compose file keeps the default stack mock-safe: `docker-compose.yml`
defines the database, queue, API, worker, and web services without selecting a
real agent runtime.

Runtime-specific environment is supplied by `docker-compose.override.yml` and
the startup script. The override passes `DOCAGENT_RUNTIME`, `LLM_API_KEY`,
`LLM_MODEL`, `LLM_BASE_URL`, and container-safe `DOCAGENT_ACP_RUNTIME_URL` to
both the API and worker. The startup script sets
`DOCAGENT_ACP_CONTAINER_RUNTIME_URL=http://openhands:8001` in OpenHands ACP
mode, which points at the Compose `openhands` service. That service mounts the
same `/workspace` volume as the API and worker, so runtime file operations see
the same task workspace.

The script reads `.env` first and `.env.local` second. Existing shell variables
win over both files, and `.env.local` only fills values that were not already
set by the shell or `.env`.

The web Docker image receives `VITE_API_BASE` and optional `VITE_ACP_UI_URL` as
build args. `-ExternalAcpUi` sets `VITE_ACP_UI_URL=http://127.0.0.1:4173/`,
prepares `.local/reference/acp-ui`, and starts the upstream ACP client before
building the web service.

Use `DOCAGENT_ACP_RUNTIME_URL=http://127.0.0.1:8001` for host-side smoke tests.
Use `DOCAGENT_ACP_CONTAINER_RUNTIME_URL=http://openhands:8001` for Compose
services. When `DOCAGENT_RUNTIME=mock-acp`, the startup script clears host and
container ACP runtime URLs from the process environment before invoking Compose.
`OPENHANDS_BASE_URL` remains a temporary compatibility fallback for the current
OpenHands SDK client only.

## Manual Fallback

To start with the OpenHands adapter selected:

```powershell
.\start-dev.cmd -Runtime openhands-acp
```

The script reads `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, and optional ACP
runtime URLs from the shell, `.env`, or `.env.local`. If
`DOCAGENT_ACP_RUNTIME_URL` is omitted, the Compose OpenHands service is still
exposed on `http://127.0.0.1:8001` for host checks.

If the startup script fails, run the services separately:

```powershell
docker compose --profile openhands up -d --build postgres redis openhands api worker web
```

```powershell
docker compose logs -f openhands api worker web
```

## Local Smoke Checks

After changing compose, Dockerfiles, nginx proxying, or runtime environment
plumbing, run the mock compose smoke:

```powershell
python tools/runtime/compose_smoke.py --runtime mock-acp
```

The OpenHands smoke is opt-in because it needs a reachable Agent Server and LLM
credentials:

```powershell
$env:DOCAGENT_RUNTIME = "openhands-acp"
$env:DOCAGENT_ACP_RUNTIME_URL = "http://127.0.0.1:8001"
$env:DATABASE_URL = "postgresql+psycopg2://docagent:docagent@localhost:5432/docagent"
python tools/runtime/openhands_smoke.py
```
