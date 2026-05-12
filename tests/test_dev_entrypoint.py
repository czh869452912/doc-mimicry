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
    dockerfile = (ROOT / "services" / "api" / "Dockerfile").read_text(encoding="utf-8")
    nginx_conf = (ROOT / "apps" / "web" / "nginx.conf").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "%*" in start_cmd
    assert "endlocal & exit /b %exitCode%" in start_cmd
    assert "requirements-openhands.txt" in dev_script
    assert "DOCAGENT_RUNTIME" in dev_script
    assert "OPENHANDS_BASE_URL" in dev_script
    assert "OpenHandsContainerBaseUrl" in dev_script
    assert "host.docker.internal" in dev_script
    assert "docagent-openhands" in dev_script
    assert "openhands.agent_server" in dev_script
    assert "Start-Process" in dev_script
    assert "openhands.err.log" in dev_script
    assert "Start-Job -Name \"docagent-openhands\"" not in dev_script
    assert "Import-LocalEnv" in dev_script
    assert "LLM_API_KEY" in dev_script
    assert "LLM_MODEL" in dev_script
    assert "LLM_BASE_URL" in dev_script
    assert "--reload" not in dev_script

    assert compose_override.count("DOCAGENT_RUNTIME") >= 2
    assert compose_override.count("OPENHANDS_BASE_URL") >= 2
    assert compose_override.count("LLM_API_KEY") >= 2
    assert compose_override.count("LLM_MODEL") >= 2
    assert compose_override.count("LLM_BASE_URL") >= 2

    assert "FROM python:3.12-slim" in dockerfile
    assert 'pip install --no-cache-dir -e ".[openhands]"' in dockerfile
    assert "openhands = [" in pyproject
    assert "openhands-sdk==1.20.1" in pyproject
    assert "opentelemetry-instrumentation==0.60b1" in pyproject
    assert "opentelemetry-sdk==1.39.1" in pyproject

    assert "resolver 127.0.0.11" in nginx_conf
    assert "set $api_upstream api:8000" in nginx_conf
    assert "location ~ ^/api/(.+)$" in nginx_conf
    assert "rewrite ^/api/(.+)$ /$1 break" in nginx_conf
    assert "proxy_pass http://$api_upstream" in nginx_conf


def test_compose_override_interpolates_repo_root() -> None:
    compose_override = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")

    assert "DOCAGENT_REPO_ROOT: ${DOCAGENT_REPO_ROOT:-/app}" in compose_override
    assert "DOCAGENT_REPO_ROOT: /app" not in compose_override


def test_local_development_documents_runtime_env_contract() -> None:
    dev_docs = (ROOT / "docs" / "quality" / "local-development.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "docker-compose.override.yml" in dev_docs
    assert "base compose" in dev_docs
    assert "OPENHANDS_CONTAINER_BASE_URL" in dev_docs
    assert "OPENHANDS_CONTAINER_BASE_URL" in env_example
    assert "DOCAGENT_RUNTIME" in env_example


def test_compose_merged_config_passes_runtime_env_to_api_and_worker() -> None:
    env = os.environ.copy()
    env.update(
        {
            "DOCAGENT_RUNTIME": "openhands",
            "OPENHANDS_CONTAINER_BASE_URL": "http://host.docker.internal:8001",
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
    assert config.count("DOCAGENT_RUNTIME: openhands") >= 2
    assert config.count("OPENHANDS_BASE_URL: http://host.docker.internal:8001") >= 2
    assert config.count("LLM_API_KEY: dummy-key") >= 2
    assert config.count("LLM_MODEL: dummy-model") >= 2
    assert config.count("LLM_BASE_URL: http://llm.example") >= 2
