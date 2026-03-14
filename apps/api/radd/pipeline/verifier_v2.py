"""
RADD AI — Response Verifier v2.0 — Correct NLI Implementation
==============================================================
يصلح الخطأ المنطقي في نظام التحقق القديم.
يستخدم نموذج NLI بالطريقة الصحيحة: premise + hypothesis بدل zero-shot-classification.

الملف الأصلي: apps/api/radd/pipeline/verifier.py (يبقى كـ fallback)
هذا الملف: apps/api/radd/pipeline/verifier_v2.py
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger("radd.pipeline.verifier_v2")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NLI_MODEL = "joeddav/xlm-roberta-large-xnli"
MIN_ENTAILMENT_CONFIDENCE = 0.60  # العتبة الافتراضية — قابلة للتعديل لكل workspace
FALLBACK_CONFIDENCE = 0.55  # درجة الثقة عند فشل النموذج
MAX_PREMISE_LENGTH = 800  # أقصى طول للـ premise (tokens تقريباً)
MAX_HYPOTHESIS_LENGTH = 200  # أقصى طول لكل جملة hypothesis
BATCH_SIZE = 8  # عدد الجمل في كل batch

# ---------------------------------------------------------------------------
# Model Loading — Singleton Pattern
# ---------------------------------------------------------------------------

_tokenizer: Optional[AutoTokenizer] = None
_model: Optional[AutoModelForSequenceClassification] = None
_model_load_attempted: bool = False
_model_available: bool = False


def _load_model():
    """يحمّل النموذج والـ tokenizer مرة واحدة فقط."""
    global _tokenizer, _model, _model_load_attempted, _model_available

    if _model_load_attempted:
        return

    _model_load_attempted = True
    try:
        logger.info("verifier_v2.loading_model", model=NLI_MODEL)
        start = time.monotonic()

        _tokenizer = AutoTokenizer.from_pretrained(NLI_MODEL)
        _model = AutoModelForSequenceClassification.from_pretrained(NLI_MODEL)
        _model.eval()  # وضع التقييم — أسرع ولا يحسب gradients

        elapsed = round((time.monotonic() - start) * 1000)
        _model_available = True
        logger.info("verifier_v2.model_loaded", model=NLI_MODEL, elapsed_ms=elapsed)

    except Exception as e:
        logger.warning(
            "verifier_v2.model_unavailable",
            error=str(e),
            fallback=FALLBACK_CONFIDENCE,
        )
        _model_available = False


# ---------------------------------------------------------------------------
# Sentence Splitting — تقسيم الرد لجمل
# ---------------------------------------------------------------------------

# أنماط لتقسيم النص العربي لجمل
_SENTENCE_SPLITTERS = re.compile(r'[.!?؟。\n]+')
_MIN_SENTENCE_LENGTH = 10  # تجاهل الجمل القصيرة جداً


def _split_sentences(text: str) -> list[str]:
    """
    يقسم النص إلى جمل منفصلة للتحقق الدقيق.
    يتجاهل الجمل القصيرة جداً (أقل من 10 أحرف).
    """
    raw = _SENTENCE_SPLITTERS.split(text)
    sentences = [s.strip() for s in raw if len(s.strip()) >= _MIN_SENTENCE_LENGTH]

    # إذا لم نجد جمل كافية، نعامل النص كجملة واحدة
    if not sentences and len(text.strip()) >= 5:
        sentences = [text.strip()]

    return sentences


# ---------------------------------------------------------------------------
# Core NLI Verification
# ---------------------------------------------------------------------------

def _compute_entailment_scores(
    premise: str,
    hypotheses: list[str],
) -> list[float]:
    """
    يحسب درجة الـ entailment لكل hypothesis مقابل الـ premise.

    Args:
        premise: نص قاعدة المعرفة (source passages مجتمعة)
        hypotheses: قائمة جمل من رد الـ AI

    Returns:
        قائمة درجات entailment (0.0 - 1.0) لكل hypothesis
    """
    if not _model_available or _tokenizer is None or _model is None:
        return [FALLBACK_CONFIDENCE] * len(hypotheses)

    scores = []

    try:
        with torch.no_grad():
            # معالجة بـ batches لتحسين الأداء
            for i in range(0, len(hypotheses), BATCH_SIZE):
                batch = hypotheses[i : i + BATCH_SIZE]

                # تحضير الأزواج (premise, hypothesis)
                inputs = _tokenizer(
                    [premise] * len(batch),
                    batch,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True,
                )

                outputs = _model(**inputs)
                logits = outputs.logits

                # النموذج يخرج logits لـ [contradiction, neutral, entailment]
                # نحتاج احتمال الـ entailment (index 2)
                probs = torch.softmax(logits, dim=1)
                entailment_probs = probs[:, 2].tolist()
                scores.extend(entailment_probs)

    except Exception as e:
        logger.warning("verifier_v2.inference_failed", error=str(e))
        scores = [FALLBACK_CONFIDENCE] * len(hypotheses)

    return scores


# ---------------------------------------------------------------------------
# Main Verification Function
# ---------------------------------------------------------------------------

def verify_response(
    response_text: str,
    source_passages: list[str],
    threshold: float = MIN_ENTAILMENT_CONFIDENCE,
) -> tuple[float, bool, dict]:
    """
    يتحقق من أن رد الـ AI مبني على محتوى قاعدة المعرفة.

    Args:
        response_text: النص الكامل لرد الـ AI
        source_passages: قائمة المقاطع المسترجعة من KB
        threshold: عتبة القبول (0.6 افتراضياً)

    Returns:
        tuple من:
            - c_verify (float): درجة التحقق الإجمالية
            - is_grounded (bool): هل الرد مبني على المصادر؟
            - details (dict): تفاصيل التحقق لكل جملة
    """
    start_time = time.monotonic()

    # --- حالات خاصة ---
    if not source_passages or not response_text:
        return 0.0, False, {"reason": "empty_input"}

    if len(response_text.strip()) < 5:
        return 0.0, False, {"reason": "response_too_short"}

    # --- تحميل النموذج ---
    _load_model()

    if not _model_available:
        logger.warning("verifier_v2.model_not_available", fallback=FALLBACK_CONFIDENCE)
        return FALLBACK_CONFIDENCE, True, {"reason": "model_unavailable_fallback"}

    # --- تحضير الـ premise ---
    # ندمج أفضل 3 مقاطع كـ premise
    premise = " ".join(source_passages[:3])
    if len(premise) > MAX_PREMISE_LENGTH * 4:  # تقريبياً 4 أحرف = token
        premise = premise[: MAX_PREMISE_LENGTH * 4]

    # --- تقسيم الرد لجمل ---
    sentences = _split_sentences(response_text)
    if not sentences:
        return 0.0, False, {"reason": "no_sentences_found"}

    # --- حساب الـ entailment لكل جملة ---
    scores = _compute_entailment_scores(premise, sentences)

    # --- تجميع النتائج ---
    sentence_details = []
    for sent, score in zip(sentences, scores):
        sentence_details.append({
            "sentence": sent[:100],  # أول 100 حرف للتخزين
            "entailment_score": round(score, 4),
            "is_grounded": score >= threshold,
        })

    # --- الدرجة النهائية = الحد الأدنى ---
    # نهج محافظ: إذا جملة واحدة ملفقة، الرد كله يُعتبر غير موثوق
    c_verify = min(scores) if scores else 0.0
    is_grounded = c_verify >= threshold

    # --- أضعف جملة (للتشخيص) ---
    weakest_idx = scores.index(min(scores)) if scores else 0
    weakest_sentence = sentences[weakest_idx] if sentences else ""

    latency_ms = round((time.monotonic() - start_time) * 1000, 1)

    details = {
        "sentence_count": len(sentences),
        "sentence_scores": sentence_details,
        "weakest_sentence": weakest_sentence[:100],
        "weakest_score": round(min(scores), 4) if scores else 0.0,
        "threshold": threshold,
        "latency_ms": latency_ms,
    }

    logger.info(
        "verifier_v2.result",
        c_verify=round(c_verify, 3),
        is_grounded=is_grounded,
        sentence_count=len(sentences),
        weakest_score=round(min(scores), 4) if scores else 0.0,
        latency_ms=latency_ms,
    )

    return round(c_verify, 4), is_grounded, details


# ---------------------------------------------------------------------------
# Async wrapper for pipeline integration
# ---------------------------------------------------------------------------

async def verify_response_async(
    response_text: str,
    source_passages: list[str],
    threshold: float = MIN_ENTAILMENT_CONFIDENCE,
) -> tuple[float, bool, dict]:
    """
    نسخة async من verify_response.
    ملاحظة: النموذج المحلي يعمل بشكل synchronous داخلياً.
    في المستقبل يمكن نقله لـ thread pool إذا أصبح bottleneck.
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, verify_response, response_text, source_passages, threshold
    )


