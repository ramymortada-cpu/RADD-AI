"use client";

import { useEffect, useState } from "react";
import {
  Plus,
  CheckCircle,
  Trash2,
  FileText,
  Clock,
  BookOpen,
} from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  getDocuments,
  createDocument,
  approveDocument,
  deleteDocument,
  type KBDocument,
} from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  review: "قيد المراجعة",
  approved: "معتمد",
  archived: "مؤرشف",
};

const STATUS_VARIANTS: Record<string, "muted" | "warning" | "success" | "secondary"> = {
  draft: "muted",
  review: "warning",
  approved: "success",
  archived: "secondary",
};

interface NewDocForm {
  title: string;
  content: string;
  content_type: string;
}

export default function KnowledgePage() {
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<NewDocForm>({
    title: "",
    content: "",
    content_type: "text/plain",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDocs();
  }, []);

  async function loadDocs() {
    setLoading(true);
    try {
      const data = await getDocuments();
      setDocs(data.items);
    } catch {
      setError("تعذّر تحميل الوثائق");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createDocument(form);
      setShowForm(false);
      setForm({ title: "", content: "", content_type: "text/plain" });
      await loadDocs();
    } catch {
      setError("تعذّر إنشاء الوثيقة");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApprove(id: string) {
    try {
      await approveDocument(id);
      await loadDocs();
    } catch {
      setError("تعذّر اعتماد الوثيقة");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("هل تريد حذف هذه الوثيقة؟")) return;
    try {
      await deleteDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
    } catch {
      setError("تعذّر حذف الوثيقة");
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="قاعدة المعرفة" subtitle={`${docs.length} وثيقة`} />

      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Add document button */}
        <div className="flex justify-end">
          <Button onClick={() => setShowForm((v) => !v)}>
            <Plus className="h-4 w-4 me-2" />
            إضافة وثيقة
          </Button>
        </div>

        {/* New doc form */}
        {showForm && (
          <Card>
            <CardContent className="pt-5">
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">عنوان الوثيقة</label>
                  <Input
                    required
                    value={form.title}
                    onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                    placeholder="مثال: سياسة الإرجاع"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">المحتوى</label>
                  <Textarea
                    required
                    rows={8}
                    value={form.content}
                    onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
                    placeholder="أدخل نص الوثيقة باللغة العربية..."
                    className="arabic-text"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowForm(false)}
                  >
                    إلغاء
                  </Button>
                  <Button type="submit" disabled={submitting}>
                    {submitting ? "جارٍ الحفظ..." : "حفظ كمسودة"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Documents list */}
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            <BookOpen className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>لا توجد وثائق بعد. أضف أول وثيقة لقاعدة المعرفة.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {docs.map((doc) => (
              <div
                key={doc.id}
                className="flex items-start gap-4 p-4 rounded-lg bg-white border border-border hover:shadow-sm transition-shadow"
              >
                <div className="p-2 rounded-lg bg-primary/10 shrink-0">
                  <FileText className="h-5 w-5 text-primary" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm">{doc.title}</span>
                    <Badge variant={STATUS_VARIANTS[doc.status] || "muted"}>
                      {STATUS_LABELS[doc.status] || doc.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      v{doc.version}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <span>{formatRelativeTime(doc.updated_at)}</span>
                    <span>·</span>
                    <span>{doc.content_type}</span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {(doc.status === "draft" || doc.status === "review") && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-green-600 border-green-200 hover:bg-green-50"
                      onClick={() => handleApprove(doc.id)}
                    >
                      <CheckCircle className="h-4 w-4 me-1" />
                      اعتماد
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:bg-destructive/10"
                    onClick={() => handleDelete(doc.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
