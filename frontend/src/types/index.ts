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

  is_intro?: boolean;
  intro_key?: string;
  connection_id?: string;

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
  estimated_affected_rows?: number;
  is_high_risk?: boolean;
  fingerprint?: string;
  conditions?: Array<{ column: string; operator: string; value: any }>;

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
  scan_state?: "not_scanned" | "scanning" | "completed_no_findings" | "completed_with_findings" | "scan_failed";
}

export interface AnomalySummary {
  total: number;
  critical: number;
  warning: number;
  info: number;
  total_anomalies?: number;
  total_count?: number;
  critical_count?: number;
  warning_count?: number;
  info_count?: number;
  scan_timestamp?: string;
  database_name?: string;
  database_type?: string;
  scan_state?: "not_scanned" | "scanning" | "completed_no_findings" | "completed_with_findings" | "scan_failed";
  anomalies?: AnomalyFinding[];
  clean_tables?: string[];
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


// ── Phase 8.7: Root-Cause & Investigation Intelligence ────────────────────────

export type InvestigationConfidenceLevel = "HIGH" | "MODERATE" | "LIMITED";

export interface InvestigationObservedChange {
  metric: string;
  current_value: unknown;
  previous_value: unknown;
  delta?: number | null;
  delta_percent?: number | null;
  time_period?: string;
  formatted_change?: string;
}

export interface InvestigationEvidenceItem {
  evidence_id: string;
  metric: string;
  current_value: unknown;
  previous_value: unknown;
  delta?: number | null;
  delta_percent?: number | null;
  time_range: string;
  source_table: string;
  source_columns: string[];
  record_count?: number | null;
  sql_lineage: string;
  calculation_description: string;
}

export interface InvestigationContributingFactor {
  factor_id: string;
  dimension: string;
  dimension_value: string;
  impact_type: "negative" | "positive" | "neutral" | string;
  contribution_percent?: number | null;
  observed_change: string;
  evidence_ids: string[];
}

export interface InvestigationHypothesis {
  hypothesis_id: string;
  statement: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  confidence_level: InvestigationConfidenceLevel;
  status: string;
  causality_caveat: string;
}

export interface InvestigationRecommendation {
  recommendation_id: string;
  action_title: string;
  reason: string;
  target_data: string;
  expected_information_gained: string;
  priority: "high" | "medium" | "low" | string;
}

export interface InvestigationConfidenceAssessment {
  level: InvestigationConfidenceLevel;
  score_rationale: string;
  supporting_signals_count: number;
  independent_sources_count: number;
  limitations: string[];
}

export interface InvestigationLineage {
  source_tables: string[];
  join_path: string;
  columns_analyzed: string[];
  calculations: string[];
  comparison_periods: string[];
  record_counts: Record<string, number>;
}

export interface InvestigationResult {
  investigation_id: string;
  user_id: string;
  signal_id: string;
  signal_title: string;
  status: "success" | "insufficient_evidence" | "disconnected" | "error" | string;
  observed_change?: InvestigationObservedChange | null;
  evidence: InvestigationEvidenceItem[];
  contributing_factors: InvestigationContributingFactor[];
  hypotheses: InvestigationHypothesis[];
  confidence?: InvestigationConfidenceAssessment | null;
  recommended_investigations: InvestigationRecommendation[];
  lineage?: InvestigationLineage | null;
  summary: string;
  explanation: string;
  missing_evidence?: Record<string, unknown> | null;
  created_at: string;
}

export interface InvestigateSignalPayload {
  signal_id?: string;
  metric?: string;
  table?: string;
  context?: Record<string, unknown>;
}


// ── Phase 8.8: Controlled Business Actions & Action Intelligence ──────────────

export type ActionProposalType = "INSERT" | "UPDATE" | "DELETE" | string;

export type ActionProposalStatus =
  | "PROPOSED"
  | "VALIDATING"
  | "READY_FOR_CONFIRMATION"
  | "CONFIRMED"
  | "EXECUTING"
  | "EXECUTED"
  | "VERIFIED"
  | "REJECTED"
  | "EXPIRED"
  | "BLOCKED"
  | "EXECUTION_FAILED"
  | "VERIFICATION_FAILED"
  | "CANCELLED"
  | string;

export type ActionProposalRisk = "LOW" | "MEDIUM" | "HIGH" | "BLOCKED" | string;

export interface ActionProposalTarget {
  table: string;
  columns: string[];
  condition_sql?: string | null;
  condition_params?: Record<string, any>;
  primary_keys?: string[];
}

export interface ActionProposalChange {
  column: string;
  current_value?: any;
  proposed_value?: any;
  value_type?: string | null;
}

export interface ActionProposalImpact {
  estimated_rows: number;
  actual_preview_rows: number;
  current_sample_records: Record<string, any>[];
  proposed_sample_records: Record<string, any>[];
  related_records_count: Record<string, number>;
  warnings: string[];
  is_excessive: boolean;
}

export interface ActionProposalValidation {
  is_valid: boolean;
  reasons: string[];
  blocked_reason?: string | null;
  passed_checks: string[];
}

export interface ActionProposalConfirmation {
  confirmation_token: string;
  confirmed_by: string;
  confirmed_at: string;
  expires_at: string;
  high_risk_acknowledged: boolean;
  is_expired: boolean;
}

export interface ActionProposalExecutionResult {
  success: boolean;
  action_id: string;
  status: string;
  actual_rows_affected: number;
  executed_at: string;
  error?: string | null;
  transaction_id: string;
}

export interface ActionProposalVerification {
  verified: boolean;
  verification_sql: string;
  expected_value?: any;
  actual_value?: any;
  details: string;
}

export interface ActionProposal {
  action_id: string;
  user_id: string;
  action_type: ActionProposalType;
  status: ActionProposalStatus;
  target: ActionProposalTarget;
  changes: ActionProposalChange[];
  reason: string;
  source_signal_id?: string | null;
  risk: ActionProposalRisk;
  sql_preview: string;
  parameterized_sql: string;
  parameters: Record<string, any>;
  verification_sql?: string | null;
  expected_verification_result?: string | null;
  validation?: ActionProposalValidation | null;
  impact?: ActionProposalImpact | null;
  confirmation?: ActionProposalConfirmation | null;
  execution_result?: ActionProposalExecutionResult | null;
  verification?: ActionProposalVerification | null;
  created_at: string;
  updated_at: string;
  database_identity: string;
}

export interface ProposeActionPayload {
  action_type: string;
  target_table: string;
  changes: {
    column: string;
    proposed_value: any;
    current_value?: any;
  }[];
  condition_sql?: string;
  condition_params?: Record<string, any>;
  reason?: string;
  source_signal_id?: string;
}

export interface ConfirmActionPayload {
  high_risk_acknowledged?: boolean;
}

export interface ExecuteActionPayload {
  confirmation_token?: string;
}

// ── Phase 8.9: Closed-Loop Outcome Optimization Types ─────────────────────────

export interface OutcomeMeasurement {
  measurement_id: string;
  user_id: string;
  action_id?: string;
  metric_name: string;
  source_table: string;
  source_column: string;
  measurement_sql: string;
  baseline_value: number | null;
  baseline_period?: string;
  observed_value: number | null;
  delta: number | null;
  delta_pct: number | null;
  window: string;
  effectiveness: string;
  confidence: string;
  attribution: string;
  confounders: string[];
  sample_size: number;
  baseline_sample_size: number;
  measured_at: string;
  action_executed_at?: string;
  epistemic_note: string;
}

export interface OutcomeAnalysis {
  analysis_id: string;
  action_id: string;
  user_id: string;
  action_type?: string;
  target_table?: string;
  measurements: OutcomeMeasurement[];
  overall_effectiveness: string;
  overall_confidence: string;
  attribution_summary: string;
  summary: string;
  data_gaps: string[];
  analyzed_at: string;
  disclaimer: string;
}

export interface AdaptiveRecommendation {
  recommendation_id: string;
  user_id: string;
  title: string;
  description: string;
  action_type: string;
  target_table: string;
  rationale: string;
  source: string;
  historical_success_rate: number | null;
  historical_sample_size: number;
  confidence: string;
  supporting_outcome_ids: string[];
  requires_human_confirmation: boolean;
  execution_path: string;
  caveat: string;
  generated_at: string;
}

export interface RecommendationExplanation {
  recommendation_id: string;
  user_id: string;
  explanation_points: string[];
  evidence_references: Record<string, unknown>[];
  limitations: string[];
  generated_at: string;
}

export interface MeasureOutcomeRequest {
  action_id: string;
  metric_name?: string;
  source_table?: string;
  source_column?: string;
  aggregation?: string;
  window?: string;
  force_remeasure?: boolean;
}

// ── Phase 9.0: Advanced Predictive & Simulation Intelligence Types ───────────

export interface ForecastPoint {
  period: string;
  value: number;
  is_forecast: boolean;
  lower_bound?: number | null;
  upper_bound?: number | null;
  uncertainty_width?: number | null;
}

export interface ModelEvaluationMetric {
  method: string;
  mae?: number | null;
  rmse?: number | null;
  mape?: number | null;
  mape_note?: string | null;
  selected: boolean;
  reason: string;
}

export interface PredictionEvidence {
  source_table: string;
  date_column: string;
  metric_column?: string | null;
  aggregation: string;
  historical_count: number;
  min_date: string;
  max_date: string;
  sql_lineage: string;
  historical_outcome_support: Array<{
    source?: string;
    id?: string;
    result?: string;
    status?: string;
    note?: string;
    delta_pct?: number;
  }>;
}

export interface PredictionResult {
  prediction_id: string;
  user_id: string;
  database_identity?: string;
  metric_name: string;
  source_table: string;
  date_column: string;
  metric_column?: string | null;
  frequency: string;
  forecast_horizon_days: number;
  horizon_periods: number;
  points: ForecastPoint[];
  selected_method: string;
  trend_direction: string;
  seasonality_detected: boolean;
  seasonality_summary: string;
  confidence_tier: string;
  confidence_rationale: string;
  data_quality_status: string;
  model_evaluations: ModelEvaluationMetric[];
  evidence?: PredictionEvidence | null;
  assumptions: string[];
  limitations: string[];
  ai_summary?: string | null;
  status: string;
  error_message?: string | null;
  created_at: string;
}

export interface ScenarioResult {
  scenario_id: string;
  prediction_id: string;
  scenario_name: string;
  scenario_type: string;
  change_percent?: number | null;
  absolute_change?: number | null;
  baseline_projected_total: number;
  scenario_projected_total: number;
  delta_total: number;
  delta_percent: number;
  scenario_points: ForecastPoint[];
  assumption_statement: string;
  causal_disclaimer: string;
  limitations: string[];
  created_at: string;
}

export interface ScenarioComparison {
  comparison_id: string;
  metric_name: string;
  forecast_horizon_days: number;
  baseline_total: number;
  scenarios: ScenarioResult[];
  summary_table: Array<{
    scenario_name: string;
    type: string;
    projected_total: number;
    delta_from_baseline: number;
    delta_percent: number;
    assumption: string;
  }>;
  guidance: string;
  created_at: string;
}

export interface PredictionExplanation {
  prediction_id: string;
  metric_name: string;
  historical_summary: string;
  method_rationale: string;
  backtest_evaluation: string;
  trend_and_seasonality: string;
  uncertainty_explanation: string;
  limitations: string[];
  phase89_historical_signals: string[];
  generated_at: string;
}

export interface PredictCandidate {
  table: string;
  date_column: string;
  metric_column?: string | null;
  metric_name: string;
  aggregation: string;
  frequency: string;
}

export interface PredictRequestPayload {
  table: string;
  date_column?: string;
  metric_column?: string;
  metric_name?: string;
  aggregation?: string;
  frequency?: string;
  horizon_days?: number;
  force_method?: string;
}

export interface ScenarioSimPayload {
  prediction_id: string;
  change_percent?: number;
  absolute_change?: number;
  scenario_name?: string;
  scenario_type?: string;
}

export interface ScenarioComparePayload {
  prediction_id: string;
  scenarios: Array<{
    scenario_name: string;
    change_percent?: number;
    absolute_change?: number;
    scenario_type?: string;
  }>;
}


// ── Phase 9.1: Enterprise Knowledge & Context Intelligence Models ─────────────

export type KnowledgeProvenance =
  | "SCHEMA_DERIVED"
  | "DATA_OBSERVED"
  | "USER_PROVIDED"
  | "SYSTEM_DEFINED"
  | "AI_INFERRED";

export type KnowledgeStatus =
  | "DRAFT"
  | "PROPOSED"
  | "CONFIRMED"
  | "ACTIVE"
  | "DISABLED"
  | "CONFLICTED";

export interface BusinessEntity {
  entity_id: string;
  name: string;
  plural_name: string;
  table_name: string;
  description: string;
  importance: "PRIMARY" | "SECONDARY" | "SUPPORTING" | string;
  primary_key?: string | null;
  foreign_keys: Array<{ column: string; target_table: string; target_column: string }>;
  provenance: KnowledgeProvenance;
  status: KnowledgeStatus;
  confidence: number;
  user_id: string;
  database_identity: string;
  created_at: string;
  updated_at: string;
}

export interface BusinessRule {
  rule_id: string;
  name: string;
  description: string;
  scope: "METRIC" | "ENTITY" | "TABLE" | "COLUMN" | "GLOBAL" | string;
  target_table: string;
  target_column?: string | null;
  rule_type: "EXCLUSION" | "INCLUSION" | "MAPPING" | "THRESHOLD" | "TEMPORAL" | string;
  expression: string;
  status: KnowledgeStatus;
  provenance: KnowledgeProvenance;
  version: number;
  affected_metrics: string[];
  user_id: string;
  database_identity: string;
  created_at: string;
  updated_at: string;
}

export interface BusinessMetric {
  metric_id: string;
  name: string;
  description: string;
  table_name: string;
  column_name?: string | null;
  aggregation: string;
  filter_expression?: string | null;
  conditions: string[];
  rules_applied: string[];
  version: number;
  provenance: KnowledgeProvenance;
  status: KnowledgeStatus;
  confidence: number;
  user_id: string;
  database_identity: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeConflict {
  conflict_id: string;
  knowledge_type: string;
  item_id_a: string;
  item_id_b: string;
  target_name: string;
  description: string;
  statement_a: string;
  statement_b: string;
  source_a: string;
  source_b: string;
  status: "UNRESOLVED" | "RESOLVED" | string;
  resolution_notes?: string | null;
  resolved_by?: string | null;
  user_id: string;
  database_identity: string;
  created_at: string;
  resolved_at?: string | null;
}

export interface KnowledgeVersionRecord {
  version_id: string;
  item_id: string;
  item_type: string;
  version: number;
  snapshot: Record<string, any>;
  change_summary: string;
  created_at: string;
}

export interface KnowledgeLineageNode {
  step: string;
  type: "ENTITY" | "METRIC" | "DEFINITION" | "RULE" | "TABLE" | "COLUMN" | "SQL" | string;
  label: string;
  details: Record<string, any>;
}

export interface KnowledgeLineage {
  target_id: string;
  target_name: string;
  nodes: KnowledgeLineageNode[];
  provenance: KnowledgeProvenance;
  status: KnowledgeStatus;
  sql_expression: string;
}

export interface KnowledgeExplanation {
  knowledge_id: string;
  title: string;
  provenance: KnowledgeProvenance;
  status: KnowledgeStatus;
  version: number;
  facts: string[];
  inferences: string[];
  assumptions: string[];
  rules_applied: string[];
  source_description: string;
}

export interface KnowledgeSummary {
  total_entities: number;
  total_metrics: number;
  total_rules: number;
  confirmed_rules_count: number;
  proposed_rules_count: number;
  conflicts_count: number;
  unconfirmed_count: number;
}

export interface ContextParseResult {
  raw_statement: string;
  parsed_successfully: boolean;
  proposed_rule?: BusinessRule | null;
  referenced_tables: string[];
  referenced_columns: string[];
  affected_metrics: string[];
  assumptions: string[];
  ambiguity_notes: string[];
  requires_user_confirmation: boolean;
}

export interface DefinitionCreatePayload {
  item_type: "METRIC" | "ENTITY" | "RULE" | string;
  name: string;
  description?: string;
  table_name: string;
  column_name?: string;
  aggregation?: string;
  filter_expression?: string;
  rule_type?: string;
  expression?: string;
  status?: string;
}

export interface ConflictResolvePayload {
  resolution_choice: "CHOOSE_A" | "CHOOSE_B" | "CUSTOM" | string;
  resolution_notes?: string;
}

// ── Phase 9.2: Advanced Agent Orchestration Interfaces ──────────────────────

export type AgentPermissionTier = "READ_ONLY" | "ANALYTICAL" | "PROPOSAL_ONLY" | "CONTROLLED_MUTATION";

export type OrchestrationRunStatus =
  | "PLANNING"
  | "VALIDATING"
  | "EXECUTING"
  | "WAITING_FOR_INPUT"
  | "WAITING_FOR_CONFIRMATION"
  | "COMPLETED"
  | "PARTIALLY_COMPLETED"
  | "FAILED"
  | "BLOCKED"
  | "CANCELLED";

export type TaskStepStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "BLOCKED" | "SKIPPED";

export type OrchestrationEvidenceType =
  | "DATABASE_FACT"
  | "METRIC_RESULT"
  | "BUSINESS_CONTEXT"
  | "TREND"
  | "ANOMALY"
  | "INVESTIGATION_FINDING"
  | "FORECAST"
  | "DECISION_FINDING"
  | "OUTCOME"
  | "USER_CONTEXT"
  | "ACTION_STATUS";

export type OrchestrationConfidenceTier = "HIGH" | "MODERATE" | "LIMITED";

export interface SpecialistAgentItem {
  agent_id: string;
  name: string;
  description: string;
  permission: AgentPermissionTier;
  capabilities: string[];
  supported_inputs: string[];
  supported_outputs: string[];
  is_read_only: boolean;
}

export interface PlanStepItem {
  step_id: string;
  agent_id: string;
  name: string;
  purpose: string;
  dependencies: string[];
  inputs: Record<string, any>;
  status: TaskStepStatus;
  output?: Record<string, any> | null;
  error?: string | null;
  duration_ms: number;
  retry_count: number;
}

export interface TaskGraphItem {
  graph_id: string;
  steps: PlanStepItem[];
  entry_steps: string[];
  exit_steps: string[];
  max_depth: number;
  total_steps: number;
}

export interface OrchestrationEvidenceLedgerItem {
  evidence_id: string;
  evidence_type: OrchestrationEvidenceType;
  title: string;
  summary: string;
  source_agent: string;
  step_id: string;
  data_facts: Record<string, any>;
  confidence: OrchestrationConfidenceTier;
  created_at: string;
  lineage: string[];
  table_references?: string[];
  metric_references?: string[];
}

export interface OrchestrationConflictItem {
  conflict_id: string;
  conflict_type: string;
  description: string;
  involved_agents: string[];
  involved_steps: string[];
  resolution_strategy: string;
  resolved: boolean;
  resolution_details: string;
}

export interface ProposedActionSummaryItem {
  action_type: string;
  title: string;
  description: string;
  preview: Record<string, any>;
  impact: Record<string, any>;
  confirmation_required: boolean;
  action_plan_id?: string | null;
  status: string;
}

export interface OrchestrationRunItem {
  orchestration_id: string;
  user_id: string;
  database_identity: string;
  goal: string;
  status: OrchestrationRunStatus;
  task_graph?: TaskGraphItem | null;
  evidence_ledger: OrchestrationEvidenceLedgerItem[];
  conflicts: OrchestrationConflictItem[];
  proposed_action?: ProposedActionSummaryItem | null;
  executive_summary: string;
  explanation: Record<string, any>;
  confidence_tier: OrchestrationConfidenceTier;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  duration_ms: number;
  metadata: Record<string, any>;
}

// ── Phase 9.3: Enterprise Governance & Observability Types ───────────────────

export type GovernanceEventType =
  | "QUERY_EXECUTED"
  | "MUTATION_PROPOSED"
  | "MUTATION_CONFIRMED"
  | "MUTATION_EXECUTED"
  | "MUTATION_REJECTED"
  | "ORCHESTRATION_STARTED"
  | "ORCHESTRATION_COMPLETED"
  | "ORCHESTRATION_FAILED"
  | "AGENT_INVOKED"
  | "AGENT_COMPLETED"
  | "AGENT_FAILED"
  | "AGENT_BLOCKED"
  | "POLICY_EVALUATION"
  | "POLICY_VIOLATION"
  | "SECURITY_EVENT"
  | "DATA_ACCESS"
  | "CHAIN_INTEGRITY_VERIFIED"
  | string;

export type GovernancePolicyScope = "SYSTEM_POLICY" | "USER_POLICY" | string;

export type GovernancePolicyDecision =
  | "ALLOW"
  | "DENY"
  | "REQUIRE_CONFIRMATION"
  | "REQUIRE_ELEVATED_REVIEW"
  | string;

export type GovernanceRiskLevel =
  | "LOW"
  | "MEDIUM"
  | "HIGH"
  | "CRITICAL"
  | "BLOCKED"
  | string;

export type SecurityEventSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;

export interface GovernanceAuditEventItem {
  event_id: string;
  timestamp: string;
  user_id: string;
  database_identity: string;
  event_type: GovernanceEventType;
  resource_type: string;
  resource_id: string;
  actor_type: string;
  action: string;
  result: string;
  risk_level: GovernanceRiskLevel;
  policy_result: string;
  agent_id?: string | null;
  orchestration_id?: string | null;
  request_id?: string | null;
  metadata?: Record<string, any>;
  previous_event_hash: string;
  event_hash: string;
}

export interface SecurityEventItem {
  event_id: string;
  timestamp: string;
  user_id: string;
  database_identity: string;
  event_type: string;
  severity: SecurityEventSeverity;
  source: string;
  resource: string;
  description: string;
  status: string;
  mitigation: string;
  metadata?: Record<string, any>;
}

export interface GovernancePolicyItem {
  policy_id: string;
  name: string;
  description: string;
  category: string;
  scope: GovernancePolicyScope;
  decision: GovernancePolicyDecision;
  enabled: boolean;
  rule_expression?: string | null;
  rationale: string;
  user_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RiskAssessmentItem {
  assessment_id: string;
  risk_level: GovernanceRiskLevel;
  operation: string;
  contributing_factors: string[];
  applicable_policies: string[];
  required_control: string;
  explanation: string;
  evaluated_at?: string;
}

export interface AgentObservabilityMetricItem {
  agent_id: string;
  name: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  blocked_executions: number;
  average_duration_ms: number;
  last_execution_at?: string | null;
  error_count: number;
}

export interface GovernanceSummaryItem {
  user_id: string;
  database_identity: string;
  time_window: string;
  total_audit_events: number;
  total_orchestrations: number;
  successful_orchestrations: number;
  failed_orchestrations: number;
  total_agent_executions: number;
  agent_failures: number;
  average_agent_duration_ms: number;
  policy_evaluations_count: number;
  policy_blocks_count: number;
  security_events_count: number;
  high_critical_security_count: number;
  actions_proposed_count: number;
  actions_confirmed_count: number;
  actions_executed_count: number;
  data_access_queries_count: number;
  hash_chain_verified: boolean;
  generated_at: string;
}

export interface ComplianceReportItem {
  report_id: string;
  user_id: string;
  database_identity: string;
  period_start: string;
  period_end: string;
  summary: GovernanceSummaryItem;
  factual_observations: string[];
  governance_interpretations: string[];
  risk_distribution: Record<string, number>;
  system_observations: string[];
  persistence_disclosure: string;
  generated_at: string;
}

// ── BG AI 2.0: Multi-Database Types ──────────────────────────────────────────

export type ConnectorCategory = "relational" | "document" | "vector" | "file" | "nosql";
export type ConnectorStatus = "connected" | "disconnected" | "error";

export interface ConnectorCatalogItem {
  id: string;
  name: string;
  connector_type?: string;
  display_name?: string;
  category: ConnectorCategory;
  description: string;
  default_port: number | null;
  badge: string;
  status: "ready" | "preview" | "planned";
  fields: string[];
}

export interface ConnectorCapabilities {
  can_read_data: boolean;
  can_insert_records: boolean;
  can_update_records: boolean;
  can_delete_records: boolean;
  can_create_entities: boolean;
  can_alter_schema: boolean;
  can_manage_indexes: boolean;
  can_execute_raw_queries: boolean;
  supports_transactions: boolean;
  read_only_reason?: string | null;
}

export interface DatabaseConnectionItem {
  connection_id: string;
  name: string;
  connector_type: string;
  category: ConnectorCategory;
  is_read_only: boolean;
  capabilities?: ConnectorCapabilities;
  status: ConnectorStatus;
  created_at: string;
  last_connected_at: string | null;
  last_error: string | null;
  is_active?: boolean;
  config: Record<string, any>;
  stats?: {
    tables?: number;
    rows?: number;
    columns?: number;
    collections?: number;
    documents?: number;
    total_points?: number;
    size?: string;
  };
  schema?: Record<string, any>;
}

export interface CrossDatabaseSubResultItem {
  source_id: string;
  source_name: string;
  connector_type: string;
  query_text: string;
  success: boolean;
  columns: string[];
  rows: Record<string, any>[];
  rows_returned: number;
  execution_time_ms: number;
  error?: string | null;
}

export interface CrossDatabaseResponseItem {
  intent: string;
  sources_used: DatabaseConnectionItem[];
  sub_results: CrossDatabaseSubResultItem[];
  combined_result: {
    columns: string[];
    rows: Record<string, any>[];
    rows_returned: number;
    join_key?: string;
    source?: string;
  } | null;
  explanation: string;
  combination_strategy?: string | null;
  chart?: any;
  requires_disambiguation?: boolean;
  disambiguation_options?: { source_id: string; name: string; type: string }[];
  error?: string | null;
}

// ── Database Cybersecurity & Security Posture Types ─────────────────────────

export interface SecurityPostureFinding {
  id: string;
  category: "SENSITIVE_DATA_EXPOSURE" | "CONNECTION_SECURITY" | "ACCESS_CONTROL" | "QUERY_SECURITY" | string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
  title: string;
  table?: string;
  column?: string;
  evidence_summary: string;
  remediation: string;
  sample_count?: number;
}

export interface SecurityPostureScanResult {
  status: string;
  connection_id: string;
  database_type: string;
  database_name: string;
  scanned_at: string;
  posture_score?: number | null;
  risk_level?: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN" | string;
  score_explanation?: string;
  tls_status: "VERIFIED" | "DISABLED" | "UNKNOWN";
  tls_details?: string;
  privilege_status: "LEAST_PRIVILEGE" | "ELEVATED" | "SUPERUSER" | "UNKNOWN";
  privilege_details?: string;
  tables_scanned: number;
  total_findings: number;
  findings: SecurityPostureFinding[];
  message?: string;
}

export interface SecurityFindingExplanation {
  finding_id: string;
  title: string;
  severity: string;
  category: string;
  location: string;
  why_it_matters: string;
  potential_impact: string;
  remediation_steps: string[];
  uncertainty_and_limitations: string;
}

export interface IPThreatBlockItem {
  ip_address: string;
  blocked_at: string;
  expires_at: string;
  remaining_seconds: number;
  reason: string;
  rule_triggered: string;
}

export interface IPReputationResult {
  ip_address: string;
  provider: string;
  status: string;
  classification: string;
  is_private_network?: boolean;
  is_loopback?: boolean;
  reason?: string;
  expires_at?: string;
  note: string;
}

export interface IPThreatListResponse {
  status: string;
  threat_events: SecurityEventItem[];
  active_blocks: IPThreatBlockItem[];
  total_returned: number;
  message?: string;
}



