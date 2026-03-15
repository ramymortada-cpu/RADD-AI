"use client";

import { useEffect, useState } from "react";
import {
  ShieldCheck,
  RefreshCw,
  Phone,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
} from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────
interface CODShieldStats {
  total_calls: number;
  confirmed: number;
  cancelled: number;
  no_answer: number;
  pending: number;
  save_attempted: number;
  confirmation_rate: number;
  revenue_saved: number;
}

interface CODShieldCallItem {
  id: string;
  order_id: string;
  customer_name: string | null;
  customer_phone: string;
  status: string;
  call_type: string;
  attempt_count: number;
  customer_response: string | null;
  created_at: string;
  called_at: string | null;
}

interface CODShieldResponse {
  stats: CODShieldStats;
  calls: CODShieldCallItem[];
}

const STATUS_LABELS: Record<string, string> = {
  pending: "قيد التأكيد",
  calling: "قيد الاتصال",
  confirmed: "مؤكدة",
  cancelled: "ملغاة",
  no_answer: "لا إجابة",
  save_attempted: "محاولة إنقاذ",
};

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "secondary",
  calling: "secondary",
  confirmed: "default",
  cancelled: "destructive",
  no_answer: "outline",
  save_attempted: "outline",
};

function StatusBadge({ status }: { status: string }) {
  const label = STATUS_LABELS[status] ?? status;
  const variant = STATUS_VARIANTS[status] ?? "outline";
  return <Badge variant={variant} className="text-xs">{label}</Badge>;
}

function CallCard({ call }: { call: CODShieldCallItem }) {
  return (
    <Card className="border hover:bg-muted/30 transition-colors">
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm truncate">
              {call.customer_name || call.customer_phone}
            </p>
            <p className="text-xs text-muted-foreground">طلب #{call.order_id}</p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <StatusBadge status={call.status} />
              <span className="text-xs text-muted-foreground">
                محاولة {call.attempt_count}
              </span>
            </div>
            {call.customer_response && (
              <p className="text-xs text-muted-foreground mt-1 arabic-text line-clamp-2">
                {call.customer_response}
              </p>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              {formatRelativeTime(call.created_at)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function CODShieldPage() {
  const [data, setData] = useState<CODShieldResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState(7);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch<CODShieldResponse>(`/cod-shield/summary?days=${days}`);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "تعذّر تحميل البيانات");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [days]);

  useEffect(() => {
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [days]);

  const pendingCalls = data?.calls.filter((c) =>
    ["pending", "calling"].includes(c.status)
  ) ?? [];
  const confirmedCalls = data?.calls.filter((c) => c.status === "confirmed") ?? [];
  const problemCalls = data?.calls.filter((c) =>
    ["cancelled", "no_answer", "save_attempted"].includes(c.status)
  ) ?? [];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar
        title="درع الـ COD"
        subtitle="متابعة مكالمات تأكيد الطلبات وإيرادات الإنقاذ"
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm"
          >
            <option value={7}>آخر 7 أيام</option>
            <option value={14}>آخر 14 يوماً</option>
            <option value={30}>آخر 30 يوماً</option>
          </select>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-muted-foreground hover:bg-muted transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            تحديث
          </button>
        </div>

        {/* Stats */}
        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : data?.stats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  نسبة التأكيد
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-green-600">
                  {data.stats.confirmation_rate}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  طلبات مؤكدة
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{data.stats.confirmed}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  إيرادات مُنقذة
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  {data.stats.revenue_saved.toLocaleString("ar-EG")} ج.م
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Phone className="h-4 w-4" />
                  إجمالي المكالمات
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{data.stats.total_calls}</p>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {/* Kanban */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Clock className="h-4 w-4 text-amber-500" />
                قيد التأكيد
                <Badge variant="secondary" className="text-xs">
                  {pendingCalls.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-20 rounded-lg bg-muted animate-pulse" />
                ))
              ) : pendingCalls.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  لا توجد مكالمات معلقة
                </div>
              ) : (
                pendingCalls.map((c) => <CallCard key={c.id} call={c} />)
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                مؤكدة
                <Badge variant="default" className="text-xs">
                  {confirmedCalls.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-20 rounded-lg bg-muted animate-pulse" />
                ))
              ) : confirmedCalls.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  لا توجد مكالمات مؤكدة
                </div>
              ) : (
                confirmedCalls.map((c) => <CallCard key={c.id} call={c} />)
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <XCircle className="h-4 w-4 text-red-500" />
                ملغاة / مشكلة
                <Badge variant="destructive" className="text-xs">
                  {problemCalls.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
              {loading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-20 rounded-lg bg-muted animate-pulse" />
                ))
              ) : problemCalls.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  لا توجد مكالمات ملغاة
                </div>
              ) : (
                problemCalls.map((c) => <CallCard key={c.id} call={c} />)
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
