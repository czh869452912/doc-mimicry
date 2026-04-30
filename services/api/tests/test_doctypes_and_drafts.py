from pathlib import Path

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.drafts import read_draft, write_draft


def test_lists_seed_prd_doc_type() -> None:
    doc_types = list_doc_types(Path("doc-types"))

    assert doc_types[0]["id"] == "prd"
    assert doc_types[0]["has_skill"] is True
    assert "examples" in doc_types[0]["resource_groups"]


def test_reads_prd_doc_type_detail() -> None:
    detail = get_doc_type(Path("doc-types"), "prd")

    assert detail is not None
    assert detail["id"] == "prd"
    assert "skill_markdown" in detail
    assert "checklists" in detail["resource_groups"]


def test_doc_type_detail_groups_markdown_and_reports() -> None:
    detail = get_doc_type(Path("doc-types"), "prd")

    assert detail is not None
    assert "examples" in detail["resource_groups"]
    assert "specs" in detail["resource_groups"]
    assert "checklists" in detail["resource_groups"]
    assert "export-references" in detail["resource_groups"]


def test_draft_read_write_roundtrip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    write_draft(workspace, "# Draft\n\nHello")

    assert read_draft(workspace) == "# Draft\n\nHello\n"
