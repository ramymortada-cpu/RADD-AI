"""
Tests: Entity Extractor — order numbers, shipping companies, product mentions, monetary amounts.
Cursor Prompt 4 requirement: ≥30 test cases, >75% recall on test set.
"""
import pytest
from radd.pipeline.entity_extractor import extract_entities


class TestOrderNumbers:
    def test_hash_format(self):
        e = extract_entities("#45678")
        assert "45678" in e.order_numbers

    def test_word_talab_prefix(self):
        e = extract_entities("وين طلب 12345")
        assert "12345" in e.order_numbers

    def test_raqam_prefix(self):
        e = extract_entities("رقم 987654")
        assert "987654" in e.order_numbers

    def test_order_english_prefix(self):
        e = extract_entities("order 3344567")
        assert "3344567" in e.order_numbers

    def test_talabyati_prefix(self):
        e = extract_entities("طلبيتي 56789 ما وصلت")
        assert "56789" in e.order_numbers

    def test_no_short_numbers_ignored(self):
        e = extract_entities("عندي 3 منتجات")
        assert len(e.order_numbers) == 0

    def test_multiple_orders(self):
        e = extract_entities("طلب 11111 وطلب 22222")
        assert "11111" in e.order_numbers
        assert "22222" in e.order_numbers

    def test_no_false_positive_year(self):
        e = extract_entities("في عام 2024")
        assert len(e.order_numbers) == 0


class TestShippingCompanies:
    def test_aramex_arabic(self):
        e = extract_entities("اشحن مع ارامكس")
        assert "Aramex" in e.shipping_companies

    def test_aramex_english(self):
        e = extract_entities("shipped via Aramex")
        assert "Aramex" in e.shipping_companies

    def test_smsa_arabic(self):
        e = extract_entities("شركة سمسا للتوصيل")
        assert "SMSA" in e.shipping_companies

    def test_smsa_english(self):
        e = extract_entities("tracking with SMSA")
        assert "SMSA" in e.shipping_companies

    def test_dhl(self):
        e = extract_entities("طردي مع DHL")
        assert "DHL" in e.shipping_companies

    def test_fedex_arabic(self):
        e = extract_entities("ارسل بـ فيدكس")
        assert "FedEx" in e.shipping_companies

    def test_naqel(self):
        e = extract_entities("شركة ناقل Express")
        assert "Naqel" in e.shipping_companies

    def test_zajil(self):
        e = extract_entities("توصيل زاجل")
        assert "Zajil" in e.shipping_companies

    def test_no_shipping_company(self):
        e = extract_entities("متى يوصل طلبي؟")
        assert len(e.shipping_companies) == 0

    def test_multiple_companies(self):
        e = extract_entities("هل تشحنون مع aramex أو sмsa")
        assert len(e.shipping_companies) >= 1


class TestProductMentions:
    def test_saar_trigger(self):
        e = extract_entities("كم سعر عطر عود")
        assert any("عطر" in m or "عود" in m for m in e.product_mentions)

    def test_endakum_trigger(self):
        e = extract_entities("عندكم عباية سوداء؟")
        assert any("عباية" in m for m in e.product_mentions)

    def test_mutawaffir_trigger(self):
        e = extract_entities("متوفر كريم نضارة")
        assert len(e.product_mentions) > 0

    def test_abgha_trigger(self):
        e = extract_entities("ابغى ساعة ذهبية")
        assert any("ساعة" in m for m in e.product_mentions)

    def test_no_product_plain_question(self):
        e = extract_entities("وين طلبي؟")
        assert len(e.product_mentions) == 0


class TestMonetaryAmounts:
    def test_riyal_arabic(self):
        e = extract_entities("السعر 250 ريال")
        assert "250" in e.monetary_amounts

    def test_sar(self):
        e = extract_entities("Price is 199.99 SAR")
        assert "199.99" in e.monetary_amounts

    def test_rs_abbreviation(self):
        e = extract_entities("بكم؟ الثمن 350 ر.س")
        assert "350" in e.monetary_amounts

    def test_no_amount_plain(self):
        e = extract_entities("مرحبا كيف حالكم")
        assert len(e.monetary_amounts) == 0

    def test_multiple_amounts(self):
        e = extract_entities("الأول بـ 100 ريال والثاني 200 ريال")
        assert "100" in e.monetary_amounts
        assert "200" in e.monetary_amounts


class TestEmptyAndEdgeCases:
    def test_empty_string(self):
        e = extract_entities("")
        assert e.order_numbers == []
        assert e.shipping_companies == []
        assert e.product_mentions == []
        assert e.monetary_amounts == []

    def test_pure_english(self):
        e = extract_entities("Hello how are you today?")
        assert e.order_numbers == []

    def test_no_duplicates_order(self):
        e = extract_entities("طلب 99999 وطلب 99999 مرة ثانية")
        assert e.order_numbers.count("99999") == 1

    def test_no_duplicates_shipping(self):
        e = extract_entities("ارامكس ارامكس ارامكس")
        assert e.shipping_companies.count("Aramex") == 1
