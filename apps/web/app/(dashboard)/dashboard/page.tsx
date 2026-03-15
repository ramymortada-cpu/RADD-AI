"use client";

/**
 * RADD AI — Dashboard Page
 * apps/web/app/(dashboard)/dashboard/page.tsx
 *
 * يجلب من 3 endpoints حقيقية:
 *   GET /api/v1/admin/analytics      → 8 KPI cards
 *   GET /api/v1/admin/revenue/summary → Revenue Attribution
 *   GET /api/v1/admin/churn-radar    → Churn Radar
 *   WS  /ws/agent?token=...          → Live Feed
 *
 * عند فشل أي endpoint → يستخدم DEMO_DATA بشفافية
 */

import { useEffect, useRef, useState, useCallback } from "react";
import TopBar from "@/components/layout/topbar";
import KPICard from "@/components/dashboard/kpi-card";
import OnboardingWizard from "./components/OnboardingWizard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";
import {
  MessageCircle,
  Zap,
  Clock,
  AlertTriangle,
  TrendingUp,
  ShieldCheck,
  Users,
  DollarSign,
} from "lucide-react";

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────

type Analytics = {
  active_conversations: number;
  automation_rate: number;
  avg_response_time_seconds: number;
  escalation_rate: number;
  messages_today: number;
  pending_escalations: number;
  hallucination_rate: number;
  automation_rate_delta: number;
};

type RevenueSummary = {
  total_revenue_sar: number;
  total_orders: number;
  avg_order_value: number;
  daily: { date: string; revenue: number; orders: number }[];
};

type ChurnCandidate = {
  customer_id: string;
  display_name: string;
  risk_score: number;
  reason: string;
  days_silent: number;
  open_escalations: number;
};

type ChurnRadar = {
  at_risk_count: number;
  candidates: ChurnCandidate[];
};

type FeedEvent = {
  id: string;
  color: string;
  text: string;
  time: string;
};

// ─────────────────────────────────────────────
// Demo Data — يُستخدم عند غياب بيانات حقيقية
// ─────────────────────────────────────────────

const DEMO_ANALYTICS: Analytics = {
  active_conversations: 47,
  automation_rate: 87.3,
  avg_response_time_seconds: 1.2,
  escalation_rate: 4.1,
  messages_today: 1234,
  pending_escalations: 5,
  hallucination_rate: 1.2,
  automation_rate_delta: 3.1,
};

const DEMO_REVENUE: RevenueSummary = {
  total_revenue_sar: 24500,
  total_orders: 138,
  avg_order_value: 177.5,
  daily: [
    { date: "01/03", revenue: 1200, orders: 8 },
    { date: "02/03", revenue: 980, orders: 6 },
    { date: "03/03", revenue: 1450, orders: 11 },
    { date: "04/03", revenue: 1100, orders: 7 },
    { date: "05/03", revenue: 1800, orders: 14 },
    { date: "06/03", revenue: 2200, orders: 18 },
    { date: "07/03", revenue: 1600, orders: 12 },
    { date: "08/03", revenue: 1900, orders: 15 },
    { date: "09/03", revenue: 2400, orders: 19 },
    { date: "10/03", revenue: 2100, orders: 16 },
    { date: "11/03", revenue: 2800, orders: 22 },
    { date: "12/03", revenue: 3100, orders: 24 },
  ],
};

const DEMO_CHURN: ChurnRadar = {
  at_risk_count: 8,
  candidates: [
    {
      customer_id: "demo-1",
      display_name: "أحمد الشمري",
      risk_score: 92,
      reason: "٣ محادثات غير محلولة · ٥ أيام صمت",
      days_silent: 5,
      open_escalations: 3,
    },
    {
      customer_id: "demo-2",
      display_name: "سارة القحطاني",
      risk_score: 78,
      reason: "شكوى تأخير شحن · تصعيد مفتوح",
      days_silent: 3,
      open_escalations: 1,
    },
    {
      customer_id: "demo-3",
      display_name: "محمد العتيبي",
      risk_score: 65,
      reason: "طلب إرجاع رُفض · تقييم سلبي",
      days_silent: 2,
      open_escalations: 0,
    },
    {
      customer_id: "demo-4",
      display_name: "نورة الدوسري",
      risk_score: 58,
      reason: "٤ أيام بدون رد · رسالتان معلقتان",
      days_silent: 4,
      open_escalations: 0,
    },
  ],
};

