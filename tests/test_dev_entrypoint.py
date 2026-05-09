from pathlib import Path


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
    assert "rewrite ^/api/(.*)$ /$1 break" in nginx_conf
    assert "proxy_pass http://$api_upstream" in nginx_conf
