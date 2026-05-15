from __future__ import annotations

import os

from docagent_contracts import RuntimeAdapter, RuntimeKind


class RuntimeConfigurationError(ValueError):
    pass


MOCK_RUNTIME_NAMES = {RuntimeKind.MOCK.value, "mock-acp"}
OPENHANDS_RUNTIME_NAMES = {RuntimeKind.OPENHANDS.value, "openhands-acp"}


def create_runtime_adapter(runtime_name: str | None = None) -> RuntimeAdapter:
    runtime = runtime_name or os.environ.get("DOCAGENT_RUNTIME", "mock-acp")
    if runtime in MOCK_RUNTIME_NAMES:
        from docagent_mock_runtime.adapter import MockRuntimeAdapter

        return MockRuntimeAdapter()
    if runtime in OPENHANDS_RUNTIME_NAMES:
        from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter
        from docagent_openhands_runtime.client import OpenHandsAgentServerClient

        base_url = os.environ.get("DOCAGENT_ACP_RUNTIME_URL") or os.environ.get("OPENHANDS_BASE_URL")
        return OpenHandsRuntimeAdapter(OpenHandsAgentServerClient(base_url=base_url))
    raise RuntimeConfigurationError(f"Unsupported DOCAGENT_RUNTIME: {runtime}")
