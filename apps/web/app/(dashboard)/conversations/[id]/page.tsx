"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Send, CheckCheck } from "lucide-react";
import TopBar from "@/components/layout/topbar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  getConversation,
  sendAgentReply,
  type ConversationDetail,
  type Message,
} from "@/lib/api";
import {
  formatArabicDate,
  INTENT_LABELS,
  STATUS_LABELS,
  STATUS_COLORS,
  confidenceColor,
  confidenceLabel,
} from "@/lib/utils";
import { cn } from "@/lib/utils";

function MessageBubble({ msg }: { msg: Message }) {
  const isCustomer = msg.sender_type === "customer";
  const isAgent = msg.sender_type === "agent";

  return (
    <div
      className={cn("flex", isCustomer ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[70%] px-4 py-2.5 text-sm",
          isCustomer && "bubble-customer",
          !isCustomer && isAgent && "bubble-agent",
          !isCustomer && !isAgent && "bubble-system"
        )}
      >
        <p className="whitespace-pre-wrap arabic-text">{msg.content}</p>

        <div className="flex items-center justify-between gap-3 mt-1.5">
          <span className="text-xs text-muted-foreground">
            {formatArabicDate(msg.created_at)}
          </span>
          {msg.confidence && (
            <span
              className={cn(
                "text-xs font-medium",
                confidenceColor(
                  Math.min(
                    msg.confidence.intent,
                    msg.confidence.retrieval,
                    msg.confidence.verify
                  )
                )
              )}
            >
              {confidenceLabel(
                Math.min(
                  msg.confidence.intent,
                  msg.confidence.retrieval,
                  msg.confidence.verify
                )
              )}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ConversationDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [conv, setConv] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getConversation(params.id)
      .then(setConv)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [params.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conv?.messages]);

  async function handleSend(resolve = false) {
    if (!reply.trim()) return;
    setSending(true);
    try {
      const msg = await sendAgentReply(params.id, reply, resolve);
      setConv((c) =>
        c ? { ...c, messages: [...c.messages, msg] } : c
      );
      setReply("");
      if (resolve) router.push("/conversations");
    } catch (e) {
      console.error(e);
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <TopBar title="..." />
        <div className="flex-1 flex items-center justify-center">
          <div className="w-10 h-10 rounded-full border-4 border-primary border-t-transparent animate-spin" />
        </div>
      </div>
    );
  }

  if (!conv) {
    return (
      <div className="flex flex-col h-full">
        <TopBar title="محادثة غير موجودة" />
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          لا توجد محادثة بهذا المعرف
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 h-16 border-b border-border bg-white shrink-0">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-md hover:bg-muted transition-colors"
        >
          <ArrowRight className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">
              {conv.customer?.display_name || "عميل"}
            </span>
            <Badge className={`${STATUS_COLORS[conv.status]} border-none text-xs`}>
              {STATUS_LABELS[conv.status] || conv.status}
            </Badge>
            {conv.intent && (
              <Badge variant="outline" className="text-xs">
                {INTENT_LABELS[conv.intent] || conv.intent}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {conv.messages.length} رسالة
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-gray-50">
        {conv.messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Reply box */}
      {conv.status !== "resolved" && (
        <div className="shrink-0 border-t border-border bg-white p-4">
          <Textarea
            placeholder="اكتب ردك هنا..."
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            className="mb-3 min-h-[80px] arabic-text"
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.ctrlKey) handleSend(false);
            }}
          />
          <div className="flex items-center gap-2 justify-end">
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleSend(true)}
              disabled={sending || !reply.trim()}
            >
              <CheckCheck className="h-4 w-4 me-1" />
              إرسال وإغلاق
            </Button>
            <Button
              size="sm"
              onClick={() => handleSend(false)}
              disabled={sending || !reply.trim()}
            >
              <Send className="h-4 w-4 me-1" />
              إرسال
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
