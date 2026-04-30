from docagent_contracts import (
    Artifact,
    ArtifactKind,
    ConversionEngine,
    ConversionReport,
    ConversionStatus,
    DraftVersion,
    ImportedResource,
    ResourceScope,
    ResourceStatus,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
    WorkspaceLayout,
)


def test_workspace_layout_defaults():
    layout = WorkspaceLayout(task_id="task-001", root="workspace/task-001")

    assert layout.brief_path == "brief.md"
    assert layout.inputs.markdown_dir == "inputs/markdown"
    assert layout.context.style_notes == "context/style_notes.md"
    assert layout.draft.current == "draft/draft.md"
    assert layout.reviews.checklist_result == "reviews/checklist_result.md"


def test_imported_resource_points_agent_to_markdown():
    resource = ImportedResource(
        id="res-001",
        scope=ResourceScope.TASK_INPUT,
        owner_id="task-001",
        source_path="inputs/original/brief.docx",
        markdown_path="inputs/markdown/brief.md",
        asset_dir="inputs/assets/brief",
        conversion_report_path="inputs/reports/brief.conversion.json",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="brief.docx",
        status=ResourceStatus.CONVERTED,
        created_at="2026-04-30T00:00:00Z",
        updated_at="2026-04-30T00:00:00Z",
    )

    assert resource.markdown_path == "inputs/markdown/brief.md"
    assert resource.source_path.endswith(".docx")


def test_conversion_report_warning_shape():
    report = ConversionReport(
        source_path="inputs/original/example.pdf",
        markdown_path=None,
        asset_dir=None,
        engine=ConversionEngine.DOCLING,
        status=ConversionStatus.FAILED,
        warnings=[{"type": "unsupported", "message": "PDF conversion is not wired yet.", "location": None}],
        features_detected={"tables": 0, "images": 0, "formulas": 0, "footnotes": 0, "pages": None},
        created_at="2026-04-30T00:00:00Z",
    )

    assert report.warnings[0]["type"] == "unsupported"
    assert report.features_detected["pages"] is None


def test_semantic_timeline_event_shape():
    event = SemanticTimelineEvent(
        id="evt-001",
        session_id="session-001",
        task_id="task-001",
        actor=TimelineActor.TOOL,
        kind=SemanticEventKind.CREATE_CHECKPOINT,
        raw_event_id="raw-001",
        summary="Create checkpoint",
        paths=["versions/v001.md"],
        status=TimelineStatus.SUCCEEDED,
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.CREATE_CHECKPOINT
    assert event.paths == ["versions/v001.md"]


def test_draft_version_and_artifact_shape():
    version = DraftVersion(
        id="ver-001",
        task_id="task-001",
        version="v001",
        source_path="draft/draft.md",
        version_path="versions/v001.md",
        summary="Initial draft",
        created_by="agent",
        created_at="2026-04-30T00:00:00Z",
    )
    artifact = Artifact(
        id="art-001",
        task_id="task-001",
        draft_version_id=version.id,
        kind=ArtifactKind.DOCX,
        path="artifacts/output.docx",
        status="created",
        created_at="2026-04-30T00:00:00Z",
    )

    assert version.version_path == "versions/v001.md"
    assert artifact.kind is ArtifactKind.DOCX


def test_phase2_semantic_event_kinds_are_available() -> None:
    assert SemanticEventKind.CONVERT_INPUT.value == "convert_input"
    assert SemanticEventKind.BUILD_CONTEXT.value == "build_context"
    assert SemanticEventKind.PROPOSE_OUTLINE.value == "propose_outline"
    assert SemanticEventKind.APPROVE_OUTLINE.value == "approve_outline"
    assert SemanticEventKind.REVISE_SELECTION.value == "revise_selection"
    assert SemanticEventKind.EXPORT_MARKDOWN.value == "export_markdown"
