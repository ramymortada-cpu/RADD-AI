"""
RADD AI — Pre-Purchase Sales Engine
Killer Feature #4: "رَدّ يبيع من داخل المحادثة"

+ Conversation Stage Tracking (from Respond.io Lifecycle concept)
+ Starter Packs (sector-based onboarding templates)
"""
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("radd.sales")


# ═══════════════════════════════════════════════
# CONVERSATION STAGES — Lifecycle Management
# ═══════════════════════════════════════════════

class ConversationStage(Enum):
    """مراحل دورة حياة المحادثة — مستوحى من Respond.io Lifecycle"""
    UNKNOWN = "unknown"
    INQUIRY = "inquiry"              # سؤال عام عن المنتج
    CONSIDERATION = "consideration"   # يقارن أو يسأل تفاصيل
    OBJECTION = "objection"          # يعترض (غالي، مو متأكد)
    PURCHASE_INTENT = "purchase_intent"  # مستعد للشراء
    CONVERTED = "converted"           # اشترى (confirmed via Salla webhook)
    POST_PURCHASE = "post_purchase"   # بعد الشراء (دعم)
    COMPLAINT = "complaint"           # شكوى
    RETURN_REQUEST = "return_request"  # طلب إرجاع
    RESOLVED = "resolved"             # تم الحل


def determine_stage(
    intent: str,
    is_pre_purchase: bool,
    message_text: str,
    conversation_turn: int,
    previous_stage: str = "unknown",
) -> ConversationStage:
    """
    Determine conversation stage based on intent, message, and history.
    Stages progress forward — inquiry → consideration → objection → intent → converted
    """
    # Post-purchase paths
    if intent == "return_policy":
        return ConversationStage.RETURN_REQUEST
    if intent in ("order_status", "shipping"):
        return ConversationStage.POST_PURCHASE

    # Complaint detection
    complaint_signals = ["شكوى", "بشتكي", "أسوأ", "خربان", "نصب", "غش"]
    if any(s in message_text for s in complaint_signals):
        return ConversationStage.COMPLAINT

    # Pre-purchase progression
    if not is_pre_purchase:
        if intent == "greeting":
            return ConversationStage.UNKNOWN
        return ConversationStage(previous_stage) if previous_stage != "unknown" else ConversationStage.UNKNOWN

    # Pre-purchase stage logic
    if intent == "product_inquiry":
        if previous_stage in ("consideration", "objection"):
            return ConversationStage(previous_stage)  # لا تتراجع
        return ConversationStage.INQUIRY

    if intent == "product_comparison":
        return ConversationStage.CONSIDERATION

    if intent == "purchase_hesitation":
        return ConversationStage.OBJECTION

    # Purchase intent signals
    purchase_signals = ["ابغى", "ابي", "اطلب", "اشتري", "خذه", "حطه بالسلة", "كيف اطلب"]
    if any(s in message_text for s in purchase_signals):
        return ConversationStage.PURCHASE_INTENT

    return ConversationStage.INQUIRY


# ═══════════════════════════════════════════════
# SALES ENGINE — Pre-Purchase Conversation Handler
# ═══════════════════════════════════════════════

@dataclass
class SalesResponse:
    response_text: str
    products_to_show: list[dict] = field(default_factory=list)
    follow_up_after_minutes: int | None = None  # جدولة متابعة
    stage: ConversationStage = ConversationStage.INQUIRY


