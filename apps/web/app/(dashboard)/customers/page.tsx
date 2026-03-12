"use client";

import { useEffect, useState } from "react";
import {
  Users,
  Star,
  AlertTriangle,
  RotateCcw,
  UserCheck,
  UserPlus,
  RefreshCw,
  MessageSquare,
  TrendingUp,
} from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getCustomers, type CustomerProfile } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

const TIER_LABELS: Record<string, string> = {
  new: "جديد",
  standard: "عادي",
  returning: "متكرر",
  vip: "VIP",
  at_risk: "يحتاج اهتمام",
};

const TIER_COLORS: Record<string, string> = {
  new: "bg-slate-100 text-slate-600",
  standard: "bg-blue-50 text-blue-600",
  returning: "bg-emerald-50 text-emerald-600",
  vip: "bg-amber-50 text-amber-600 font-semibold",
  at_risk: "bg-red-50 text-red-600",
};

const TIER_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  new: UserPlus,
  standard: Users,
  returning: RotateCcw,
  vip: Star,
  at_risk: AlertTriangle,
};

const TIER_FILTERS = [
  { value: "", label: "الكل" },
  { value: "vip", label: "⭐ VIP" },
  { value: "at_risk", label: "⚠️ يحتاج اهتمام" },
  { value: "returning", label: "🔄 متكرر" },
  { value: "standard", label: "عادي" },
  { value: "new", label: "جديد" },
];

function SentimentBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-muted-foreground">—</span>;
  const pct = Math.round(score * 100);
  const color = score >= 0.7 ? "bg-emerald-400" : score >= 0.4 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 bg-muted rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground">{pct}%</span>
    </div>
  );
}

export default function CustomersPage() {
  const [items, setItems] = useState<CustomerProfile[]>([]);
  const [total, setTotal] = useState(0);
  const [tier, setTier] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(t: string) {
    setLoading(true);
    setError("");
    try {
      const data = await getCustomers(t || undefined);
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("تعذّر تحميل بيانات العملاء");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(tier);
  }, [tier]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar
        title="ذاكرة العملاء"
        subtitle={`${total} عميل`}
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Tier filter tabs */}
        <div className="flex items-center gap-2 flex-wrap">
          {TIER_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setTier(f.value)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
                tier === f.value
                  ? "bg-primary text-white border-primary"
                  : "bg-white text-muted-foreground border-border hover:border-primary/40 hover:text-foreground"
              }`}
            >
              {f.label}
            </button>
          ))}
          <button
            onClick={() => load(tier)}
            className="ms-auto flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            تحديث
          </button>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "VIP", tier: "vip", icon: Star, color: "text-amber-500" },
            { label: "يحتاج اهتمام", tier: "at_risk", icon: AlertTriangle, color: "text-red-500" },
            { label: "متكرر", tier: "returning", icon: RotateCcw, color: "text-emerald-500" },
            { label: "جديد", tier: "new", icon: UserPlus, color: "text-blue-500" },
          ].map((s) => {
            const count = items.filter((c) => c.customer_tier === s.tier).length;
            return (
              <button
                key={s.tier}
                onClick={() => setTier(tier === s.tier ? "" : s.tier)}
                className={`flex items-center gap-3 p-3 rounded-xl border bg-white text-start transition-shadow hover:shadow-sm ${
                  tier === s.tier ? "border-primary/40 shadow-sm" : "border-border"
                }`}
              >
                <s.icon className={`h-5 w-5 shrink-0 ${s.color}`} />
                <div>
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                  <p className="text-xl font-bold">{loading ? "—" : count}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Table */}
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            <UserCheck className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>لا يوجد عملاء بعد في هذه الفئة</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 border-b border-border">
                <tr>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">العميل</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">الفئة</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden sm:table-cell">محادثات</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden md:table-cell">تصعيدات</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">الرضا</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground hidden lg:table-cell">آخر نشاط</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((c) => {
                  const TierIcon = TIER_ICON[c.customer_tier] || Users;
                  return (
                    <tr key={c.id} className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                            <TierIcon className="h-4 w-4 text-primary" />
                          </div>
                          <div>
                            <p className="font-medium">
                              {c.display_name || (
                                <span className="text-muted-foreground text-xs font-mono">
                                  {c.phone_hash.slice(0, 10)}…
                                </span>
                              )}
                            </p>
                            {c.salla_total_orders > 0 && (
                              <p className="text-xs text-muted-foreground">
                                {c.salla_total_orders} طلب · {c.salla_total_revenue.toLocaleString("ar-SA")} ر.س
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${TIER_COLORS[c.customer_tier]}`}>
                          {TIER_LABELS[c.customer_tier]}
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <MessageSquare className="h-3.5 w-3.5" />
                          {c.total_conversations}
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        {c.total_escalations > 0 ? (
                          <span className="flex items-center gap-1 text-orange-600 text-xs">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            {c.total_escalations}
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        <SentimentBar score={c.avg_sentiment} />
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                        {c.last_seen_at ? formatRelativeTime(c.last_seen_at) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
