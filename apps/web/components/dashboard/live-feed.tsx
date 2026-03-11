"use client";

import { useEffect, useRef, useState } from "react";
import { MessageSquare, AlertTriangle, CheckCircle } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";

type FeedEvent = {
  id: string;
  type: "message" | "escalation" | "resolved";
  text: string;
  customer?: string;
  timestamp: string;
};

function eventIcon(type: FeedEvent["type"]) {
  if (type === "escalation")
    return <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />;
  if (type === "resolved")
    return <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />;
  return <MessageSquare className="h-4 w-4 text-primary shrink-0" />;
}

interface LiveFeedProps {
  workspaceId?: string;
}

export default function LiveFeed({ workspaceId }: LiveFeedProps) {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!workspaceId) return;

    const token = typeof window !== "undefined"
      ? localStorage.getItem("radd_access_token")
      : null;
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = process.env.NEXT_PUBLIC_WS_URL || `${protocol}//${window.location.hostname}:8000`;
    const ws = new WebSocket(`${host}/ws/agent?token=${token}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const feedEvent: FeedEvent = {
          id: Math.random().toString(36).slice(2),
          type: data.type === "new_escalation" ? "escalation"
               : data.type === "conversation_resolved" ? "resolved"
               : "message",
          text: data.conversation_id
            ? `محادثة #${String(data.conversation_id).slice(0, 8)}`
            : data.message || "حدث جديد",
          customer: data.customer_name,
          timestamp: new Date().toISOString(),
        };
        setEvents((prev) => [feedEvent, ...prev].slice(0, 50));
      } catch {
        // ignore parse errors
      }
    };

    return () => {
      ws.close();
    };
  }, [workspaceId]);

  // Auto-scroll to top on new events
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0;
    }
  }, [events]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 pb-3 border-b border-border">
        <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-sm font-medium">التغذية المباشرة</span>
      </div>

      <div ref={feedRef} className="flex-1 overflow-y-auto mt-3 space-y-2">
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            لا توجد أحداث حديثة
          </p>
        ) : (
          events.map((ev) => (
            <div
              key={ev.id}
              className="flex items-start gap-2.5 p-2.5 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
            >
              {eventIcon(ev.type)}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-foreground truncate">{ev.text}</p>
                {ev.customer && (
                  <p className="text-xs text-muted-foreground">{ev.customer}</p>
                )}
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {formatRelativeTime(ev.timestamp)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
