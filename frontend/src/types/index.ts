export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;

  sql?: string;

  result?: {
    success: boolean;
    columns?: string[];
    rows?: any[][];
    error?: string;
    execution_time_ms?: number;
    rows_returned?: number;
  };

  explanation?: string;

  chart?: {
    chart_type: string;
    title: string;
    labels: string[];
    values: number[];
  } | null;

  diagram?: string | { nodes: any[]; edges: any[] } | null;

  analytics?: {
    cards: {
      customers: number;
      orders: number;
      products: number;
      revenue: number;
    };
    bar: {
      labels: string[];
      values: number[];
    };
    line: {
      labels: string[];
      values: number[];
    };
    pie: {
      labels: string[];
      values: number[];
    };
  } | null;

  followups?: string[];
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
}
