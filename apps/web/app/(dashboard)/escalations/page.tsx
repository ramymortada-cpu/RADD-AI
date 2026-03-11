"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, UserCheck, CheckCircle2, Clock } from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getEscalations,
  acceptEscalation,
  resolveEscalation,
  type Escalation,
  type EscalationStatus,
} from "@/lib/api";
import { formatRelativeTime, INTENT_LABELS, confidenceColor } from "@/lib/utils";

const STATUS_FILTER_LABELS: { value: EscalationStatus; label: string }[] = [
  { value: "pending", label: "معلّق" },
  { value: "accepted", label: "مقبول" },
  { value: "resolved", label: "محلول" },
];

export default function EscalationsPage() {
  const [items, setItems] = useState<Escalation[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<EscalationStatus>("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [resolveNotes, setResolveNotes] = useState<Record<string, string>>({});

  useEffect(() => {
    loadEscalations();
  }, [statusFilter]);

  async function loadEscalations() {
    setLoading(true);
    try {
      const data = await getEscalations(statusFilter);
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("تعذّر تحميل التصعيدات");
    } finally {
      setLoading(false);
    }
  }

  async function handleAccept(id: string) {
    try {
      await acceptEscalation(id);
      await loadEscalations();
    } catch {
      setError("تعذّر قبول التصعيد");
    }
  }

  async function handleResolve(id: string) {
    try {
      await resolveEscalation(id, resolveNotes[id]);
      await loadEscalations();
    } catch {
      setError("تعذّر إغلاق التصعيد");
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="التصعيدات" subtitle={`${total} تصعيد`} />

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-2">
          {STATUS_FILTER_LABELS.map(({ value, label }) => (
            <Button
              key={value}
              size="sm"
              variant={statusFilter === value ? "default" : "outline"}
              onClick={() => setStatusFilter(value)}
            >
              {label}
            </Button>
          ))}
        </div>

        {/* List */}
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-36 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            <AlertTriangle className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>لا توجد تصعيدات {statusFilter === "pending" ? "معلّقة" : statusFilter === "accepted" ? "مقبولة" : "محلولة"}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((esc) => (
              <Card key={esc.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle
                        className={`h-5 w-5 shrink-0 ${
                          esc.escalation_type === "hard"
                            ? "text-red-500"
                            : "text-amber-500"
                        }`}
                      />
                      <CardTitle className="text-sm font-semibold">
                        تصعيد {esc.escalation_type === "hard" ? "عاجل" : "ناعم"}
                      </CardTitle>
                      <Badge
                        variant={
                          esc.status === "pending"
                            ? "warning"
                            : esc.status === "accepted"
                            ? "default"
                            : "success"
                        }
                        className="text-xs"
                      >
                        {esc.status === "pending" ? "معلّق" : esc.status === "accepted" ? "مقبول" : "محلول"}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {formatRelativeTime(esc.created_at)}
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-3">
                  {/* Context package summary */}
                  <div className="bg-muted/50 rounded-lg p-3 text-sm">
                    <p className="text-muted-foreground text-xs mb-1">ملخص السياق:</p>
                    <p className="arabic-text">{esc.context_package?.summary || "—"}</p>
                  </div>

                  {/* Meta row */}
                  <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    <span>
                      نية:{" "}
                      <strong>
                        {INTENT_LABELS[esc.context_package?.detected_intent || ""] ||
                          esc.context_package?.detected_intent}
                      </strong>
                    </span>
                    {esc.confidence_at_escalation !== null && (
                      <span className={confidenceColor(esc.confidence_at_escalation ?? 0)}>
                        ثقة: {((esc.confidence_at_escalation ?? 0) * 100).toFixed(0)}%
                      </span>
                    )}
                    <Link
                      href={`/conversations/${esc.conversation_id}`}
                      className="text-primary hover:underline"
                    >
                      عرض المحادثة ←
                    </Link>
                  </div>

                  {/* RAG draft */}
                  {esc.rag_draft && (
                    <div className="border-s-2 border-primary/40 ps-3 text-sm text-muted-foreground italic arabic-text">
                      مسودة الرد: {esc.rag_draft}
                    </div>
                  )}

                  {/* Actions */}
                  {esc.status === "pending" && (
                    <Button
                      size="sm"
                      onClick={() => handleAccept(esc.id)}
                      className="w-full"
                    >
                      <UserCheck className="h-4 w-4 me-2" />
                      قبول التصعيد
                    </Button>
                  )}

                  {esc.status === "accepted" && (
                    <div className="flex gap-2">
                      <input
                        className="flex-1 rounded-md border border-input px-3 py-1.5 text-sm"
                        placeholder="ملاحظات الإغلاق (اختياري)..."
                        value={resolveNotes[esc.id] || ""}
                        onChange={(e) =>
                          setResolveNotes((n) => ({
                            ...n,
                            [esc.id]: e.target.value,
                          }))
                        }
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-green-600 border-green-200 hover:bg-green-50 shrink-0"
                        onClick={() => handleResolve(esc.id)}
                      >
                        <CheckCircle2 className="h-4 w-4 me-1" />
                        إغلاق
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
