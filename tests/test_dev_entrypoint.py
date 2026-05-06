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

    assert "%*" in start_cmd
    assert "endlocal & exit /b %exitCode%" in start_cmd
    assert "agent\\runtime-adapters\\openhands" in dev_script
    assert "DOCAGENT_RUNTIME" in dev_script
    assert "OPENHANDS_BASE_URL" in dev_script
    assert "docagent-openhands" in dev_script
    assert "openhands.agent_server" in dev_script
    assert "Import-LocalEnv" in dev_script
    assert "LLM_API_KEY" in dev_script
    assert "LLM_MODEL" in dev_script
    assert "LLM_BASE_URL" in dev_script
    assert "--reload" not in dev_script
