
from radd.pipeline.normalizer import normalize_arabic
from radd.pipeline.dialect import detect_dialect
from radd.pipeline.intent import classify_intent
from radd.pipeline.entity_extractor import extract_entities
from radd.customers.profile_updater import compute_sentiment, build_customer_context

# ── Normalizer ──
def test_remove_tashkeel(): assert normalize_arabic("مَرْحَبًا") == "مرحبا"
def test_normalize_alef(): assert normalize_arabic("أهلاً") == "اهلا"
def test_normalize_ya(): assert normalize_arabic("على") == "علي"
def test_remove_tatweel(): assert normalize_arabic("مـرحـبـا") == "مرحبا"
def test_eastern_numbers(): assert normalize_arabic("١٢٣") == "123"
def test_empty(): assert normalize_arabic("") == ""

# ── Dialect ──
def test_gulf(): assert detect_dialect("وش وضع طلبي").dialect == "gulf"
def test_gulf_strong(): assert detect_dialect("ابغى اعرف وين طلبي الحين").confidence >= 0.7
def test_egyptian(): assert detect_dialect("ايه اخبار الاوردر بتاعي").dialect == "egyptian"
def test_msa_fallback(): assert detect_dialect("اريد معرفة حالة الطلب").dialect == "msa"

# ── Intent (9 intents) ──
def test_greeting(): assert classify_intent("هلا وغلا").intent == "greeting"
def test_order_status(): assert classify_intent("وين طلبي رقم 4523").intent == "order_status"
def test_shipping(): assert classify_intent("كم مدة الشحن").intent == "shipping"
def test_return(): assert classify_intent("ابي ارجع المنتج").intent == "return_policy"
def test_hours(): assert classify_intent("متى تفتحون").intent == "store_hours"
def test_general(): r = classify_intent("xxxxxxx"); assert r.intent == "general" and r.confidence <= 0.5

# NEW: Pre-purchase intents
def test_product_inquiry(): r = classify_intent("عندكم عطر عود"); assert r.intent == "product_inquiry" and r.is_pre_purchase
def test_product_price(): r = classify_intent("كم سعر الساعة"); assert r.intent == "product_inquiry" and r.is_pre_purchase
def test_comparison(): r = classify_intent("ايش الفرق بين العطرين"); assert r.intent == "product_comparison" and r.is_pre_purchase
def test_recommend(): r = classify_intent("تنصحوني بأي واحد"); assert r.intent == "product_comparison"
def test_hesitation_price(): r = classify_intent("غالي شوي عندكم خصم"); assert r.intent == "purchase_hesitation" and r.is_pre_purchase
def test_hesitation_tamara(): r = classify_intent("فيه تقسيط تمارا"); assert r.intent == "purchase_hesitation"

# ── Entity Extractor ──
def test_order_hash(): assert "45678" in extract_entities("طلب #45678 وين وصل").order_numbers
def test_order_arabic(): assert "901234" in extract_entities("رقم الطلب 901234").order_numbers
def test_shipping_ar(): assert "Aramex" in extract_entities("الشحنة مع ارامكس متاخرة").shipping_companies
def test_shipping_en(): assert "SMSA" in extract_entities("smsa ما وصلو الطلب").shipping_companies
def test_multi_ship(): assert len(extract_entities("ارامكس احسن ولا سمسا").shipping_companies) == 2
def test_money(): assert "250" in extract_entities("سعره 250 ريال").monetary_amounts
def test_no_entities(): e = extract_entities("مرحبا كيف الحال"); assert len(e.order_numbers) == 0

# ── Customer Profile ──
def test_sentiment_pos(): assert compute_sentiment("شكرا ممتاز") > 0.5
def test_sentiment_neg(): assert compute_sentiment("سيء خربان مشكلة") < 0.5
def test_sentiment_neutral(): assert compute_sentiment("ابي اعرف حالة الطلب") == 0.5

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
