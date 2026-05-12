from __future__ import annotations

from pathlib import Path

from docagent_contracts import PromptBundle

from docagent_api.doctypes import is_valid_doc_type_id


def build_prompt_bundle(
    repo_root: Path,
    workspace_root: Path,
    task_id: str,
    session_id: str,
    doc_type_id: str,
) -> PromptBundle:
    if not is_valid_doc_type_id(doc_type_id):
        raise ValueError("Invalid document type id")
    system_prompt_path = repo_root / "agent" / "system-prompts" / "docagent-core.md"
    skill_path = repo_root / "doc-types" / doc_type_id / "SKILL.md"
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    skill_markdown = skill_path.read_text(encoding="utf-8")
    task_instruction = (
        f"Task ID: {task_id}\n"
        f"Session ID: {session_id}\n"
        f"Document type: {doc_type_id}\n"
        f"Workspace root: {workspace_root}\n\n"
        "Use the document type skill below as active writing guidance.\n\n"
        f"{skill_markdown}"
    )
    return PromptBundle(
        system_prompt=system_prompt,
        task_instruction=task_instruction,
        workspace_root=workspace_root,
        doc_type_id=doc_type_id,
        metadata={
            "task_id": task_id,
            "session_id": session_id,
            "system_prompt_path": str(system_prompt_path),
            "skill_path": str(skill_path),
        },
    )
