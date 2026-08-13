const API_BASE = "https://bg-chatbox.onrender.com";

export async function sendMessage(message: string, signal?: AbortSignal) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
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

export async function getDatabaseType() {
  const response = await fetch(`${API_BASE}/database-type`);
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
  return response.json() as Promise<{ db_type: string }>;
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
  return response.blob();
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
