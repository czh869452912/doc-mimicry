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
- start the OpenHands Agent Server when `-Runtime openhands` is selected and no server is already available;
- keep API state, logs, and local runtime artifacts under `.local/`;
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

## Manual Fallback

To start with the OpenHands adapter selected:

```powershell
.\start-dev.cmd -Runtime openhands
```

The script reads `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, and optional `OPENHANDS_BASE_URL` from the shell or `.env.local`. If `OPENHANDS_BASE_URL` is omitted, the script starts OpenHands Agent Server on `http://127.0.0.1:8001`.

If the startup script fails, run the services separately:

```powershell
docker compose up -d --build postgres redis api worker web
```

```powershell
docker compose logs -f api worker web
```
