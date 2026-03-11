"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Filter } from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getConversations, type ConversationSummary } from "@/lib/api";
import {
  formatRelativeTime,
  INTENT_LABELS,
  STATUS_LABELS,
  STATUS_COLORS,
  confidenceColor,
} from "@/lib/utils";

const STATUS_FILTERS = ["", "active", "waiting_agent", "resolved"] as const;

export default function ConversationsPage() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<string>("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    getConversations(status || undefined, page)
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [status, page]);

  const filtered = search
    ? items.filter(
        (c) =>
          c.customer?.display_name?.includes(search) ||
          c.id.includes(search)
      )
    : items;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <TopBar title="المحادثات" subtitle={`${total} محادثة إجمالاً`} />

      <div className="flex-1 overflow-y-auto p-6">
        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mb-5">
          <div className="relative flex-1 min-w-52">
            <Search className="absolute end-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="ابحث باسم العميل أو معرف المحادثة..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pe-9"
            />
          </div>
          <div className="flex items-center gap-1">
            <Filter className="h-4 w-4 text-muted-foreground ms-1" />
            {STATUS_FILTERS.map((s) => (
              <Button
                key={s}
                size="sm"
                variant={status === s ? "default" : "outline"}
                onClick={() => { setStatus(s); setPage(1); }}
                className="text-xs"
              >
                {s ? STATUS_LABELS[s] : "الكل"}
              </Button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-20 rounded-lg bg-muted animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">لا توجد محادثات</div>
        ) : (
          <div className="space-y-2">
            {filtered.map((conv) => (
              <Link
                key={conv.id}
                href={`/conversations/${conv.id}`}
                className="flex items-center gap-4 p-4 rounded-lg bg-white border border-border hover:border-primary/40 hover:shadow-sm transition-all"
              >
                {/* Avatar */}
                <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <span className="text-primary font-semibold text-sm">
                    {(conv.customer?.display_name || "؟")[0]}
                  </span>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm">
                      {conv.customer?.display_name || "عميل"}
                    </span>
                    <Badge
                      className={
                        STATUS_COLORS[conv.status] + " text-xs border-none"
                      }
                    >
                      {STATUS_LABELS[conv.status] || conv.status}
                    </Badge>
                    {conv.intent && (
                      <Badge variant="outline" className="text-xs">
                        {INTENT_LABELS[conv.intent] || conv.intent}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {conv.message_count} رسالة
                    {conv.last_message_at ? ` · ${formatRelativeTime(conv.last_message_at)}` : ""}
                  </p>
                </div>

                {/* Confidence */}
                {conv.confidence_score !== null && (
                  <div className={`text-xs font-semibold ${confidenceColor(conv.confidence_score ?? 0)}`}>
                    {((conv.confidence_score ?? 0) * 100).toFixed(0)}%
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}

        {/* Pagination */}
        {total > 20 && (
          <div className="flex justify-center gap-2 mt-6">
            <Button
              size="sm"
              variant="outline"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              السابق
            </Button>
            <span className="text-sm text-muted-foreground self-center">
              صفحة {page}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={items.length < 20}
              onClick={() => setPage((p) => p + 1)}
            >
              التالي
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
