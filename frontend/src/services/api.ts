const API_BASE = "http://127.0.0.1:8001";

export async function sendMessage(message: string, sessionId: string) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

export async function sendInsert(inputValues: Record<string, string>, table: string, sessionId: string) {
  const message = Object.entries(inputValues)
    .map(([key, value]) => `${key}: ${value}`)
    .join(", ");

  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      input_values: inputValues,
      pending_insert: true,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
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

export async function confirmQuery(sql: string) {
  const response = await fetch(`${API_BASE}/confirm-query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
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