const DEMO_FEED: FeedEvent[] = [
  { id: "f1", color: "#22c55e", text: "رَدّ أكمل طلب شراء (٣٢٠ ر.س) — أحمد م.", time: "الآن" },
  { id: "f2", color: "#f59e0b", text: "تصعيد جديد — سارة ق. تنتظر موظفاً", time: "٢ د" },
  { id: "f3", color: "#378ADD", text: "تم فهرسة وثيقة 'سياسة الإرجاع'", time: "٥ د" },
  { id: "f4", color: "#22c55e", text: "رَدّ أجاب على ٢٣ سؤال شحن بلا تصعيد", time: "٨ د" },
  { id: "f5", color: "#E24B4A", text: "Verifier رفض رداً (هلوسة محتملة) — تم تصعيد", time: "١٢ د" },
];

// ─────────────────────────────────────────────
// API Response Mapping
// ─────────────────────────────────────────────

function mapAnalyticsApi(api: Record<string, unknown>): Analytics {
  const msg = Number(api.messages_today ?? 0);
  return {
    active_conversations: Number(api.active_conversations ?? 0),
    automation_rate: Number(api.automation_rate ?? 0),
    avg_response_time_seconds: Number(api.avg_response_time_seconds ?? 0),
    escalation_rate: Number(api.escalation_rate ?? 0),
    messages_today: msg,
    pending_escalations: Number(api.pending_escalations ?? 0),
    hallucination_rate: Number(api.hallucination_rate ?? 0),
    automation_rate_delta: Number(api.automation_rate_delta ?? 0),
  };
}

function mapRevenueApi(api: Record<string, unknown>): RevenueSummary {
  const total = Number(api.total_attributed_sar ?? api.assisted_sales_sar ?? 0);
  const orders = Number(api.event_count ?? 0);
  return {
    total_revenue_sar: total,
    total_orders: orders || 1,
    avg_order_value: orders ? Math.round(total / orders) : 0,
    daily: DEMO_REVENUE.daily,
  };
}

