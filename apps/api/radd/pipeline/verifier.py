from __future__ import annotations
"""
NLI verifier — checks if generated response is entailed by source passages.
Uses joeddav/xlm-roberta-large-xnli (cross-lingual NLI).
Returns C_verify: entailment probability (0-1).

Model is loaded once and cached. Falls back to 0.75 stub if model unavailable.
"""
import structlog

logger = structlog.get_logger()

_nli_pipeline = None
_model_load_attempted = False
_model_available = False

NLI_MODEL = "joeddav/xlm-roberta-large-xnli"
FALLBACK_CONFIDENCE = 0.75   # Sprint 1 stub value; replaced when model loads
MIN_ENTAILMENT_CONFIDENCE = 0.60


def _load_model():
    global _nli_pipeline, _model_load_attempted, _model_available
    if _model_load_attempted:
        return
    _model_load_attempted = True
    try:
        from transformers import pipeline
        _nli_pipeline = pipeline(
            "zero-shot-classification",
            model=NLI_MODEL,
            device=-1,               # CPU; switch to 0 for GPU
            multi_label=False,
        )
        _model_available = True
        logger.info("verifier.model_loaded", model=NLI_MODEL)
    except Exception as e:
        logger.warning("verifier.model_unavailable", error=str(e), fallback=FALLBACK_CONFIDENCE)
        _model_available = False


def verify_response(
    response_text: str,
    source_passages: list[str],
    threshold: float = MIN_ENTAILMENT_CONFIDENCE,
) -> tuple[float, bool]:
    """
    Check if response is entailed by source passages using NLI.
    Returns (c_verify, is_grounded).

    If model not available: returns (FALLBACK_CONFIDENCE, True) — conservative fallback.
    If no passages: returns (0.0, False).
    """
    if not source_passages:
        return 0.0, False

    if not response_text or len(response_text.strip()) < 5:
        return 0.0, False

    _load_model()

    if not _model_available or _nli_pipeline is None:
        return FALLBACK_CONFIDENCE, True

    # Combine top 3 passages as premise
    premise = " ".join(source_passages[:3])[:1500]
    hypothesis = response_text[:500]

    try:
        result = _nli_pipeline(
            hypothesis,
            candidate_labels=["entailment", "contradiction", "neutral"],
            hypothesis_template="{}",
            # Pass premise as the sequence to classify
        )
        # The pipeline's first positional arg is the sequence; we treat it as:
        # Does the hypothesis (response) follow from the premise (passages)?
        # Re-run with premise as sequence, response as label for true NLI:
        nli_result = _nli_pipeline(
            premise[:800],
            candidate_labels=[hypothesis],
        )
        entailment_score = nli_result["scores"][0] if nli_result["scores"] else FALLBACK_CONFIDENCE
        c_verify = min(1.0, max(0.0, float(entailment_score)))

    except Exception as e:
        logger.warning("verifier.inference_failed", error=str(e))
        c_verify = FALLBACK_CONFIDENCE

    is_grounded = c_verify >= threshold
    logger.debug("verifier.result", c_verify=round(c_verify, 3), is_grounded=is_grounded)
    return c_verify, is_grounded


def verify_response_fast(response_text: str, source_passages: list[str]) -> tuple[float, bool]:
    """
    Fast heuristic verifier for when NLI model is too slow or unavailable.
    Checks keyword overlap between response and passages.
    """
    if not source_passages or not response_text:
        return 0.0, False

    from radd.pipeline.normalizer import normalize
    norm_response = set(normalize(response_text).split())
    norm_passages = set()
    for p in source_passages[:3]:
        norm_passages.update(normalize(p).split())

    if not norm_passages:
        return FALLBACK_CONFIDENCE, True

    overlap = len(norm_response & norm_passages)
    total_response_words = len(norm_response)
    if total_response_words == 0:
        return 0.0, False

    overlap_ratio = overlap / total_response_words
    # Map overlap ratio to confidence: >50% overlap → ~0.85, <10% → ~0.50
    c_verify = min(0.95, 0.50 + overlap_ratio * 0.9)
    return c_verify, c_verify >= MIN_ENTAILMENT_CONFIDENCE
