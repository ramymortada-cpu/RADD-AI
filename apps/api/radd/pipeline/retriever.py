from __future__ import annotations
"""
Hybrid retrieval: Qdrant vector search + PostgreSQL BM25 + Reciprocal Rank Fusion.
Returns top-k ranked passages with scores.
"""
import uuid
from dataclasses import dataclass, field

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from radd.knowledge.embedder import collection_name, embed_texts

logger = structlog.get_logger()

VECTOR_TOP_K = 10
BM25_TOP_K = 10
RRF_K = 60          # RRF constant — higher = less emphasis on top ranks
FINAL_TOP_K = 5


@dataclass
class RetrievedPassage:
    chunk_id: str
    document_id: str
    content: str
    score: float                          # RRF-fused score (0-1)
    vector_rank: int | None = None
    bm25_rank: int | None = None
    metadata: dict = field(default_factory=dict)


async def retrieve(
    query: str,
    workspace_id: uuid.UUID,
    db: AsyncSession,
    qdrant: AsyncQdrantClient,
    top_k: int = FINAL_TOP_K,
) -> tuple[list[RetrievedPassage], float]:
    """
    Hybrid retrieval for a query against a workspace KB.
    Returns (passages, C_retrieval) where C_retrieval = top passage score.
    """
    vector_results: dict[str, tuple[str, str, float]] = {}  # chunk_id → (content, doc_id, score)
    bm25_results: dict[str, tuple[str, str, float]] = {}

    # ── 1. Vector search (Qdrant) ─────────────────────────────────────────────
    try:
        embeddings = await embed_texts([query])
        query_vector = embeddings[0]
        cname = collection_name(workspace_id)

        hits = await qdrant.search(
            collection_name=cname,
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="workspace_id", match=MatchValue(value=str(workspace_id)))]
            ),
            limit=VECTOR_TOP_K,
            with_payload=True,
        )
        for hit in hits:
            chunk_id = hit.payload.get("chunk_id", str(hit.id))
            doc_id = hit.payload.get("document_id", "")
            content = hit.payload.get("content_preview", "")
            vector_results[chunk_id] = (content, doc_id, hit.score)

    except Exception as e:
        logger.warning("retriever.vector_failed", error=str(e))

    # ── 2. BM25 search (PostgreSQL FTS) ──────────────────────────────────────
    try:
        # Use 'simple' dictionary for Arabic (no stemmer needed; normalized text)
        bm25_query = await db.execute(
            text("""
                SELECT
                    kc.id::text AS chunk_id,
                    kc.document_id::text AS document_id,
                    kc.content,
                    ts_rank_cd(kc.tsv, plainto_tsquery('simple', :query)) AS score
                FROM kb_chunks kc
                WHERE kc.workspace_id = :workspace_id
                  AND kc.is_active = true
                  AND kc.tsv @@ plainto_tsquery('simple', :query)
                ORDER BY score DESC
                LIMIT :limit
            """),
            {
                "query": query,
                "workspace_id": str(workspace_id),
                "limit": BM25_TOP_K,
            },
        )
        for row in bm25_query.fetchall():
            bm25_results[row.chunk_id] = (row.content, row.document_id, float(row.score))

    except Exception as e:
        logger.warning("retriever.bm25_failed", error=str(e))

    # ── 3. Load full content for vector results (payload may be truncated) ────
    all_chunk_ids = list(set(vector_results.keys()) | set(bm25_results.keys()))
    if all_chunk_ids:
        try:
            rows = await db.execute(
                text("""
                    SELECT id::text, content, document_id::text
                    FROM kb_chunks
                    WHERE workspace_id = :workspace_id
                      AND id = ANY(:ids::uuid[])
                      AND is_active = true
                """),
                {"workspace_id": str(workspace_id), "ids": all_chunk_ids},
            )
            for row in rows.fetchall():
                if row.id in vector_results:
                    _, doc_id, score = vector_results[row.id]
                    vector_results[row.id] = (row.content, row.document_id, score)
                if row.id in bm25_results:
                    _, doc_id, score = bm25_results[row.id]
                    bm25_results[row.id] = (row.content, row.document_id, score)
        except Exception as e:
            logger.warning("retriever.content_load_failed", error=str(e))

    # ── 4. RRF fusion ─────────────────────────────────────────────────────────
    vector_ranking = {cid: rank + 1 for rank, cid in enumerate(vector_results.keys())}
    bm25_ranking = {cid: rank + 1 for rank, cid in enumerate(bm25_results.keys())}
    all_ids = set(vector_ranking.keys()) | set(bm25_ranking.keys())

    rrf_scores: dict[str, float] = {}
    for cid in all_ids:
        v_rank = vector_ranking.get(cid, VECTOR_TOP_K + 1)
        b_rank = bm25_ranking.get(cid, BM25_TOP_K + 1)
        rrf_scores[cid] = 1 / (RRF_K + v_rank) + 1 / (RRF_K + b_rank)

    # Normalize RRF scores to 0–1
    max_score = max(rrf_scores.values()) if rrf_scores else 1.0
    if max_score > 0:
        rrf_scores = {cid: s / max_score for cid, s in rrf_scores.items()}

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    # ── 5. Build result ───────────────────────────────────────────────────────
    passages: list[RetrievedPassage] = []
    for chunk_id, score in ranked:
        content, doc_id = "", ""
        if chunk_id in vector_results:
            content, doc_id, _ = vector_results[chunk_id]
        elif chunk_id in bm25_results:
            content, doc_id, _ = bm25_results[chunk_id]

        passages.append(RetrievedPassage(
            chunk_id=chunk_id,
            document_id=doc_id,
            content=content,
            score=score,
            vector_rank=vector_ranking.get(chunk_id),
            bm25_rank=bm25_ranking.get(chunk_id),
        ))

    c_retrieval = passages[0].score if passages else 0.0

    logger.info(
        "retriever.complete",
        query_preview=query[:50],
        passages=len(passages),
        c_retrieval=round(c_retrieval, 3),
        vector_hits=len(vector_results),
        bm25_hits=len(bm25_results),
    )

    return passages, c_retrieval
