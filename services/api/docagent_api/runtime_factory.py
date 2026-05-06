from __future__ import annotations

import os

from docagent_contracts import RuntimeAdapter, RuntimeKind


class RuntimeConfigurationError(ValueError):
    pass


def create_runtime_adapter(runtime_name: str | None = None) -> RuntimeAdapter:
    runtime = runtime_name or os.environ.get("DOCAGENT_RUNTIME", RuntimeKind.MOCK.value)
    if runtime == RuntimeKind.MOCK.value:
        from docagent_mock_runtime.adapter import MockRuntimeAdapter

        return MockRuntimeAdapter()
    if runtime == RuntimeKind.OPENHANDS.value:
        from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter
        from docagent_openhands_runtime.client import OpenHandsAgentServerClient

        return OpenHandsRuntimeAdapter(OpenHandsAgentServerClient(base_url=os.environ.get("OPENHANDS_BASE_URL")))
    raise RuntimeConfigurationError(f"Unsupported DOCAGENT_RUNTIME: {runtime}")