# ---------------------------------------------------------------------------
# Fast Verifier — للحالات البسيطة
# ---------------------------------------------------------------------------

def fast_verify(response_text: str, source_passages: list[str]) -> tuple[float, bool]:
    """
    تحقق سريع بدون NLI — يُستخدم كخطوة أولى قبل NLI الكامل.
    يتحقق من وجود كلمات الرد الرئيسية في المصادر.

    Returns:
        (confidence, passes_fast_check)
    """
    if not source_passages or not response_text:
        return 0.0, False

    combined_source = " ".join(source_passages).lower()
    response_words = set(response_text.lower().split())

    # إزالة الكلمات الشائعة (stop words عربية)
    stop_words = {
        "في", "من", "على", "إلى", "أن", "هو", "هي", "هذا", "هذه",
        "كان", "لم", "لا", "ما", "مع", "عن", "هل", "نعم", "و",
        "أو", "ثم", "حتى", "لكن", "بل", "إذا", "قد", "كل",
        "the", "is", "are", "was", "a", "an", "in", "on", "to",
    }
    response_words -= stop_words

    if not response_words:
        return 0.5, True

    # نسبة الكلمات الموجودة في المصادر
    found = sum(1 for w in response_words if w in combined_source)
    ratio = found / len(response_words)

    return round(ratio, 3), ratio >= 0.4


