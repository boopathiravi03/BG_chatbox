export interface AnalyticsData {
  cards: {
    table_count: number;
    total_rows: number;
    tables: Record<string, number>;
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
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;

  type?: string;
  message?: string;

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

  operation?: string;
  table?: string;

  affected_rows_preview?: number;

  confirmed?: boolean;

  technical_details?: string;

  chart?: {
    chart_type: string;
    title: string;
    labels: string[];
    values: number[];
  } | null;

  diagram?: string | {
    nodes: any[];
    edges: any[];
  } | null;

  analytics?: AnalyticsData | null;

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

export interface AttentionItem {
  id: string;
  category: "critical" | "warning" | "performance" | "insight" | "healthy";
  title: string;
  description: string;
  table?: string;
  column?: string;
  target_module: "health" | "explorer" | "sqllab" | "analytics";
}

export interface DataQualitySummary {
  null_percentage: number;
  empty_tables: string[];
  null_heavy_columns: Array<{
    table: string;
    column: string;
    null_count: number;
    total_rows: number;
    null_percentage: number;
  }>;
  duplicate_table_schemas: string[][];
  orphan_foreign_keys: Array<{
    source_table: string;
    foreign_key_column: string;
    target_table: string;
    target_column: string;
    orphan_count: number;
  }>;
}

export interface PerformanceFinding {
  type: string;
  table: string;
  column?: string;
  description: string;
  recommendation: string;
}

export interface BusinessMetric {
  label: string;
  value: string;
  table: string;
  column: string;
  calculation: string;
}

export interface DatabaseIntelligenceReport {
  database_type: string;
  database_name: string;
  total_tables: number;
  total_rows: number;
  total_columns: number;
  total_relationships: number;
  health_score: number;
  schema_summary: Record<string, any>;
  data_quality: DataQualitySummary;
  performance_findings: PerformanceFinding[];
  business_metrics: BusinessMetric[];
  attention_items: AttentionItem[];
  scan_timestamp: string;
  scan_duration_ms: number;
  is_partial: boolean;
  error_message?: string | null;
}

export interface ColumnIntelligence {
  name: string;
  type: string;
  semantic_type: string;
  is_pk: boolean;
  is_fk: boolean;
  fk_target?: string | null;
  nullable: boolean;
  default?: string | null;
  null_percentage: number;
  distinct_count?: number | null;
}

export interface TableProfile {
  table_name: string;
  database: string;
  database_type: string;
  row_count: number;
  column_count: number;
  primary_keys: string[];
  outgoing_foreign_keys: Array<{
    foreign_key_columns: string[];
    referred_table: string;
    referred_columns: string[];
  }>;
  incoming_foreign_keys: Array<{
    referencing_table: string;
    foreign_key_columns: string[];
    referenced_columns: string[];
  }>;
  health_status: "healthy" | "warning" | "critical";
  health_reasons: string[];
  column_type_breakdown: {
    numeric: number;
    text: number;
    datetime: number;
    boolean: number;
    nullable: number;
  };
  columns: ColumnIntelligence[];
  ai_summary: string;
}

export interface TableSampleData {
  table_name: string;
  total_rows: number;
  limit: number;
  offset: number;
  columns: string[];
  rows: any[][];
}

export interface ColumnProfile {
  table_name: string;
  column_name: string;
  sql_type: string;
  semantic_type: string;
  nullable: boolean;
  is_pk: boolean;
  total_rows: number;
  null_count: number | string | null;
  null_percentage: number | string | null;
  distinct_count: number | string | null;
  statistics: Record<string, any>;
}

export interface AnalystEvidence {
  metric_name: string;
  calculation: string;
  source_table: string;
  source_column?: string | null;
  date_column?: string | null;
  current_value?: number | string | null;
  previous_value?: number | string | null;
  absolute_change?: number | null;
  percentage_change?: number | null;
  growth_rate?: number | null;
  direction?: "up" | "down" | "flat" | null;
  sample_count: number;
  time_period?: string | null;
  breakdown: any[];
  confidence_note: string;
}

export interface RecommendedInvestigation {
  label: string;
  action: "explorer" | "sqllab" | "health" | "analytics";
  target?: string | null;
  query?: string | null;
}

export interface AnalystResult {
  question: string;
  analysis_type: string;
  key_insight: string;
  evidence: AnalystEvidence;
  chart?: {
    chart_type: string;
    title: string;
    labels: string[];
    values: number[];
  } | null;
  breakdown: any[];
  recommended_investigations: RecommendedInvestigation[];
  ai_explanation: string;
  sql_query?: string | null;
  status: string;
  error_message?: string | null;
}

export interface AnalystQuickAction {
  id: string;
  title: string;
  question: string;
  category: string;
  table?: string | null;
  metric?: string | null;
}

export interface ForecastCandidate {
  table: string;
  date_column: string;
  metric_column: string | null;
  metric_label: string;
  calculation: string;
  frequency: "daily" | "weekly" | "monthly";
  historical_points_count: number;
  min_date: string;
  max_date: string;
}

export interface ForecastObservation {
  period: string;
  value: number;
  is_forecast: boolean;
  lower_bound?: number | null;
  upper_bound?: number | null;
}

export interface ForecastResult {
  metric_name: string;
  source_table: string;
  date_column: string;
  metric_column?: string | null;
  frequency: string;
  historical_range: { start?: string; end?: string };
  forecast_horizon: number;
  horizon_unit: string;
  observations: ForecastObservation[];
  method: string;
  model_params: Record<string, any>;
  validation: {
    validation_performed?: boolean;
    mae?: number | null;
    mape?: number | null;
    mape_note?: string | null;
    train_observations?: number;
    holdout_observations?: number;
    limitation?: string;
    reason?: string;
  };
  limitations: string[];
  ai_explanation?: string | null;
  chart?: {
    chart_type: string;
    title: string;
    labels: string[];
    values: number[];
  } | null;
  sql_query?: string | null;
  status: string;
  error_message?: string | null;
}

export interface AnomalyFinding {
  id: string;
  metric: string;
  table: string;
  column?: string | null;
  time_period?: string | null;
  observed_value: any;
  expected_value: any;
  deviation_str: string;
  detection_method: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  explanation: string;
  suggested_action: "explorer" | "sqllab" | "analytics" | "health";
  action_target?: string | null;
  chart?: any | null;
}

export interface AnomalyScanReport {
  total_anomalies: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
  anomalies: AnomalyFinding[];
  scan_timestamp: string;
  database_name: string;
  database_type: string;
}

export interface AnomalySummary {
  total: number;
  critical: number;
  warning: number;
  info: number;
}

export interface AgentInfo {
  name: string;
  role: string;
  description: string;
  is_read_only: boolean;
  capabilities: string[];
  allowed_tools: string[];
}

export interface AgentFinding {
  id: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  title: string;
  description: string;
  table?: string | null;
  column?: string | null;
  evidence?: any;
}

export interface ActionPlan {
  action_id: string;
  task_id: string;
  agent_name: string;
  table: string;
  action_type: "UPDATE" | "DELETE" | "INSERT";
  estimated_rows: number;
  exact_sql: string;
  verification_sql: string;
  expected_verification_result: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  potential_consequence: string;
  rollback_considerations: string;
  status:
    | "PROPOSED"
    | "AWAITING_CONFIRMATION"
    | "EXECUTING"
    | "EXECUTED"
    | "VERIFIED"
    | "VERIFICATION_FAILED"
    | "FAILED"
    | "CANCELLED";
  created_at: string;
  confirmed_at?: string | null;
  executed_at?: string | null;
  actual_rows_affected?: number | null;
  verification_details?: {
    verified: boolean;
    expected: string;
    observed: string;
  } | null;
  error?: string | null;
  database_identity?: string | null;
}

export interface AgentResult {
  task_id: string;
  agent_name: string;
  status: "COMPLETED" | "ACTION_REQUIRED" | "WAITING_CONFIRMATION" | "FAILED";
  summary: string;
  findings: AgentFinding[];
  evidence: Record<string, any>;
  recommendations: string[];
  proposed_action?: ActionPlan | null;
  limitations: string[];
  execution_steps: string[];
  duration_ms: number;
}

export interface AgentActionResponse {
  success: boolean;
  status?: string;
  actual_rows_affected?: number;
  error?: string;
  action?: ActionPlan;
}

export interface BusinessInsight {
  id: string;
  title: string;
  summary: string;
  category:
    | "TREND"
    | "GROWTH"
    | "DECLINE"
    | "TOP_CONTRIBUTOR"
    | "CONCENTRATION"
    | "QUALITY"
    | "ANOMALY"
    | "FORECAST"
    | "PERFORMANCE"
    | "DATA_COMPLETENESS"
    | string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  priority: number;
  metric?: string | null;
  current_value?: any;
  previous_value?: any;
  change_value?: any;
  change_percent?: number | null;
  source_tables: string[];
  source_columns: string[];
  sql?: string | null;
  evidence: Record<string, any>;
  generated_at: string;
  investigation_type: string;
  recommended_next_step: string;
}

export interface BusinessInsightsResponse {
  success: boolean;
  status?: string;
  message?: string;
  generated_at?: string;
  database_context?: any;
  insights: BusinessInsight[];
  summary: {
    total: number;
    critical: number;
    warning: number;
    info: number;
  };
}

export interface JoinStepInfo {
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
  is_reverse: boolean;
  join_type: string;
}

export interface JoinPathInfo {
  source_table: string;
  target_table: string;
  depth: number;
  steps: JoinStepInfo[];
  lineage: string[];
  generated_join_clause: string;
}

export interface BiQueryResponse {
  status: "success" | "no_relationship" | "error";
  question?: string;
  key_insight?: string;
  ai_explanation?: string;
  data?: any[] | null;
  lineage: string[];
  sql?: string | null;
  source_tables?: string[];
  calculation?: string;
  record_count?: number;
  message?: string;
  available_relationships?: string[];
}



