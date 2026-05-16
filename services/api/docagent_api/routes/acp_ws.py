from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from docagent_api.routes._shared import (
    append_acp_prompt_event,
    append_runtime_result,
    require_session,
    require_task,
    run_runtime_operation,
    set_session_state,
)
from docagent_api.state import DocAgentState
from docagent_contracts import RuntimeSessionState


async def handle_acp_websocket(
    websocket: WebSocket,
    session_id: str,
    state: DocAgentState,
    adapter: Any,
) -> None:
    session = require_session(state, session_id)
    require_task(state, session["task_id"])
    await websocket.accept(subprotocol="acp.v1")

    try:
        while True:
            text = await websocket.receive_text()
            for frame in _jsonrpc_frames(text):
                await _handle_frame(websocket, frame, session_id, state, adapter)
    except WebSocketDisconnect:
        return


async def _handle_frame(
    websocket: WebSocket,
    frame: dict[str, Any],
    session_id: str,
    state: DocAgentState,
    adapter: Any,
) -> None:
    method = frame.get("method")
    request_id = frame.get("id")
    params = frame.get("params") if isinstance(frame.get("params"), dict) else {}
    if method == "$/ping":
        return
    try:
        if method == "initialize":
            await _send_result(websocket, request_id, _initialize_result(params))
            return
        if method == "session/new":
            _require_matching_session(params, session_id)
            await _send_result(websocket, request_id, {"sessionId": session_id})
            await _send_replay(websocket, session_id, state)
            return
        if method == "session/prompt":
            _require_matching_session(params, session_id)
            await _handle_prompt(websocket, request_id, params, session_id, state, adapter)
            return
        if method == "session/cancel":
            _require_matching_session(params, session_id)
            _handle_cancel(session_id, state, adapter)
            await _send_session_update(websocket, session_id, {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "docagent-session",
                "status": "completed",
                "title": "Session cancelled",
            })
            if request_id is not None:
                await _send_result(websocket, request_id, {})
            return
        if request_id is not None:
            await _send_error(websocket, request_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        if request_id is not None:
            await _send_error(websocket, request_id, -32000, str(exc))


async def _handle_prompt(
    websocket: WebSocket,
    request_id: object,
    params: dict[str, Any],
    session_id: str,
    state: DocAgentState,
    adapter: Any,
) -> None:
    prompt = _prompt_text(params.get("prompt"))
    if not prompt:
        await _send_error(websocket, request_id, -32602, "Prompt text is required.")
        return

    before_sequence = _last_acp_sequence(state, session_id)
    session = require_session(state, session_id)
    task = require_task(state, session["task_id"])
    append_acp_prompt_event(state, session_id, prompt, {"action": "send_message", "source": "acp_ws"})

    send_prompt_method = getattr(adapter, "send_prompt", None)
    if not callable(send_prompt_method):
        raise RuntimeError("Runtime adapter must implement send_prompt")
    operation = lambda: send_prompt_method(session_id, prompt, {"action": "send_message", "source": "acp_ws"})
    result = run_runtime_operation(
        state,
        session,
        RuntimeSessionState.RUNNING_CHAT,
        operation,
        task_id=task["id"],
    )
    append_runtime_result(state, task["id"], session_id, result)
    set_session_state(state, session, result.next_state, task_id=task["id"])

    for event in state.list_acp_events_after(session_id, before_sequence):
        for update in _session_updates_for_event(event, replay=False):
            await _send_session_update(websocket, session_id, update)
    await _send_result(websocket, request_id, {"stopReason": "end_turn"})


def _handle_cancel(session_id: str, state: DocAgentState, adapter: Any) -> None:
    session = require_session(state, session_id)
    task = require_task(state, session["task_id"])
    result = adapter.cancel(session_id)
    append_runtime_result(state, task["id"], session_id, result)
    set_session_state(state, session, result.next_state, task_id=task["id"])


async def _send_replay(websocket: WebSocket, session_id: str, state: DocAgentState) -> None:
    for event in state.list_acp_events(session_id):
        for update in _session_updates_for_event(event, replay=True):
            await _send_session_update(websocket, session_id, update)


def _session_updates_for_event(event: dict[str, Any], *, replay: bool) -> list[dict[str, Any]]:
    event_type = str(event.get("event_type") or "").lower()
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    projection = event.get("projection") if isinstance(event.get("projection"), dict) else {}
    text = _event_text(payload, projection)
    actor = str(payload.get("role") or projection.get("actor") or "")

    if event_type == "docagent/prompt" and replay and text:
        return [_message_update("user_message_chunk", text)]
    if event_type in {"message_delta", "message", "session/update"} and text:
        kind = "user_message_chunk" if actor == "user" else "agent_message_chunk"
        return [_message_update(kind, text)]
    if event_type in {"file/write", "tool/call", "tool/result", "permission/request"}:
        title = str(projection.get("summary") or payload.get("name") or payload.get("path") or "Tool activity")
        status = str(projection.get("status") or payload.get("status") or "completed")
        return [{
            "sessionUpdate": "tool_call",
            "toolCallId": str(payload.get("id") or projection.get("timeline_id") or event.get("id")),
            "title": title,
            "kind": _tool_kind(event_type),
            "status": _tool_status(status),
            "locations": _locations(payload, projection),
        }]
    return []


def _message_update(kind: str, text: str) -> dict[str, Any]:
    return {
        "sessionUpdate": kind,
        "content": {"type": "text", "text": text},
    }


async def _send_session_update(websocket: WebSocket, session_id: str, update: dict[str, Any]) -> None:
    await websocket.send_json({
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {"sessionId": session_id, "update": update},
    })


async def _send_result(websocket: WebSocket, request_id: object, result: dict[str, Any]) -> None:
    if request_id is None:
        return
    await websocket.send_json({"jsonrpc": "2.0", "id": request_id, "result": result})


async def _send_error(websocket: WebSocket, request_id: object, code: int, message: str) -> None:
    await websocket.send_json({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    })


def _initialize_result(params: dict[str, Any]) -> dict[str, Any]:
    protocol_version = params.get("protocolVersion") or 1
    return {
        "protocolVersion": protocol_version,
        "agentCapabilities": {"loadSession": False},
        "agentInfo": {"name": "docagent", "title": "DocAgent Workbench", "version": "0"},
    }


def _jsonrpc_frames(text: str) -> list[dict[str, Any]]:
    frames = []
    for line in text.splitlines() or [text]:
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            frames.append(parsed)
    return frames


def _prompt_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        return ""
    parts = [
        str(part.get("text")).strip()
        for part in value
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
    ]
    return "\n".join(part for part in parts if part)


def _event_text(payload: dict[str, Any], projection: dict[str, Any]) -> str:
    for key in ("content", "delta", "message", "prompt"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    value = projection.get("summary")
    return value if isinstance(value, str) else ""


def _last_acp_sequence(state: DocAgentState, session_id: str) -> int:
    events = state.list_acp_events(session_id)
    if not events:
        return 0
    return max(int(event["sequence"]) for event in events)


def _require_matching_session(params: dict[str, Any], session_id: str) -> None:
    requested = params.get("sessionId")
    if requested is not None and requested != session_id:
        raise ValueError(f"ACP session mismatch: {requested}")


def _tool_kind(event_type: str) -> str:
    if event_type == "file/write":
        return "edit"
    if event_type == "permission/request":
        return "other"
    return "execute"


def _tool_status(status: str) -> str:
    if status in {"pending", "in_progress", "completed", "failed"}:
        return status
    if status == "running":
        return "in_progress"
    if status == "succeeded":
        return "completed"
    return "completed"


def _locations(payload: dict[str, Any], projection: dict[str, Any]) -> list[dict[str, str]]:
    paths = payload.get("paths") or projection.get("paths") or []
    if isinstance(payload.get("path"), str):
        paths = [payload["path"], *paths]
    if not isinstance(paths, list):
        return []
    return [{"path": path} for path in paths if isinstance(path, str) and path]
