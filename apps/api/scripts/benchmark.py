"""
Arabic NLP Benchmark — Gate G1.
Tests intent classification on 100 Arabic CS queries.
Pass criteria: >80% intent accuracy.

Run with: make benchmark
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from radd.pipeline.normalizer import normalize
from radd.pipeline.intent import classify_intent
from radd.pipeline.dialect import detect_dialect

# ─── 100-query test set ───────────────────────────────────────────────────────
# Format: (query, expected_intent)

TEST_QUERIES = [
    # greeting (15)
    ("مرحبا كيف حالكم", "greeting"),
    ("السلام عليكم ورحمة الله", "greeting"),
    ("هلا والله", "greeting"),
    ("صباح الخير", "greeting"),
    ("مساء النور", "greeting"),
    ("أهلاً وسهلاً", "greeting"),
    ("هلو", "greeting"),
    ("هاي", "greeting"),
    ("كيفكم", "greeting"),
    ("يسلمو", "greeting"),
    ("تصبحون على خير", "greeting"),
    ("مرحبتين", "greeting"),
    ("وعليكم السلام", "greeting"),
    ("كيف حالك", "greeting"),
    ("أهلين", "greeting"),
    # order_status (20)
    ("وين طلبي؟", "order_status"),
    ("متى يوصل طلبي؟", "order_status"),
    ("أبغى أتابع طلبي", "order_status"),
    ("ما وصلني طلبي لحد الآن", "order_status"),
    ("رقم الطلب 12345 وين وصل؟", "order_status"),
    ("أريد معرفة حالة طلبي", "order_status"),
    ("طلبتي فين؟", "order_status"),
    ("تتبع الطلب", "order_status"),
    ("كم متبقي على وصول طلبي", "order_status"),
    ("الطلب رقم 9876 لم يصل", "order_status"),
    ("أين اوردري", "order_status"),
    ("طلبي تأخر ليش؟", "order_status"),
    ("ما شفت طلبي", "order_status"),
    ("عندي طلب محجوز متى يوصل", "order_status"),
    ("أبي أعرف حالة طلبي", "order_status"),
    ("طلبي اتأخر", "order_status"),
    ("وصل طلبي ولا لا؟", "order_status"),
    ("كيف أتابع شحنتي", "order_status"),
    ("استفسار عن طلب", "order_status"),
    ("طلبي من امبارح", "order_status"),
    # shipping (20)
    ("كم يوم التوصيل؟", "shipping"),
    ("هل الشحن مجاني؟", "shipping"),
    ("متى يوصل التوصيل", "shipping"),
    ("كم مدة الشحن", "shipping"),
    ("موعد التوصيل متى؟", "shipping"),
    ("أرامكس ولا سمسا؟", "shipping"),
    ("توصلون لكل السعودية؟", "shipping"),
    ("شحن سريع متاح؟", "shipping"),
    ("كيف يوصلني الطلب", "shipping"),
    ("مدة الشحن كم يوم؟", "shipping"),
    ("يوصل بكره ولا لا", "shipping"),
    ("الشحن بكام؟", "shipping"),
    ("شركة الشحن ايه", "shipping"),
    ("رسوم التوصيل كام", "shipping"),
    ("هل تشحنون لجدة", "shipping"),
    ("أبغى شحن اليوم", "shipping"),
    ("الشحن المجاني من كام", "shipping"),
    ("تقدرون توصلونلي بكره", "shipping"),
    ("توصيل خارج الرياض", "shipping"),
    ("كم تاخذ الشحنة وقت", "shipping"),
    # return_policy (20)
    ("كيف أرجع المنتج؟", "return_policy"),
    ("أبغى أسترجع الطلب", "return_policy"),
    ("سياسة الإرجاع عندكم كيف؟", "return_policy"),
    ("المنتج ما عجبني أرجعه", "return_policy"),
    ("ممكن أرجع بضاعة؟", "return_policy"),
    ("رد المبلغ كيف يصير", "return_policy"),
    ("أبغى استرداد", "return_policy"),
    ("مدة الإرجاع كم يوم", "return_policy"),
    ("المنتج وصلني مكسور", "return_policy"),
    ("تبديل بدل الإرجاع؟", "return_policy"),
    ("هل ترجعون الفلوس", "return_policy"),
    ("استرجاع طلب", "return_policy"),
    ("إرجاع منتج إيه الخطوات", "return_policy"),
    ("المنتج غلط أرجعه", "return_policy"),
    ("شروط الإرجاع ايه", "return_policy"),
    ("ممكن استبدل", "return_policy"),
    ("refund ممكن", "return_policy"),
    ("أرجع طلبي إزاي", "return_policy"),
    ("هل يقبلون الإرجاع", "return_policy"),
    ("عايز أرجع", "return_policy"),
    # store_hours (15)
    ("متى تفتحون؟", "store_hours"),
    ("ساعات عملكم؟", "store_hours"),
    ("هل انتم مفتوحين الحين؟", "store_hours"),
    ("مواعيد خدمة العملاء", "store_hours"),
    ("كم ساعة دوامكم", "store_hours"),
    ("تشتغلون يوم الجمعة؟", "store_hours"),
    ("الدوام من كام لكام", "store_hours"),
    ("اوقات الرد على الرسائل", "store_hours"),
    ("هل في خدمة ٢٤ ساعة", "store_hours"),
    ("متى تغلقون", "store_hours"),
    ("اوقات العمل عندكم", "store_hours"),
    ("هتردوا امتى", "store_hours"),
    ("بعد كام الدعم ما يرد", "store_hours"),
    ("خدمة عملاء الوقت", "store_hours"),
    ("هل في رد في الليل", "store_hours"),
    # other (10)
    ("أبغى تواصل مع المدير", "other"),
    ("عندي شكوى", "other"),
    ("منتج معيب", "other"),
    ("الموقع ما يشتغل", "other"),
    ("كوبون خصم", "other"),
    ("باقات الاشتراك", "other"),
    ("هل عندكم تطبيق", "other"),
    ("تعاون تجاري", "other"),
    ("وظائف شاغرة", "other"),
    ("شكراً جزيلاً", "other"),
]


def run_benchmark():
    print("\n" + "═" * 60)
    print("  RADD Arabic NLP Benchmark — Gate G1")
    print("═" * 60)
    print(f"  Total queries: {len(TEST_QUERIES)}")
    print()

    results_by_intent: dict[str, dict] = {}
    total_correct = 0
    total = len(TEST_QUERIES)

    for query, expected in TEST_QUERIES:
        normalized = normalize(query)
        result = classify_intent(normalized)
        correct = result.intent == expected

        if correct:
            total_correct += 1

        if expected not in results_by_intent:
            results_by_intent[expected] = {"correct": 0, "total": 0, "errors": []}
        results_by_intent[expected]["total"] += 1
        if correct:
            results_by_intent[expected]["correct"] += 1
        else:
            results_by_intent[expected]["errors"].append({
                "query": query,
                "expected": expected,
                "got": result.intent,
                "confidence": result.confidence,
            })

    overall_accuracy = total_correct / total * 100

    print(f"  Overall accuracy: {overall_accuracy:.1f}%  ({total_correct}/{total})")
    print()
    print("  Per-intent breakdown:")
    print("  " + "─" * 50)

    for intent, stats in results_by_intent.items():
        acc = stats["correct"] / stats["total"] * 100
        bar = "█" * int(acc / 10) + "░" * (10 - int(acc / 10))
        print(f"  {intent:<18} {bar}  {acc:5.1f}%  ({stats['correct']}/{stats['total']})")

    print()
    print("  Errors:")
    for intent, stats in results_by_intent.items():
        for err in stats["errors"]:
            print(f"  ✗ [{err['expected']} → {err['got']}] \"{err['query']}\"")

    print()
    print("═" * 60)
    gate_pass = overall_accuracy >= 80
    if gate_pass:
        print(f"  ✓ GATE G1 PASS — {overall_accuracy:.1f}% ≥ 80% threshold")
        print("  → Proceed to RAG pipeline (Sprint 2)")
    else:
        print(f"  ✗ GATE G1 FAIL — {overall_accuracy:.1f}% < 80% threshold")
        if overall_accuracy >= 70:
            print("  → Contingency: template-only pivot. No RAG.")
        else:
            print("  → STOP. Reassess Arabic NLP approach.")
    print("═" * 60 + "\n")

    return overall_accuracy


if __name__ == "__main__":
    run_benchmark()
