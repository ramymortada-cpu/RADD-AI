from __future__ import annotations
"""
Embedding generator using OpenAI text-embedding-3-small.
Batch embeds chunks and upserts into Qdrant per-workspace collection.
"""
import uuid
from typing import Any

import structlog
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from radd.config import settings

logger = structlog.get_logger()

EMBEDDING_DIM = 1536
QDRANT_COLLECTION_PREFIX = "kb_"
BATCH_SIZE = 50  # OpenAI embedding batch limit


def collection_name(workspace_id: uuid.UUID) -> str:
    return f"{QDRANT_COLLECTION_PREFIX}{str(workspace_id).replace('-', '_')}"


async def ensure_collection(qdrant: AsyncQdrantClient, workspace_id: uuid.UUID) -> None:
    """Create Qdrant collection for workspace if it doesn't exist."""
    cname = collection_name(workspace_id)
    existing = await qdrant.get_collections()
    existing_names = {c.name for c in existing.collections}

    if cname not in existing_names:
        await qdrant.create_collection(
            collection_name=cname,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info("qdrant.collection_created", collection=cname)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using OpenAI text-embedding-3-small."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = await client.embeddings.create(
            model=settings.openai_embedding_model,
            input=batch,
            encoding_format="float",
        )
        embeddings.extend([item.embedding for item in response.data])

    return embeddings


async def upsert_chunks(
    qdrant: AsyncQdrantClient,
    workspace_id: uuid.UUID,
    chunk_ids: list[uuid.UUID],
    chunk_contents: list[str],
    document_id: uuid.UUID,
    extra_payloads: list[dict] | None = None,
) -> list[str]:
    """
    Embed chunks and upsert into Qdrant.
    Returns list of Qdrant point IDs (= chunk_id strings).
    """
    await ensure_collection(qdrant, workspace_id)
    cname = collection_name(workspace_id)

    embeddings = await embed_texts(chunk_contents)

    points = []
    point_ids = []
    for chunk_id, content, embedding, idx in zip(chunk_ids, chunk_contents, embeddings, range(len(chunk_ids))):
        pid = str(chunk_id)
        payload: dict[str, Any] = {
            "chunk_id": pid,
            "document_id": str(document_id),
            "workspace_id": str(workspace_id),
            "content_preview": content[:200],
        }
        if extra_payloads and idx < len(extra_payloads):
            payload.update(extra_payloads[idx])

        points.append(PointStruct(id=pid, vector=embedding, payload=payload))
        point_ids.append(pid)

    await qdrant.upsert(collection_name=cname, points=points)
    logger.info("qdrant.chunks_upserted", count=len(points), collection=cname)
    return point_ids


async def delete_document_chunks(
    qdrant: AsyncQdrantClient,
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    """Remove all Qdrant points for a given document."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    cname = collection_name(workspace_id)
    await qdrant.delete(
        collection_name=cname,
        points_selector=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=str(document_id)))]
        ),
    )
    logger.info("qdrant.document_deleted", document_id=str(document_id), collection=cname)
