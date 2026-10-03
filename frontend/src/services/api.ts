import type {
  AgentInfo,
  AgentResult,
  ActionPlan,
  AgentActionResponse,
  BusinessInsight,
  BusinessInsightsResponse,
  ProactiveAlert,
  ProactiveAlertListResponse,
  ProactiveEvaluationResponse,
  ProactiveActionProposalResponse,
  DecisionAnalysisResponse,
  OutcomeRecord,
  RecordOutcomePayload,
  OutcomeListResponse,
  FeedbackRecord,
  RecordFeedbackPayload,
  LearningSummaryResponse,
  MonitoringEvaluateResponse,
  MonitoringStatusResponse,
  MonitoringSummaryResponse,
  InvestigationResult,
  InvestigateSignalPayload,
  ActionProposal,
  ProposeActionPayload,
  ConfirmActionPayload,
  ExecuteActionPayload,
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

export async function getRelationships() {
  return apiFetch("/intelligence/relationships");
}

export async function getJoinPaths(maxDepth: number = 3) {
  return apiFetch(`/intelligence/join-paths?max_depth=${maxDepth}`);
}

export async function queryBi(question: string) {
  return apiFetch("/intelligence/bi-query", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

// ── Phase 8.3 Proactive Intelligence Endpoints ───────────────────────────────

export async function getProactiveAlerts(params?: {
  status?: string;
  severity?: string;
  category?: string;
  limit?: number;
}): Promise<ProactiveAlertListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.severity) query.set("severity", params.severity);
  if (params?.category) query.set("category", params.category);
  if (params?.limit) query.set("limit", String(params.limit));

  const qs = query.toString();
  return apiFetch<ProactiveAlertListResponse>(`/proactive/alerts${qs ? `?${qs}` : ""}`);
}

export async function evaluateProactive(req?: { force?: boolean }): Promise<ProactiveEvaluationResponse> {
  return apiFetch<ProactiveEvaluationResponse>("/proactive/evaluate", {
    method: "POST",
    body: JSON.stringify(req || {}),
  });
}

export async function getProactiveAlert(alertId: string): Promise<{ alert: ProactiveAlert }> {
  return apiFetch<{ alert: ProactiveAlert }>(`/proactive/alerts/${encodeURIComponent(alertId)}`);
}

export async function acknowledgeProactiveAlert(alertId: string): Promise<{ alert: ProactiveAlert }> {
  return apiFetch<{ alert: ProactiveAlert }>(`/proactive/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
    method: "POST",
  });
}

export async function resolveProactiveAlert(alertId: string): Promise<{ alert: ProactiveAlert }> {
  return apiFetch<{ alert: ProactiveAlert }>(`/proactive/alerts/${encodeURIComponent(alertId)}/resolve`, {
    method: "POST",
  });
}

export async function proposeProactiveAction(alertId: string): Promise<ProactiveActionProposalResponse> {
  return apiFetch<ProactiveActionProposalResponse>(`/proactive/alerts/${encodeURIComponent(alertId)}/propose-action`, {
    method: "POST",
  });
}

// ── Phase 8.4 AI Decision & Planning Intelligence Endpoints ────────────────

export async function queryDecisionIntelligence(
  question: string
): Promise<DecisionAnalysisResponse> {
  return apiFetch<DecisionAnalysisResponse>("/intelligence/decision", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

// ── Phase 8.5 Outcome & Learning Intelligence Endpoints ─────────────────────

export async function recordOutcome(
  payload: RecordOutcomePayload
): Promise<{ status: string; outcome?: OutcomeRecord; message?: string }> {
  return apiFetch<{ status: string; outcome?: OutcomeRecord; message?: string }>("/intelligence/outcomes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getOutcomes(params?: {
  limit?: number;
  action_type?: string;
  status?: string;
}): Promise<OutcomeListResponse> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.action_type) query.set("action_type", params.action_type);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return apiFetch<OutcomeListResponse>(`/intelligence/outcomes${qs ? `?${qs}` : ""}`);
}

export async function recordFeedback(
  payload: RecordFeedbackPayload
): Promise<{ status: string; feedback?: FeedbackRecord; message?: string }> {
  return apiFetch<{ status: string; feedback?: FeedbackRecord; message?: string }>("/intelligence/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getLearningSummary(): Promise<LearningSummaryResponse> {
  return apiFetch<LearningSummaryResponse>("/intelligence/learning-summary");
}


// ── Phase 8.6: Continuous Intelligence & Executive Monitoring ─────────────────

export async function runMonitoringScan(): Promise<MonitoringEvaluateResponse> {
  return apiFetch<MonitoringEvaluateResponse>("/intelligence/monitoring/evaluate", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getMonitoringStatus(): Promise<MonitoringStatusResponse> {
  return apiFetch<MonitoringStatusResponse>("/intelligence/monitoring/status");
}

export async function getMonitoringSummary(): Promise<MonitoringSummaryResponse> {
  return apiFetch<MonitoringSummaryResponse>("/intelligence/monitoring/summary");
}

// ── Phase 8.7: Root-Cause & Investigation Intelligence ───────────────────────

export async function investigateSignal(
  payload: InvestigateSignalPayload
): Promise<{ status: string; investigation?: InvestigationResult; message?: string }> {
  return apiFetch<{ status: string; investigation?: InvestigationResult; message?: string }>(
    "/intelligence/investigate",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

// ── Phase 8.8: Controlled Business Actions & Action Intelligence ────────────

export async function proposeAction(
  payload: ProposeActionPayload
): Promise<{ status: string; action: ActionProposal; message?: string }> {
  return apiFetch<{ status: string; action: ActionProposal; message?: string }>(
    "/intelligence/actions/propose",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function previewAction(
  actionId: string
): Promise<{ status: string; action: ActionProposal; impact?: any; message?: string }> {
  return apiFetch<{ status: string; action: ActionProposal; impact?: any; message?: string }>(
    `/intelligence/actions/${encodeURIComponent(actionId)}/preview`,
    {
      method: "POST",
    }
  );
}

export async function confirmAction(
  actionId: string,
  payload?: ConfirmActionPayload
): Promise<{ status: string; action: ActionProposal; confirmation?: any; message?: string }> {
  return apiFetch<{ status: string; action: ActionProposal; confirmation?: any; message?: string }>(
    `/intelligence/actions/${encodeURIComponent(actionId)}/confirm`,
    {
      method: "POST",
      body: JSON.stringify(payload || {}),
    }
  );
}

export async function executeAction(
  actionId: string,
  payload?: ExecuteActionPayload
): Promise<{
  status: string;
  action: ActionProposal;
  execution?: any;
  verification?: any;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    action: ActionProposal;
    execution?: any;
    verification?: any;
    message?: string;
  }>(`/intelligence/actions/${encodeURIComponent(actionId)}/execute`, {
    method: "POST",
    body: JSON.stringify(payload || {}),
  });
}

export async function getAction(
  actionId: string
): Promise<{ status: string; action: ActionProposal; message?: string }> {
  return apiFetch<{ status: string; action: ActionProposal; message?: string }>(
    `/intelligence/actions/${encodeURIComponent(actionId)}`
  );
}

export async function listActions(params?: {
  status?: string;
  limit?: number;
}): Promise<{ status: string; actions: ActionProposal[]; count: number; message?: string }> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return apiFetch<{ status: string; actions: ActionProposal[]; count: number; message?: string }>(
    `/intelligence/actions${qs ? `?${qs}` : ""}`
  );
}

export async function cancelAction(
  actionId: string
): Promise<{ status: string; action: ActionProposal; message?: string }> {
  return apiFetch<{ status: string; action: ActionProposal; message?: string }>(
    `/intelligence/actions/${encodeURIComponent(actionId)}/cancel`,
    {
      method: "POST",
    }
  );
}


// ── Phase 8.9: Closed-Loop Outcome Optimization & Adaptive Recommendations ────

export async function measureOutcome(payload: {
  action_id: string;
  window?: string;
  force_remeasure?: boolean;
}): Promise<{ status: string; analysis: any; message?: string }> {
  return apiFetch<{ status: string; analysis: any; message?: string }>(
    "/intelligence/outcomes/measure",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function getOutcomeMeasurement(
  outcomeId: string
): Promise<{ status: string; measurement: any; message?: string }> {
  return apiFetch<{ status: string; measurement: any; message?: string }>(
    `/intelligence/outcomes/${encodeURIComponent(outcomeId)}`
  );
}

export async function getOutcomeAnalysis(
  outcomeId: string
): Promise<{ status: string; analysis: any; message?: string }> {
  return apiFetch<{ status: string; analysis: any; message?: string }>(
    `/intelligence/outcomes/${encodeURIComponent(outcomeId)}/analysis`
  );
}

export async function getAdaptiveRecommendations(): Promise<{
  status: string;
  recommendations: any[];
  total: number;
  note?: string;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    recommendations: any[];
    total: number;
    note?: string;
    message?: string;
  }>("/intelligence/recommendations/adaptive");
}

export async function explainRecommendation(
  recommendationId: string
): Promise<{ status: string; recommendation_id: string; explanation: any; message?: string }> {
  return apiFetch<{
    status: string;
    recommendation_id: string;
    explanation: any;
    message?: string;
  }>(`/intelligence/recommendations/${encodeURIComponent(recommendationId)}/explain`, {
    method: "POST",
  });
}


// ── Phase 9.0: Advanced Predictive & Simulation Intelligence ──────────────────

export async function getPredictCandidates(): Promise<{
  status: string;
  candidates: any[];
  total: number;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    candidates: any[];
    total: number;
    message?: string;
  }>("/intelligence/predict/candidates");
}

export async function predictMetric(payload: {
  table: string;
  date_column?: string;
  metric_column?: string;
  metric_name?: string;
  aggregation?: string;
  frequency?: string;
  horizon_days?: number;
  force_method?: string;
}): Promise<{ status: string; prediction?: any; message?: string }> {
  return apiFetch<{ status: string; prediction?: any; message?: string }>(
    "/intelligence/predict",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function simulateScenario(payload: {
  prediction_id: string;
  change_percent?: number;
  absolute_change?: number;
  scenario_name?: string;
  scenario_type?: string;
}): Promise<{ status: string; scenario?: any; message?: string }> {
  return apiFetch<{ status: string; scenario?: any; message?: string }>(
    "/intelligence/predict/scenario",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function compareScenarios(payload: {
  prediction_id: string;
  scenarios: Array<{
    scenario_name: string;
    change_percent?: number;
    absolute_change?: number;
    scenario_type?: string;
  }>;
}): Promise<{ status: string; comparison?: any; message?: string }> {
  return apiFetch<{ status: string; comparison?: any; message?: string }>(
    "/intelligence/predict/compare",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function getPredictionHistory(): Promise<{
  status: string;
  predictions: any[];
  total: number;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    predictions: any[];
    total: number;
    message?: string;
  }>("/intelligence/predict/history");
}

export async function getPredictionById(
  predictionId: string
): Promise<{ status: string; prediction?: any; message?: string }> {
  return apiFetch<{ status: string; prediction?: any; message?: string }>(
    `/intelligence/predict/${encodeURIComponent(predictionId)}`
  );
}

export async function explainPrediction(
  predictionId: string
): Promise<{ status: string; explanation?: any; message?: string }> {
  return apiFetch<{ status: string; explanation?: any; message?: string }>(
    `/intelligence/predict/${encodeURIComponent(predictionId)}/explain`,
    {
      method: "POST",
    }
  );
}


// ── Phase 9.1: Enterprise Knowledge & Context Intelligence ────────────────────

export async function getKnowledgeSummary(): Promise<{
  status: string;
  summary?: any;
  entities?: any[];
  metrics?: any[];
  rules?: any[];
  conflicts?: any[];
  message?: string;
}> {
  return apiFetch<{
    status: string;
    summary?: any;
    entities?: any[];
    metrics?: any[];
    rules?: any[];
    conflicts?: any[];
    message?: string;
  }>("/intelligence/knowledge");
}

export async function getKnowledgeEntities(): Promise<{
  status: string;
  entities: any[];
  total: number;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    entities: any[];
    total: number;
    message?: string;
  }>("/intelligence/knowledge/entities");
}

export async function getKnowledgeMetrics(): Promise<{
  status: string;
  metrics: any[];
  total: number;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    metrics: any[];
    total: number;
    message?: string;
  }>("/intelligence/knowledge/metrics");
}

export async function getKnowledgeRules(): Promise<{
  status: string;
  rules: any[];
  total: number;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    rules: any[];
    total: number;
    message?: string;
  }>("/intelligence/knowledge/rules");
}

export async function parseBusinessContext(statement: string): Promise<{
  status: string;
  parse_result?: any;
  message?: string;
}> {
  return apiFetch<{ status: string; parse_result?: any; message?: string }>(
    "/intelligence/knowledge/context",
    {
      method: "POST",
      body: JSON.stringify({ statement }),
    }
  );
}

export async function createOrUpdateDefinition(payload: any): Promise<{
  status: string;
  item?: any;
  item_type?: string;
  message?: string;
}> {
  return apiFetch<{ status: string; item?: any; item_type?: string; message?: string }>(
    "/intelligence/knowledge/definitions",
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function confirmKnowledgeItem(knowledgeId: string): Promise<{
  status: string;
  message?: string;
}> {
  return apiFetch<{ status: string; message?: string }>(
    `/intelligence/knowledge/${encodeURIComponent(knowledgeId)}/confirm`,
    {
      method: "POST",
    }
  );
}

export async function disableKnowledgeItem(knowledgeId: string): Promise<{
  status: string;
  message?: string;
}> {
  return apiFetch<{ status: string; message?: string }>(
    `/intelligence/knowledge/${encodeURIComponent(knowledgeId)}/disable`,
    {
      method: "POST",
    }
  );
}

export async function resolveKnowledgeConflict(
  knowledgeId: string,
  payload: { resolution_choice: string; resolution_notes?: string }
): Promise<{ status: string; message?: string }> {
  return apiFetch<{ status: string; message?: string }>(
    `/intelligence/knowledge/${encodeURIComponent(knowledgeId)}/resolve`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function getKnowledgeItem(knowledgeId: string): Promise<{
  status: string;
  item?: any;
  item_type?: string;
  message?: string;
}> {
  return apiFetch<{ status: string; item?: any; item_type?: string; message?: string }>(
    `/intelligence/knowledge/${encodeURIComponent(knowledgeId)}`
  );
}

export async function getKnowledgeLineage(knowledgeId: string): Promise<{
  status: string;
  lineage?: any;
  message?: string;
}> {
  return apiFetch<{ status: string; lineage?: any; message?: string }>(
    `/intelligence/knowledge/${encodeURIComponent(knowledgeId)}/lineage`
  );
}

export async function explainKnowledgeItem(knowledgeId: string): Promise<{
  status: string;
  explanation?: any;
  message?: string;
}> {
  return apiFetch<{ status: string; explanation?: any; message?: string }>(
    `/intelligence/knowledge/${encodeURIComponent(knowledgeId)}/explain`
  );
}

export async function searchKnowledge(query: string): Promise<{
  status: string;
  found: boolean;
  answer: string;
  metrics?: any[];
  rules?: any[];
  entities?: any[];
  message?: string;
}> {
  return apiFetch<{
    status: string;
    found: boolean;
    answer: string;
    metrics?: any[];
    rules?: any[];
    entities?: any[];
    message?: string;
  }>(`/intelligence/knowledge/search?q=${encodeURIComponent(query)}`);
}

// ── Phase 9.2: Advanced Agent Orchestration API ──────────────────────────────

export async function initiateOrchestration(goal: string): Promise<{
  status: string;
  orchestration?: any;
  message?: string;
}> {
  return apiFetch<{ status: string; orchestration?: any; message?: string }>(
    "/intelligence/orchestrate",
    {
      method: "POST",
      body: JSON.stringify({ goal }),
    }
  );
}

export async function listOrchestrations(limit = 20): Promise<{
  status: string;
  runs?: any[];
  message?: string;
}> {
  return apiFetch<{ status: string; runs?: any[]; message?: string }>(
    `/intelligence/orchestrate?limit=${limit}`
  );
}

export async function listOrchestrationAgents(): Promise<{
  status: string;
  agents?: any[];
  message?: string;
}> {
  return apiFetch<{ status: string; agents?: any[]; message?: string }>(
    "/intelligence/orchestrate/agents"
  );
}

export async function getOrchestration(orchestrationId: string): Promise<{
  status: string;
  orchestration?: any;
  message?: string;
}> {
  return apiFetch<{ status: string; orchestration?: any; message?: string }>(
    `/intelligence/orchestrate/${encodeURIComponent(orchestrationId)}`
  );
}

export async function getOrchestrationEvidence(orchestrationId: string): Promise<{
  status: string;
  orchestration_id?: string;
  evidence?: any[];
  total_items?: number;
  message?: string;
}> {
  return apiFetch<{
    status: string;
    orchestration_id?: string;
    evidence?: any[];
    total_items?: number;
    message?: string;
  }>(`/intelligence/orchestrate/${encodeURIComponent(orchestrationId)}/evidence`);
}

export async function cancelOrchestration(orchestrationId: string): Promise<{
  status: string;
  message?: string;
  orchestration?: any;
}> {
  return apiFetch<{ status: string; message?: string; orchestration?: any }>(
    `/intelligence/orchestrate/${encodeURIComponent(orchestrationId)}/cancel`,
    {
      method: "POST",
    }
  );
}



