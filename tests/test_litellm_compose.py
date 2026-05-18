from __future__ import annotations

import os
import subprocess
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
    assert openhands_env["LLM_MODEL"] == "${LLM_MODEL:-openai/docagent/default}"


def test_litellm_config_declares_docagent_model_aliases() -> None:
    config = yaml.safe_load((ROOT / "config" / "litellm.yaml").read_text(encoding="utf-8"))
    aliases = {entry["model_name"] for entry in config["model_list"]}

    assert {"docagent/default", "docagent/fast", "docagent/reasoning", "docagent/deepseek"}.issubset(aliases)


def test_litellm_reasoning_alias_has_provider_specific_api_key() -> None:
    config = yaml.safe_load((ROOT / "config" / "litellm.yaml").read_text(encoding="utf-8"))
    aliases = {entry["model_name"]: entry["litellm_params"] for entry in config["model_list"]}

    assert aliases["docagent/default"]["api_key"] == "os.environ/OPENAI_API_KEY"
    assert aliases["docagent/fast"]["api_key"] == "os.environ/OPENAI_API_KEY"
    assert aliases["docagent/reasoning"]["api_key"] == "os.environ/DOCAGENT_LITELLM_REASONING_API_KEY"


def test_litellm_aliases_can_target_openai_compatible_api_base() -> None:
    config = yaml.safe_load((ROOT / "config" / "litellm.yaml").read_text(encoding="utf-8"))
    aliases = {entry["model_name"]: entry["litellm_params"] for entry in config["model_list"]}

    assert aliases["docagent/default"]["api_base"] == "os.environ/DOCAGENT_LITELLM_DEFAULT_API_BASE"
    assert aliases["docagent/fast"]["api_base"] == "os.environ/DOCAGENT_LITELLM_FAST_API_BASE"
    assert aliases["docagent/reasoning"]["api_base"] == "os.environ/DOCAGENT_LITELLM_REASONING_API_BASE"


def test_litellm_deepseek_alias_disables_thinking_mode_for_tool_loops() -> None:
    config = yaml.safe_load((ROOT / "config" / "litellm.yaml").read_text(encoding="utf-8"))
    aliases = {entry["model_name"]: entry["litellm_params"] for entry in config["model_list"]}

    assert "extra_body" not in aliases["docagent/default"]
    assert "extra_body" not in aliases["docagent/fast"]
    assert "extra_body" not in aliases["docagent/reasoning"]
    assert aliases["docagent/deepseek"]["model"] == "os.environ/DOCAGENT_LITELLM_DEEPSEEK_MODEL"
    assert aliases["docagent/deepseek"]["api_key"] == "os.environ/OPENAI_API_KEY"
    assert aliases["docagent/deepseek"]["api_base"] == "os.environ/DOCAGENT_LITELLM_DEEPSEEK_API_BASE"
    assert aliases["docagent/deepseek"]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_litellm_config_uses_litellm_environment_reference_syntax() -> None:
    config_text = (ROOT / "config" / "litellm.yaml").read_text(encoding="utf-8")
    config = yaml.safe_load(config_text)
    aliases = {entry["model_name"]: entry["litellm_params"] for entry in config["model_list"]}

    assert "${" not in config_text
    assert ":-" not in config_text
    assert aliases["docagent/default"]["model"] == "os.environ/DOCAGENT_LITELLM_DEFAULT_MODEL"
    assert aliases["docagent/fast"]["model"] == "os.environ/DOCAGENT_LITELLM_FAST_MODEL"
    assert aliases["docagent/reasoning"]["model"] == "os.environ/DOCAGENT_LITELLM_REASONING_MODEL"
    assert config["general_settings"]["master_key"] == "os.environ/LITELLM_MASTER_KEY"


def test_compose_passes_litellm_env_overrides_to_gateway() -> None:
    env = os.environ.copy()
    env.update(
        {
            "OPENAI_API_KEY": "dummy-provider-key",
            "DOCAGENT_LITELLM_DEFAULT_MODEL": "openai/deepseek-test-default",
            "DOCAGENT_LITELLM_FAST_MODEL": "openai/deepseek-test-fast",
            "DOCAGENT_LITELLM_REASONING_MODEL": "openai/deepseek-test-reasoning",
            "DOCAGENT_LITELLM_DEEPSEEK_MODEL": "openai/deepseek-test-tool-loop",
            "DOCAGENT_LITELLM_DEFAULT_API_BASE": "https://api.deepseek.example/v1",
            "DOCAGENT_LITELLM_FAST_API_BASE": "https://api.deepseek.example/v1",
            "DOCAGENT_LITELLM_REASONING_API_BASE": "https://api.deepseek.example/v1",
            "DOCAGENT_LITELLM_DEEPSEEK_API_BASE": "https://api.deepseek.example/v1",
            "DOCAGENT_LITELLM_REASONING_API_KEY": "dummy-reasoning-key",
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
    config = yaml.safe_load(result.stdout)
    litellm_env = config["services"]["litellm"]["environment"]

    assert litellm_env["DOCAGENT_LITELLM_DEFAULT_MODEL"] == "openai/deepseek-test-default"
    assert litellm_env["DOCAGENT_LITELLM_FAST_MODEL"] == "openai/deepseek-test-fast"
    assert litellm_env["DOCAGENT_LITELLM_REASONING_MODEL"] == "openai/deepseek-test-reasoning"
    assert litellm_env["DOCAGENT_LITELLM_DEEPSEEK_MODEL"] == "openai/deepseek-test-tool-loop"
    assert litellm_env["DOCAGENT_LITELLM_DEFAULT_API_BASE"] == "https://api.deepseek.example/v1"
    assert litellm_env["DOCAGENT_LITELLM_FAST_API_BASE"] == "https://api.deepseek.example/v1"
    assert litellm_env["DOCAGENT_LITELLM_REASONING_API_BASE"] == "https://api.deepseek.example/v1"
    assert litellm_env["DOCAGENT_LITELLM_DEEPSEEK_API_BASE"] == "https://api.deepseek.example/v1"


def test_env_example_defaults_litellm_aliases_to_kimi() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "OPENAI_API_KEY=PASTE_KIMI_API_KEY_HERE" in env_example
    assert "DOCAGENT_LITELLM_DEFAULT_MODEL=openai/kimi-k2-0905-preview" in env_example
    assert "DOCAGENT_LITELLM_FAST_MODEL=openai/kimi-k2-0905-preview" in env_example
    assert "DOCAGENT_LITELLM_REASONING_MODEL=openai/kimi-k2-0905-preview" in env_example
    assert "DOCAGENT_LITELLM_DEEPSEEK_MODEL=openai/deepseek-v4-flash" in env_example
    assert "DOCAGENT_LITELLM_DEFAULT_API_BASE=https://api.moonshot.cn/v1" in env_example
    assert "DOCAGENT_LITELLM_FAST_API_BASE=https://api.moonshot.cn/v1" in env_example
    assert "DOCAGENT_LITELLM_REASONING_API_BASE=https://api.moonshot.cn/v1" in env_example
    assert "DOCAGENT_LITELLM_DEEPSEEK_API_BASE=https://api.deepseek.com/v1" in env_example
