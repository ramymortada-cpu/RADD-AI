"use client";

import { useEffect, useState } from "react";
import {
  Star, TrendingDown, Users, Clock,
  CheckCircle2, AlertTriangle, RefreshCw, Award, UserCheck,
} from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────
interface RaddScore {
  total: number;
  grade: string;
  summary_ar: string;
  breakdown: {
    automation: number;
    quality: number;
    escalation_health: number;
    knowledge_coverage: number;
    customer_happiness: number;
  };
}

interface ChurnAlert {
  customer_id: string;
  customer_tier: string;
  risk_level: "low" | "medium" | "high" | "critical";
  reason: string;
  days_inactive: number;
  total_revenue: number;
  suggested_action: string;
}

interface ChurnData {
  summary: { total: number; critical: number; high: number; medium: number; at_risk_revenue: number };
  alerts: ChurnAlert[];
}

interface AgentMetrics {
  user_id: string;
  agent_name: string;
  total_assigned: number;
  total_resolved: number;
  resolution_rate: number;
  avg_resolution_minutes: number;
  estimated_csat: number;
}

interface AgentData {
  summary: { agents: number; avg_csat: number; avg_resolution_minutes: number; total_resolved: number };
  agents: AgentMetrics[];
}

// ─── API fetchers ─────────────────────────────────────────────────────────────
const getRaddScore = (days = 30) =>
  apiFetch<RaddScore>(`/admin/radd-score?period_days=${days}`);
const getChurnRadar = (days = 45) =>
  apiFetch<ChurnData>(`/admin/churn-radar?inactive_days=${days}`);
const getAgentPerformance = (days = 30) =>
  apiFetch<AgentData>(`/admin/agent-performance?period_days=${days}`);

