from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from docagent_api.request_models import (
    AddSkillPackTextResourceRequest,
    CreateSkillPackRequest,
    PublishSkillPackRequest,
    SkillCreatorMessageRequest,
    UpdateSkillPackArtifactRequest,
)
from docagent_api.response_models import (
    SkillCreatorEventResponse,
    SkillCreatorRunResponse,
    SkillCreatorSessionResponse,
    SkillPackArtifactResponse,
    SkillPackResourceResponse,
    SkillPackSummaryResponse,
    SkillPackValidationResponse,
    SkillPackVersionResponse,
)
from docagent_api.prompts import build_skill_creator_prompt_bundle
from docagent_api.skill_packs import (
    PACK_GROUPS,
    add_file_resource,
    add_text_resource,
    draft_root,
    is_valid_pack_id,
    publish_skill_pack_snapshot,
    resolve_artifact_path,
    validate_skill_pack_draft,
    write_skill_pack_artifact,
)
from docagent_api.state import DocAgentState


def create_skill_packs_router(state: DocAgentState, adapter: Any | None = None) -> APIRouter:
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

    @router.post("/skill-packs/{pack_id}/resources/files", response_model=SkillPackResourceResponse)
    async def add_pack_file_resource(
        pack_id: str,
        group: str = Form(...),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        _require_pack(state, pack_id)
        if group not in PACK_GROUPS:
            raise HTTPException(status_code=400, detail="Invalid resource group")
        content = await file.read()
        resource = add_file_resource(
            state,
            pack_id,
            group,
            file.filename or "upload.bin",
            content,
            file.content_type or "application/octet-stream",
        )
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
            version = publish_skill_pack_snapshot(state, pack_id, request.publish_note, validation)
        except (FileExistsError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _version_response(version)

    @router.post(
        "/skill-packs/{pack_id}/skill-creator/sessions",
        response_model=SkillCreatorSessionResponse,
    )
    def create_skill_creator_session(pack_id: str, request: SkillCreatorMessageRequest) -> dict[str, Any]:
        _require_pack(state, pack_id)
        session_id = f"creator-{uuid4().hex[:8]}"
        session = {
            "id": session_id,
            "pack_id": pack_id,
            "session_scope": "pack-management",
            "status": "idle",
        }
        prompt_bundle = build_skill_creator_prompt_bundle(
            pack_id,
            session_id,
            draft_root(state, pack_id),
            _resource_manifest(state, pack_id),
            _current_artifacts(state, pack_id),
        )
        state.save_skill_creator_session(session)
        if adapter is not None:
            try:
                result = adapter.create_session(session_id, prompt_bundle)
            except Exception as exc:
                state.delete_skill_creator_session(session_id)
                raise HTTPException(
                    status_code=502,
                    detail=f"Skill Creator runtime session creation failed: {exc}",
                ) from exc
            _append_skill_creator_updates(state, session_id, result.acp_updates)
        return state.get_skill_creator_session(session_id) or session

    @router.post(
        "/skill-packs/{pack_id}/skill-creator/sessions/{session_id}/generate",
        response_model=SkillCreatorRunResponse,
    )
    def generate_skill_pack(
        pack_id: str,
        session_id: str,
        request: SkillCreatorMessageRequest,
    ) -> dict[str, list[str]]:
        return _run_skill_creator_prompt(state, adapter, pack_id, session_id, request.message, "skill_creator_generate")

    @router.post(
        "/skill-packs/{pack_id}/skill-creator/sessions/{session_id}/messages",
        response_model=SkillCreatorRunResponse,
    )
    def send_skill_creator_message(
        pack_id: str,
        session_id: str,
        request: SkillCreatorMessageRequest,
    ) -> dict[str, list[str]]:
        return _run_skill_creator_prompt(state, adapter, pack_id, session_id, request.message, "skill_creator_message")

    @router.get(
        "/skill-packs/{pack_id}/skill-creator/sessions/{session_id}/events",
        response_model=list[SkillCreatorEventResponse],
    )
    def list_skill_creator_session_events(pack_id: str, session_id: str) -> list[dict[str, Any]]:
        _require_pack(state, pack_id)
        session = state.get_skill_creator_session(session_id)
        if session is None or session["pack_id"] != pack_id:
            raise HTTPException(status_code=404, detail="Skill Creator session not found")
        return state.list_skill_creator_events(session_id)

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


def _run_skill_creator_prompt(
    state: DocAgentState,
    adapter: Any | None,
    pack_id: str,
    session_id: str,
    message: str,
    action: str,
) -> dict[str, list[str]]:
    _require_pack(state, pack_id)
    session = state.get_skill_creator_session(session_id)
    if session is None or session["pack_id"] != pack_id:
        raise HTTPException(status_code=404, detail="Skill Creator session not found")
    if adapter is None:
        return {"paths": []}
    try:
        result = adapter.send_prompt(session_id, message, {"action": action})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Skill Creator runtime failed: {exc}") from exc
    _append_skill_creator_updates(state, session_id, result.acp_updates)
    return {"paths": result.changed_paths}


def _append_skill_creator_updates(state: DocAgentState, session_id: str, updates: list[Any]) -> None:
    for update in updates:
        state.append_skill_creator_event(
            session_id,
            {
                "event_type": update.event_type,
                "payload": update.payload,
            },
            update.projection,
        )


def _resource_manifest(state: DocAgentState, pack_id: str) -> dict[str, object]:
    return {"resources": state.list_skill_pack_resources(pack_id)}


def _current_artifacts(state: DocAgentState, pack_id: str) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    root = draft_root(state, pack_id)
    for path in ["SKILL.md", "checklists/quality.yaml", "notes/resources.md"]:
        target = root / path
        if target.is_file():
            artifacts[path] = target.read_text(encoding="utf-8")
    return artifacts
