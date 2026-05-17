from __future__ import annotations

import json
from pathlib import Path

from docagent_contracts import PromptBundle

from docagent_api.doctypes import is_valid_doc_type_id

SKILL_CREATOR_SYSTEM_PROMPT = """You are Skill Creator for DocAgent Workbench.
Create and revise document type skill packs from converted Markdown resources.
Do not build fixed workflows, content templates, or semantic RAG behavior.
Read current artifacts before revising them. Preserve intentional human edits.
Write concise SKILL.md guidance, checklist files, and resource notes."""

GROUP_PRIORITY = {"specs": 0, "checklists": 1, "examples": 2, "export-references": 3}


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


def build_skill_creator_prompt_bundle(
    pack_id: str,
    session_id: str,
    pack_workspace_root: Path,
    resource_manifest: dict[str, object],
    current_artifacts: dict[str, str],
    resource_budget_words: int = 6000,
) -> PromptBundle:
    budgeted_manifest = _budget_skill_creator_resources(resource_manifest, resource_budget_words)
    instruction = (
        f"Pack ID: {pack_id}\n"
        f"Session ID: {session_id}\n"
        f"Workspace root: {pack_workspace_root}\n"
        "Session scope: pack-management\n\n"
        "Resource manifest:\n"
        f"{json.dumps(budgeted_manifest, indent=2, ensure_ascii=False)}\n\n"
        "Current artifacts:\n"
        f"{json.dumps(current_artifacts, indent=2, ensure_ascii=False)}\n"
    )
    return PromptBundle(
        system_prompt=SKILL_CREATOR_SYSTEM_PROMPT,
        task_instruction=instruction,
        workspace_root=pack_workspace_root,
        doc_type_id="",
        pack_id=pack_id,
        metadata={"session_scope": "pack-management", "pack_id": pack_id, "session_id": session_id},
    )


def _budget_skill_creator_resources(resource_manifest: dict[str, object], budget_words: int) -> dict[str, object]:
    resources = list(resource_manifest.get("resources", []))
    budgeted: list[dict[str, object]] = []
    warnings: list[str] = []
    remaining = budget_words
    for resource in sorted(resources, key=lambda item: GROUP_PRIORITY.get(str(item.get("group")), 99)):
        copied = dict(resource)
        content = str(copied.get("markdown_excerpt") or copied.get("markdown") or "")
        words = content.split()
        if content and remaining <= 0:
            copied.pop("markdown", None)
            copied.pop("markdown_excerpt", None)
            warnings.append(f"Omitted {copied.get('id')} because Skill Creator context budget was exhausted")
        elif len(words) > remaining:
            copied.pop("markdown", None)
            copied["markdown_excerpt"] = " ".join(words[:remaining])
            warnings.append(f"Truncated {copied.get('id')} to fit Skill Creator context budget")
            remaining = 0
        else:
            if content:
                copied["markdown_excerpt"] = content
                copied.pop("markdown", None)
                remaining -= len(words)
        budgeted.append(copied)
    return {**resource_manifest, "resources": budgeted, "budget_warnings": warnings}
