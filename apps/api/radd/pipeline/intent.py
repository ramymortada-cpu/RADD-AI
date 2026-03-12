"""RADD AI — Intent Classifier v0.2 — 9 intents (6 original + 3 pre-purchase)"""
import re
from dataclasses import dataclass, field


@dataclass
class IntentResult:
    intent: str
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    is_pre_purchase: bool = False


INTENT_KEYWORDS = {
    "greeting": {
        "keywords": ["مرحبا", "هلا", "السلام عليكم", "سلام", "اهلا", "صباح الخير", "مساء الخير", "حياك", "كيفك"],
        "weight": 1.0,
    },
    "order_status": {
        "keywords": ["طلب", "طلبي", "رقم الطلب", "اين طلبي", "وين طلبي", "حالة الطلب", "تتبع", "tracking",
                     "وصل", "ماوصل", "ما وصل", "توصيل", "متى يوصل", "رقم التتبع", "شحنة", "شحنتي", "طلبيتي"],
        "weight": 1.2,
    },
    "shipping": {
        "keywords": ["شحن", "توصيل", "كم يوم", "متى توصل", "مدة الشحن", "مناطق الشحن", "رسوم الشحن",
                     "شحن مجاني", "ارامكس", "سمسا", "dhl", "smsa", "الشحن كم", "تكلفة الشحن"],
        "weight": 1.0,
    },
    "return_policy": {
        "keywords": ["ارجاع", "استرجاع", "ابي ارجع", "ابغى ارجع", "ارجع", "رجوع", "استبدال", "تبديل",
                     "ابدل", "ابي ابدل", "ابغى ابدل", "سياسة الارجاع", "ضمان", "مرتجع",
                     "ابي فلوسي", "استرداد", "رد المبلغ"],
        "weight": 1.1,
    },
    "store_hours": {
        "keywords": ["مواعيد", "ساعات العمل", "متى تفتحون", "متى تقفلون", "وقت الدوام", "اوقات العمل",
                     "الفرع", "العنوان"],
        "weight": 0.9,
    },
    "product_inquiry": {
        "keywords": ["عندكم", "متوفر", "موجود", "كم سعر", "بكم", "السعر", "تفاصيل", "مواصفات",
                     "الوان", "احجام", "مقاسات", "انواع", "كم سعره", "بكم هذا", "ابغى هذا"],
        "weight": 1.0,
        "is_pre_purchase": True,
    },
    "product_comparison": {
        "keywords": ["الفرق", "ايهم افضل", "مقارنة", "افضل", "احسن", "الفرق بين", "وش الفرق",
                     "ايش الفرق", "تنصحني", "تنصحوني", "وش تنصح", "ايهم"],
        "weight": 1.0,
        "is_pre_purchase": True,
    },
    "purchase_hesitation": {
        "keywords": ["غالي", "غالية", "بفكر", "افكر", "خصم", "عرض", "تخفيض", "كوبون", "كود خصم",
                     "بالتقسيط", "تمارا", "تابي", "مضمون", "اصلي", "رخيص"],
        "weight": 1.0,  # raised from 0.9 so single match ≥ 0.70
        "is_pre_purchase": True,
    },
}

TEMPLATE_INTENTS = {"greeting", "order_status", "shipping", "return_policy", "store_hours"}
PRE_PURCHASE_INTENTS = {"product_inquiry", "product_comparison", "purchase_hesitation"}

# Strip Arabic/Latin punctuation before building the word set
_PUNCT_RE = re.compile(r"[،؛؟!?.،,;:\-\"'()[\]{}]")


def classify_intent(text: str) -> IntentResult:
    if not text:
        return IntentResult("general", 0.3)

    text_lower = text.lower()
    # Remove punctuation so "خصم؟" matches keyword "خصم"
    cleaned = _PUNCT_RE.sub(" ", text_lower)
    words = set(cleaned.split())

    best_intent, best_score, best_matches, best_pp = "general", 0.0, [], False

    for name, cfg in INTENT_KEYWORDS.items():
        matches = []
        for kw in cfg["keywords"]:
            if " " in kw:
                if kw in text_lower:
                    matches.append(kw)
            elif kw in words:
                matches.append(kw)
        if matches:
            # Base 0.55 ensures single match with weight=1.0 → 0.55+0.15 = 0.70
            score = min(0.98, 0.55 + len(matches) * cfg["weight"] * 0.15)
            if score > best_score:
                best_score, best_intent, best_matches = score, name, matches
                best_pp = cfg.get("is_pre_purchase", False)

    if best_score == 0.0:
        return IntentResult("general", 0.3)
    return IntentResult(best_intent, round(best_score, 3), best_matches, best_pp)
