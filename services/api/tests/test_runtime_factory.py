import pytest
from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.runtime_factory import RuntimeConfigurationError, create_runtime_adapter
from docagent_mock_runtime.adapter import MockRuntimeAdapter
from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter


def test_create_runtime_adapter_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCAGENT_RUNTIME", raising=False)

    assert isinstance(create_runtime_adapter(), MockRuntimeAdapter)


def test_create_runtime_adapter_accepts_acp_runtime_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCAGENT_RUNTIME", raising=False)

    assert isinstance(create_runtime_adapter("mock-acp"), MockRuntimeAdapter)


def test_create_runtime_adapter_prefers_acp_runtime_url_for_openhands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCAGENT_ACP_RUNTIME_URL", "http://acp-runtime.example")
    monkeypatch.setenv("OPENHANDS_BASE_URL", "http://legacy.example")

    adapter = create_runtime_adapter("openhands-acp")

    assert isinstance(adapter, OpenHandsRuntimeAdapter)
    assert adapter.client.base_url == "http://acp-runtime.example"


def test_create_runtime_adapter_rejects_unknown_runtime() -> None:
    with pytest.raises(RuntimeConfigurationError, match="Unsupported"):
        create_runtime_adapter("missing")


def test_health_reports_selected_runtime_without_secrets(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCAGENT_RUNTIME", "mock")
    monkeypatch.setenv("LLM_API_KEY", "secret-value")
    client = TestClient(create_app(state_root=tmp_path / "state"))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["runtime"] == "mock"
    assert "secret-value" not in str(body)


def test_health_defaults_to_acp_mock_runtime(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCAGENT_RUNTIME", raising=False)
    client = TestClient(create_app(state_root=tmp_path / "state"))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["runtime"] == "mock-acp"
