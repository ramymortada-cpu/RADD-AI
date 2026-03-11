from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from radd.auth.middleware import CurrentUser, require_admin, require_agent, require_reviewer
from radd.db.session import get_db_session
from radd.knowledge import service
from radd.knowledge.schemas import (
    KBDocumentCreate,
    KBDocumentDetail,
    KBDocumentList,
    KBDocumentResponse,
    KBDocumentUpdate,
    KBChunkResponse,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
)

router = APIRouter(prefix="/kb", tags=["knowledge"])


# ─── Documents ────────────────────────────────────────────────────────────────

@router.get("/documents", response_model=KBDocumentList)
async def list_documents(
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    async with get_db_session(current.workspace_id) as db:
        docs, total = await service.list_documents(
            db, current.workspace_id, status=status_filter, page=page, page_size=page_size
        )
    return KBDocumentList(
        items=[KBDocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{doc_id}", response_model=KBDocumentDetail)
async def get_document(
    doc_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    async with get_db_session(current.workspace_id) as db:
        doc = await service.get_document(db, current.workspace_id, doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        chunk_count = await service.get_chunk_count(db, doc_id)

    resp = KBDocumentDetail.model_validate(doc)
    resp.chunk_count = chunk_count
    return resp


@router.post("/documents", response_model=KBDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: KBDocumentCreate,
    background_tasks: BackgroundTasks,
    current: Annotated[CurrentUser, Depends(require_agent)],
):
    async with get_db_session(current.workspace_id) as db:
        doc = await service.create_document(db, current.workspace_id, current.user.id, body)
        doc_id = doc.id

    return KBDocumentResponse.model_validate(doc)


@router.patch("/documents/{doc_id}", response_model=KBDocumentResponse)
async def update_document(
    doc_id: uuid.UUID,
    body: KBDocumentUpdate,
    current: Annotated[CurrentUser, Depends(require_agent)],
):
    async with get_db_session(current.workspace_id) as db:
        doc = await service.get_document(db, current.workspace_id, doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        doc = await service.update_document(db, doc, body)
    return KBDocumentResponse.model_validate(doc)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    async with get_db_session(current.workspace_id) as db:
        doc = await service.get_document(db, current.workspace_id, doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        await service.soft_delete_document(db, doc)


@router.post("/documents/{doc_id}/approve", response_model=KBDocumentResponse)
async def approve_document(
    doc_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """
    Approve a KB document for use in RAG responses.
    Triggers background indexing (chunking + embedding + Qdrant upsert).
    """
    async with get_db_session(current.workspace_id) as db:
        doc = await service.get_document(db, current.workspace_id, doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if doc.status not in ("draft", "review"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve document with status '{doc.status}'",
            )
        doc = await service.approve_document(db, doc, current.user.id)

    # Trigger async indexing
    from radd.workers.kb_indexer import index_document
    background_tasks.add_task(index_document, str(doc_id), str(current.workspace_id))

    return KBDocumentResponse.model_validate(doc)


# ─── Templates ────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    intent_id: str | None = None,
):
    async with get_db_session(current.workspace_id) as db:
        templates = await service.list_templates(db, current.workspace_id, intent_id)
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    async with get_db_session(current.workspace_id) as db:
        template = await service.create_template(db, current.workspace_id, body)
    return TemplateResponse.model_validate(template)


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    from sqlalchemy import select
    from radd.db.models import ResponseTemplate
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(ResponseTemplate).where(
                ResponseTemplate.id == template_id,
                ResponseTemplate.workspace_id == current.workspace_id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        template = await service.update_template(db, template, body)
    return TemplateResponse.model_validate(template)
