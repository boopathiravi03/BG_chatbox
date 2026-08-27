export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;

  sql?: string;

  result?: {
    success: boolean;
    columns?: string[];
    rows?: any[];
    error?: string;
    execution_time_ms?: number;
    rows_returned?: number;
    pending_confirmation?: boolean;
    operation?: string;
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
    cards: Record<string, number>;
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

  requires_confirmation?: boolean;

  input_request?: {
    type: string;
    table: string;
    title: string;
    message: string;
    fields: {
      name: string;
      label: string;
      type: string;
      required: boolean;
    }[];
  } | null;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
}