class SalesEngine:
    """
    Handles pre-purchase conversations with sales intelligence.
    Uses Salla product data to show real products.
    """

    async def handle_inquiry(
        self,
        message: str,
        dialect: str,
        product_mentions: list[str],
        available_products: list[dict],
        customer_tier: str = "standard",
    ) -> SalesResponse:
        """Handle product inquiry — show matching products."""

        if not available_products:
            return SalesResponse(
                response_text=self._no_product_response(dialect, product_mentions),
                stage=ConversationStage.INQUIRY,
            )

        # Show top 3 matching products
        products_to_show = available_products[:3]

        response = self._format_product_list(products_to_show, dialect)

        # Recommendations engine (structure ready — activates when catalog available)
        try:
            from radd.sales.recommendations import Product, RecommendationEngine

            rec_engine = RecommendationEngine()
            # TODO: Load real catalog from Salla API or workspace products
            # rec_engine.load_catalog(workspace_products)

            # If we can identify the product being asked about:
            # identified_product = Product(
            #     id=str(p.get("id", "")),
            #     name=p.get("name", "منتج"),
            #     price=float(p.get("price", 0)),
            #     category=p.get("category", ""),
            #     tags=p.get("tags", []),
            #     in_stock=p.get("in_stock", True),
            # ) for p in products_to_show
            # recommendations = rec_engine.get_recommendations(
            #     current_product=identified_product,
            #     context="inquiry",
            #     dialect=dialect,
            # )
            # for r in recommendations:
            #     response += f"\n\n{r.reason_ar}"
        except Exception as e:
            logger.debug("Recommendations not available: %s", e)

        return SalesResponse(
            response_text=response,
            products_to_show=products_to_show,
            stage=ConversationStage.INQUIRY,
        )

    async def handle_comparison(
        self,
        message: str,
        dialect: str,
        products: list[dict],
    ) -> SalesResponse:
        """Handle product comparison."""
        if len(products) < 2:
            return SalesResponse(
                response_text=self._ask_which_products(dialect),
                stage=ConversationStage.CONSIDERATION,
            )

        p1, p2 = products[0], products[1]
        response = self._format_comparison(p1, p2, dialect)

        return SalesResponse(
            response_text=response,
            products_to_show=products[:2],
            stage=ConversationStage.CONSIDERATION,
        )

    async def handle_objection(
        self,
        message: str,
        dialect: str,
        objection_type: str,
        current_product: dict | None,
        alternatives: list[dict],
    ) -> SalesResponse:
        """Handle purchase objection (price, doubt, etc.)."""

        if "غالي" in message or "السعر" in message:
            return self._handle_price_objection(dialect, current_product, alternatives)

        if "مضمون" in message or "اصلي" in message or "تقليد" in message:
            return self._handle_trust_objection(dialect, current_product)

        if "بفكر" in message or "مو متاكد" in message:
            return self._handle_hesitation(dialect, current_product)

        # Generic objection
        responses = {
            "gulf": "فهمتك! وش الشي اللي يخليك تتردد؟ ممكن أساعدك تقرر.",
            "egyptian": "فهمتك! إيه اللي مخليك متردد؟ ممكن أساعدك تقرر.",
            "msa": "أفهمك! ما الذي يجعلك متردداً؟ يمكنني مساعدتك في اتخاذ القرار.",
        }
        return SalesResponse(
            response_text=responses.get(dialect, responses["gulf"]),
            stage=ConversationStage.OBJECTION,
            follow_up_after_minutes=120,
        )

    # ──── Follow-up Message ────

    def generate_follow_up(
        self,
        dialect: str,
        product_name: str = "",
        hours_since: int = 2,
    ) -> str:
        """Generate smart follow-up message for abandoned conversations."""
        responses = {
            "gulf": f"هلا مرة ثانية! {f'سألت عن {product_name}. لسه متوفر.' if product_name else 'شفت إنك كنت تتصفح منتجاتنا.'}\nتبي أساعدك بشي؟",
            "egyptian": f"أهلاً تاني! {f'سألت عن {product_name}. لسه متاح.' if product_name else 'شوفت إنك كنت بتتصفح منتجاتنا.'}\nمحتاج مساعدة في حاجة؟",
            "msa": f"مرحباً مجدداً! {f'كنت تسأل عن {product_name}. لا يزال متوفراً.' if product_name else ''}\nهل يمكنني مساعدتك؟",
        }
        return responses.get(dialect, responses["gulf"])

    # ──── Internal Formatting ────

    def _format_product_list(self, products: list[dict], dialect: str) -> str:
        intro = {
            "gulf": "عندنا الخيارات هذي:",
            "egyptian": "عندنا الخيارات دي:",
            "msa": "لدينا الخيارات التالية:",
        }

        lines = [intro.get(dialect, intro["gulf"]), ""]

        for i, p in enumerate(products, 1):
            name = p.get("name", "منتج")
            price = p.get("price", 0)
            in_stock = p.get("in_stock", True)
            stock_badge = "✅" if in_stock else "❌ نفد"

            line = f"{i}. {name} — {price} ر.س {stock_badge}"
            lines.append(line)

        ask = {
            "gulf": "\nتبي تعرف أكثر عن أي واحد؟",
            "egyptian": "\nعايز تعرف أكتر عن أي واحد؟",
            "msa": "\nهل تودّ معرفة المزيد عن أي منها؟",
        }
        lines.append(ask.get(dialect, ask["gulf"]))

        return "\n".join(lines)

    def _format_comparison(self, p1: dict, p2: dict, dialect: str) -> str:
        intro = {
            "gulf": "خلني أقارن لك بين الاثنين:",
            "egyptian": "خليني أقارنلك بين الاتنين:",
            "msa": "دعني أقارن بين الاثنين:",
        }

        lines = [
            intro.get(dialect, intro["gulf"]),
            "",
            f"🔹 {p1.get('name', 'المنتج الأول')}",
            f"   السعر: {p1.get('price', '?')} ر.س",
            f"   {p1.get('description', '')[:100]}",
            "",
            f"🔸 {p2.get('name', 'المنتج الثاني')}",
            f"   السعر: {p2.get('price', '?')} ر.س",
            f"   {p2.get('description', '')[:100]}",
        ]

        ask = {
            "gulf": "\nوش تميل له أكثر؟",
            "egyptian": "\nإيه اللي بتميل ليه أكتر؟",
            "msa": "\nأيهما تفضل؟",
        }
        lines.append(ask.get(dialect, ask["gulf"]))

        return "\n".join(lines)

    def _handle_price_objection(self, dialect, product, alternatives) -> SalesResponse:
        if alternatives:
            alt = alternatives[0]
            responses = {
                "gulf": f"فهمتك! عندنا بديل بسعر أقل:\n{alt.get('name', '')} بـ {alt.get('price', '')} ر.س\nنفس الجودة بس حجم/موديل مختلف. وش رأيك؟",
                "egyptian": f"فهمتك! عندنا بديل بسعر أقل:\n{alt.get('name', '')} بـ {alt.get('price', '')} ر.س\nنفس الجودة بس حجم/موديل مختلف. إيه رأيك؟",
                "msa": f"أفهمك! لدينا بديل بسعر أقل:\n{alt.get('name', '')} بـ {alt.get('price', '')} ر.س\nماذا تعتقد؟",
            }
        else:
            responses = {
                "gulf": "فهمتك! لو تبي أقول لك — هالمنتج من أكثر المنتجات مبيعاً عندنا، وعملاءنا يشيدون بجودته. القيمة تستاهل الاستثمار.",
                "egyptian": "فهمتك! لو تحب أقولك — المنتج ده من أكتر المنتجات مبيعاً عندنا والعملاء شايفين إن الجودة تستاهل.",
                "msa": "أفهمك! هذا المنتج من الأكثر مبيعاً لدينا والعملاء يثنون على جودته.",
            }
        response_text = responses.get(dialect, responses["gulf"])

        # Recommendations: price alternative (structure ready — activates when catalog available)
        try:
            from radd.sales.recommendations import Product, RecommendationEngine

            rec_engine = RecommendationEngine()
            # TODO: Load real catalog from Salla API or workspace products
            # if product:
            #     current = Product(
            #         id=str(product.get("id", "")),
            #         name=product.get("name", ""),
            #         price=float(product.get("price", 0)),
            #         category=product.get("category", ""),
            #         tags=product.get("tags", []),
            #         in_stock=product.get("in_stock", True),
            #     )
            #     alt_rec = rec_engine.get_price_alternative(current, dialect)
            #     if alt_rec:
            #         response_text += f"\n\n{alt_rec.reason_ar}"
        except Exception as e:
            logger.debug("Price alternative not available: %s", e)

        return SalesResponse(
            response_text=response_text,
            products_to_show=[alternatives[0]] if alternatives else [],
            stage=ConversationStage.OBJECTION,
            follow_up_after_minutes=120,
        )

    def _handle_trust_objection(self, dialect, product) -> SalesResponse:
        responses = {
            "gulf": "كل منتجاتنا أصلية 100% ومضمونة. عندنا سياسة إرجاع 14 يوم — إذا مو راضي ترجعه بدون أي سؤال. ثقتك تهمنا.",
            "egyptian": "كل منتجاتنا أصلية 100% ومضمونة. عندنا سياسة إرجاع 14 يوم — لو مش راضي ترجعه من غير أي سؤال. ثقتك مهمة لنا.",
            "msa": "جميع منتجاتنا أصلية ومضمونة 100%. لدينا سياسة إرجاع 14 يوماً بدون أي أسئلة. ثقتك أولوية لنا.",
        }
        return SalesResponse(
            response_text=responses.get(dialect, responses["gulf"]),
            stage=ConversationStage.OBJECTION,
        )

    def _handle_hesitation(self, dialect, product) -> SalesResponse:
        responses = {
            "gulf": "خذ وقتك! لو تبي أي معلومة إضافية أنا هنا. وإذا قررت، أرسل لي وأنا أساعدك تكمل الطلب بسهولة.",
            "egyptian": "خد وقتك! لو محتاج أي معلومة إضافية أنا هنا. ولو قررت ابعتلي وأنا أساعدك تكمل الأوردر بسهولة.",
            "msa": "خذ وقتك! أنا هنا لأي استفسار إضافي. وعندما تقرر، أرسل لي وسأساعدك في إكمال الطلب.",
        }
        return SalesResponse(
            response_text=responses.get(dialect, responses["gulf"]),
            stage=ConversationStage.OBJECTION,
            follow_up_after_minutes=120,  # تابع بعد ساعتين
        )

    def _no_product_response(self, dialect, mentions) -> str:
        product_name = mentions[0] if mentions else "هذا المنتج"
        responses = {
            "gulf": f"للأسف ما لقيت معلومات عن {product_name} حالياً. خلني أحولك لفريقنا يساعدك أكثر.",
            "egyptian": f"للأسف ملقتش معلومات عن {product_name} دلوقتي. خليني أحولك للفريق يساعدك أكتر.",
            "msa": f"للأسف لا تتوفر لدي معلومات عن {product_name} حالياً. دعني أحيلك للفريق.",
        }
        return responses.get(dialect, responses["gulf"])

    def _ask_which_products(self, dialect) -> str:
        responses = {
            "gulf": "ممتاز! وش المنتجات اللي تبي تقارن بينها؟",
            "egyptian": "ممتاز! إيه المنتجات اللي عايز تقارن بينها؟",
            "msa": "رائع! ما المنتجات التي تودّ المقارنة بينها؟",
        }
        return responses.get(dialect, responses["gulf"])


