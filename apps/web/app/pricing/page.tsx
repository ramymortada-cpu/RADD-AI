import Link from "next/link";
import { CheckCircle2, Zap, Star, Crown } from "lucide-react";

const PLANS = [
  {
    name: "أساسية",
    price: 199,
    badge: null,
    icon: <Zap className="h-6 w-6 text-blue-500" />,
    description: "للتاجر المبتدئ الذي يريد أتمتة الردود الأساسية",
    target: "50-200 طلب/شهر",
    color: "border-blue-200",
    btnClass: "bg-blue-600 hover:bg-blue-700",
    features: [
      "ردود AI بالعربية ✓",
      "قاعدة معرفة 20 مستند",
      "تقرير الصباح اليومي",
      "شخصية AI واحدة",
      "مستخدم واحد",
      "تكامل واتساب",
      "دعم بالواتساب",
    ],
    missing: ["AI Personas (3 شخصيات)", "منع الإرجاع", "العائد المالي", "الرادار التشغيلي"],
  },
  {
    name: "احترافية",
    price: 499,
    badge: "الأكثر طلباً ⭐",
    icon: <Star className="h-6 w-6 text-primary" />,
    description: "للتاجر النامي الذي يريد المبيعات والتحليلات",
    target: "200-2000 طلب/شهر",
    color: "border-primary",
    btnClass: "bg-primary hover:bg-primary/90",
    features: [
      "كل مميزات الأساسية",
      "3 شخصيات AI متخصصة",
      "محرك المبيعات قبل الشراء",
      "منع الإرجاع الذكي",
      "إثبات العائد المالي",
      "قاعدة معرفة غير محدودة",
      "3 مستخدمين",
      "مزامنة Salla تلقائية",
      "باقات البداية السريعة",
      "قواعد ذكية",
      "دعم أولوية",
    ],
    missing: ["الرادار التشغيلي", "رادار التلاشي"],
  },
  {
    name: "نمو",
    price: 999,
    badge: "للمتاجر الكبيرة",
    icon: <Crown className="h-6 w-6 text-amber-500" />,
    description: "للتاجر المتوسط الذي يريد ذكاء عملاء كامل",
    target: "2000+ طلب/شهر",
    color: "border-amber-300",
    btnClass: "bg-amber-600 hover:bg-amber-700",
    features: [
      "كل مميزات الاحترافية",
      "الرادار التشغيلي (كشف الشذوذات)",
      "رادار التلاشي (VIP خاملون)",
      "RADD Score (0-100)",
      "أداء الفريق البشري",
      "متابعة ذكية بعد المحادثة",
      "فحص ما بعد الشراء",
      "10 مستخدمين",
      "API للمطورين (قريباً)",
      "White-glove onboarding",
      "مدير حساب مخصص",
    ],
    missing: [],
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white" dir="rtl">
      {/* Header */}
      <div className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="font-bold text-lg">رَدّ</span>
          </Link>
          <Link
            href="/login"
            className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            ابدأ مجاناً
          </Link>
        </div>
      </div>

      {/* Hero */}
      <div className="max-w-4xl mx-auto px-6 py-16 text-center">
        <p className="text-sm text-primary font-medium mb-3 bg-primary/10 inline-block px-4 py-1 rounded-full">
          تسعير شفاف — بدون مفاجآت
        </p>
        <h1 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
          استثمار يثبت قيمته كل يوم
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          رَدّ لا يكلّفك — رَدّ يكسبك. كل باقة تثبت عائدها في Dashboard يومياً.
        </p>
        <div className="mt-6 inline-flex items-center gap-2 text-sm text-green-700 bg-green-50 px-4 py-2 rounded-full border border-green-200">
          <CheckCircle2 className="h-4 w-4" />
          تجربة مجانية 21 يوم — بدون بطاقة ائتمان
        </div>
      </div>

      {/* Plans */}
      <div className="max-w-6xl mx-auto px-6 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`relative bg-white rounded-2xl border-2 shadow-sm hover:shadow-md transition-shadow p-6 flex flex-col gap-5 ${plan.color} ${plan.name === "احترافية" ? "ring-2 ring-primary ring-offset-2" : ""}`}
            >
              {plan.badge && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-white text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap">
                  {plan.badge}
                </div>
              )}

              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-muted/40">{plan.icon}</div>
                <div>
                  <h2 className="text-xl font-bold">{plan.name}</h2>
                  <p className="text-xs text-muted-foreground">{plan.target}</p>
                </div>
              </div>

              <div>
                <div className="flex items-baseline gap-1">
                  <span className="text-4xl font-bold">{plan.price.toLocaleString("ar-SA")}</span>
                  <span className="text-muted-foreground text-sm">ر.س/شهر</span>
                </div>
                <p className="text-sm text-muted-foreground mt-1">{plan.description}</p>
              </div>

              <Link
                href={`/onboarding?plan=${plan.name === "أساسية" ? "basic" : plan.name === "احترافية" ? "pro" : "growth"}`}
                className={`w-full py-3 rounded-xl text-white text-sm font-bold text-center transition-colors ${plan.btnClass}`}
              >
                ابدأ تجربة مجانية 21 يوم
              </Link>

              <div className="space-y-2">
                {plan.features.map((f) => (
                  <div key={f} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                    <span>{f}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Comparison note */}
        <div className="mt-12 p-6 bg-gradient-to-l from-primary/5 to-primary/10 rounded-2xl border border-primary/20">
          <h3 className="font-bold text-lg mb-4 text-center">لماذا رَدّ أفضل من البدائل؟</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            {[
              {
                vs: "vs. Thikaa (37 ر.س)",
                text: "Thikaa يرد. رَدّ يرد + يبيع + يثبت كم كسبت بالأرقام. العائد على الاستثمار مع رَدّ: 40-80x.",
              },
              {
                vs: "vs. Respond.io (600+ ر.س)",
                text: "Respond.io لا يعرف سلة ولا منتجاتك. رَدّ يعرف كل شيء من اللحظة الأولى — ومزامنة تلقائية.",
              },
              {
                vs: "vs. Gabster (240+ ر.س)",
                text: "رَدّ يقدم نفس العمق بسعر أقل وبساطة أكبر — ودعم بالعربي من يومك الأول.",
              },
            ].map(({ vs, text }) => (
              <div key={vs} className="p-4 bg-white rounded-xl border border-primary/10">
                <p className="font-bold text-primary text-xs mb-2">{vs}</p>
                <p className="text-muted-foreground leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>

        {/* FAQ */}
        <div className="mt-12 space-y-4 max-w-2xl mx-auto">
          <h3 className="font-bold text-xl text-center mb-6">أسئلة شائعة</h3>
          {[
            { q: "هل هناك عقد سنوي؟", a: "لا. كل شيء شهري. يمكنك الإلغاء في أي وقت. خصم 20% إذا اخترت الدفع السنوي." },
            { q: "كيف تعمل التجربة المجانية؟", a: "21 يوم كاملة بدون قيود وبدون بطاقة ائتمان. بعدها تختار باقتك." },
            { q: "ماذا يحدث لبياناتي إذا ألغيت؟", a: "يمكنك تصدير كل بياناتك كاملة قبل الإلغاء. بياناتك لك دائماً." },
            { q: "هل رَدّ يعمل مع Zid؟", a: "حالياً مع سلة فقط. تكامل Zid قادم في Q3 2026." },
          ].map(({ q, a }) => (
            <details key={q} className="group bg-white border rounded-xl">
              <summary className="px-5 py-4 cursor-pointer font-medium list-none flex justify-between items-center">
                {q}
                <span className="text-muted-foreground group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="px-5 pb-4 text-sm text-muted-foreground">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}