// ─── Score Ring ───────────────────────────────────────────────────────────────
function ScoreRing({ score, grade }: { score: number; grade: string }) {
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#f59e0b" : "#ef4444";
  const circumference = 2 * Math.PI * 45;
  const strokeDash = (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-32 h-32">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="45" fill="none" stroke="#e5e7eb" strokeWidth="8" />
          <circle
            cx="50" cy="50" r="45" fill="none"
            stroke={color} strokeWidth="8"
            strokeDasharray={`${strokeDash} ${circumference}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 1s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold">{score}</span>
          <span className="text-xs text-muted-foreground">/ 100</span>
        </div>
      </div>
      <div
        className="px-3 py-1 rounded-full text-sm font-bold"
        style={{ background: color + "20", color }}
      >
        درجة {grade}
      </div>
    </div>
  );
}

// ─── Risk Badge ───────────────────────────────────────────────────────────────
const RISK_STYLES: Record<string, string> = {
  critical: "text-red-700 bg-red-50 border-red-200",
  high: "text-orange-700 bg-orange-50 border-orange-200",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  low: "text-blue-700 bg-blue-50 border-blue-200",
};
const RISK_LABELS: Record<string, string> = {
  critical: "حرج", high: "مرتفع", medium: "متوسط", low: "منخفض"
};

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [score, setScore] = useState<RaddScore | null>(null);
  const [churn, setChurn] = useState<ChurnData | null>(null);
  const [agents, setAgents] = useState<AgentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [s, c, a] = await Promise.all([
        getRaddScore(),
        getChurnRadar(),
        getAgentPerformance(),
      ]);
      setScore(s);
      setChurn(c);
      setAgents(a);
    } catch {
      setError("تعذّر تحميل بيانات التحليلات");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="تحليلات الأداء" subtitle="RADD Score · رادار التلاشي · أداء الفريق" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="flex justify-end">
          <button onClick={load} className="p-2 rounded-lg text-muted-foreground hover:bg-muted transition-colors">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">{error}</div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-64 rounded-xl bg-muted animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {/* ── RADD Score ── */}
            {score && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Award className="h-4 w-4 text-primary" />
                    RADD Score — تقييم أداء رَدّ في متجرك
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col md:flex-row items-center gap-8">
                    <ScoreRing score={score.total} grade={score.grade} />
                    <div className="flex-1 space-y-3">
                      <p className="text-sm text-muted-foreground">{score.summary_ar}</p>
                      <div className="space-y-2">
                        {[
                          { label: "معدل الأتمتة", val: score.breakdown.automation, max: 30 },
                          { label: "جودة الردود", val: score.breakdown.quality, max: 25 },
                          { label: "صحة التصعيد", val: score.breakdown.escalation_health, max: 20 },
                          { label: "تغطية المعرفة", val: score.breakdown.knowledge_coverage, max: 15 },
                          { label: "رضا العملاء", val: score.breakdown.customer_happiness, max: 10 },
                        ].map(({ label, val, max }) => (
                          <div key={label} className="flex items-center gap-3">
                            <span className="text-xs text-muted-foreground w-28 text-start">{label}</span>
                            <div className="flex-1 h-2 bg-muted rounded-full">
                              <div
                                className="h-2 bg-primary rounded-full transition-all"
                                style={{ width: `${(val / max) * 100}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium w-12 text-start">{val}/{max}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* ── Churn Radar ── */}
            {churn && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingDown className="h-4 w-4 text-red-500" />
                    رادار التلاشي — عملاء في خطر الرحيل
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Summary */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "إجمالي في خطر", val: churn.summary.total, color: "text-foreground" },
                      { label: "خطر حرج", val: churn.summary.critical, color: "text-red-600" },
                      { label: "خطر مرتفع", val: churn.summary.high, color: "text-orange-600" },
                      { label: "إيرادات في خطر", val: `${churn.summary.at_risk_revenue.toLocaleString("ar-SA", { maximumFractionDigits: 0 })} ر.س`, color: "text-red-600" },
                    ].map(({ label, val, color }) => (
                      <div key={label} className="p-3 rounded-lg bg-muted/40 text-center">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className={`text-xl font-bold ${color}`}>{val}</p>
                      </div>
                    ))}
                  </div>

                  {/* Alerts list */}
                  {churn.alerts.length === 0 ? (
                    <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 px-4 py-3 rounded-lg">
                      <CheckCircle2 className="h-4 w-4" />
                      لا يوجد عملاء في خطر التلاشي حالياً
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {churn.alerts.slice(0, 20).map((alert) => (
                        <div key={alert.customer_id} className="flex items-start gap-3 p-3 rounded-lg bg-muted/20 hover:bg-muted/40 transition-colors">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium border shrink-0 ${RISK_STYLES[alert.risk_level]}`}>
                            {RISK_LABELS[alert.risk_level]}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium">{alert.reason}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{alert.suggested_action}</p>
                          </div>
                          <div className="text-end shrink-0">
                            <p className="text-xs text-muted-foreground">{alert.days_inactive} يوم</p>
                            {alert.total_revenue > 0 && (
                              <p className="text-xs font-medium text-primary">{alert.total_revenue.toLocaleString("ar-SA", { maximumFractionDigits: 0 })} ر.س</p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* ── Agent Performance ── */}
            {agents && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <UserCheck className="h-4 w-4 text-primary" />
                    أداء الفريق البشري
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Team summary */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[
                      { label: "الموظفون النشطون", val: agents.summary.agents, icon: <Users className="h-4 w-4 text-primary" /> },
                      { label: "متوسط CSAT", val: `${agents.summary.avg_csat}/5`, icon: <Star className="h-4 w-4 text-amber-500" /> },
                      { label: "متوسط وقت الحل", val: `${agents.summary.avg_resolution_minutes} د`, icon: <Clock className="h-4 w-4 text-blue-500" /> },
                      { label: "محادثات مُحلّة", val: agents.summary.total_resolved, icon: <CheckCircle2 className="h-4 w-4 text-green-500" /> },
                    ].map(({ label, val, icon }) => (
                      <div key={label} className="p-3 rounded-lg bg-muted/40 text-center">
                        <div className="flex justify-center mb-1">{icon}</div>
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="text-lg font-bold">{val}</p>
                      </div>
                    ))}
                  </div>

                  {/* Agent table */}
                  {agents.agents.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">لا توجد بيانات موظفين بعد</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/30">
                          <th className="px-3 py-2 text-start text-xs font-medium text-muted-foreground">الموظف</th>
                          <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">تعيينات</th>
                          <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">مُحلّة</th>
                          <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">وقت الحل</th>
                          <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">CSAT</th>
                        </tr>
                      </thead>
                      <tbody>
                        {agents.agents.map((agent) => (
                          <tr key={agent.user_id} className="border-b last:border-0 hover:bg-muted/20">
                            <td className="px-3 py-2 font-medium">{agent.agent_name}</td>
                            <td className="px-3 py-2 text-center text-muted-foreground">{agent.total_assigned}</td>
                            <td className="px-3 py-2 text-center text-green-700 font-medium">{agent.total_resolved}</td>
                            <td className="px-3 py-2 text-center text-muted-foreground">{agent.avg_resolution_minutes} د</td>
                            <td className="px-3 py-2 text-center">
                              <span className={`font-bold ${agent.estimated_csat >= 4 ? "text-green-600" : agent.estimated_csat >= 3 ? "text-amber-600" : "text-red-600"}`}>
                                {agent.estimated_csat}
                              </span>
                              <span className="text-xs text-muted-foreground">/5</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}
