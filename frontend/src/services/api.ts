import type {
  AgentInfo,
  AgentResult,
  ActionPlan,
  AgentActionResponse,
  BusinessInsight,
  BusinessInsightsResponse,
} from "../types";

export const API_BASE = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8001"
).replace(/\/+$/, "");

const TOKEN_KEY = "bgai_session";

export function getAuthToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      sessionStorage.setItem(TOKEN_KEY, token);
    } else {
      sessionStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // sessionStorage unavailable
  }
}

export async function apiFetch<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: any) {
    throw new Error(err.message || "Network error. Is the server running?");
  }

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("bgai:auth-expired"));
    throw new Error("Session expired. Please log in again.");
  }

  const contentType = response.headers.get("content-type") || "";
  let data: any;
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errorMsg =
      (typeof data === "object" && data && (data.detail || data.message || data.error)) ||
      `HTTP error! status: ${response.status}`;
    throw new Error(errorMsg);
  }

  return data as T;
}

export async function sendMessage(
  message: string,
  sessionId: string,
  inputValues?: Record<string, string>,
  pendingInsert?: boolean
) {
  return apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      session_id: sessionId,
      input_values: inputValues,
      pending_insert: pendingInsert,
    }),
  });
}

export async function sendInsert(
  inputValues: Record<string, string>,
  _table: string,
  sessionId: string
) {
  const message = Object.entries(inputValues)
    .map(([key, value]) => `${key}: ${value}`)
    .join(", ");

  return apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      session_id: sessionId,
      input_values: inputValues,
      pending_insert: true,
    }),
  });
}

export async function getSchema() {
  return apiFetch("/schema");
}