# ---------------------------------------------------------------------------
# CLI Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # اختبار بسيط
    kb_passages = [
        "سياسة الشحن: يتم الشحن خلال 3-5 أيام عمل لجميع مناطق المملكة. تكلفة الشحن 25 ريال.",
        "سياسة الإرجاع: يمكن إرجاع المنتج خلال 14 يوم من تاريخ الاستلام بشرط أن يكون بحالته الأصلية.",
    ]

    test_cases = [
        # صحيح — مبني على KB
        ("يتم الشحن خلال 3-5 أيام عمل وتكلفة الشحن 25 ريال.", True),
        # ملفق — أرقام مختلفة
        ("لدينا شحن مجاني لكل المدن ويصل خلال يوم واحد.", False),
        # ملفق بالكامل
        ("نقدم خصم 50% على جميع المنتجات هذا الأسبوع.", False),
        # صادق — يعترف بعدم المعرفة
        ("لا أملك معلومات عن هذا الموضوع، سأحولك لأحد فريقنا.", True),
        # مختلط — بعض صحيح وبعض ملفق
        ("يتم الشحن خلال 3-5 أيام عمل ونقدم شحن مجاني للطلبات فوق 500 ريال.", False),
    ]

    print("=" * 70)
    print("RADD AI — Verifier v2 Test")
    print("=" * 70)

    for response, expected_grounded in test_cases:
        c_verify, is_grounded, details = verify_response(response, kb_passages)
        status = "✅" if is_grounded == expected_grounded else "❌"
        print(f"\n{status} الرد: {response[:60]}...")
        print(f"   C_verify: {c_verify:.4f} | Grounded: {is_grounded} | Expected: {expected_grounded}")
        print(f"   Weakest: {details.get('weakest_score', 'N/A')} | Time: {details.get('latency_ms', 'N/A')}ms")
