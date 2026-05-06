# Local Development

## One-Click Startup

The supported local development entrypoint on Windows is:

```powershell
.\start-dev.cmd
```

`start-dev.cmd` delegates to `scripts/dev.ps1`.

## Script Contract

The startup script must:

- start the FastAPI service from `services/api`;
- start the Vite web app from `apps/web`;
- start the OpenHands Agent Server when `-Runtime openhands` is selected and no server is already available;
- keep API state, logs, and local runtime artifacts under `.local/`;
- write startup logs under `.local/dev`;
- install frontend dependencies with `npm ci` when `apps/web/node_modules` is missing;
- install API runtime dependencies into `.local/dev/.venv`;
- set `PYTHONPATH` so API code can import shared packages, the mock runtime adapter, and the OpenHands runtime adapter;
- run FastAPI without `--reload` so stopping the wrapper job does not leave a reloader child process on port 8000;
- use `http://127.0.0.1:8000` for the API and `http://127.0.0.1:5173` for the web app;
- keep existing package-level run commands usable for CI and debugging.

The script must not:

- write generated files outside `.local/`, `apps/web/node_modules/`, or ignored build/cache folders;
- replace package-specific test or build commands;
- hide API or web logs from developers;
- require Docker or a production database for the Phase 1 local loop.

## Manual Fallback

To start with the OpenHands adapter selected:

```powershell
.\start-dev.cmd -Runtime openhands
```

The script reads `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, and optional `OPENHANDS_BASE_URL` from the shell or `.env.local`. If `OPENHANDS_BASE_URL` is omitted, the script starts OpenHands Agent Server on `http://127.0.0.1:8001`.

If the startup script fails, run the services separately:

```powershell
uvicorn docagent_api.app:app --reload --app-dir services/api
```

```powershell
cd apps/web
npm ci
npm run dev
```