export async function runQuery(query: string) {
  return apiFetch("/query", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function getFlowchart() {
  return apiFetch("/flowchart");
}

export async function clearDatabase() {
  return apiFetch("/clear-db", {
    method: "POST",
  });
}

export async function getDatabaseInfo() {
  return apiFetch("/database-info");
}

export async function getDatabaseType() {
  return apiFetch("/database-type");
}

export async function getDatabaseConnectionInfo() {
  return apiFetch("/database-connection-info");
}

export async function getDashboardData() {
  return apiFetch("/dashboard");
}

export async function getAnalytics() {
  return apiFetch("/analytics");
}

export async function confirmQuery(sessionId: string) {
  return apiFetch("/confirm-query", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function createBackup() {
  return apiFetch("/backup", {
    method: "POST",
  });
}

export async function restoreDatabase(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch("/restore", {
    method: "POST",
    body: formData,
  });
}

export async function downloadBackup(): Promise<Response> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}/download-backup`, { headers });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response;
}

export async function getSuggestions() {
  return apiFetch("/suggestions");
}

export async function optimizeSQL(sql: string) {
  return apiFetch("/optimize", {
    method: "POST",
    body: JSON.stringify({ sql }),
  });
}

export async function getRelationshipGraph() {
  return apiFetch("/relationship-graph");
}

export interface DatabaseConnectionRequest {
  db_type: string;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
}

export async function connectDatabase(data: DatabaseConnectionRequest) {
  return apiFetch("/connect", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function disconnectDatabase() {
  return apiFetch("/disconnect", {
    method: "POST",
  });
}

export async function uploadDatabase(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch("/upload", {
    method: "POST",
    body: formData,
  });
}

export async function getBusinessAnalysis() {
  return apiFetch("/analyze-business");
}

export async function getIntelligenceReport(forceRefresh = false) {
  const data = await apiFetch(`/intelligence/report?force_refresh=${forceRefresh}`);
  return data.report || data;
}

export async function triggerIntelligenceScan() {
  const data = await apiFetch("/intelligence/scan", {
    method: "POST",
  });
  return data.report || data;
}

export async function getTableProfile(tableName: string) {
  const data = await apiFetch(`/intelligence/table/${encodeURIComponent(tableName)}`);
  if (data.status === "error") throw new Error(data.message || "Failed to load table profile");
  return data.table;
}

export async function getTableSample(
  tableName: string,
  params: {
    limit?: number;
    offset?: number;
    sort_by?: string;
    sort_dir?: string;
    search?: string;
  } = {}
) {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.sort_dir) query.set("sort_dir", params.sort_dir);
  if (params.search) query.set("search", params.search);

  const data = await apiFetch(
    `/intelligence/table/${encodeURIComponent(tableName)}/sample?${query.toString()}`
  );
  if (data.status === "error") throw new Error(data.message || "Failed to load table sample");
  return data.sample;
}

export async function getColumnProfile(tableName: string, columnName: string) {
  const data = await apiFetch(
    `/intelligence/column/${encodeURIComponent(tableName)}/${encodeURIComponent(columnName)}`
  );
  if (data.status === "error") throw new Error(data.message || "Failed to load column profile");
  return data.column;
}

export async function askAnalyst(
  question: string,
  options: { table?: string; metric?: string } = {}
) {
  const data = await apiFetch("/analyst/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
      table: options.table,
      metric: options.metric,
    }),
  });
  if (data.status === "error") throw new Error(data.message || "Analysis could not be completed.");
  return data.analysis;
}

export async function getAnalystQuickActions() {
  const data = await apiFetch("/analyst/quick-actions");
  return data.actions || [];
}

export async function getForecastingCandidates() {
  const data = await apiFetch("/forecasting/candidates");
  return {
    status: data.status,
    candidates: data.candidates || [],
    message: data.message,
  };
}

export async function generateForecast(params: {
  table: string;
  date_column: string;
  metric_column?: string | null;
  frequency?: string;
  horizon?: number;
  aggregation?: string;
}) {
  const data = await apiFetch("/forecasting/generate", {
    method: "POST",
    body: JSON.stringify({
      table: params.table,
      date_column: params.date_column,
      metric_column: params.metric_column || null,
      frequency: params.frequency || "monthly",
      horizon: params.horizon || 3,
      aggregation: params.aggregation || "SUM",
    }),
  });
  if (data.status === "error") throw new Error(data.message || "Forecast could not be generated.");
  return data.forecast;
}

export async function getAnomalyReport(forceRefresh = false) {
  const data = await apiFetch(`/anomaly/report?force_refresh=${forceRefresh}`);
  if (data.status === "error") throw new Error(data.message || "Failed to load anomaly report");
  return data.report;
}

export async function getAnomalySummary() {
  return apiFetch("/anomaly/summary");
}

export async function getBusinessInsights(forceRefresh = false): Promise<BusinessInsightsResponse> {
  return apiFetch<BusinessInsightsResponse>(`/intelligence/insights?force_refresh=${forceRefresh}`);
}

export async function refreshBusinessInsights(): Promise<BusinessInsightsResponse> {
  return apiFetch<BusinessInsightsResponse>("/intelligence/insights/refresh", {
    method: "POST",
  });
}

export async function getAgents(): Promise<AgentInfo[]> {
  const data = await apiFetch("/agents");
  if (data.status === "error") throw new Error(data.message || "Failed to load agents");
  return data.agents || [];
}

export async function runAgentTask(
  task: string,
  agentName?: string | null,
  context?: Record<string, any> | null
): Promise<AgentResult> {
  const data = await apiFetch("/agents/run", {
    method: "POST",
    body: JSON.stringify({
      task,
      agent_name: agentName || null,
      context: context || null,
    }),
  });
  if (data.status === "error") throw new Error(data.message || "Agent task failed");
  return data.result;
}

export async function getAgentActions(): Promise<ActionPlan[]> {
  const data = await apiFetch("/agent-actions");
  if (data.status === "error") throw new Error(data.message || "Failed to load agent actions");
  return data.actions || [];
}

export async function getAgentAction(actionId: string): Promise<ActionPlan> {
  const data = await apiFetch(`/agent-actions/${encodeURIComponent(actionId)}`);
  if (data.status === "error") throw new Error(data.message || "Failed to load action details");
  return data.action;
}

export async function confirmAgentAction(actionId: string): Promise<AgentActionResponse> {
  return apiFetch(`/agent-actions/${encodeURIComponent(actionId)}/confirm`, {
    method: "POST",
  });
}

export async function cancelAgentAction(actionId: string): Promise<AgentActionResponse> {
  return apiFetch(`/agent-actions/${encodeURIComponent(actionId)}/cancel`, {
    method: "POST",
  });
}

export async function getAuditHistory() {
  return apiFetch("/audit-history");
}
