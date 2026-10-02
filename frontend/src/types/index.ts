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

  diagram?:
    | string
    | {
        nodes: any[];
        edges: any[];
      }
    | null;

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

// ── Phase 8.3: Proactive Data Intelligence Models ──────────────────────────

export type ProactiveAlertSeverity = "CRITICAL" | "WARNING" | "INFO" | string;

export type ProactiveAlertStatus = "NEW" | "ACKNOWLEDGED" | "INVESTIGATING" | "RESOLVED" | string;

export type ProactiveAlertCategory =
  | "METRIC_SPIKE"
  | "METRIC_DROP"
  | "ANOMALY_DETECTED"
  | "DATA_QUALITY_DEGRADATION"
  | "INVENTORY_RISK"
  | "FORECAST_DEVIATION"
  | "METRIC_CHANGE"
  | "DATA_QUALITY"
  | "ANOMALY"
  | "RELATIONAL_INTEGRITY"
  | string;

export interface ProactiveAlert {
  alert_id: string;
  title: string;
  category: ProactiveAlertCategory;
  severity: ProactiveAlertSeverity;
  status: ProactiveAlertStatus;
  metric: string;
  metric_name?: string;
  user_id?: string;
  timestamp?: string;
  previous_value?: number | null;
  current_value?: number | null;
  delta?: number | null;
  delta_percent?: number | null;
  threshold_applied?: string | null;
  threshold_used?: string | null;
  source_tables: string[];
  source_columns: string[];
  lineage_steps?: string[];
  lineage?: string[];
  sql?: string | null;
  sql_used?: string | null;
  evidence: Record<string, any>;
  explanation: string;
  recommendation: string;
  action_suggestion?: any;
  action_supported?: boolean;
  created_at: string;
  updated_at?: string;
  resolved_at?: string | null;
}

export interface ProactiveAlertListResponse {
  alerts: ProactiveAlert[];
  count: number;
  total?: number;
  active_count?: number;
  status?: string;
  message?: string;
}

export interface ProactiveEvaluationResponse {
  status: string;
  alerts: ProactiveAlert[];
  count: number;
  database_name?: string;
  database_type?: string;
  timestamp?: string;
  message?: string;
  alerts_evaluated?: number;
  new_alerts?: number;
  active_alerts?: number;
}

export interface ProactiveActionProposal {
  action_id?: string;
  task_id?: string;
  action_type: string;
  description?: string;
  target_table: string;
  target_columns?: string[];
  proposed_sql?: string;
  preview_sql?: string;
  verification_sql?: string;
  parameters?: Record<string, any>;
  estimated_affected_rows: number;
  dry_run?: boolean;
  requires_confirmation: boolean;
  safety_notes?: string;
  consequences?: string;
  risk_level?: string;
  recommended_agent?: string;
  source_alert_id?: string;
  action_plan?: any;
}

export interface ProactiveActionProposalResponse {
  available: boolean;
  proposal?: ProactiveActionProposal;
  action_proposal?: ProactiveActionProposal;
  alert_id?: string;
  reason?: string;
}

// ── Phase 8.4: AI Decision & Planning Intelligence Models ──────────────────

export interface DecisionEvidenceItem {
  evidence_id: string;
  metric: string;
  title: string;
  current_value: any;
  previous_value?: any;
  delta?: number | null;
  delta_percent?: number | null;
  source_tables: string[];
  source_columns: string[];
  sql?: string | null;
  calculation: string;
  source_system: string;
  metadata?: Record<string, any>;
}

export interface DecisionFinding {
  finding_id: string;
  statement: string;
  evidence_ids: string[];
  severity: "CRITICAL" | "WARNING" | "INFO" | string;
  category: string;
  source_tables: string[];
}

export interface DecisionHypothesis {
  hypothesis_id: string;
  statement: string;
  status: "UNCONFIRMED_HYPOTHESIS" | string;
  supporting_evidence_ids: string[];
  likelihood: "PROBABLE" | "POSSIBLE" | "UNCERTAIN" | string;
  causality_caveat: string;
}

export interface DecisionRecommendedInvestigation {
  investigation_id: string;
  title: string;
  rationale: string;
  target_table?: string | null;
  suggested_focus?: string | null;
  priority: number;
}

export interface DecisionPlanStep {
  step_number: number;
  title: string;
  description: string;
  action_type: "INVESTIGATE" | "AUDIT" | "COMPARE" | "REMEDIATE" | string;
  target_table?: string | null;
  requires_confirmation: boolean;
  safe_action_eligible: boolean;
  suggested_action_id?: string | null;
}

export interface DecisionConfidenceAssessment {
  level: "HIGH" | "MODERATE" | "LIMITED" | string;
  signal_count: number;
  corroborating_sources: string[];
  rationale: string;
  limitations: string[];
}

export interface DecisionAnalysisResponse {
  status: "success" | "disconnected" | "error" | string;
  question: string;
  intent?: string;
  problem_statement: string;
  findings: DecisionFinding[];
  evidence: DecisionEvidenceItem[];
  hypotheses: DecisionHypothesis[];
  recommended_investigations: DecisionRecommendedInvestigation[];
  decision_plan: DecisionPlanStep[];
  confidence?: DecisionConfidenceAssessment | null;
  source_tables: string[];
  generated_at?: string;
  database_name?: string;
  database_type?: string;
  message?: string;
  analysis?: any;
}

