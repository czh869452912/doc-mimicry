from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.response_models import DocTypeSummaryResponse


def create_doctypes_router(root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/doc-types", response_model=list[DocTypeSummaryResponse])
    def doc_types() -> list[dict[str, Any]]:
        return list_doc_types(root / "doc-types")

    @router.get("/doc-types/{doc_type_id}", response_model=DocTypeSummaryResponse)
    def doc_type_detail(doc_type_id: str) -> dict[str, Any]:
        detail = get_doc_type(root / "doc-types", doc_type_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        return detail

    return router
