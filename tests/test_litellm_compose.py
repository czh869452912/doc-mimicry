from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_compose_defines_litellm_gateway_and_openhands_uses_aliases() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert "litellm" in services
    assert services["litellm"]["ports"] == ["4000:4000"]
    assert services["litellm"]["volumes"][0]["source"] == "./config/litellm.yaml"

    openhands_env = services["openhands"]["environment"]
    assert openhands_env["LLM_BASE_URL"] == "${LLM_BASE_URL:-http://litellm:4000}"
    assert openhands_env["LLM_MODEL"] == "${LLM_MODEL:-docagent/default}"


def test_litellm_config_declares_docagent_model_aliases() -> None:
    config = yaml.safe_load((ROOT / "config" / "litellm.yaml").read_text(encoding="utf-8"))
    aliases = {entry["model_name"] for entry in config["model_list"]}

    assert {"docagent/default", "docagent/fast", "docagent/reasoning"}.issubset(aliases)
