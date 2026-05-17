from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from docagent_api.request_models import (
    AddSkillPackTextResourceRequest,
    CreateSkillPackRequest,
    PublishSkillPackRequest,
    UpdateSkillPackArtifactRequest,
)
from docagent_api.response_models import (
    SkillPackArtifactResponse,
    SkillPackResourceResponse,
    SkillPackSummaryResponse,
    SkillPackValidationResponse,
    SkillPackVersionResponse,
)
from docagent_api.skill_packs import (
    add_text_resource,
    draft_root,
    is_valid_pack_id,
    publish_skill_pack_snapshot,
    resolve_artifact_path,
    validate_skill_pack_draft,
    write_skill_pack_artifact,
)
from docagent_api.state import DocAgentState


def create_skill_packs_router(state: DocAgentState) -> APIRouter:
    router = APIRouter()

    @router.get("/skill-packs", response_model=list[SkillPackSummaryResponse])
    def list_packs() -> list[dict[str, Any]]:
        return state.list_skill_packs()

    @router.post("/skill-packs", response_model=SkillPackSummaryResponse)
    def create_pack(request: CreateSkillPackRequest) -> dict[str, Any]:
        if not is_valid_pack_id(request.id):
            raise HTTPException(status_code=422, detail="Invalid pack id")
        if state.get_skill_pack(request.id) is not None:
            raise HTTPException(status_code=409, detail="Skill pack already exists")
        record = {
            "id": request.id,
            "title": request.title,
            "description": request.description,
            "draft_status": "draft",
        }
        state.save_skill_pack(record)
        return _require_pack(state, request.id)

    @router.get("/skill-packs/{pack_id}", response_model=SkillPackSummaryResponse)
    def get_pack(pack_id: str) -> dict[str, Any]:
        return _require_pack(state, pack_id)

    @router.post("/skill-packs/{pack_id}/resources/text", response_model=SkillPackResourceResponse)
    def add_pack_text_resource(pack_id: str, request: AddSkillPackTextResourceRequest) -> dict[str, Any]:
        _require_pack(state, pack_id)
        try:
            resource = add_text_resource(state, pack_id, request.group, request.name, request.content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state.save_skill_pack_resource(resource)
        return resource

    @router.put("/skill-packs/{pack_id}/artifacts", response_model=SkillPackArtifactResponse)
    def update_artifact(pack_id: str, request: UpdateSkillPackArtifactRequest) -> dict[str, str]:
        _require_pack(state, pack_id)
        try:
            write_skill_pack_artifact(state, pack_id, request.path, request.content, "user", request.summary)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"pack_id": pack_id, "path": request.path, "content": request.content}

    @router.get("/skill-packs/{pack_id}/artifacts", response_model=SkillPackArtifactResponse)
    def get_artifact(pack_id: str, path: str = Query(alias="path")) -> dict[str, str]:
        _require_pack(state, pack_id)
        try:
            artifact_path = resolve_artifact_path(draft_root(state, pack_id), path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not artifact_path.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return {"pack_id": pack_id, "path": path, "content": artifact_path.read_text(encoding="utf-8")}

    @router.post("/skill-packs/{pack_id}/validate", response_model=SkillPackValidationResponse)
    def validate_pack(pack_id: str) -> dict[str, Any]:
        _require_pack(state, pack_id)
        return validate_skill_pack_draft(state, pack_id)

    @router.post("/skill-packs/{pack_id}/publish", response_model=SkillPackVersionResponse)
    def publish_pack(pack_id: str, request: PublishSkillPackRequest) -> dict[str, Any]:
        _require_pack(state, pack_id)
        validation = validate_skill_pack_draft(state, pack_id)
        if validation["status"] != "passed":
            raise HTTPException(status_code=422, detail=validation["errors"])
        unacknowledged = [
            warning for warning in validation["warnings"]
            if warning not in request.acknowledged_warnings
        ]
        if unacknowledged:
            raise HTTPException(status_code=422, detail={"warnings": unacknowledged})
        try:
            version = publish_skill_pack_snapshot(state, pack_id, request.publish_note)
        except (FileExistsError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _version_response(version)

    return router


def _require_pack(state: DocAgentState, pack_id: str) -> dict[str, Any]:
    pack = state.get_skill_pack(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Skill pack not found")
    return pack


def _version_response(version: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": version["id"],
        "pack_id": version["pack_id"],
        "version": version["version"],
        "manifest": version.get("manifest", {}),
        "validation": version.get("validation", {}),
        "publish_note": version.get("publish_note", ""),
        "created_at": version.get("created_at"),
    }