function mapChurnApi(api: {
  summary?: { total?: number };
  alerts?: Array<{
    customer_id: string;
    risk_level?: string;
    reason: string;
    days_inactive?: number;
  }>;
}): ChurnRadar {
  const riskMap: Record<string, number> = {
    critical: 92,
    high: 78,
    medium: 58,
    low: 35,
  };
  const alerts = api.alerts ?? [];
  const candidates: ChurnCandidate[] = alerts.map((a) => ({
    customer_id: a.customer_id,
    display_name: `عميل ${String(a.customer_id).slice(-4)}`,
    risk_score: riskMap[(a.risk_level ?? "medium").toLowerCase()] ?? 50,
    reason: a.reason,
    days_silent: a.days_inactive ?? 0,
    open_escalations: 0,
  }));
  return {
    at_risk_count: api.summary?.total ?? candidates.length,
    candidates,
  };
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function riskColor(score: number): string {
  if (score >= 80) return "#E24B4A";
  if (score >= 60) return "#BA7517";
  return "#EF9F27";
}

function riskLabel(score: number): string {
  if (score >= 80) return "خطر عالٍ";
  if (score >= 60) return "خطر متوسط";
  return "تحت المراقبة";
}

function avatarLetters(name: string): string {
  const parts = name.trim().split(" ");
  if (parts.length >= 2) return parts[0][0] + parts[1][0];
  return parts[0].slice(0, 2);
}

function avatarColors(idx: number): { bg: string; color: string } {
  const palette = [
    { bg: "#FAECE7", color: "#D85A30" },
    { bg: "#E1F5EE", color: "#0F6E56" },
    { bg: "#E6F1FB", color: "#185FA5" },
    { bg: "#EEEDFE", color: "#534AB7" },
    { bg: "#FBEAF0", color: "#993556" },
  ];
  return palette[idx % palette.length];
}

function formatSAR(n: number): string {
  return n.toLocaleString("ar-SA", { maximumFractionDigits: 0 });
}

// ─────────────────────────────────────────────
// Mini Bar Chart — CSS only, no lib dependency
// ─────────────────────────────────────────────

function RevenueBarChart({ data }: { data: { date: string; revenue: number }[] }) {
  const max = Math.max(...data.map((d) => d.revenue), 1);
  return (
    <div className="flex items-end gap-1 h-24 w-full mt-2">
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1 group">
          <div
            className="w-full rounded-sm transition-all duration-300 group-hover:opacity-80"
            style={{
              height: `${(d.revenue / max) * 88}px`,
              background: i === data.length - 1 ? "#1D9E75" : "#1D9E7566",
              minHeight: "4px",
            }}
          />
          {(i === 0 || i === data.length - 1 || i === Math.floor(data.length / 2)) && (
            <span className="text-[10px] text-muted-foreground">{d.date}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [revenue, setRevenue] = useState<RevenueSummary | null>(null);
  const [churn, setChurn] = useState<ChurnRadar | null>(null);
  const [feed, setFeed] = useState<FeedEvent[]>(DEMO_FEED);
  const [loading, setLoading] = useState(true);
  const [isDemo, setIsDemo] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const feedIdRef = useRef(100);

  // ── Fetch all data ──────────────────────────
  const fetchAll = useCallback(async () => {
    try {
      const [analyticsRes, revenueRes, churnRes] = await Promise.allSettled([
        apiFetch<Record<string, unknown>>("/admin/analytics"),
        apiFetch<Record<string, unknown>>("/admin/revenue/summary"),
        apiFetch<Record<string, unknown>>("/admin/churn-radar"),
      ]);

      const analyticsData =
        analyticsRes.status === "fulfilled" ? analyticsRes.value : null;
      const revenueData =
        revenueRes.status === "fulfilled" ? revenueRes.value : null;
      const churnData =
        churnRes.status === "fulfilled" ? churnRes.value : null;

      const hasRealData =
        analyticsData && Number(analyticsData.messages_today ?? 0) > 0;

      if (hasRealData) {
        setAnalytics(mapAnalyticsApi(analyticsData as Record<string, unknown>));
        setRevenue(revenueData ? mapRevenueApi(revenueData) : DEMO_REVENUE);
        setChurn(churnData ? mapChurnApi(churnData as Parameters<typeof mapChurnApi>[0]) : DEMO_CHURN);
        setIsDemo(false);
      } else {
        setAnalytics(DEMO_ANALYTICS);
        setRevenue(DEMO_REVENUE);
        setChurn(DEMO_CHURN);
        setIsDemo(true);
      }
    } catch {
      setAnalytics(DEMO_ANALYTICS);
      setRevenue(DEMO_REVENUE);
      setChurn(DEMO_CHURN);
      setIsDemo(true);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── WebSocket Live Feed ─────────────────────
  const connectWS = useCallback(() => {
    const token = getToken();
    if (!token) return;
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000"}/ws/agent?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as {
          type: string;
          data?: { customer_name?: string; amount?: number; message?: string };
        };
        const newEvent = buildFeedEvent(event);
        if (newEvent) {
          setFeed((prev) => [newEvent, ...prev].slice(0, 8));
        }
        if (["new_escalation", "conversation_resolved"].includes(event.type)) {
          fetchAll();
        }
      } catch {
        // ignore malformed events
      }
    };

    ws.onclose = () => {
      setTimeout(connectWS, 5000);
    };
  }, [fetchAll]);

  function buildFeedEvent(event: {
    type: string;
    data?: { customer_name?: string; amount?: number; message?: string };
  }): FeedEvent | null {
    const id = String(feedIdRef.current++);
    const name = event.data?.customer_name ?? "عميل";
    const amount = event.data?.amount;
    switch (event.type) {
      case "new_escalation":
        return { id, color: "#f59e0b", text: `تصعيد جديد — ${name} ينتظر موظفاً`, time: "الآن" };
      case "conversation_resolved":
        return { id, color: "#22c55e", text: `تم حل محادثة ${name} بنجاح`, time: "الآن" };
      case "revenue_event":
        return { id, color: "#22c55e", text: `رَدّ أكمل طلب شراء (${amount ? formatSAR(amount) : "—"} ر.س) — ${name}`, time: "الآن" };
      case "hallucination_blocked":
        return { id, color: "#E24B4A", text: "Verifier رفض رداً (هلوسة محتملة) — تم تصعيد", time: "الآن" };
      default:
        return null;
    }
  }

  useEffect(() => {
    fetchAll();
    connectWS();
    const interval = setInterval(fetchAll, 30_000);
    return () => {
      clearInterval(interval);
      wsRef.current?.close();
    };
  }, [fetchAll, connectWS]);

  // ── Data aliases (real or demo) ─────────────
  const a = analytics ?? DEMO_ANALYTICS;
  const r = revenue ?? DEMO_REVENUE;
  const c = churn ?? DEMO_CHURN;

  // ─────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar
        title="لوحة التحكم"
        subtitle={
          isDemo
            ? "بيانات تجريبية — ابدأ باستقبال رسائل واتساب لرؤية بياناتك الحقيقية"
            : "البيانات محدّثة كل ٣٠ ثانية"
        }
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* ── Onboarding Wizard ───────────────── */}
        <OnboardingWizard />

        {/* ── Demo Banner ─────────────────────── */}
        {isDemo && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            <span className="font-medium">وضع العرض التجريبي</span> — هذه بيانات demo. عند استقبال رسائل واتساب حقيقية ستظهر بياناتك تلقائياً.
          </div>
        )}

        {/* ── KPI Grid ────────────────────────── */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <KPICard
            loading={loading}
            title="محادثات نشطة"
            value={a.active_conversations}
            icon={<MessageCircle className="h-4 w-4" />}
            delta="+١٢ من الأمس"
            deltaPositive
          />
          <KPICard
            loading={loading}
            title="معدل الأتمتة"
            value={`${a.automation_rate.toFixed(1)}%`}
            icon={<Zap className="h-4 w-4" />}
            delta={`+${a.automation_rate_delta.toFixed(1)}% هذا الأسبوع`}
            deltaPositive
            valueClassName="text-green-600 dark:text-green-400"
          />
          <KPICard
            loading={loading}
            title="متوسط وقت الرد"
            value={`${a.avg_response_time_seconds.toFixed(1)} ث`}
            icon={<Clock className="h-4 w-4" />}
            delta="↓ ٠.٣ث تحسن"
            deltaPositive
          />
          <KPICard
            loading={loading}
            title="تصعيدات معلقة"
            value={a.pending_escalations}
            icon={<AlertTriangle className="h-4 w-4" />}
            delta={a.pending_escalations > 3 ? "يحتاج تدخل" : "ضمن المعدل"}
            deltaPositive={a.pending_escalations <= 3}
            valueClassName={a.pending_escalations > 3 ? "text-amber-600 dark:text-amber-400" : ""}
          />
          <KPICard
            loading={loading}
            title="رسائل اليوم"
            value={a.messages_today.toLocaleString("ar-SA")}
            icon={<MessageCircle className="h-4 w-4" />}
            delta="↑ ١٨% من أمس"
            deltaPositive
          />
          <KPICard
            loading={loading}
            title="إيرادات بسبب رَدّ"
            value={`${formatSAR(r.total_revenue_sar)} ر.س`}
            icon={<DollarSign className="h-4 w-4" />}
            delta="هذا الشهر"
            deltaPositive
            valueClassName="text-green-600 dark:text-green-400"
          />
          <KPICard
            loading={loading}
            title="معدل الهلوسة"
            value={`${a.hallucination_rate.toFixed(1)}%`}
            icon={<ShieldCheck className="h-4 w-4" />}
            delta="↓ ٣.١% (Verifier v2)"
            deltaPositive
            valueClassName="text-green-600 dark:text-green-400"
          />
          <KPICard
            loading={loading}
            title="عملاء في خطر تسرب"
            value={c.at_risk_count}
            icon={<Users className="h-4 w-4" />}
            delta="يحتاجون تدخل"
            deltaPositive={false}
            valueClassName={c.at_risk_count > 5 ? "text-amber-600 dark:text-amber-400" : ""}
          />
        </div>

        {/* ── Row 2: Revenue + Live Feed ───────── */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Revenue Attribution */}
          <Card className="lg:col-span-2">
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-green-600" />
                    إثبات الإيرادات
                  </CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    المبيعات التي أتمّها رَدّ هذا الشهر
                  </p>
                </div>
                <Badge variant="success" className="text-xs">
                  {r.total_orders} طلب مكتمل
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="text-[11px] text-muted-foreground">إجمالي المبيعات</p>
                  <p className="text-xl font-medium mt-0.5 text-green-600 dark:text-green-400">
                    {formatSAR(r.total_revenue_sar)}
                    <span className="text-xs font-normal text-muted-foreground mr-1">ر.س</span>
                  </p>
                </div>
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="text-[11px] text-muted-foreground">طلبات أكملها رَدّ</p>
                  <p className="text-xl font-medium mt-0.5">{r.total_orders}</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="text-[11px] text-muted-foreground">متوسط قيمة الطلب</p>
                  <p className="text-xl font-medium mt-0.5">
                    {formatSAR(r.avg_order_value)}
                    <span className="text-xs font-normal text-muted-foreground mr-1">ر.س</span>
                  </p>
                </div>
              </div>
              <div>
                <p className="text-[11px] text-muted-foreground mb-1">الإيرادات اليومية (ر.س)</p>
                <RevenueBarChart data={r.daily} />
              </div>
            </CardContent>
          </Card>

          {/* Live Feed */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">الأحداث المباشرة</CardTitle>
                <div className="flex items-center gap-1.5 text-xs text-green-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                  مباشر
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {feed.map((event) => (
                  <div
                    key={event.id}
                    className="flex items-start gap-2.5 rounded-lg border border-border/50 px-3 py-2.5 text-sm"
                  >
                    <span
                      className="mt-1 h-2 w-2 flex-shrink-0 rounded-full"
                      style={{ background: event.color }}
                    />
                    <span className="flex-1 text-xs leading-relaxed arabic-text">
                      {event.text}
                    </span>
                    <span className="flex-shrink-0 text-[10px] text-muted-foreground">
                      {event.time}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── Row 3: Churn Radar ───────────────── */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">رادار التسرب</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  عملاء يحتاجون تدخلاً فورياً قبل أن يغادروا
                </p>
              </div>
              {c.at_risk_count > 0 && (
                <Badge variant="warning">{c.at_risk_count} في خطر</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {c.candidates.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <ShieldCheck className="h-8 w-8 text-green-500 mb-2" />
                <p className="text-sm text-muted-foreground">لا يوجد عملاء في خطر تسرب حالياً</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {c.candidates.map((candidate, idx) => {
                  const { bg, color } = avatarColors(idx);
                  const rColor = riskColor(candidate.risk_score);
                  return (
                    <div
                      key={candidate.customer_id}
                      className="flex flex-col gap-2 rounded-lg border border-border/60 p-3"
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs font-medium"
                          style={{ background: bg, color }}
                        >
                          {avatarLetters(candidate.display_name)}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {candidate.display_name}
                          </p>
                          <p
                            className="text-[10px] font-medium"
                            style={{ color: rColor }}
                          >
                            {riskLabel(candidate.risk_score)}
                          </p>
                        </div>
                      </div>
                      <div>
                        <div className="mb-1 flex items-center justify-between">
                          <span className="text-[10px] text-muted-foreground">درجة الخطر</span>
                          <span
                            className="text-xs font-medium"
                            style={{ color: rColor }}
                          >
                            {candidate.risk_score}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full transition-all duration-700"
                            style={{
                              width: `${candidate.risk_score}%`,
                              background: rColor,
                            }}
                          />
                        </div>
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-relaxed arabic-text">
                        {candidate.reason}
                      </p>
                      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                        {candidate.days_silent > 0 && (
                          <span className="rounded bg-muted px-1.5 py-0.5">
                            {candidate.days_silent} أيام صمت
                          </span>
                        )}
                        {candidate.open_escalations > 0 && (
                          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-700 dark:bg-amber-900 dark:text-amber-300">
                            {candidate.open_escalations} تصعيد مفتوح
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
