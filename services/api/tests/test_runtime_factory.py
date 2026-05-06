import pytest

from docagent_api.runtime_factory import RuntimeConfigurationError, create_runtime_adapter
from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_create_runtime_adapter_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCAGENT_RUNTIME", raising=False)

    assert isinstance(create_runtime_adapter(), MockRuntimeAdapter)


def test_create_runtime_adapter_rejects_unknown_runtime() -> None:
    with pytest.raises(RuntimeConfigurationError, match="Unsupported"):
        create_runtime_adapter("missing")
