"use client";

import { useEffect, useState } from "react";
import TopBar from "@/components/layout/topbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import {
  DollarSign,
  TrendingUp,
  ShoppingCart,
  RotateCcw,
  Trophy,
  ArrowUpRight,
} from "lucide-react";

// ─── Types ───

type Stats = {
  total_attributed: number;
  assisted_sales: number;
  carts_recovered: number;
  returns_prevented: number;
  subscription_cost: number;
  roi_multiplier: number;
  events_count: number;
};

type RevenueEvent = {
  id: string;
  event_type: string;
  order_id: string;
  order_value: number;
  created_at: string;
  source: string;
};

type DashboardData = {
  stats: Stats;
  recent_events: RevenueEvent[];
  period_days: number;
};

// ─── Event Type Config ───

const eventTypeConfig: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  assisted_sale: {
    label: "بيعة مساعدة",
    color: "bg-green-100 text-green-800",
    icon: <ShoppingCart className="h-4 w-4" />,
  },
  cart_recovered: {
    label: "سلة مسترجعة",
    color: "bg-blue-100 text-blue-800",
    icon: <RotateCcw className="h-4 w-4" />,
  },
  return_prevented: {
    label: "إرجاع تم منعه",
    color: "bg-purple-100 text-purple-800",
    icon: <TrendingUp className="h-4 w-4" />,
  },
};

// ─── Main Page ───

export default function RevenueDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const res = await apiFetch<DashboardData>(
          `/revenue/dashboard?days=${days}`
        );
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "تعذّر تحميل البيانات");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [days]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar
        title="لوحة الإيرادات"
        subtitle="القيمة التي يحققها رَدّ لمتجرك"
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Period selector */}
        <div className="flex gap-2 justify-end">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                days === d
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {d} يوم
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-32 rounded-lg bg-muted animate-pulse"
              />
            ))}
          </div>
        ) : error ? (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        ) : data ? (
          <>
            {/* ─── Hero Card: ROI ─── */}
            <Card className="border-2 border-primary/30 bg-gradient-to-l from-primary/5 to-transparent">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      دفعت هذا الشهر
                    </p>
                    <p className="text-2xl font-bold">
                      {data.stats.subscription_cost.toLocaleString()} ريال
                    </p>
                  </div>
                  <div className="text-center">
                    <Trophy className="h-10 w-10 text-primary mx-auto mb-1" />
                    <p className="text-3xl font-bold text-primary">
                      {data.stats.roi_multiplier}x
                    </p>
                    <p className="text-xs text-muted-foreground">
                      عائد الاستثمار
                    </p>
                  </div>
                  <div className="text-left">
                    <p className="text-sm text-muted-foreground">
                      رَدّ حقق لك
                    </p>
                    <p className="text-2xl font-bold text-green-600">
                      {data.stats.total_attributed.toLocaleString()} ريال
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* ─── Breakdown Cards ─── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-full bg-green-100 p-2">
                      <ShoppingCart className="h-6 w-6 text-green-600" />
                    </div>
                    <div>
                      <p className="text-xl font-bold">
                        {data.stats.assisted_sales.toLocaleString()}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        بيعات مساعدة
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-full bg-blue-100 p-2">
                      <RotateCcw className="h-6 w-6 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-xl font-bold">
                        {data.stats.carts_recovered.toLocaleString()}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        سلات مسترجعة
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-3">
                    <div className="rounded-full bg-purple-100 p-2">
                      <TrendingUp className="h-6 w-6 text-purple-600" />
                    </div>
                    <div>
                      <p className="text-xl font-bold">
                        {data.stats.returns_prevented.toLocaleString()}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        إرجاعات تم منعها
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* ─── Recent Events ─── */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  آخر الإيرادات المنسوبة ({data.stats.events_count} حدث)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.recent_events.length === 0 ? (
                  <div className="text-center py-8">
                    <DollarSign className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                    <p className="text-sm text-muted-foreground">
                      لا توجد إيرادات منسوبة بعد.
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      ستظهر هنا عندما يساعد رَدّ في إتمام عمليات بيع.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {data.recent_events.map((event) => {
                      const config =
                        eventTypeConfig[event.event_type] || {
                          label: event.event_type,
                          color: "bg-gray-100",
                          icon: (
                            <ArrowUpRight className="h-4 w-4" />
                          ),
                        };
                      return (
                        <div
                          key={event.id}
                          className="flex items-center justify-between border-b pb-2 last:border-0"
                        >
                          <div className="flex items-center gap-3">
                            <Badge
                              variant="outline"
                              className={`${config.color} gap-1`}
                            >
                              {config.icon}
                              {config.label}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                              #{event.order_id}
                            </span>
                          </div>
                          <div className="text-left">
                            <span className="font-semibold text-green-600">
                              +{event.order_value.toLocaleString()} ريال
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        ) : null}
      </div>
    </div>
  );
}
