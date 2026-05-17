from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from docagent_conversion import ConversionLayout, convert_resource_bytes
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now

PACK_GROUPS = ("examples", "specs", "checklists", "export-references")
ARTIFACT_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json"}

logger = logging.getLogger(__name__)


def is_valid_pack_id(pack_id: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", pack_id))


def draft_root(state: DocAgentState, pack_id: str) -> Path:
    return state.skill_pack_root(pack_id) / "draft"


def published_root(state: DocAgentState, pack_id: str, version: str) -> Path:
    return state.skill_pack_root(pack_id) / "published" / version


def write_skill_pack_artifact(
    state: DocAgentState,
    pack_id: str,
    relative_path: str,
    content: str,
    source: str,
    summary: str,
) -> dict[str, Any]:
    path = _resolve_artifact_path(draft_root(state, pack_id), relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = content if content.endswith("\n") else f"{content}\n"
    path.write_text(text, encoding="utf-8")
    revision = {
        "id": f"rev-{uuid4().hex[:12]}",
        "pack_id": pack_id,
        "artifact_path": relative_path,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source": source,
        "summary": summary,
    }
    state.save_skill_pack_artifact_revision(revision)
    return revision


def add_text_resource(
    state: DocAgentState,
    pack_id: str,
    group: str,
    name: str,
    content: str,
) -> dict[str, Any]:
    if group not in PACK_GROUPS:
        raise ValueError("Invalid resource group")
    root = draft_root(state, pack_id)
    text = content if content.endswith("\n") else f"{content}\n"
    result = convert_resource_bytes(
        ConversionLayout(
            root=root,
            original_dir=f"resources/original/{group}",
            markdown_dir=f"resources/markdown/{group}",
            assets_dir=f"resources/assets/{group}",
            reports_dir=f"resources/reports/{group}",
        ),
        original_filename=name,
        content=text.encode("utf-8"),
        mime_type="text/plain",
        created_at=utc_now(),
    )
    return {
        "id": f"resource-{uuid4().hex[:12]}",
        "pack_id": pack_id,
        "group": group,
        "original_filename": name,
        "source_path": result["source_path"],
        "markdown_path": result["markdown_path"],
        "conversion_report_path": result["conversion_report_path"],
        "status": _resource_status(result),
        "summary": "",
        "warnings": result.get("warnings") or [],
    }


def add_file_resource(
    state: DocAgentState,
    pack_id: str,
    group: str,
    name: str,
    content: bytes,
    mime_type: str,
) -> dict[str, Any]:
    if group not in PACK_GROUPS:
        raise ValueError("Invalid resource group")
    root = draft_root(state, pack_id)
    result = convert_resource_bytes(
        ConversionLayout(
            root=root,
            original_dir=f"resources/original/{group}",
            markdown_dir=f"resources/markdown/{group}",
            assets_dir=f"resources/assets/{group}",
            reports_dir=f"resources/reports/{group}",
        ),
        original_filename=name,
        content=content,
        mime_type=mime_type,
        created_at=utc_now(),
    )
    return {
        "id": f"resource-{uuid4().hex[:12]}",
        "pack_id": pack_id,
        "group": group,
        "original_filename": name,
        "source_path": result["source_path"],
        "markdown_path": result["markdown_path"],
        "conversion_report_path": result["conversion_report_path"],
        "status": _resource_status(result),
        "summary": "",
        "warnings": result.get("warnings") or [],
    }


def validate_skill_pack_draft(state: DocAgentState, pack_id: str) -> dict[str, Any]:
    root = draft_root(state, pack_id)
    errors: list[str] = []
    warnings: list[str] = []
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        errors.append("SKILL.md is missing")
    else:
        content = skill_path.read_text(encoding="utf-8")
        if not content.strip():
            errors.append("SKILL.md is empty")
        if not content.startswith("---"):
            errors.append("SKILL.md frontmatter is missing")
        else:
            try:
                frontmatter = content.split("---", 2)[1]
                parsed = yaml.safe_load(frontmatter) or {}
                if not parsed.get("name") or not parsed.get("description"):
                    errors.append("SKILL.md frontmatter must include name and description")
            except (ValueError, yaml.YAMLError) as exc:
                errors.append(f"SKILL.md frontmatter is invalid: {exc}")
        if len(content.split()) > 2000:
            warnings.append("SKILL.md is over the MVP 2,000 word size limit")
        warnings.extend(_source_copy_warnings(root, content, state.list_skill_pack_resources(pack_id)))
    for checklist in sorted((root / "checklists").glob("*.y*ml")):
        try:
            yaml.safe_load(checklist.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{checklist.relative_to(root).as_posix()} is invalid YAML: {exc}")
    return {"status": "failed" if errors else "passed", "errors": errors, "warnings": warnings}


def publish_skill_pack_snapshot(
    state: DocAgentState,
    pack_id: str,
    publish_note: str,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validation or validate_skill_pack_draft(state, pack_id)
    if validation["status"] != "passed":
        raise ValueError("; ".join(validation["errors"]))
    version = _next_version(state, pack_id)
    target = published_root(state, pack_id, version)
    if target.exists():
        raise FileExistsError(target)
    temp_target = target.with_name(f".{version}-{uuid4().hex}.tmp")
    renamed = False
    try:
        shutil.copytree(draft_root(state, pack_id), temp_target)
        manifest = _snapshot_manifest(temp_target)
        if target.exists():
            raise FileExistsError(target)
        temp_target.rename(target)
        renamed = True
        record = {
            "id": f"{pack_id}-{version}",
            "pack_id": pack_id,
            "version": version,
            "snapshot_path": str(target),
            "manifest": manifest,
            "validation": validation,
            "publish_note": publish_note,
        }
        state.save_skill_pack_version(record)
    except Exception:
        if temp_target.exists():
            shutil.rmtree(temp_target, ignore_errors=True)
        if renamed and target.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise
    return state.get_latest_skill_pack_version(pack_id)


def bootstrap_seed_skill_packs(state: DocAgentState, seed_root: Path) -> None:
    if not seed_root.exists():
        return
    for path in sorted(item for item in seed_root.iterdir() if item.is_dir()):
        pack_id = path.name
        try:
            state.save_skill_pack({
                "id": pack_id,
                "title": pack_id.upper(),
                "description": "",
                "draft_status": "draft",
            })
            latest = state.get_latest_skill_pack_version(pack_id)
            draft = draft_root(state, pack_id)
            if not draft.exists():
                shutil.copytree(path, draft, ignore=shutil.ignore_patterns(".gitkeep"))
            if latest is None:
                publish_skill_pack_snapshot(state, pack_id, "Seed version")
        except Exception as exc:
            logger.warning("Failed to bootstrap seed skill pack %s: %s", pack_id, exc, exc_info=True)


def _resolve_artifact_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Artifact path escapes pack workspace")
    if target.suffix not in ARTIFACT_TEXT_SUFFIXES and target.name != "SKILL.md":
        raise ValueError("Only text skill artifacts are supported")
    return target


def resolve_artifact_path(root: Path, relative_path: str) -> Path:
    return _resolve_artifact_path(root, relative_path)


def list_resource_summaries(state: DocAgentState, pack_id: str) -> list[dict[str, Any]]:
    root = draft_root(state, pack_id)
    summaries: list[dict[str, Any]] = []
    for resource in state.list_skill_pack_resources(pack_id):
        summary = dict(resource)
        summary["warnings"] = _resource_warnings(root, resource)
        summaries.append(summary)
    return summaries


def list_resource_details(state: DocAgentState, pack_id: str) -> list[dict[str, Any]]:
    root = draft_root(state, pack_id)
    details: list[dict[str, Any]] = []
    for resource in state.list_skill_pack_resources(pack_id):
        details.append(_resource_detail(root, resource))
    return details


def _next_version(state: DocAgentState, pack_id: str) -> str:
    versions = state.list_skill_pack_versions(pack_id)
    return f"v{len(versions) + 1:03d}"


def _resource_status(result: dict[str, Any]) -> str:
    if result["status"] == "converted" and result.get("warnings"):
        return "warning"
    if result["status"] == "converted":
        return "ready"
    return "failed"


def _resource_detail(root: Path, resource: dict[str, Any]) -> dict[str, Any]:
    detail = dict(resource)
    markdown_path = resource.get("markdown_path")
    markdown = ""
    conversion_report = _resource_report(root, resource)
    warnings = list(conversion_report.get("warnings") or [])
    if markdown_path:
        markdown_file = _resolve_resource_path(root, markdown_path)
        if markdown_file.is_file():
            markdown = markdown_file.read_text(encoding="utf-8")
    detail["markdown"] = markdown
    # Cap each resource before serializing the complete prompt bundle.
    detail["markdown_excerpt"] = _word_excerpt(markdown, 800)
    detail["warnings"] = warnings
    detail["conversion_report"] = conversion_report
    return detail


def _resource_warnings(root: Path, resource: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_resource_report(root, resource).get("warnings") or [])


def _resource_report(root: Path, resource: dict[str, Any]) -> dict[str, Any]:
    report_path = resource.get("conversion_report_path")
    if not report_path:
        return {}
    report_file = _resolve_resource_path(root, report_path)
    if not report_file.is_file():
        return {}
    return json.loads(report_file.read_text(encoding="utf-8"))


def _resolve_resource_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Resource path escapes pack workspace")
    return target


def _word_excerpt(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _snapshot_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        content = path.read_bytes()
        files.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        })
    return {"files": files}


def _source_copy_warnings(root: Path, skill_content: str, resources: list[dict[str, Any]]) -> list[str]:
    skill_words = re.findall(r"\w+", skill_content.lower())
    if len(skill_words) < 25:
        return []
    skill_runs = {" ".join(skill_words[index:index + 25]) for index in range(len(skill_words) - 24)}
    warnings: list[str] = []
    for resource in resources:
        if resource["group"] not in {"examples", "specs"} or resource["status"] != "ready":
            continue
        markdown_path = resource.get("markdown_path")
        if not markdown_path:
            continue
        resource_path = root / markdown_path
        if not resource_path.is_file():
            continue
        resource_words = re.findall(r"\w+", resource_path.read_text(encoding="utf-8").lower())
        for index in range(max(0, len(resource_words) - 24)):
            if " ".join(resource_words[index:index + 25]) in skill_runs:
                warnings.append(f"SKILL.md shares 25+ consecutive words with {resource['original_filename']}")
                break
    return warnings
