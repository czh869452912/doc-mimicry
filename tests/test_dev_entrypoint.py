from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_one_click_dev_entrypoint_files_exist() -> None:
    assert (ROOT / "start-dev.cmd").is_file()
    assert (ROOT / "scripts" / "dev.ps1").is_file()


def test_one_click_dev_entrypoint_is_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dev_docs = (ROOT / "docs" / "quality" / "local-development.md").read_text(encoding="utf-8")

    assert "start-dev.cmd" in readme
    assert "scripts/dev.ps1" in dev_docs
    assert ".local/dev" in dev_docs


def test_dev_entrypoint_supports_openhands_runtime() -> None:
    start_cmd = (ROOT / "start-dev.cmd").read_text(encoding="utf-8")
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    compose_override = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "services" / "api" / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "services" / "api" / "docker-entrypoint.sh").read_text(encoding="utf-8")
    nginx_conf = (ROOT / "apps" / "web" / "nginx.conf").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "%*" in start_cmd
    assert "endlocal & exit /b %exitCode%" in start_cmd
    assert "requirements-openhands.txt" not in dev_script
    assert "DOCAGENT_RUNTIME" in dev_script
    assert "DOCAGENT_ACP_RUNTIME_URL" in dev_script
    assert "VITE_ACP_UI_URL" in dev_script
    assert 'Import-LocalEnv (Join-Path $repoRoot ".env")' in dev_script
    assert 'Import-LocalEnv (Join-Path $repoRoot ".env.local")' in dev_script
    assert "AcpContainerRuntimeUrl" in dev_script
    assert "docker compose --profile openhands up -d --build postgres redis openhands api worker web" in dev_script
    assert "http://openhands:$openHandsContainerPort" in dev_script
    assert "openhands.agent_server" in compose
    assert "VITE_ACP_UI_URL: ${VITE_ACP_UI_URL:-}" in compose
    assert 'DOCAGENT_RUN_MIGRATIONS: "1"' in compose
    assert 'DOCAGENT_RUN_MIGRATIONS: "0"' in compose
    assert "Ensure-OpenHandsVenv" not in dev_script
    assert "Start-Process -FilePath $venvPython" not in dev_script
    assert "Start-Job -Name \"docagent-openhands\"" not in dev_script
    assert "Import-LocalEnv" in dev_script
    assert "LLM_API_KEY" in dev_script
    assert "LLM_MODEL" in dev_script
    assert "LLM_BASE_URL" in dev_script
    assert "--reload" not in dev_script

    assert compose_override.count("DOCAGENT_RUNTIME") >= 2
    assert compose_override.count("DOCAGENT_ACP_RUNTIME_URL") >= 2
    assert compose_override.count("LLM_API_KEY") >= 2
    assert compose_override.count("LLM_MODEL") >= 2
    assert compose_override.count("LLM_BASE_URL") >= 2

    assert "FROM python:3.12-slim" in dockerfile
    assert 'pip install --no-cache-dir -e ".[openhands]"' in dockerfile
    assert "cp services/api/docker-entrypoint.sh /usr/local/bin/docagent-api-entrypoint" in dockerfile
    assert "sed -i 's/\\r$//' /usr/local/bin/docagent-api-entrypoint" in dockerfile
    assert 'ENTRYPOINT ["sh", "/usr/local/bin/docagent-api-entrypoint"]' in dockerfile
    assert 'if [ "${DOCAGENT_RUN_MIGRATIONS:-1}" = "1" ]; then' in entrypoint
    assert "openhands = [" in pyproject
    assert "openhands-sdk==1.20.1" in pyproject
    assert "opentelemetry-instrumentation==0.60b1" in pyproject
    assert "opentelemetry-sdk==1.39.1" in pyproject

    assert "resolver 127.0.0.11" in nginx_conf
    assert "set $api_upstream api:8000" in nginx_conf
    assert "location ~ ^/api/(.+)$" in nginx_conf
    assert "rewrite ^/api/(.+)$ /$1 break" in nginx_conf
    assert "proxy_pass http://$api_upstream" in nginx_conf
    assert "proxy_set_header Upgrade $http_upgrade" in nginx_conf
    assert 'proxy_set_header Connection "upgrade"' in nginx_conf