# ═══════════════════════════════════════════════
# STARTER PACKS — Sector-Based Onboarding
# ═══════════════════════════════════════════════

@dataclass
class StarterPack:
    sector: str
    sector_ar: str
    kb_documents: list[dict]  # pre-built KB docs
    custom_keywords: dict  # sector-specific keywords for intent classifier
    sales_tips: list[str]  # tips for sales persona
    common_objections: list[str]  # common objections in this sector


STARTER_PACKS = {
    "perfumes": StarterPack(
        sector="perfumes",
        sector_ar="عطور ومستحضرات تجميل",
        kb_documents=[
            {"title": "الفرق بين تركيزات العطور", "content": "العطور تأتي بعدة تركيزات:\n- Parfum (بارفان): أعلى تركيز (20-30%)، يدوم 8-12 ساعة. الأغلى.\n- EDP (أو دو بارفان): تركيز عالي (15-20%)، يدوم 6-8 ساعات. الأكثر شيوعاً.\n- EDT (أو دو تواليت): تركيز متوسط (5-15%)، يدوم 3-5 ساعات. سعر معقول.\n- EDC (أو دو كولون): تركيز خفيف (2-5%)، يدوم 1-2 ساعة. للاستخدام اليومي.", "content_type": "faq"},
            {"title": "طريقة حفظ العطور", "content": "لحفظ العطر بشكل صحيح:\n- احفظه في مكان بارد وجاف بعيداً عن الشمس\n- لا تحفظه في الحمام (الرطوبة تفسده)\n- أغلق الغطاء بإحكام بعد كل استخدام\n- العطر يدوم 3-5 سنوات إذا حُفظ بشكل صحيح", "content_type": "faq"},
            {"title": "هل العطور أصلية؟", "content": "جميع عطورنا أصلية 100% ومستوردة من المصنع مباشرة. كل عطر يأتي بباركود قابل للتحقق. نقدم ضمان الأصالة ونقبل الإرجاع خلال 14 يوم إذا كان المنتج غير مفتوح.", "content_type": "faq"},
            {"title": "كيف أختار العطر المناسب؟", "content": "اختيار العطر يعتمد على:\n- المناسبة: للعمل (عطور خفيفة)، للمناسبات (عطور قوية)\n- الموسم: صيفاً (عطور منعشة)، شتاءً (عطور دافئة)\n- الذوق الشخصي: خشبي، زهري، شرقي، بحري\n\nإذا مو متأكد، جرب عيناتنا المجانية أولاً!", "content_type": "faq"},
        ],
        custom_keywords={
            "product_inquiry": ["تركيز", "EDP", "EDT", "بارفان", "عود", "مسك", "عنبر", "دهن عود", "بخور", "عينة", "تستر"],
            "product_comparison": ["الفرق بين التركيزات", "ايهم اثبت", "ايهم اقوى", "نوتات"],
        },
        sales_tips=[
            "العميل اللي يسأل عن التركيز يريد يفهم القيمة مقابل السعر",
            "إذا قال 'غالي' — اعرض تركيز أقل (EDT بدل EDP)",
            "إذا سأل 'أصلي ولا تقليد' — أكد الأصالة فوراً ثم اذكر الضمان",
        ],
        common_objections=["غالي", "أصلي ولا تقليد", "الريحة تدوم كم", "كيف أعرف يناسبني"],
    ),

    "fashion": StarterPack(
        sector="fashion",
        sector_ar="أزياء وملابس",
        kb_documents=[
            {"title": "جدول المقاسات", "content": "جدول المقاسات:\n- S: صدر 88-92 سم، خصر 72-76 سم\n- M: صدر 96-100 سم، خصر 80-84 سم\n- L: صدر 104-108 سم، خصر 88-92 سم\n- XL: صدر 112-116 سم، خصر 96-100 سم\n\nنصيحة: إذا كنت بين مقاسين، اختر المقاس الأكبر.", "content_type": "faq"},
            {"title": "سياسة التبديل والإرجاع", "content": "تقدر تبدل أو ترجع خلال 14 يوم من الاستلام بشرط:\n- المنتج بحالته الأصلية مع التاغ\n- غير مغسول أو معدّل\n- في الكيس الأصلي\n\nالتبديل مجاني. الإرجاع يُخصم منه رسوم الشحن.", "content_type": "policy"},
            {"title": "طريقة العناية بالملابس", "content": "للحفاظ على ملابسك:\n- اتبع تعليمات الغسيل على الليبل\n- اغسل بالماء البارد للألوان الداكنة\n- جفف في الظل (لا تستخدم المجفف للأقمشة الحساسة)\n- استخدم المكواة على حرارة مناسبة للقماش", "content_type": "faq"},
        ],
        custom_keywords={
            "product_inquiry": ["مقاس", "لون", "قماش", "قطن", "حرير", "موديل", "تصميم", "كولكشن"],
            "purchase_hesitation": ["مقاسي كم", "المقاس يطابق", "الصورة زي الحقيقي"],
        },
        sales_tips=[
            "أكثر سبب إرجاع: مقاس غلط. ساعد العميل يختار المقاس الصح",
            "إذا تردد بسبب اللون — اعرض بقية الألوان المتوفرة",
            "ادفعه نحو التبديل وليس الإرجاع — 'نبدل لك مجاناً'",
        ],
        common_objections=["مقاسي كم", "اللون يختلف عن الصورة", "القماش كيف", "يناسب جسمي"],
    ),

    "electronics": StarterPack(
        sector="electronics",
        sector_ar="إلكترونيات",
        kb_documents=[
            {"title": "سياسة الضمان", "content": "جميع منتجاتنا مشمولة بضمان:\n- الأجهزة الإلكترونية: ضمان سنة كاملة\n- الإكسسوارات: ضمان 6 أشهر\n- الضمان يشمل عيوب التصنيع فقط\n- الضمان لا يشمل الكسر أو سوء الاستخدام\n\nللتفعيل: أرسل صورة الفاتورة + رقم السيريال.", "content_type": "policy"},
            {"title": "طرق الدفع", "content": "نقبل:\n- مدى / فيزا / ماستركارد\n- Apple Pay\n- تقسيط تمارا (4 أقساط بدون فوائد)\n- تقسيط تابي\n- الدفع عند الاستلام (COD) — إضافة 15 ريال", "content_type": "faq"},
        ],
        custom_keywords={
            "product_inquiry": ["مواصفات", "رام", "معالج", "بطارية", "شاشة", "كاميرا", "ضمان", "أصلي"],
            "purchase_hesitation": ["تقسيط", "تمارا", "تابي", "ضمان", "وكيل"],
        },
        sales_tips=[
            "العميل يسأل عن المواصفات — قارن بالمنافسين إذا متوفر",
            "التقسيط يحل أكبر اعتراض سعري — اذكره دائماً",
            "الضمان والأصالة أهم من السعر لعميل الإلكترونيات",
        ],
        common_objections=["أصلي ولا تقليد", "فيه ضمان", "فيه تقسيط", "ليش أغلى من أمازون"],
    ),

    "food": StarterPack(
        sector="food",
        sector_ar="أغذية ومشروبات",
        kb_documents=[
            {"title": "مناطق التوصيل ومواعيده", "content": "نوصل لجميع مناطق المملكة:\n- الرياض: نفس اليوم (للطلبات قبل 2 ظهراً)\n- جدة/الدمام: 1-2 يوم عمل\n- باقي المناطق: 2-4 أيام عمل\n\nالمنتجات المبرّدة تُشحن بتغليف حراري خاص.", "content_type": "faq"},
            {"title": "معلومات الحساسية", "content": "جميع منتجاتنا توضح المكونات على العبوة. إذا عندك حساسية من أي مكون، تواصل معنا قبل الطلب وبنساعدك تختار المنتج المناسب.", "content_type": "faq"},
        ],
        custom_keywords={
            "product_inquiry": ["سعرات", "مكونات", "حلال", "صلاحية", "تاريخ", "عضوي", "طبيعي"],
        },
        sales_tips=[
            "مواعيد التوصيل أهم شيء في الأغذية — أجب عنها فوراً",
            "إذا سأل عن المكونات — لا تختلق. حوّل للفريق إذا مو متأكد",
        ],
        common_objections=["يوصل طازج", "كم الصلاحية", "فيه مواد حافظة", "حلال"],
    ),
}


def get_starter_pack(sector: str) -> StarterPack | None:
    """Get starter pack for a sector."""
    return STARTER_PACKS.get(sector)


def get_available_sectors() -> list[dict]:
    """Get list of available sectors for onboarding UI."""
    return [
        {"id": s.sector, "name": s.sector_ar, "docs_count": len(s.kb_documents)}
        for s in STARTER_PACKS.values()
    ]


async def apply_starter_pack(
    workspace_id: str,
    sector: str,
    kb_service,
) -> dict:
    """Apply a starter pack — create all KB documents for the workspace."""
    pack = get_starter_pack(sector)
    if not pack:
        return {"error": f"Sector '{sector}' not found"}

    created = 0
    for doc in pack.kb_documents:
        await kb_service.create_document(
            workspace_id=workspace_id,
            title=doc["title"],
            content=doc["content"],
            content_type=doc["content_type"],
            status="approved",  # Auto-approve starter pack docs
            metadata={"source": "starter_pack", "sector": sector},
        )
        created += 1

    return {
        "sector": sector,
        "sector_ar": pack.sector_ar,
        "documents_created": created,
        "message": f"تم تحميل حزمة {pack.sector_ar} — {created} مستند جاهز",
    }
