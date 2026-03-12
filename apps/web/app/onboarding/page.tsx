"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Zap, CheckCircle2, ArrowLeft, Layers, Link as LinkIcon, PlayCircle } from "lucide-react";
import { applyStarterPack, triggerSallaSync } from "@/lib/api";

const SECTORS = [
  { id: "perfumes", label: "عطور ومستحضرات تجميل", emoji: "🌸", desc: "FAQs العطور، نبرة فاخرة، كلمات مفتاحية للتركيزات والجودة" },
  { id: "fashion", label: "أزياء وملابس", emoji: "👗", desc: "مقاسات، ألوان، سياسة الإرجاع والاستبدال، التوصيل" },
  { id: "electronics", label: "إلكترونيات", emoji: "📱", desc: "ضمان، مواصفات تقنية، مقارنات، دعم فني" },
  { id: "food", label: "أغذية ومشروبات", emoji: "🍫", desc: "مكونات، صلاحية، توصيل سريع، حساسية غذائية" },
  { id: "jewelry", label: "مجوهرات وإكسسوارات", emoji: "💎", desc: "مواد، أصالة، تخصيص، تعبئة هدايا" },
  { id: "other", label: "أخرى", emoji: "📦", desc: "قاعدة معرفة عامة قابلة للتخصيص" },
];

type Step = "plan" | "sector" | "salla" | "done";

