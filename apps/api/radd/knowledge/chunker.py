"""
Document chunker.
Splits Arabic KB documents at semantic boundaries (paragraphs, sections).
Target: 200–500 tokens per chunk. Never split mid-sentence.
"""
import re
from dataclasses import dataclass

from radd.pipeline.normalizer import normalize

# Rough Arabic token estimate: 1 token ≈ 4 characters
CHARS_PER_TOKEN = 4
MIN_CHUNK_TOKENS = 100
MAX_CHUNK_TOKENS = 500
TARGET_CHUNK_TOKENS = 300


@dataclass
class Chunk:
    content: str
    content_normalized: str
    chunk_index: int
    token_count: int


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _split_into_sentences(text: str) -> list[str]:
    """Split Arabic text at sentence boundaries."""
    # Arabic sentence-ending punctuation: . ؟ ! \n\n
    parts = re.split(r"(?<=[.؟!])\s+|(?:\n{2,})", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_into_paragraphs(text: str) -> list[str]:
    """Split at double newlines first (structural boundaries)."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_document(content: str) -> list[Chunk]:
    """
    Chunk a document into semantic segments.
    Strategy:
    1. Split at paragraph boundaries (double newlines).
    2. If paragraph > MAX_CHUNK_TOKENS, further split at sentence boundaries.
    3. If paragraph < MIN_CHUNK_TOKENS, merge with next paragraph.
    4. Normalize each chunk for FTS indexing.
    """
    paragraphs = _split_into_paragraphs(content)
    raw_chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)

        if para_tokens > MAX_CHUNK_TOKENS:
            # Flush buffer first
            if buffer:
                raw_chunks.append(buffer.strip())
                buffer = ""
            # Split large paragraph at sentence level
            sentences = _split_into_sentences(para)
            sent_buffer = ""
            for sent in sentences:
                if _estimate_tokens(sent_buffer + " " + sent) > TARGET_CHUNK_TOKENS and sent_buffer:
                    raw_chunks.append(sent_buffer.strip())
                    sent_buffer = sent
                else:
                    sent_buffer = (sent_buffer + " " + sent).strip()
            if sent_buffer:
                raw_chunks.append(sent_buffer.strip())
        elif _estimate_tokens(buffer + "\n\n" + para) > TARGET_CHUNK_TOKENS and buffer:
            # Buffer would overflow — flush it
            raw_chunks.append(buffer.strip())
            buffer = para
        else:
            buffer = (buffer + "\n\n" + para).strip() if buffer else para

    if buffer:
        raw_chunks.append(buffer.strip())

    # Build Chunk objects
    chunks: list[Chunk] = []
    for i, raw in enumerate(raw_chunks):
        if not raw:
            continue
        chunks.append(Chunk(
            content=raw,
            content_normalized=normalize(raw),
            chunk_index=i,
            token_count=_estimate_tokens(raw),
        ))

    return chunks
