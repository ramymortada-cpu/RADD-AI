"use client";

import { useEffect, useState } from "react";
import {
  MessageSquare,
  Bot,
  Clock,
  AlertTriangle,
  Star,
  TrendingUp,
  Inbox,
  ShieldAlert,
} from "lucide-react";
import TopBar from "@/components/layout/topbar";
import KPICard from "@/components/dashboard/kpi-card";
import LiveFeed from "@/components/dashboard/live-feed";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAnalytics, type KPIs } from "@/lib/api";

function formatSeconds(s: number): string {
  if (s < 60) return `${s.toFixed(0)}ث`;
  return `${(s / 60).toFixed(1)}د`;
}

export default function DashboardPage() {
  const [kpis, setKpis] = useState<KPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const data = await getAnalytics();
        setKpis(data);
      } catch {
        setError("تعذّر تحميل البيانات");
      } finally {
        setLoading(false);
      }
    }
    load();
    // Refresh every 30 seconds
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="الرئيسية" subtitle="نظرة عامة على أداء المنصة" />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* 8 KPI Cards */}
        {loading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-32 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : kpis ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KPICard
              title="محادثات نشطة"
              value={kpis.active_conversations}
              icon={MessageSquare}
              colorClass="text-blue-600"
              subtitle="الآن"
            />
            <KPICard
              title="معدل الأتمتة"
              value={kpis.automation_rate}
              unit="%"
              icon={Bot}
              colorClass="text-green-600"
              subtitle="آخر 24 ساعة"
              trend={kpis.automation_rate >= 70 ? "up" : "down"}
              trendValue={kpis.automation_rate >= 70 ? "فوق الهدف" : "دون الهدف (70%)"}
            />
            <KPICard
              title="متوسط وقت الرد"
              value={formatSeconds(kpis.avg_response_time_seconds)}
              icon={Clock}
              colorClass="text-teal-600"
              subtitle="آخر 24 ساعة"
            />
            <KPICard
              title="معدل التصعيد"
              value={kpis.escalation_rate}
              unit="%"
              icon={AlertTriangle}
              colorClass={kpis.escalation_rate > 20 ? "text-red-600" : "text-amber-600"}
              subtitle="آخر 24 ساعة"
              trend={kpis.escalation_rate > 20 ? "up" : "neutral"}
            />
            <KPICard
              title="رسائل اليوم"
              value={kpis.messages_today}
              icon={TrendingUp}
              colorClass="text-indigo-600"
              subtitle="رسائل العملاء الواردة"
            />
            <KPICard
              title="تصعيدات معلّقة"
              value={kpis.pending_escalations}
              icon={Inbox}
              colorClass={kpis.pending_escalations > 5 ? "text-red-600" : "text-orange-600"}
              subtitle="تنتظر موظفاً"
            />
            <KPICard
              title="تقييم الرضا"
              value={kpis.csat_score !== null ? `${kpis.csat_score}%` : "—"}
              icon={Star}
              colorClass="text-yellow-500"
              subtitle="قريباً"
            />
            <KPICard
              title="معدل الهلوسة"
              value={kpis.hallucination_rate}
              unit="%"
              icon={ShieldAlert}
              colorClass={kpis.hallucination_rate > 10 ? "text-red-600" : "text-green-600"}
              subtitle="استجابات منخفضة التحقق"
              trend={kpis.hallucination_rate > 10 ? "up" : "neutral"}
            />
          </div>
        ) : null}

        {/* Live feed + last updated */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader className="pb-0">
              <CardTitle className="text-base">نشاط المحادثات</CardTitle>
            </CardHeader>
            <CardContent className="h-64 flex items-center justify-center">
              <p className="text-sm text-muted-foreground">
                سيتم إضافة الرسم البياني في الإصدار القادم
              </p>
            </CardContent>
          </Card>

          <Card className="flex flex-col h-80">
            <CardHeader className="pb-0 shrink-0">
              <CardTitle className="text-base">الأحداث المباشرة</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-hidden mt-3">
              <LiveFeed />
            </CardContent>
          </Card>
        </div>

        {kpis && (
          <p className="text-xs text-muted-foreground text-center">
            آخر تحديث:{" "}
            {new Date(kpis.computed_at).toLocaleTimeString("ar-SA")}
          </p>
        )}
      </div>
    </div>
  );
}
