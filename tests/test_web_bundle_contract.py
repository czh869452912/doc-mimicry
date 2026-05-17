from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_bundle_check_tracks_initial_and_editor_budgets() -> None:
    script = (ROOT / "tools" / "quality" / "check_web_bundle.py").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "quality" / "local-development.md").read_text(encoding="utf-8")

    assert "DEFAULT_INITIAL_MAX_KB = 760.0" in script
    assert "DEFAULT_EDITOR_MAX_KB = 650.0" in script
    assert "DraftEditor-" in script
    assert "dist/index.html" in script
    assert "python tools/quality/check_web_bundle.py apps/web/dist" in docs
