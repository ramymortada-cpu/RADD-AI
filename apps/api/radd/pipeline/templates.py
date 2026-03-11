from __future__ import annotations
"""
Template response engine.
5 intents × 3 dialects (gulf, egyptian, msa) = 15 base templates.
Parameters: {customer_name}, {order_number}, {store_name}.
"""
from dataclasses import dataclass
from string import Formatter

# ─── Template store ───────────────────────────────────────────────────────────
# Format: TEMPLATES[intent][dialect] = template string

TEMPLATES: dict[str, dict[str, str]] = {
    "greeting": {
        "gulf": "أهلاً وسهلاً! كيف أقدر أساعدك اليوم؟",
        "egyptian": "أهلاً بيك! إزيك؟ إيه اللي تحتاجه النهارده؟",
        "msa": "أهلاً وسهلاً! كيف يمكنني مساعدتك اليوم؟",
    },
    "order_status": {
        "gulf": "تفضل، تقدر تتابع طلبك رقم {order_number} من خلال الرابط اللي راح يوصلك، أو حياك هنا وأساعدك. وش رقم طلبك؟",
        "egyptian": "حاضر، عشان أعرف أساعدك في طلبك، ممكن تديني رقم الطلب؟",
        "msa": "بكل سرور، لمتابعة طلبك يرجى تزويدنا برقم الطلب.",
    },
    "shipping": {
        "gulf": "التوصيل يوصلك خلال ٢-٤ أيام عمل. الشحن مجاني للطلبات فوق ٢٠٠ ريال. تحتاج تفاصيل أكثر؟",
        "egyptian": "التوصيل بيوصلك في ٢-٤ أيام شغل. الشحن مجاني للطلبات فوق ٢٠٠ ريال. محتاج تفاصيل تانية؟",
        "msa": "يتم التوصيل خلال ٢-٤ أيام عمل. الشحن مجاني للطلبات التي تتجاوز ٢٠٠ ريال. هل تحتاج معلومات إضافية؟",
    },
    "return_policy": {
        "gulf": "سياسة الإرجاع عندنا: تقدر ترجع أي منتج خلال ١٤ يوم من تاريخ الاستلام بشرط يكون بحالته الأصلية. كيف أقدر أساعدك؟",
        "egyptian": "إحنا بنقبل الإرجاع في خلال ١٤ يوم من الاستلام، بشرط المنتج يكون زي ما اتسلمته. محتاج مساعدة تانية؟",
        "msa": "يمكن إرجاع المنتجات خلال ١٤ يوماً من تاريخ الاستلام بشرط أن تكون بحالتها الأصلية. هل يمكنني مساعدتك بشيء آخر؟",
    },
    "store_hours": {
        "gulf": "متجرنا الإلكتروني متاح ٢٤/٧. فريق خدمة العملاء متاح من ٩ الصبح لـ١٠ الليل كل أيام الأسبوع.",
        "egyptian": "متجرنا أونلاين متاح ٢٤ ساعة كل يوم. فريق خدمة العملاء من الساعة ٩ الصبح لـ١٠ بالليل طول الأسبوع.",
        "msa": "متجرنا الإلكتروني متاح على مدار الساعة. فريق خدمة العملاء متاح من ٩ صباحاً حتى ١٠ مساءً طوال أيام الأسبوع.",
    },
}

ESCALATION_MESSAGES: dict[str, str] = {
    "gulf": "سأحولك لأحد فريقنا لمساعدتك. انتظر لحظة.",
    "egyptian": "هحولك لحد من فريقنا يساعدك. لحظة من فضلك.",
    "msa": "سأحولك إلى أحد أعضاء فريقنا لمساعدتك. يرجى الانتظار.",
}

UNSUPPORTED_MEDIA_MESSAGE = "عذراً، حالياً نقدر نساعدك بالرسائل النصية فقط. إرسل رسالتك نصياً وسنرد عليك فوراً."


@dataclass
class TemplateResult:
    text: str
    intent: str
    dialect: str
    template_key: str
    parameters_used: dict[str, str]


def render_template(
    intent: str,
    dialect: str,
    parameters: dict[str, str] | None = None,
) -> TemplateResult | None:
    """
    Render a template for the given intent and dialect.
    Returns None if no template exists for this intent/dialect.
    """
    dialect_map = TEMPLATES.get(intent)
    if not dialect_map:
        return None

    template = dialect_map.get(dialect) or dialect_map.get("msa")
    if not template:
        return None

    params = parameters or {}
    try:
        text = template.format(**params)
    except KeyError as e:
        # Missing parameter — use template as-is with placeholder unfilled
        text = template

    return TemplateResult(
        text=text,
        intent=intent,
        dialect=dialect,
        template_key=f"{intent}.{dialect}",
        parameters_used=params,
    )


def get_escalation_message(dialect: str) -> str:
    return ESCALATION_MESSAGES.get(dialect, ESCALATION_MESSAGES["msa"])


def is_template_intent(intent: str) -> bool:
    return intent in TEMPLATES
