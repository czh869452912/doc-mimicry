from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_web_bundle_check_tracks_initial_and_editor_budgets() -> None:
    script = (ROOT / "tools" / "quality" / "check_web_bundle.py").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "quality" / "local-development.md").read_text(encoding="utf-8")

    assert "DEFAULT_INITIAL_MAX_KB = 760.0" in script
    assert "DEFAULT_EDITOR_MAX_KB = 650.0" in script
    assert "DraftEditor-" in script
    assert "dist/index.html" in script
    assert "python tools/quality/check_web_bundle.py apps/web/dist" in docs


def test_web_bundle_check_fails_when_initial_chunk_exceeds_budget(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text('<script type="module" src="/assets/index-big.js"></script>', encoding="utf-8")
    (assets / "index-big.js").write_bytes(b"x" * 2000)
    (assets / "DraftEditor-small.js").write_bytes(b"x")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "quality" / "check_web_bundle.py"),
            str(dist),
            "--initial-max-kb",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Initial chunk index-big.js" in result.stderr


def test_web_build_ci_runs_bundle_budget_after_production_build() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python tools/quality/check_web_bundle.py apps/web/dist" in workflow
