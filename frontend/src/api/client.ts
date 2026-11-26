import type {
  AppSettings,
  AwardOpportunity,
  ConnectorStatus,
  JobRun,
  Mention,
  MonitoredSystem,
  NotificationLog,
  PipelineStatus,
  ProblemDiagnostics,
  ProjectStarRating,
  SentimentOverview,
  SystemPayload,
  TemporalAnalysis,
} from "../types";

const API_BASE = "/api";
const AUTH_TOKEN_KEY = "cidadaopulse_auth_token";

export function getStoredAuthToken(): string {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setStoredAuthToken(token: string): void {
  try {
    if (token) {
      localStorage.setItem(AUTH_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(AUTH_TOKEN_KEY);
    }
  } catch {
    // ignore storage errors
  }
}

export function clearStoredAuthToken(): void {
  setStoredAuthToken("");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getStoredAuthToken();
  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...(options?.headers || {}),
    },
  });
  if (res.status === 401 && path !== "/auth/login") {
    clearStoredAuthToken();
    window.dispatchEvent(new CustomEvent("cidadaopulse:unauthorized"));
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Erro HTTP ${res.status}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

export const api = {
  // Optional cloud password, Google (Gmail) login & admin-issued guest token auth
  getAuthStatus: () =>
    request<{
      auth_required: boolean;
      authenticated: boolean;
      role: "admin" | "editor" | "viewer" | "anonymous";
      label: string;
      password_enabled: boolean;
      google_enabled: boolean;
      google_client_id: string;
    }>("/auth/status"),
  login: async (password: string) => {
    const res = await request<{
      auth_required: boolean;
      authenticated: boolean;
      role: "admin" | "editor" | "viewer";
      label: string;
      token: string;
    }>("/auth/login", { method: "POST", body: JSON.stringify({ password }) });
    if (res.token) setStoredAuthToken(res.token);
    return res;
  },
  loginWithGoogle: async (credential: string) => {
    const res = await request<{
      auth_required: boolean;
      authenticated: boolean;
      role: "admin" | "editor" | "viewer";
      label: string;
      token: string;
    }>("/auth/google", { method: "POST", body: JSON.stringify({ credential }) });
    if (res.token) setStoredAuthToken(res.token);
    return res;
  },
  getAccessConfig: () =>
    request<{
      password_enabled: boolean;
      password_from_env: boolean;
      google_client_id: string;
      admin_google_emails: string;
      allowed_google_emails: string;
    }>("/auth/access-config"),
  updateAccessConfig: async (payload: {
    app_password?: string;
    clear_app_password?: boolean;
    google_client_id?: string;
    admin_google_emails?: string;
    allowed_google_emails?: string;
  }) => {
    const res = await request<{
      password_enabled: boolean;
      google_client_id: string;
      admin_google_emails: string;
      allowed_google_emails: string;
      admin_token: string;
    }>("/auth/access-config", { method: "PUT", body: JSON.stringify(payload) });
    if (res.admin_token) setStoredAuthToken(res.admin_token);
    return res;
  },
  logout: () => clearStoredAuthToken(),
  listAccessTokens: () =>
    request<
      {
        id: number;
        label: string;
        role: "viewer" | "editor";
        token_prefix: string;
        is_active: boolean;
        is_expired: boolean;
        expires_at: string | null;
        last_used_at: string | null;
        use_count: number;
        created_at: string | null;
      }[]
    >("/auth/tokens"),
  createAccessToken: (payload: {
    label: string;
    role: "viewer" | "editor";
    expires_in_days: number | null;
    custom_token?: string;
  }) =>
    request<{
      id: number;
      label: string;
      role: "viewer" | "editor";
      token_prefix: string;
      token: string;
      is_active: boolean;
      is_expired: boolean;
      expires_at: string | null;
      last_used_at: string | null;
      use_count: number;
      created_at: string | null;
    }>("/auth/tokens", { method: "POST", body: JSON.stringify(payload) }),
  revokeAccessToken: (id: number) =>
    request<void>(`/auth/tokens/${id}`, { method: "DELETE" }),

  // Systems
  listSystems: () => request<MonitoredSystem[]>("/systems"),
  createSystem: (data: SystemPayload) =>
    request<MonitoredSystem>("/systems", { method: "POST", body: JSON.stringify(data) }),
  updateSystem: (id: number, data: Partial<SystemPayload>) =>
    request<MonitoredSystem>(`/systems/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteSystem: (id: number) =>
    request<void>(`/systems/${id}`, { method: "DELETE" }),

  // Sentiment
  getSentimentOverview: (systemId?: number, days?: number) => {
    const qs = new URLSearchParams();
    if (systemId) qs.set("system_id", String(systemId));
    if (days) qs.set("days", String(days));
    const q = qs.toString();
    return request<SentimentOverview>(`/sentiment/overview${q ? `?${q}` : ""}`);
  },
  getTemporalAnalysis: (systemId?: number | null, days: number = 30) => {
    const qs = new URLSearchParams({ days: String(days) });
    if (systemId) qs.set("system_id", String(systemId));
    return request<TemporalAnalysis>(`/sentiment/temporal?${qs.toString()}`);
  },
  listMentions: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== false) qs.set(k, String(v));
    });
    return request<Mention[]>(`/sentiment/mentions?${qs.toString()}`);
  },
  triggerSentimentScan: (systemId?: number, connectors?: string[], lookbackDays?: number) =>
    request<JobRun>("/sentiment/scan", {
      method: "POST",
      body: JSON.stringify({
        system_id: systemId ?? null,
        connectors: connectors ?? null,
        lookback_days: lookbackDays ?? 365,
      }),
    }),
  deleteMention: (id: number) =>
    request<void>(`/sentiment/mentions/${id}`, { method: "DELETE" }),
  cleanupIrrelevantMentions: (systemId?: number) =>
    request<{ evaluated: number; removed: number; cleaned_html: number }>(
      `/sentiment/cleanup-irrelevant${systemId ? `?system_id=${systemId}` : ""}`,
      { method: "POST" }
    ),
  getProblemDiagnostics: (params: {
    systemId?: number | null;
    days?: number | null;
    channelGroup?: string;
    useAi?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params.systemId) qs.set("system_id", String(params.systemId));
    if (params.days) qs.set("days", String(params.days));
    if (params.channelGroup) qs.set("channel_group", params.channelGroup);
    if (params.useAi !== undefined) qs.set("use_ai", String(params.useAi));
    return request<ProblemDiagnostics>(`/sentiment/problems?${qs.toString()}`);
  },
  getStarRatings: (params?: {
    systemId?: number | null;
    days?: number | null;
    useAi?: boolean;
    refresh?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params?.systemId) qs.set("system_id", String(params.systemId));
    if (params?.days) qs.set("days", String(params.days));
    if (params?.useAi !== undefined) qs.set("use_ai", String(params.useAi));
    if (params?.refresh) qs.set("refresh", "true");
    const q = qs.toString();
    return request<ProjectStarRating[]>(`/sentiment/star-ratings${q ? `?${q}` : ""}`);
  },
  importComments: (payload: {
    system_id: number;
    platform: "instagram" | "facebook" | "youtube" | "x" | "reclame_aqui" | "web";
    post_url: string;
    raw_text: string;
  }) =>
    request<{ parsed: number; saved: number; duplicates_skipped: number; crisis_signals: number }>(
      "/sentiment/import-comments",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  fetchPostComments: (payload: { system_id: number; post_url: string; max_comments?: number }) =>
    request<{ extracted: number; saved: number; crisis_signals: number }>(
      "/sentiment/fetch-post-comments",
      { method: "POST", body: JSON.stringify(payload) }
    ),

  // Awards Radar
  listAwards: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== false) qs.set(k, String(v));
    });
    return request<AwardOpportunity[]>(`/awards?${qs.toString()}`);
  },
  verifyAwardDeadlines: (systemId?: number | null) =>
    request<{ checked: number; aberto: number; previsto: number; encerrado: number }>(
      `/awards/verify-deadlines${systemId ? `?system_id=${systemId}` : ""}`,
      { method: "POST" }
    ),
  triggerAwardsScan: (payload: {
    system_id?: number | null;
    focus_scope?: "todos" | "internacional" | "nacional";
    include_ai_filter?: "auto" | "com_ia" | "sem_ia" | "ambos";
  }) =>
    request<JobRun>("/awards/scan", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAwardPipeline: (
    id: number,
    data: {
      pipeline_status?: PipelineStatus;
      user_notes?: string;
      award_status?: "aberto" | "previsto" | "recorrente" | "encerrado";
      deadline?: string;
      deadline_date?: string;
      deadline_source_note?: string;
    }
  ) =>
    request<AwardOpportunity>(`/awards/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAward: (id: number) =>
    request<void>(`/awards/${id}`, { method: "DELETE" }),
  exportAwardsUrl: (format: "markdown" | "csv", systemId?: number) =>
    `${API_BASE}/awards/export/report?format=${format}${systemId ? `&system_id=${systemId}` : ""}`,

  // Settings, Connectors, Jobs, Alerts
  getSettings: () => request<AppSettings>("/settings"),
  updateSettings: (data: Record<string, unknown>) =>
    request<AppSettings>("/settings", { method: "PUT", body: JSON.stringify(data) }),
  listConnectors: () => request<ConnectorStatus[]>("/settings/connectors"),
  testNotification: () =>
    request<{ results: { channel: string; status: string; details: string }[] }>(
      "/settings/test-notification",
      { method: "POST" }
    ),
  listNotificationLogs: () => request<NotificationLog[]>("/settings/notifications"),
  listJobs: (jobType?: string) =>
    request<JobRun[]>(`/jobs${jobType ? `?job_type=${jobType}` : ""}`),
};
