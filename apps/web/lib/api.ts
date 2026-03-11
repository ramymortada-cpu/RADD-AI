/**
 * Typed API client for the Radd FastAPI backend.
 * All requests go through Next.js rewrite → localhost:8000.
 */

const API_BASE = "/api/v1";

// ─── Auth ─────────────────────────────────────────────────────────────────────

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export async function login(
  workspaceSlug: string,
  email: string,
  password: string
): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspace_slug: workspaceSlug, email, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

// ─── Authenticated fetch ──────────────────────────────────────────────────────

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("radd_access_token");
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("radd_access_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export type KPIs = {
  active_conversations: number;
  automation_rate: number;
  avg_response_time_seconds: number;
  escalation_rate: number;
  csat_score: number | null;
  messages_today: number;
  pending_escalations: number;
  hallucination_rate: number;
  computed_at: string;
};

export const getAnalytics = () => apiFetch<KPIs>("/admin/analytics");

// ─── Conversations ────────────────────────────────────────────────────────────

export type ConversationStatus = "active" | "waiting_agent" | "resolved" | "expired";

export type ConversationSummary = {
  id: string;
  status: ConversationStatus;
  intent: string | null;
  dialect: string | null;
  confidence_score: number | null;
  resolution_type: string | null;
  message_count: number;
  last_message_at: string | null;
  customer: { id: string; display_name: string | null; language: string | null; channel_type: string } | null;
};

export type Message = {
  id: string;
  sender_type: "customer" | "system" | "agent";
  content: string;
  confidence: { intent: number; retrieval: number; verify: number } | null;
  source_passages: Array<{ chunk_id: string; score: number; text_preview: string }> | null;
  created_at: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: Message[];
  assigned_user_id: string | null;
};

export const getConversations = (status?: string, page = 1) =>
  apiFetch<{ items: ConversationSummary[]; total: number; page: number; page_size: number }>(
    `/conversations?page=${page}${status ? `&status=${status}` : ""}`
  );

export const getConversation = (id: string) =>
  apiFetch<ConversationDetail>(`/conversations/${id}`);

export const sendAgentReply = (id: string, content: string, resolve = false) =>
  apiFetch<Message>(`/conversations/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, resolve }),
  });

// ─── KB Documents ─────────────────────────────────────────────────────────────

export type KBDocument = {
  id: string;
  title: string;
  content_type: string;
  status: "draft" | "review" | "approved" | "archived";
  language: string;
  version: number;
  uploaded_by_user_id: string;
  approved_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export const getDocuments = (status?: string) =>
  apiFetch<{ items: KBDocument[]; total: number; page: number; page_size: number }>(
    `/kb/documents${status ? `?status=${status}` : ""}`
  );

export const createDocument = (data: {
  title: string;
  content: string;
  content_type: string;
}) =>
  apiFetch<KBDocument>("/kb/documents", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const approveDocument = (id: string) =>
  apiFetch<KBDocument>(`/kb/documents/${id}/approve`, { method: "POST" });

export const deleteDocument = (id: string) =>
  apiFetch<void>(`/kb/documents/${id}`, { method: "DELETE" });

// ─── Escalations ──────────────────────────────────────────────────────────────

export type EscalationStatus = "pending" | "accepted" | "resolved" | "expired";

export type Escalation = {
  id: string;
  conversation_id: string;
  escalation_type: "hard" | "soft";
  reason: string | null;
  confidence_at_escalation: number | null;
  context_package: {
    summary: string;
    recent_messages: Array<{ sender_type: string; content: string; created_at: string }>;
    customer_info: { display_name: string; language: string };
    detected_intent: string;
    kb_gaps: string[];
  };
  status: EscalationStatus;
  rag_draft: string | null;
  created_at: string;
};

export const getEscalations = (status: EscalationStatus = "pending") =>
  apiFetch<{ items: Escalation[]; total: number }>(`/escalations?status=${status}`);

export const acceptEscalation = (id: string) =>
  apiFetch<Escalation>(`/escalations/${id}/accept`, { method: "POST" });

export const resolveEscalation = (id: string, notes?: string) =>
  apiFetch<Escalation>(`/escalations/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });

// ─── Admin ────────────────────────────────────────────────────────────────────

export type WorkspaceSettings = {
  workspace_id: string;
  name: string;
  slug: string;
  plan: string;
  settings: Record<string, unknown>;
};

export const getSettings = () => apiFetch<WorkspaceSettings>("/admin/settings");

export const updateSettings = (data: Record<string, unknown>) =>
  apiFetch<{ updated: boolean; settings: Record<string, unknown> }>("/admin/settings", {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export type User = { id: string; email: string; name: string; role: string; is_active: boolean };

export const getUsers = () => apiFetch<User[]>("/admin/users");

export const createUser = (data: {
  email: string;
  name: string;
  role: string;
  password: string;
}) =>
  apiFetch<User>("/admin/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
