"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Pause,
  Play,
  RefreshCw,
  Zap,
  AlertTriangle,
  CheckCircle2,
  Clock,
  MessageSquare,
  BarChart2,
} from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, getSettings } from "@/lib/api";
import { formatRelativeTime, INTENT_LABELS, confidenceColor } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────
interface Decision {
  message_id: string;
  conversation_id: string;
  customer_phone_hash: string;
  intent: string;
  confidence_score: number;
  resolution_path: string;
  response_preview: string;
  created_at: string | null;
  was_escalated: boolean;
}

interface Stats {
  total_auto: number;
  total_escalated: number;
  total_soft: number;
  automation_rate: number;
}

interface PendingReview {
  escalation_id: string;
  conversation_id: string;
  reason: string;
  confidence_at_escalation: number | null;
  context_package_summary: string;
  created_at: string | null;
  minutes_waiting: number;
}

const REASON_LABELS: Record<string, string> = {
  low_confidence: "ثقة منخفضة",
  unknown_intent: "نية غير معروفة",
  soft_confidence: "ثقة متوسطة",
  automation_paused: "أتمتة متوقفة",
};

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function ControlCenterPage() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [pendingReviews, setPendingReviews] = useState<PendingReview[]>([]);
  const [automationPaused, setAutomationPaused] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pauseLoading, setPauseLoading] = useState(false);
  const [resumeLoading, setResumeLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [decRes, statsRes, pendingRes, settingsRes] = await Promise.all([
        apiFetch<{ decisions: Decision[] }>("/admin/control-center/decisions"),
        apiFetch<Stats>("/admin/control-center/stats"),
        apiFetch<{ pending_reviews: PendingReview[] }>("/admin/control-center/pending-reviews"),
        getSettings(),
      ]);
      setDecisions(decRes.decisions);
      setStats(statsRes);
      setPendingReviews(pendingRes.pending_reviews);
      setAutomationPaused(Boolean(settingsRes.settings?.automation_paused));
    } catch (e) {
      setError(e instanceof Error ? e.message : "تعذّر تحميل البيانات");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handlePause() {
    setPauseLoading(true);
    try {
      await apiFetch<{ status: string }>("/admin/control-center/pause-automation", {
        method: "POST",
      });
      setAutomationPaused(true);
      await load();
    } catch {
      setError("تعذّر إيقاف الأتمتة");
    } finally {
      setPauseLoading(false);
    }
  }

  async function handleResume() {
    setResumeLoading(true);
    try {
      await apiFetch<{ status: string }>("/admin/control-center/resume-automation", {
        method: "POST",
      });
      setAutomationPaused(false);
      await load();
    } catch {
      setError("تعذّر استئناف الأتمتة");
    } finally {
      setResumeLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar
        title="مركز التحكم"
        subtitle={automationPaused ? "الأتمتة متوقفة" : "الأتمتة نشطة"}
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Pause / Resume */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="h-5 w-5" />
              حالة الأتمتة
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-4">
            {automationPaused ? (
              <Button
                onClick={handleResume}
                disabled={resumeLoading}
                className="bg-green-600 hover:bg-green-700"
              >
                <Play className="h-4 w-4 me-2" />
                {resumeLoading ? "جارٍ..." : "استئناف الأتمتة"}
              </Button>
            ) : (
              <Button
                variant="destructive"
                onClick={handlePause}
                disabled={pauseLoading}
              >
                <Pause className="h-4 w-4 me-2" />
                {pauseLoading ? "جارٍ..." : "إيقاف الأتمتة مؤقتاً"}
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={load} disabled={loading}>
              <RefreshCw className={`h-4 w-4 me-2 ${loading ? "animate-spin" : ""}`} />
              تحديث
            </Button>
          </CardContent>
        </Card>

        {/* Stats */}
        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : stats ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  تم تلقائياً اليوم
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-green-600">{stats.total_auto}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  تم تصعيدها اليوم
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-amber-600">{stats.total_escalated}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  تصعيد ناعم
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{stats.total_soft}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  معدل الأتمتة
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{stats.automation_rate}%</p>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {/* Pending Reviews */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              قائمة المراجعة المعلقة
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-20 rounded-lg bg-muted animate-pulse" />
                ))}
              </div>
            ) : pendingReviews.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <CheckCircle2 className="h-12 w-12 mx-auto mb-3 opacity-30 text-green-500" />
                <p>لا توجد مراجعات معلقة</p>
              </div>
            ) : (
              <div className="space-y-3">
                {pendingReviews.map((pr) => (
                  <div
                    key={pr.escalation_id}
                    className="flex items-start justify-between gap-4 p-3 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {REASON_LABELS[pr.reason] || pr.reason}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1 arabic-text line-clamp-2">
                        {pr.context_package_summary || "—"}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {pr.minutes_waiting} دقيقة
                        </span>
                        {pr.confidence_at_escalation !== null && (
                          <span className={confidenceColor(pr.confidence_at_escalation)}>
                            ثقة: {(pr.confidence_at_escalation * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                    </div>
                    <Link
                      href={`/conversations/${pr.conversation_id}`}
                      className="shrink-0 text-sm text-primary hover:underline"
                    >
                      عرض ←
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Decisions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart2 className="h-5 w-5" />
              سجل قرارات الـ AI
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
                ))}
              </div>
            ) : decisions.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p>لا توجد قرارات مسجلة</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {decisions.map((d) => (
                  <div
                    key={d.message_id}
                    className="flex items-start justify-between gap-4 p-3 rounded-lg border hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium">
                          {INTENT_LABELS[d.intent] || d.intent}
                        </span>
                        <Badge
                          variant={d.was_escalated ? "destructive" : "default"}
                          className="text-xs"
                        >
                          {d.was_escalated ? "تصعيد" : "تلقائي"}
                        </Badge>
                        <span
                          className={`text-xs ${confidenceColor(d.confidence_score)}`}
                        >
                          {(d.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1 arabic-text line-clamp-2">
                        {d.response_preview || "—"}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {d.created_at ? formatRelativeTime(d.created_at) : "—"}
                      </p>
                    </div>
                    <Link
                      href={`/conversations/${d.conversation_id}`}
                      className="shrink-0 text-sm text-primary hover:underline"
                    >
                      عرض ←
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