// ── Phase 8.5: Outcome & Learning Intelligence Models ──────────────────────

export type OutcomeStatusType = "SUCCESSFUL" | "PARTIAL" | "FAILED" | "UNKNOWN";

export interface OutcomeRecord {
  outcome_id: string;
  user_id: string;
  action_type: string;
  expected_outcome: string;
  actual_outcome: string;
  status: OutcomeStatusType;
  decision_id?: string | null;
  question?: string | null;
  action_id?: string | null;
  plan_step?: number | null;
  evidence?: any;
  notes?: string | null;
  created_at: string;
}

export interface RecordOutcomePayload {
  action_type: string;
  expected_outcome: string;
  actual_outcome: string;
  status: OutcomeStatusType;
  decision_id?: string | null;
  question?: string | null;
  action_id?: string | null;
  plan_step?: number | null;
  evidence?: any;
  notes?: string | null;
}

export interface OutcomeListResponse {
  status: "success" | "error" | string;
  outcomes: OutcomeRecord[];
  total: number;
  message?: string;
}

export type FeedbackTargetType = "DECISION" | "PLAN" | "ALERT" | "RECOMMENDATION" | "INVESTIGATION";

export interface FeedbackRecord {
  feedback_id: string;
  user_id: string;
  target_type: FeedbackTargetType;
  target_id?: string | null;
  question?: string | null;
  useful?: boolean | null;
  accepted?: boolean | null;
  comment?: string | null;
  created_at: string;
}

export interface RecordFeedbackPayload {
  target_type: FeedbackTargetType;
  target_id?: string | null;
  question?: string | null;
  useful?: boolean | null;
  accepted?: boolean | null;
  comment?: string | null;
}

export interface LearningPattern {
  pattern_id: string;
  action_type?: string;
  target_type?: string;
  description: string;
  total_occurrences?: number;
  success_rate?: number;
  failure_rate?: number;
  accepted_count?: number;
  rejected_count?: number;
  acceptance_rate?: number;
  rejection_rate?: number;
  evidence_support?: string;
  summary?: string;
  caveat?: string;
}

export interface LearningSummary {
  user_id: string;
  total_outcomes: number;
  successful_count: number;
  partial_count: number;
  failed_count: number;
  unknown_count: number;
  total_feedbacks: number;
  useful_count: number;
  not_useful_count: number;
  accepted_count: number;
  rejected_count: number;
  successful_patterns: LearningPattern[];
  rejected_patterns: LearningPattern[];
  frequently_accepted_actions: LearningPattern[];
  frequently_rejected_actions: LearningPattern[];
  evidence_coverage: {
    outcomes_with_evidence_count: number;
    total_outcomes: number;
    coverage_ratio: number;
    documented_percentage: string;
  };
  areas_with_insufficient_data: string[];
  insufficient_data: boolean;
  disclaimer: string;
  generated_at: string;
}

export interface LearningSummaryResponse {
  status: "success" | "error" | string;
  summary: LearningSummary | null;
  message?: string;
}


// ── Phase 8.6: Continuous Intelligence & Executive Monitoring ────────────────

export type MonitoringSeverity = "critical" | "warning" | "info";
export type MonitoringItemType =
  | "anomaly"
  | "proactive_alert"
  | "bi_insight"
  | "cross_table";

export interface MonitoringItem {
  item_id: string;
  item_type: MonitoringItemType;
  severity: MonitoringSeverity;
  title: string;
  observed_change: string;
  business_impact: string;
  possible_explanation: string;
  recommended_next_step: string;
  evidence: Record<string, unknown>;
  source_component: string;
}

export interface ExecutiveSummary {
  overall_status: "healthy" | "attention_needed" | "critical" | string;
  headline: string;
  critical_count: number;
  warning_count: number;
  info_count: number;
  top_risks: string[];
  top_opportunities: string[];
  generated_at: string;
}

export interface MonitoringReport {
  user_id: string;
  db_type: string;
  scanned_at: string;
  items: MonitoringItem[];
  executive_summary: ExecutiveSummary | null;
  scan_duration_ms: number;
  status: string;
  message: string;
}

export interface MonitoringEvaluateResponse {
  status: "success" | "disconnected" | "error" | string;
  message?: string;
  report: MonitoringReport | null;
}

export interface MonitoringStatusResponse {
  status: "ok" | "no_scan" | "error" | string;
  message?: string;
  last_scanned_at: string | null;
  db_type?: string;
  scan_duration_ms?: number;
  item_counts?: {
    total: number;
    critical: number;
    warning: number;
    info: number;
  };
  overall_status?: string;
}

export interface MonitoringSummaryResponse {
  status: "success" | "no_scan" | "error" | string;
  message?: string;
  summary: ExecutiveSummary | null;
  items?: MonitoringItem[];
  scanned_at?: string;
}

