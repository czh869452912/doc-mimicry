from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools" / "acp_ui" / "prepare_acp_ui.ps1"
PATCH_PATH = REPO_ROOT / "tools" / "acp_ui" / "patches" / "docagent-query-bootstrap.patch"


def test_prepare_script_clones_upstream_and_applies_docagent_patch() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "https://github.com/formulahendry/acp-ui.git" in script
    assert "docagent-query-bootstrap.patch" in script
    assert "Invoke-CheckedNative" in script
    assert "Test-NativeCommand" in script
    assert "git -C $AcpUiDir apply --check --unidiff-zero $patchPath" in script
    assert "Test-NativeCommand git -C $AcpUiDir apply --reverse --check --unidiff-zero $patchPath" in script
    assert "2>$null" not in script
    assert "Push-Location $AcpUiDir" in script
    assert "npm install" in script
    assert "npm run dev:web -- --host 127.0.0.1 --port 4173" in script


def test_docagent_patch_bootstraps_acp_ui_from_iframe_query_params() -> None:
    patch = PATCH_PATH.read_text(encoding="utf-8")

    assert "docagentAcpWsUrl" in patch
    assert "DocAgent" in patch
    assert "transport: 'websocket'" in patch
    assert "url: wsUrl" in patch
    assert "docagentWorkspaceRoot" in patch
    assert "cwd.startsWith('/')" in patch
    assert "sessionStore.createSession" in patch


def test_docagent_patch_matches_local_reference_checkout_when_present() -> None:
    acp_ui_checkout = REPO_ROOT / ".local" / "reference" / "acp-ui"
    if not (acp_ui_checkout / ".git").exists():
        pytest.skip("local acp-ui reference checkout is optional")

    reverse_check = subprocess.run(
        [
            "git",
            "-C",
            str(acp_ui_checkout),
            "apply",
            "--reverse",
            "--check",
            "--unidiff-zero",
            str(PATCH_PATH),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if reverse_check.returncode == 0:
        return

    apply_check = subprocess.run(
        [
            "git",
            "-C",
            str(acp_ui_checkout),
            "apply",
            "--check",
            "--unidiff-zero",
            str(PATCH_PATH),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert apply_check.returncode == 0, apply_check.stderr