def test_dev_entrypoint_can_prepare_external_acp_ui_for_compose_web() -> None:
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "apps" / "web" / "Dockerfile").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dev_docs = (ROOT / "docs" / "quality" / "local-development.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "[switch]$ExternalAcpUi" in dev_script
    assert "[int]$AcpUiPort = 4173" in dev_script
    assert "Start-ExternalAcpUiIfNeeded" in dev_script
    assert "tools\\acp_ui\\prepare_acp_ui.ps1" in dev_script
    assert "npm run dev:web -- --host 127.0.0.1 --port $AcpUiPort" in dev_script
    assert "VITE_ACP_UI_URL: ${VITE_ACP_UI_URL:-}" in compose
    assert "ARG VITE_ACP_UI_URL=" in dockerfile
    assert "ENV VITE_ACP_UI_URL=$VITE_ACP_UI_URL" in dockerfile
    assert "VITE_ACP_UI_URL=" in env_example
    assert "-ExternalAcpUi" in readme
    assert "-ExternalAcpUi" in dev_docs


def test_external_acp_ui_can_be_enabled_from_env_file() -> None:
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "EXTERNAL_ACP_UI=false" in env_example
    assert "ACP_UI_PORT=4173" in env_example
    assert "$envExternalAcpUi = $env:EXTERNAL_ACP_UI" in dev_script
    assert "$envAcpUiPort = $env:ACP_UI_PORT" in dev_script
    assert "EXTERNAL_ACP_UI must be one of" in dev_script
    assert "$ExternalAcpUi = $true" in dev_script
    assert "EXTERNAL_ACP_UI=true" in readme


def test_compose_defines_openhands_service_with_shared_workspace() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    override = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")

    assert "openhands:" in compose
    assert "entrypoint: []" in compose
    assert "python -m openhands.agent_server --host 0.0.0.0 --port 8001" in compose
    assert "target: /workspace" in compose
    assert "DOCAGENT_ACP_RUNTIME_URL: ${DOCAGENT_ACP_CONTAINER_RUNTIME_URL:-}" in override


def test_openhands_host_port_can_avoid_windows_excluded_ranges() -> None:
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "[int]$OpenHandsPort = 18001" in dev_script
    assert '$env:OPENHANDS_HOST_PORT = "$OpenHandsPort"' in dev_script
    assert "http://openhands:$openHandsContainerPort" in dev_script
    assert '"${OPENHANDS_HOST_PORT:-18001}:8001"' in compose
    assert "OPENHANDS_HOST_PORT=18001" in env_example
    assert "DOCAGENT_ACP_RUNTIME_URL=http://127.0.0.1:18001" in env_example
    assert "DOCAGENT_ACP_CONTAINER_RUNTIME_URL=http://openhands:8001" in env_example


def test_api_host_port_can_avoid_windows_excluded_ranges() -> None:
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "[int]$ApiPort = 18000" in dev_script
    assert '$env:API_HOST_PORT = "$ApiPort"' in dev_script
    assert '"${API_HOST_PORT:-18000}:8000"' in compose
    assert "API_HOST_PORT=18000" in env_example
    assert "VITE_API_BASE=http://localhost:18000" in env_example
    assert "http://127.0.0.1:$ApiPort/health" in dev_script


def test_compose_worker_uses_single_process_for_nonresumable_openhands_client() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    override = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")

    assert "--pool=solo" in compose
    assert "--concurrency=1" in compose
    assert "--pool=solo" in override
    assert "--concurrency=1" in override


def test_openhands_direct_openai_compatible_model_requires_provider_prefix() -> None:
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dev_docs = (ROOT / "docs" / "quality" / "local-development.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "Assert-OpenHandsLlmModel" in dev_script
    assert "OpenAI-compatible LLM_BASE_URL values require an LLM_MODEL with a LiteLLM provider prefix" in dev_script
    assert "openai/kimi-k2-0905-preview" in readme
    assert "openai/kimi-k2-0905-preview" in dev_docs
    assert "openai/kimi-k2-0905-preview" in env_example
    assert "Provider NOT provided" in dev_docs


def test_runtime_services_share_single_api_image_build() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert compose.count("dockerfile: services/api/Dockerfile") == 1
    assert compose.count("image: docagent-api") == 3


def test_compose_override_interpolates_repo_root() -> None:
    compose_override = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")

    assert "DOCAGENT_REPO_ROOT: ${DOCAGENT_REPO_ROOT:-/app}" in compose_override
    assert "DOCAGENT_REPO_ROOT: /app" not in compose_override


def test_local_development_documents_runtime_env_contract() -> None:
    dev_docs = (ROOT / "docs" / "quality" / "local-development.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "docker-compose.override.yml" in dev_docs
    assert "base compose" in dev_docs
    assert ".env" in dev_docs
    assert ".env.local" in dev_docs
    assert "http://openhands:8001" in dev_docs
    assert "DOCAGENT_ACP_CONTAINER_RUNTIME_URL" in dev_docs
    assert "DOCAGENT_ACP_CONTAINER_RUNTIME_URL" in env_example
    assert "DOCAGENT_RUNTIME" in env_example


def test_runtime_env_contract_uses_acp_runtime_names() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    override = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")

    assert "DOCAGENT_RUNTIME=mock-acp" in env_example
    assert "DOCAGENT_ACP_RUNTIME_URL=http://127.0.0.1:18001" in env_example
    assert "DOCAGENT_ACP_CONTAINER_RUNTIME_URL=http://openhands:8001" in env_example
    assert "OPENHANDS_CONTAINER_BASE_URL" not in env_example
    assert "DOCAGENT_ACP_RUNTIME_URL" in override


def test_dev_script_reloads_runtime_from_env_files_after_import() -> None:
    dev_script = (ROOT / "scripts" / "dev.ps1").read_text(encoding="utf-8")

    assert '$Runtime = $env:DOCAGENT_RUNTIME' in dev_script
    assert '$AcpRuntimeUrl = $env:DOCAGENT_ACP_RUNTIME_URL' in dev_script
    assert '$AcpContainerRuntimeUrl = $env:DOCAGENT_ACP_CONTAINER_RUNTIME_URL' in dev_script
    assert dev_script.index('Import-LocalEnv (Join-Path $repoRoot ".env.local")') < dev_script.index(
        '$Runtime = $env:DOCAGENT_RUNTIME'
    )


def test_compose_merged_config_passes_runtime_env_to_api_and_worker() -> None:
    env = os.environ.copy()
    env.update(
        {
            "DOCAGENT_RUNTIME": "openhands-acp",
            "DOCAGENT_ACP_CONTAINER_RUNTIME_URL": "http://openhands:8001",
            "LLM_API_KEY": "dummy-key",
            "LLM_MODEL": "dummy-model",
            "LLM_BASE_URL": "http://llm.example",
        }
    )

    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    config = result.stdout
    for service in ("api:", "worker:"):
        assert service in config
    assert "openhands:" in config
    assert config.count("DOCAGENT_RUNTIME: openhands-acp") >= 2
    assert config.count("DOCAGENT_ACP_RUNTIME_URL: http://openhands:8001") >= 2
    assert config.count("LLM_API_KEY: dummy-key") >= 2
    assert config.count("LLM_MODEL: dummy-model") >= 2
    assert config.count("LLM_BASE_URL: http://llm.example") >= 2
    assert "target: /workspace" in config


def test_compose_smoke_uses_openhands_profile_for_openhands_runtime() -> None:
    smoke = (ROOT / "tools" / "runtime" / "compose_smoke.py").read_text(encoding="utf-8")

    assert '"--profile", "openhands"' in smoke
    assert '"openhands-acp"' in smoke
    assert "DOCAGENT_ACP_CONTAINER_RUNTIME_URL" in smoke
    assert '"http://127.0.0.1:18000"' in smoke


def test_compose_smoke_checks_acp_events_not_legacy_timeline() -> None:
    smoke = (ROOT / "tools" / "runtime" / "compose_smoke.py").read_text(encoding="utf-8")

    assert "/api/sessions/{session['id']}/events" in smoke
    assert "/api/sessions/{session['id']}/timeline" not in smoke


def test_openhands_smoke_accepts_doc_type_argument() -> None:
    smoke = (ROOT / "tools" / "runtime" / "openhands_smoke.py").read_text(encoding="utf-8")

    assert "--doc-type" in smoke
    assert "doc_type_id" in smoke


def test_playwright_e2e_uses_project_managed_api_runner() -> None:
    playwright_config = (ROOT / "apps" / "web" / "playwright.config.ts").read_text(encoding="utf-8")
    runner = (ROOT / "tools" / "runtime" / "e2e_api_server.py").read_text(encoding="utf-8")

    assert ".local\\dev\\.venv" not in playwright_config
    assert ".local/dev/.venv" not in playwright_config
    assert "tools\\\\runtime\\\\e2e_api_server.py" in playwright_config
    assert "PostgresContainer" in runner
    assert "DATABASE_URL" in runner
    assert "DOCAGENT_QUEUE" in runner
    assert "TemporaryDirectory" in runner
    assert "DOCAGENT_STATE_ROOT" in runner
