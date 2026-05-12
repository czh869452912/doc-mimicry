import pytest
from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.runtime_factory import RuntimeConfigurationError, create_runtime_adapter
from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_create_runtime_adapter_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCAGENT_RUNTIME", raising=False)

    assert isinstance(create_runtime_adapter(), MockRuntimeAdapter)


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
