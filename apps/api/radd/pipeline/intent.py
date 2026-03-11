"""
Intent classifier v0 — keyword + TF-IDF matching.
6 intents: greeting, order_status, shipping, return_policy, store_hours, other.
v1 (Sprint 2): replace with AraBERT fine-tuned.
"""
from dataclasses import dataclass

# ─── Intent keyword vocabulary (normalized Arabic) ───────────────────────────

INTENT_KEYWORDS: dict[str, list[str]] = {
    "greeting": [
        "مرحبا", "السلام", "هلا", "هلو", "اهلا", "صباح", "مساء",
        "السلام عليكم", "وعليكم", "كيف حالك", "كيفك", "كيفكم",
        "مرحبتين", "يسلمو", "هاي", "تصبحون", "أهلين", "اهلين",
        "تحيه", "يسعد", "مساك", "صباحك",
    ],
    "order_status": [
        "طلب", "طلبي", "وين طلبي", "تتبع", "رقم الطلب", "اين طلبي",
        "متى وصل", "متى يوصل طلبي", "طلبي فين", "ما وصل طلبي",
        "اوردر", "تتبع الطلب", "حالة الطلب", "استفسار طلب",
        "طلبتي", "طلبات", "شحنتي", "تتبع شحن", "تتبع طلب",
    ],
    "shipping": [
        "شحن", "توصيل", "يوصل", "الشحن", "موعد التوصيل",
        "مدة التوصيل", "توصيل سريع", "شحن مجاني",
        "الشركة الشاحنة", "ارامكس", "سمسا", "دي اتش",
        "توصلون", "توصلوا", "توصلولي", "توصلونلي",
        "بيوصل", "يوصلكم", "توصيلكم", "الشحنه", "شحنة",
        "كم يوم يوصل", "مدة الشحن", "سعر الشحن", "رسوم الشحن",
    ],
    "return_policy": [
        "ارجاع", "إرجاع", "استرجاع", "رد المبلغ", "استرداد",
        "تبديل", "مرتجع", "شروط الارجاع", "سياسة الارجاع",
        "مدة الارجاع", "رفوند", "refund",
        "ارجع", "أرجع", "يرجع", "ترجع", "ترجعون", "ترجعوا",
        "ارجعه", "ارجعها", "ارجع بضاعه", "ارجع بضاعة",
        "استبدل", "استبدال", "تبديل المنتج",
        "مكسور", "معيب", "خطا", "غلط منتج", "مش صح",
        "عايز ارجع", "ابغى ارجع", "ابي ارجع",
        "المبلغ يرجع", "رجعوا فلوس",
    ],
    "store_hours": [
        "ساعات", "دوام", "مواعيد", "اوقات العمل",
        "وقت العمل", "الدوام", "ساعات العمل", "الاوقات",
        "مفتوحين", "مفتوح", "تفتحون", "تفتح", "تغلقون", "تغلق",
        "تشتغلون", "تشتغل", "دوامكم", "دوامهم",
        "اوقات الرد", "متى ترد", "هتردوا", "امتى تردوا",
        "خدمة عملاء الوقت", "وقت الدعم", "ساعة خدمة",
        "٢٤ ساعه", "٢٤ ساعة", "٢٤ساعة", "الليل",
        "جمعه", "جمعة", "الويكند", "عطلة",
    ],
}


@dataclass
class IntentResult:
    intent: str   # greeting | order_status | shipping | return_policy | store_hours | other
    confidence: float
    matched_keywords: list[str]


def classify_intent(text: str) -> IntentResult:
    """
    Keyword-based intent classification on normalized Arabic text.
    Returns intent + confidence score.

    Scoring:
    - Exact full-phrase match: 1.0
    - Multiple keyword matches: 0.85
    - Single keyword match: 0.70
    - No match: other at 0.30
    """
    words = text.split()
    text_lower = text.lower()

    best_intent = "other"
    best_score = 0.30
    best_matches: list[str] = []

    for intent, keywords in INTENT_KEYWORDS.items():
        matches = []
        for kw in keywords:
            if kw in text_lower:
                matches.append(kw)

        if not matches:
            continue

        # Score based on match count and phrase specificity
        if len(matches) >= 3:
            score = 0.95
        elif len(matches) == 2:
            score = 0.85
        else:
            # Single match: higher confidence for longer/more specific keywords
            score = 0.90 if len(matches[0]) > 5 else 0.70

        if score > best_score:
            best_score = score
            best_intent = intent
            best_matches = matches

    return IntentResult(intent=best_intent, confidence=best_score, matched_keywords=best_matches)