function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialPlan = searchParams.get("plan") || "pro";

  const [step, setStep] = useState<Step>("sector");
  const [selectedSector, setSelectedSector] = useState("");
  const [sallaToken, setSallaToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [error, setError] = useState("");

  async function handleSectorNext() {
    if (!selectedSector) return;
    setLoading(true);
    setError("");
    setProgress([]);

    try {
      setProgress((p) => [...p, `✓ تحميل باقة ${SECTORS.find((s) => s.id === selectedSector)?.label}...`]);
      await applyStarterPack(selectedSector);
      setProgress((p) => [...p, "✓ تم تحميل قاعدة المعرفة الجاهزة"]);
      setProgress((p) => [...p, "✓ تم ضبط الشخصيات والكلمات المفتاحية"]);
      setStep("salla");
    } catch {
      setError("حدث خطأ في تحميل الباقة. يمكنك المتابعة بدونها.");
      setStep("salla");
    } finally {
      setLoading(false);
    }
  }

  async function handleSallaSync() {
    if (!sallaToken.trim()) {
      setStep("done");
      return;
    }
    setLoading(true);
    setError("");

    try {
      setProgress((p) => [...p, "⟳ جارٍ الاتصال بـ Salla API..."]);
      const result = await triggerSallaSync(sallaToken);
      setProgress((p) => [
        ...p,
        `✓ تمت مزامنة ${result.products_synced} منتج`,
        `✓ تم إنشاء ${result.documents_created} مستند في قاعدة المعرفة`,
      ]);
    } catch {
      setError("تعذّر الاتصال بـ Salla. يمكنك تكرارها من الإعدادات لاحقاً.");
    } finally {
      setLoading(false);
      setStep("done");
    }
  }

  const STEP_LABELS: Record<Step, string> = {
    plan: "الباقة",
    sector: "نوع المتجر",
    salla: "ربط Salla",
    done: "جاهز!",
  };

  const steps: Step[] = ["sector", "salla", "done"];
  const currentIdx = steps.indexOf(step);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-primary/5 flex items-center justify-center p-4" dir="rtl">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center shadow-lg">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <span className="text-xl font-bold text-foreground">رَدّ</span>
        </div>

        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  i <= currentIdx ? "bg-primary text-white" : "bg-muted text-muted-foreground"
                }`}
              >
                {i < currentIdx ? "✓" : i + 1}
              </div>
              {i < steps.length - 1 && (
                <div className={`w-8 h-0.5 ${i < currentIdx ? "bg-primary" : "bg-muted"}`} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border p-6 space-y-6">
          {/* ── Step 1: Sector ── */}
          {step === "sector" && (
            <>
              <div className="text-center">
                <div className="inline-flex p-3 rounded-xl bg-primary/10 mb-3">
                  <Layers className="h-6 w-6 text-primary" />
                </div>
                <h2 className="text-xl font-bold">وش نوع متجرك؟</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  نُحمّل لك قاعدة معرفة جاهزة ومخصصة لقطاعك — مجاناً
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {SECTORS.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelectedSector(s.id)}
                    className={`p-3 rounded-xl border-2 text-start transition-all hover:border-primary/50 ${
                      selectedSector === s.id ? "border-primary bg-primary/5" : "border-border"
                    }`}
                  >
                    <span className="text-2xl">{s.emoji}</span>
                    <p className="text-sm font-medium mt-1">{s.label}</p>
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{s.desc}</p>
                  </button>
                ))}
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
              {progress.length > 0 && (
                <div className="space-y-1">
                  {progress.map((p, i) => <p key={i} className="text-xs text-green-700">{p}</p>)}
                </div>
              )}

              <button
                onClick={handleSectorNext}
                disabled={!selectedSector || loading}
                className="w-full py-3 bg-primary text-white rounded-xl font-bold hover:bg-primary/90 disabled:opacity-60 transition-colors"
              >
                {loading ? "جارٍ التحميل..." : "متابعة ←"}
              </button>
            </>
          )}

          {/* ── Step 2: Salla ── */}
          {step === "salla" && (
            <>
              <div className="text-center">
                <div className="inline-flex p-3 rounded-xl bg-green-50 mb-3">
                  <LinkIcon className="h-6 w-6 text-green-600" />
                </div>
                <h2 className="text-xl font-bold">اربط متجر Salla الخاص بك</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  رَدّ سيسحب منتجاتك وسياساتك تلقائياً — في 30 ثانية
                </p>
              </div>

              <div className="p-4 bg-green-50 rounded-xl text-sm text-green-800 space-y-1">
                <p className="font-medium">كيف تحصل على Salla API Token؟</p>
                <ol className="list-decimal list-inside space-y-1 text-green-700 text-xs">
                  <li>سجّل الدخول في لوحة تحكم Salla</li>
                  <li>اذهب إلى التطبيقات ← API Keys</li>
                  <li>أنشئ مفتاح جديد وانسخه هنا</li>
                </ol>
              </div>

              <input
                type="password"
                dir="ltr"
                placeholder="salla_token_xxxxxxxx"
                value={sallaToken}
                onChange={(e) => setSallaToken(e.target.value)}
                className="w-full px-4 py-3 text-sm border rounded-xl bg-muted/20 font-mono focus:outline-none focus:ring-2 focus:ring-primary/30"
              />

              {progress.length > 0 && (
                <div className="space-y-1">
                  {progress.map((p, i) => <p key={i} className="text-xs text-green-700">{p}</p>)}
                </div>
              )}
              {error && <p className="text-sm text-amber-700 bg-amber-50 px-3 py-2 rounded-lg">{error}</p>}

              <div className="flex gap-3">
                <button
                  onClick={() => setStep("done")}
                  className="flex-1 py-3 border rounded-xl text-sm text-muted-foreground hover:bg-muted transition-colors"
                >
                  تخطي لاحقاً
                </button>
                <button
                  onClick={handleSallaSync}
                  disabled={loading}
                  className="flex-1 py-3 bg-primary text-white rounded-xl font-bold hover:bg-primary/90 disabled:opacity-60 transition-colors"
                >
                  {loading ? "جارٍ المزامنة..." : "ربط وتزامن ←"}
                </button>
              </div>
            </>
          )}

          {/* ── Step 3: Done ── */}
          {step === "done" && (
            <div className="text-center space-y-5">
              <div className="flex justify-center">
                <div className="w-20 h-20 bg-green-50 rounded-full flex items-center justify-center">
                  <CheckCircle2 className="h-10 w-10 text-green-500" />
                </div>
              </div>
              <div>
                <h2 className="text-2xl font-bold">رَدّ جاهز! 🎉</h2>
                <p className="text-muted-foreground mt-2">
                  متجرك جاهز لاستقبال أول رد ذكي بالعربية
                </p>
              </div>

              <div className="p-4 bg-primary/5 rounded-xl text-sm space-y-2">
                {[
                  "✓ قاعدة المعرفة جاهزة",
                  "✓ الشخصيات والكلمات المفتاحية مُضبّطة",
                  sallaToken ? "✓ Salla مُربوط ومنتجاتك محمّلة" : "◎ يمكنك ربط Salla لاحقاً من الإعدادات",
                  "✓ Shadow Mode مُفعّل لأول 48 ساعة (للتحقق)",
                ].map((item, i) => (
                  <p key={i} className="text-start">{item}</p>
                ))}
              </div>

              <div className="flex flex-col gap-3">
                <button
                  onClick={() => router.push("/dashboard")}
                  className="w-full py-3 bg-primary text-white rounded-xl font-bold hover:bg-primary/90 flex items-center justify-center gap-2 transition-colors"
                >
                  <PlayCircle className="h-5 w-5" />
                  انتقل للوحة التحكم
                </button>
                <button
                  onClick={() => router.push("/settings")}
                  className="w-full py-3 border rounded-xl text-sm text-muted-foreground hover:bg-muted transition-colors"
                >
                  إعداد متقدم
                </button>
              </div>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          تجربة مجانية 21 يوم — لا بطاقة ائتمان — يمكنك الإلغاء في أي وقت
        </p>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">جارٍ التحميل...</div>}>
      <OnboardingContent />
    </Suspense>
  );
}
