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

export async function apiFetch<T>(
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
  honesty_blocks_this_month: number;
  honesty_blocks_today: number;
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

// ─── Super Admin ──────────────────────────────────────────────────────────────

export type PlatformKPIs = {
  total_workspaces: number;
  active_workspaces: number;
  total_messages_today: number;
  total_messages_week: number;
  platform_automation_rate: number;
  total_active_conversations: number;
  total_pending_escalations: number;
  top_workspaces: Array<{
    id: string;
    name: string;
    slug: string;
    plan: string;
    status: string;
    messages_today: number;
  }>;
  computed_at: string;
};

export type WorkspaceSummary = {
  id: string;
  name: string;
  slug: string;
  plan: string;
  status: string;
  user_count: number;
  message_count_today: number;
  conversation_count: number;
  created_at: string;
};

export type WorkspaceDetail = WorkspaceSummary & {
  settings: Record<string, unknown>;
  updated_at: string;
  message_count_total: number;
  kb_document_count: number;
  channel_count: number;
  pending_escalations: number;
  users: Array<{
    id: string;
    email: string;
    name: string;
    role: string;
    is_active: boolean;
    last_login_at: string | null;
    created_at: string;
  }>;
  channels: Array<{
    id: string;
    type: string;
    name: string | null;
    is_active: boolean;
    created_at: string;
  }>;
};

export type PlatformUser = {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  is_superadmin: boolean;
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string;
  last_login_at: string | null;
  created_at: string;
};

export type ServiceStatus = {
  name: string;
  status: "ok" | "degraded" | "down";
  latency_ms: number | null;
  detail: string | null;
};

export type SystemHealth = {
  overall: string;
  services: ServiceStatus[];
  checked_at: string;
};

export type PipelineConfig = {
  confidence_auto_threshold: number;
  confidence_soft_escalation_threshold: number;
  openai_chat_model: string;
  openai_embedding_model: string;
  intents: Array<{ name: string; keyword_count: number }>;
};

export type PlatformAuditEntry = {
  id: number;
  workspace_id: string;
  workspace_name: string;
  user_id: string | null;
  user_email: string | null;
  user_name: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
};

// Analytics
export const getSAAnalytics = () =>
  apiFetch<PlatformKPIs>("/superadmin/analytics");

// Workspaces
export const getSAWorkspaces = (page = 1, statusFilter?: string) =>
  apiFetch<{ items: WorkspaceSummary[]; total: number; page: number; page_size: number }>(
    `/superadmin/workspaces?page=${page}${statusFilter ? `&status=${statusFilter}` : ""}`
  );

export const getSAWorkspace = (id: string) =>
  apiFetch<WorkspaceDetail>(`/superadmin/workspaces/${id}`);

export const createSAWorkspace = (data: {
  name: string;
  slug: string;
  plan: string;
  owner_name: string;
  owner_email: string;
  owner_password: string;
}) =>
  apiFetch<WorkspaceSummary>("/superadmin/workspaces", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateSAWorkspace = (
  id: string,
  data: { name?: string; plan?: string; status?: string; settings?: Record<string, unknown> }
) =>
  apiFetch<{ updated: boolean }>(`/superadmin/workspaces/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const deleteSAWorkspace = (id: string) =>
  apiFetch<void>(`/superadmin/workspaces/${id}`, { method: "DELETE" });

// Users
export const getSAUsers = (params?: {
  page?: number;
  workspace_id?: string;
  role?: string;
  is_active?: boolean;
}) => {
  const p = new URLSearchParams();
  if (params?.page) p.set("page", String(params.page));
  if (params?.workspace_id) p.set("workspace_id", params.workspace_id);
  if (params?.role) p.set("role", params.role);
  if (params?.is_active !== undefined) p.set("is_active", String(params.is_active));
  return apiFetch<{ items: PlatformUser[]; total: number; page: number; page_size: number }>(
    `/superadmin/users?${p.toString()}`
  );
};

export const suspendSAUser = (id: string) =>
  apiFetch<void>(`/superadmin/users/${id}/suspend`, { method: "POST" });

export const activateSAUser = (id: string) =>
  apiFetch<void>(`/superadmin/users/${id}/activate`, { method: "POST" });

export const resetSAUserPassword = (id: string, newPassword: string) =>
  apiFetch<void>(`/superadmin/users/${id}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });

// Pipeline
export const getSAPipeline = () =>
  apiFetch<PipelineConfig>("/superadmin/pipeline");

export const updateSAPipeline = (data: {
  confidence_auto_threshold?: number;
  confidence_soft_escalation_threshold?: number;
}) =>
  apiFetch<{ updated: boolean; values: Record<string, unknown> }>("/superadmin/pipeline", {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const getSABenchmark = () =>
  apiFetch<Record<string, unknown>>("/superadmin/pipeline/benchmark");

// System health
export const getSASystemHealth = () =>
  apiFetch<SystemHealth>("/superadmin/system");

// Audit log
export const getSAAuditLog = (params?: {
  page?: number;
  workspace_id?: string;
  action?: string;
}) => {
  const p = new URLSearchParams();
  if (params?.page) p.set("page", String(params.page));
  if (params?.workspace_id) p.set("workspace_id", params.workspace_id);
  if (params?.action) p.set("action", params.action);
  return apiFetch<{ items: PlatformAuditEntry[]; total: number; page: number; page_size: number }>(
    `/superadmin/audit-log?${p.toString()}`
  );
};

// ─── Customers ────────────────────────────────────────────────────────────────
export interface CustomerProfile {
  id: string;
  display_name: string | null;
  phone_hash: string;
  customer_tier: "new" | "standard" | "returning" | "vip" | "at_risk";
  total_conversations: number;
  total_escalations: number;
  avg_sentiment: number | null;
  salla_total_orders: number;
  salla_total_revenue: number;
  last_seen_at: string | null;
  last_complaint_at: string | null;
  created_at: string | null;
}

export const getCustomers = (tier?: string, page = 1) => {
  const p = new URLSearchParams({ page: String(page) });
  if (tier) p.set("tier", tier);
  return apiFetch<{ items: CustomerProfile[]; total: number; page: number; page_size: number }>(
    `/admin/customers?${p.toString()}`
  );
};

// ─── Shadow Mode ──────────────────────────────────────────────────────────────
export const getShadowMode = () =>
  apiFetch<{ shadow_mode: boolean }>("/admin/shadow-mode");

export const setShadowMode = (enabled: boolean) =>
  apiFetch<{ shadow_mode: boolean; message: string }>("/admin/shadow-mode", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });

// ─── V2: Revenue Attribution ──────────────────────────────────────────────────
export interface RevenueSummary {
  period: string;
  total_attributed_sar: number;
  assisted_sales_sar: number;
  returns_prevented_sar: number;
  carts_recovered_sar: number;
  upsells_sar: number;
  event_count: number;
  roi_multiplier: number;
  subscription_cost_sar: number;
}

export interface RevenueEvent {
  id: string;
  event_type: "assisted_sale" | "return_prevented" | "cart_recovered" | "upsell";
  amount_sar: number;
  product_name: string | null;
  order_id: string | null;
  conversation_id: string | null;
  created_at: string;
}

export const getRevenueSummary = (period = "this_month") =>
  apiFetch<RevenueSummary>(`/admin/revenue/summary?period=${period}`);

export const getRevenueEvents = (page = 1) =>
  apiFetch<{ items: RevenueEvent[]; total: number; page: number }>(
    `/admin/revenue/events?page=${page}`
  );

// ─── V2: Radar Alerts ─────────────────────────────────────────────────────────
export interface RadarAlert {
  id: string;
  alert_type: "shipping_anomaly" | "product_issue" | "demand_opportunity";
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  suggested_action: string | null;
  is_read: boolean;
  created_at: string;
}

export const getRadarAlerts = (unreadOnly = false, page = 1) =>
  apiFetch<{ items: RadarAlert[]; total: number; page: number }>(
    `/admin/radar/alerts?unread_only=${unreadOnly}&page=${page}`
  );

export const triggerRadarScan = () =>
  apiFetch<{ scanned: boolean; alerts_found: number; alerts: RadarAlert[] }>(
    "/admin/radar/scan",
    { method: "POST" }
  );

export const markAlertRead = (alertId: string) =>
  apiFetch<{ marked_read: boolean }>(`/admin/radar/alerts/${alertId}/read`, {
    method: "PATCH",
  });

// ─── V2: Smart Rules ──────────────────────────────────────────────────────────
export interface SmartRule {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  priority: number;
  triggers: Array<{ type: string; value: string }>;
  actions: Array<{ type: string; value: string }>;
  created_at: string;
}

export const getSmartRules = () =>
  apiFetch<{ items: SmartRule[] }>("/admin/rules");

export const createSmartRule = (data: Omit<SmartRule, "id" | "created_at">) =>
  apiFetch<{ id: string; name: string; created: boolean }>("/admin/rules", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateSmartRule = (id: string, data: Partial<SmartRule>) =>
  apiFetch<{ updated: boolean }>(`/admin/rules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const deleteSmartRule = (id: string) =>
  apiFetch<void>(`/admin/rules/${id}`, { method: "DELETE" });

// ─── V2: Salla Sync ───────────────────────────────────────────────────────────
export const triggerSallaSync = (salla_token: string, salla_api_url?: string) =>
  apiFetch<{ synced: boolean; products_synced: number; documents_created: number }>(
    "/admin/salla/sync",
    {
      method: "POST",
      body: JSON.stringify({
        salla_token,
        salla_api_url: salla_api_url ?? "https://api.salla.dev/admin/v2",
      }),
    }
  );

// ─── V2: Starter Packs ────────────────────────────────────────────────────────
export const applyStarterPack = (sector: string) =>
  apiFetch<{ success: boolean; documents_created?: number }>(
    "/admin/starter-pack",
    {
      method: "POST",
      body: JSON.stringify({ sector }),
    }
  );

// ─── Intelligence ──────────────────────────────────────────────────────────────
export interface KnowledgeGap {
  question_pattern: string;
  sample_question: string;
  occurrence_count: number;
  intent: string;
  last_asked: string;
}

export const getKnowledgeGaps = (days = 7, limit = 20) =>
  apiFetch<KnowledgeGap[]>(`/intelligence/knowledge-gaps?days=${days}&limit=${limit}`);

// ─── V3: RADD Score ───────────────────────────────────────────────────────────
export const getRaddScore = (days = 30) =>
  apiFetch<{ total: number; grade: string; summary_ar: string; breakdown: Record<string, number>; period_days: number }>(
    `/admin/radd-score?period_days=${days}`
  );

// ─── V3: Churn Radar ──────────────────────────────────────────────────────────
export const getChurnRadar = (inactiveDays = 45) =>
  apiFetch<{
    summary: { total: number; critical: number; high: number; medium: number; at_risk_revenue: number };
    alerts: Array<{
      customer_id: string; customer_tier: string; risk_level: string;
      reason: string; days_inactive: number; total_revenue: number; suggested_action: string;
    }>;
  }>(`/admin/churn-radar?inactive_days=${inactiveDays}`);

// ─── V3: Agent Performance ────────────────────────────────────────────────────
export const getAgentPerformance = (days = 30) =>
  apiFetch<{
    summary: { agents: number; avg_csat: number; avg_resolution_minutes: number; total_resolved: number };
    agents: Array<{
      user_id: string; agent_name: string; total_assigned: number; total_resolved: number;
      resolution_rate: number; avg_resolution_minutes: number; estimated_csat: number;
    }>;
  }>(`/admin/agent-performance?period_days=${days}`);

// ─── V3: Follow-ups ───────────────────────────────────────────────────────────
export const getFollowupStats = () =>
  apiFetch<{ pending: number; sent: number; cancelled: number; total: number }>("/admin/followups/stats");

export const processFollowups = () =>
  apiFetch<{ processed: number; items: unknown[] }>("/admin/followups/process", { method: "POST" });

// ─── V3: Salla Advanced ──────────────────────────────────────────────────────
export const cancelSallaOrder = (order_reference: string, salla_token: string, reason = "change_mind") =>
  apiFetch<{ success: boolean; error?: string; reference: string }>("/admin/salla/cancel-order", {
    method: "POST",
    body: JSON.stringify({ order_reference, salla_token, reason }),
  });

export const trackSallaShipment = (order_reference: string, salla_token: string) =>
  apiFetch<{ found: boolean; tracking_number?: string; carrier?: string; tracking_url?: string; estimated_delivery?: string }>(
    "/admin/salla/track-shipment",
    { method: "POST", body: JSON.stringify({ order_reference, salla_token }) }
  );

// ─── V3: Agent Assist ─────────────────────────────────────────────────────────
export const getAgentAssist = (escalationId: string) =>
  apiFetch<{ suggestion: string; recommended_action: string; confidence: number; context: Record<string, unknown> }>(
    `/admin/escalations/${escalationId}/assist`
  );
