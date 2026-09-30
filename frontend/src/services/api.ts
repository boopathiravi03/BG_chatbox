import axios from "axios";
import type { AgentInfo, AgentResult, ActionPlan, AgentActionResponse } from "../types";

export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001"
).replace(/\/+$/, "");

export async function sendMessage(message: string, sessionId: string) {
  const response = await axios.post(`${API_BASE}/chat`, {
    message,
    session_id: sessionId,
  });
  return response.data;
}

export async function sendInsert(
  inputValues: Record<string, string>,
  table: string,
  sessionId: string,
) {
  const message = Object.entries(inputValues)
    .map(([key, value]) => `${key}: ${value}`)
    .join(", ");

  const response = await axios.post(`${API_BASE}/chat`, {
    message,
    session_id: sessionId,
    input_values: inputValues,
    pending_insert: true,
  });
  return response.data;
}

export async function getSchema() {
  const response = await fetch(`${API_BASE}/schema`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function runQuery(query: string) {
  const response = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getFlowchart() {
  const response = await fetch(`${API_BASE}/flowchart`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function clearDatabase() {
  const response = await fetch(`${API_BASE}/clear-db`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getDatabaseInfo() {
  const response = await fetch(`${API_BASE}/database-info`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getDashboardData() {
  const response = await fetch(`${API_BASE}/dashboard`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function confirmQuery(sessionId: string) {
  const response = await fetch(`${API_BASE}/confirm-query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function createBackup() {
  const response = await fetch(`${API_BASE}/backup`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function restoreDatabase(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/restore`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function downloadBackup() {
  const response = await fetch(`${API_BASE}/download-backup`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response;
}

export async function getSuggestions() {
  const response = await fetch(`${API_BASE}/suggestions`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getDatabaseType() {
  const response = await fetch(`${API_BASE}/database-type`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getDatabaseConnectionInfo() {
  const response = await fetch(`${API_BASE}/database-connection-info`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function optimizeSQL(sql: string) {
  const response = await fetch(`${API_BASE}/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getRelationshipGraph() {
  const response = await fetch(`${API_BASE}/relationship-graph`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getAnalytics() {
  const response = await fetch(`${API_BASE}/analytics`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
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
  const response = await fetch(`${API_BASE}/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function disconnectDatabase() {
  const response = await fetch(`${API_BASE}/disconnect`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getBusinessAnalysis() {
  const response = await fetch(`${API_BASE}/analyze-business`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json();
}

export async function getIntelligenceReport() {
  const response = await fetch(`${API_BASE}/intelligence/report`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  return data.report || data;
}

export async function triggerIntelligenceScan() {
  const response = await fetch(`${API_BASE}/intelligence/scan`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  return data.report || data;
}

export async function getTableProfile(tableName: string) {
  const response = await fetch(`${API_BASE}/intelligence/table/${encodeURIComponent(tableName)}`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
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

  const response = await fetch(`${API_BASE}/intelligence/table/${encodeURIComponent(tableName)}/sample?${query.toString()}`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Failed to load table sample");
  return data.sample;
}

export async function getColumnProfile(tableName: string, columnName: string) {
  const response = await fetch(
    `${API_BASE}/intelligence/column/${encodeURIComponent(tableName)}/${encodeURIComponent(columnName)}`
  );
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Failed to load column profile");
  return data.column;
}

export async function askAnalyst(
  question: string,
  options: { table?: string; metric?: string } = {}
) {
  const response = await fetch(`${API_BASE}/analyst/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      table: options.table,
      metric: options.metric,
    }),
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Analysis could not be completed.");
  return data.analysis;
}

export async function getAnalystQuickActions() {
  const response = await fetch(`${API_BASE}/analyst/quick-actions`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  return data.actions || [];
}

export async function getForecastingCandidates() {
  const response = await fetch(`${API_BASE}/forecasting/candidates`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
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
  const response = await fetch(`${API_BASE}/forecasting/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      table: params.table,
      date_column: params.date_column,
      metric_column: params.metric_column || null,
      frequency: params.frequency || "monthly",
      horizon: params.horizon || 3,
      aggregation: params.aggregation || "SUM",
    }),
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Forecast could not be generated.");
  return data.forecast;
}

export async function getAnomalyReport(forceRefresh = false) {
  const response = await fetch(`${API_BASE}/anomaly/report?force_refresh=${forceRefresh}`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Failed to load anomaly report");
  return data.report;
}

export async function getAnomalySummary() {
  const response = await fetch(`${API_BASE}/anomaly/summary`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return await response.json();
}

export async function getAgents(): Promise<AgentInfo[]> {
  const response = await fetch(`${API_BASE}/agents`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Failed to load agents");
  return data.agents || [];
}

export async function runAgentTask(
  task: string,
  agentName?: string | null,
  context?: Record<string, any> | null
): Promise<AgentResult> {
  const response = await fetch(`${API_BASE}/agents/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task,
      agent_name: agentName || null,
      context: context || null,
    }),
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Agent task failed");
  return data.result;
}

export async function getAgentActions(): Promise<ActionPlan[]> {
  const response = await fetch(`${API_BASE}/agent-actions`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Failed to load agent actions");
  return data.actions || [];
}

export async function getAgentAction(actionId: string): Promise<ActionPlan> {
  const response = await fetch(`${API_BASE}/agent-actions/${encodeURIComponent(actionId)}`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  const data = await response.json();
  if (data.status === "error") throw new Error(data.message || "Failed to load action details");
  return data.action;
}

export async function confirmAgentAction(actionId: string): Promise<AgentActionResponse> {
  const response = await fetch(`${API_BASE}/agent-actions/${encodeURIComponent(actionId)}/confirm`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return await response.json();
}

export async function cancelAgentAction(actionId: string): Promise<AgentActionResponse> {
  const response = await fetch(`${API_BASE}/agent-actions/${encodeURIComponent(actionId)}/cancel`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return await response.json();
}



