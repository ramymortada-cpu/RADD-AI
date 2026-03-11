"""
KB indexer worker.
Triggered on document approval: chunk → embed → Qdrant upsert → DB update.
"""
import asyncio
import sys
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select, update

sys.path.insert(0, str(Path(__file__).parent.parent))

from radd.db.models import KBChunk, KBDocument
from radd.db.session import get_db_session
from radd.deps import get_qdrant
from radd.knowledge.chunker import chunk_document
from radd.knowledge.embedder import delete_document_chunks, upsert_chunks

logger = structlog.get_logger()


async def index_document(document_id: str, workspace_id: str) -> None:
    """
    Full indexing pipeline for one document:
    1. Load document content from DB.
    2. Deactivate + delete old chunks (for re-indexing).
    3. Chunk document.
    4. Store chunks in DB.
    5. Embed chunks and upsert into Qdrant.
    6. Update chunks with embedding_id.
    """
    doc_uuid = uuid.UUID(document_id)
    ws_uuid = uuid.UUID(workspace_id)
    qdrant = get_qdrant()

    logger.info("kb_indexer.start", document_id=document_id, workspace_id=workspace_id)

    # ── Load document ─────────────────────────────────────────────────────────
    async with get_db_session(ws_uuid) as db:
        result = await db.execute(
            select(KBDocument).where(KBDocument.id == doc_uuid, KBDocument.workspace_id == ws_uuid)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            logger.error("kb_indexer.document_not_found", document_id=document_id)
            return

        content = doc.content
        doc_id = doc.id

    # ── Delete old chunks from Qdrant ─────────────────────────────────────────
    try:
        await delete_document_chunks(qdrant, ws_uuid, doc_uuid)
    except Exception as e:
        logger.warning("kb_indexer.qdrant_delete_failed", error=str(e))

    # ── Chunk document ────────────────────────────────────────────────────────
    chunks = chunk_document(content)
    if not chunks:
        logger.warning("kb_indexer.no_chunks", document_id=document_id)
        return

    logger.info("kb_indexer.chunks_created", count=len(chunks), document_id=document_id)

    # ── Store chunks in DB + embed ────────────────────────────────────────────
    async with get_db_session(ws_uuid) as db:
        # Deactivate old chunks
        await db.execute(
            update(KBChunk)
            .where(KBChunk.document_id == doc_uuid, KBChunk.workspace_id == ws_uuid)
            .values(is_active=False)
        )

        # Insert new chunks
        new_chunks: list[KBChunk] = []
        for chunk in chunks:
            db_chunk = KBChunk(
                workspace_id=ws_uuid,
                document_id=doc_uuid,
                content=chunk.content,
                content_normalized=chunk.content_normalized,
                chunk_index=chunk.chunk_index,
                token_count=chunk.token_count,
                is_active=True,
            )
            db.add(db_chunk)
            new_chunks.append(db_chunk)

        await db.flush()
        chunk_ids = [c.id for c in new_chunks]
        chunk_contents = [c.content for c in chunks]

    # ── Embed and upsert to Qdrant ────────────────────────────────────────────
    try:
        point_ids = await upsert_chunks(
            qdrant=qdrant,
            workspace_id=ws_uuid,
            chunk_ids=chunk_ids,
            chunk_contents=chunk_contents,
            document_id=doc_uuid,
        )

        # Update embedding_id on each chunk
        async with get_db_session(ws_uuid) as db:
            for chunk_id, point_id in zip(chunk_ids, point_ids):
                await db.execute(
                    update(KBChunk)
                    .where(KBChunk.id == chunk_id)
                    .values(embedding_id=point_id)
                )

        logger.info(
            "kb_indexer.complete",
            document_id=document_id,
            chunks=len(chunks),
            points=len(point_ids),
        )

    except Exception as e:
        logger.error("kb_indexer.embedding_failed", error=str(e), document_id=document_id)
        # Mark document back to review so merchant knows indexing failed
        async with get_db_session(ws_uuid) as db:
            await db.execute(
                update(KBDocument)
                .where(KBDocument.id == doc_uuid)
                .values(status="review")
            )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python kb_indexer.py <document_id> <workspace_id>")
        sys.exit(1)
    asyncio.run(index_document(sys.argv[1], sys.argv[2]))
