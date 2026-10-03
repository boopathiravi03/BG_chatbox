import React, { useState, useEffect, useCallback } from "react";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Database,
  Lightbulb,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Target,
} from "lucide-react";
import { getAuthToken } from "../../../services/api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────────────

interface OutcomeMeasurement {
  measurement_id: string;
  metric_name: string;
  source_table: string;
  source_column: string;
  baseline_value: number | null;
  baseline_period?: string;
  observed_value: number | null;
  delta: number | null;
  delta_pct: number | null;
  effectiveness: string;
  confidence: string;
  attribution: string;
  confounders: string[];
  window: string;
  epistemic_note: string;
  measured_at: string;
}

interface OutcomeAnalysis {
  analysis_id: string;
  action_id: string;
  measurements: OutcomeMeasurement[];
  overall_effectiveness: string;
  overall_confidence: string;
  attribution_summary: string;
  summary: string;
  data_gaps: string[];
  analyzed_at: string;
  disclaimer: string;
}

interface AdaptiveRecommendation {
  recommendation_id: string;
  title: string;
  description: string;
  action_type: string;
  target_table: string;
  rationale: string;
  source: string;
  historical_success_rate: number | null;
  historical_sample_size: number;
  confidence: string;
  requires_human_confirmation: boolean;
  caveat: string;
  generated_at: string;
}

interface Props {
  dbConnected: boolean;
  onConnectDatabase?: () => void;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function effectivenessColor(label: string): string {
  switch (label) {
    case "POSITIVE":
      return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
    case "NEGATIVE":
      return "text-rose-400 bg-rose-500/10 border-rose-500/30";
    case "NEUTRAL":
      return "text-zinc-400 bg-zinc-500/10 border-zinc-500/30";
    case "INCONCLUSIVE":
      return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    default:
      return "text-zinc-500 bg-zinc-900 border-zinc-700";
  }
}

function effectivenessIcon(label: string) {
  switch (label) {
    case "POSITIVE":
      return <TrendingUp size={12} className="text-emerald-400" />;
    case "NEGATIVE":
      return <TrendingDown size={12} className="text-rose-400" />;
    case "NEUTRAL":
      return <Minus size={12} className="text-zinc-400" />;
    case "INCONCLUSIVE":
      return <AlertTriangle size={12} className="text-amber-400" />;
    default:
      return <Minus size={12} className="text-zinc-500" />;
  }
}

function confidenceBadge(conf: string): string {
  switch (conf) {
    case "HIGH":
      return "text-emerald-300 bg-emerald-500/10 border-emerald-500/30";
    case "MODERATE":
      return "text-amber-300 bg-amber-500/10 border-amber-500/30";
    default:
      return "text-zinc-400 bg-zinc-800 border-zinc-700";
  }
}

// ── API functions ─────────────────────────────────────────────────────────────

async function apiGet(path: string) {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

async function apiPost(path: string, body: unknown) {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ── Measurement Row Component ─────────────────────────────────────────────────

function MeasurementRow({ m }: { m: OutcomeMeasurement }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#0e0e12] overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.03] transition-colors text-left"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex items-center gap-3 min-w-0">
          {effectivenessIcon(m.effectiveness)}
          <span className="text-xs font-medium text-white truncate">{m.metric_name}</span>
          <span className="text-[10px] text-zinc-500 truncate hidden sm:block">
            {m.source_table}
          </span>
        </div>
        <div className="flex items-center gap-2 ml-3 shrink-0">
          {m.delta_pct !== null && m.delta_pct !== undefined && (
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                m.delta_pct > 0
                  ? "text-emerald-400 border-emerald-500/30"
                  : m.delta_pct < 0
                  ? "text-rose-400 border-rose-500/30"
                  : "text-zinc-400 border-zinc-700"
              }`}
            >
              {m.delta_pct > 0 ? "+" : ""}
              {m.delta_pct.toFixed(2)}%
            </span>
          )}
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${effectivenessColor(m.effectiveness)}`}
          >
            {m.effectiveness.replace("_", " ")}
          </span>
          {expanded ? (
            <ChevronDown size={12} className="text-zinc-500" />
          ) : (
            <ChevronRight size={12} className="text-zinc-500" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/[0.05] pt-3">
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            <div>
              <p className="text-zinc-500 uppercase tracking-wider font-semibold mb-1">Baseline</p>
              <p className="text-zinc-300 font-mono">
                {m.baseline_value !== null ? m.baseline_value?.toFixed(4) : "N/A"}
              </p>
              <p className="text-zinc-600">{m.baseline_period ?? ""}</p>
            </div>
            <div>
              <p className="text-zinc-500 uppercase tracking-wider font-semibold mb-1">Observed</p>
              <p className="text-zinc-300 font-mono">
                {m.observed_value !== null ? m.observed_value?.toFixed(4) : "N/A"}
              </p>
              <p className="text-zinc-600">Window: {m.window}</p>
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${confidenceBadge(m.confidence)}`}>
              Confidence: {m.confidence}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full border border-zinc-700 text-zinc-400">
              Attribution: {m.attribution.replace("_", " ")}
            </span>
          </div>

          {m.confounders && m.confounders.length > 0 && (
            <div className="rounded-lg bg-amber-500/5 border border-amber-500/20 p-3">
              <p className="text-[10px] font-semibold text-amber-400 mb-1">
                ⚠ Potential Confounders Detected
              </p>
              {m.confounders.map((c, i) => (
                <p key={i} className="text-[10px] text-amber-300/80 mt-0.5">
                  • {c}
                </p>
              ))}
            </div>
          )}

          <div className="rounded-lg bg-black/40 border border-white/[0.05] p-3">
            <p className="text-[10px] text-zinc-500 italic">{m.epistemic_note}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Recommendation Card ───────────────────────────────────────────────────────

function RecommendationCard({ rec }: { rec: AdaptiveRecommendation }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#0d0d10] p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Lightbulb size={14} className="text-violet-400 shrink-0" />
          <span className="text-xs font-semibold text-white">{rec.title}</span>
        </div>
        <span
          className={`text-[10px] shrink-0 font-semibold px-2 py-0.5 rounded-full border ${confidenceBadge(rec.confidence)}`}
        >
          {rec.confidence}
        </span>
      </div>

      <p className="text-[11px] text-zinc-400">{rec.description}</p>

      {rec.historical_success_rate !== null && rec.historical_success_rate !== undefined && (
        <div className="flex items-center gap-3">
          <div className="h-1.5 flex-1 rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-500/60 transition-all"
              style={{ width: `${Math.round(rec.historical_success_rate * 100)}%` }}
            />
          </div>
          <span className="text-[10px] text-emerald-400 font-mono whitespace-nowrap">
            {Math.round(rec.historical_success_rate * 100)}% historical success
            ({rec.historical_sample_size} samples)
          </span>
        </div>
      )}

      <button
        className="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1"
        onClick={() => setExpanded((e) => !e)}
      >
        {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        {expanded ? "Hide" : "Show"} rationale & caveat
      </button>

      {expanded && (
        <div className="space-y-2">
          <div className="rounded-lg bg-black/40 border border-white/[0.05] p-3">
            <p className="text-[10px] font-semibold text-zinc-400 mb-1">Rationale</p>
            <p className="text-[10px] text-zinc-300">{rec.rationale}</p>
          </div>
          <div className="rounded-lg bg-amber-500/5 border border-amber-500/20 p-3">
            <p className="text-[10px] text-amber-300/80 italic">{rec.caveat}</p>
          </div>
          <p className="text-[10px] text-zinc-600">
            Source: {rec.source.replace(/_/g, " ")} · Generated:{" "}
            {new Date(rec.generated_at).toLocaleString()}
          </p>
        </div>
      )}

      <div className="pt-1 border-t border-white/[0.05]">
        <p className="text-[10px] text-zinc-600">
          ℹ︎ To act on this: use the Action Proposal section (Phase 8.8). Human confirmation required.
        </p>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function OutcomeOptimizationSection({ dbConnected, onConnectDatabase }: Props) {
  const [activeTab, setActiveTab] = useState<"measure" | "recommendations">("recommendations");

  // Measure tab state
  const [actionIdInput, setActionIdInput] = useState("");
  const [windowInput, setWindowInput] = useState("7d");
  const [measuring, setMeasuring] = useState(false);
  const [analysis, setAnalysis] = useState<OutcomeAnalysis | null>(null);
  const [measureError, setMeasureError] = useState<string | null>(null);

  // Recommendations tab state
  const [recs, setRecs] = useState<AdaptiveRecommendation[]>([]);
  const [recsLoading, setRecsLoading] = useState(false);
  const [recsError, setRecsError] = useState<string | null>(null);

  const loadRecommendations = useCallback(async () => {
    if (!getAuthToken()) return;
    setRecsLoading(true);
    setRecsError(null);
    try {
      const data = await apiGet("/intelligence/recommendations/adaptive");
      if (data.status === "success" && Array.isArray(data.recommendations)) {
        setRecs(data.recommendations);
      } else if (data.status === "error") {
        setRecsError(data.message || "Failed to load recommendations.");
      } else {
        setRecs([]);
      }
    } catch (err: any) {
      setRecsError(err.message || "Network error.");
    } finally {
      setRecsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "recommendations") {
      loadRecommendations();
    }
  }, [activeTab, loadRecommendations]);

  const handleMeasure = async () => {
    if (!actionIdInput.trim()) {
      setMeasureError("Please enter an Action ID.");
      return;
    }
    setMeasuring(true);
    setMeasureError(null);
    setAnalysis(null);
    try {
      const data = await apiPost("/intelligence/outcomes/measure", {
        action_id: actionIdInput.trim(),
        window: windowInput,
        force_remeasure: false,
      });
      if (data.status === "error") {
        setMeasureError(data.message || "Measurement failed.");
      } else {
        setAnalysis(data.analysis);
      }
    } catch (err: any) {
      setMeasureError(err.message || "Network error.");
    } finally {
      setMeasuring(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-violet-500/15 border border-violet-500/30 flex items-center justify-center text-violet-400">
            <BarChart3 size={14} />
          </div>
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
            Outcome Optimization
          </h3>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-300">
            Phase 8.9 · Closed-Loop Learning
          </span>
        </div>
      </div>

      {!dbConnected ? (
        <div className="rounded-2xl border border-white/[0.08] bg-[#0d0d10] p-6 text-center space-y-3">
          <Database size={24} className="text-zinc-600 mx-auto" />
          <p className="text-sm font-semibold text-zinc-300">No Database Connected</p>
          <p className="text-xs text-zinc-500">
            Connect a database to measure action outcomes and generate adaptive recommendations.
          </p>
          {onConnectDatabase && (
            <button
              onClick={onConnectDatabase}
              className="px-4 py-2 rounded-xl bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-semibold hover:bg-violet-500/20 transition-colors"
            >
              Connect Database
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-white/[0.08] bg-[#0d0d10] overflow-hidden">
          {/* Tabs */}
          <div className="flex border-b border-white/[0.06]">
            {[
              { key: "recommendations", label: "Adaptive Recommendations", icon: <Lightbulb size={12} /> },
              { key: "measure", label: "Measure Outcome", icon: <Target size={12} /> },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={`flex items-center gap-1.5 px-4 py-3 text-xs font-semibold transition-colors border-b-2 ${
                  activeTab === tab.key
                    ? "border-violet-500 text-white"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          <div className="p-5">
            {/* Recommendations Tab */}
            {activeTab === "recommendations" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] text-zinc-500">
                    Evidence-based recommendations from your historical outcomes.
                    Never auto-executes.
                  </p>
                  <button
                    onClick={loadRecommendations}
                    disabled={recsLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-xs text-zinc-300 transition-colors"
                  >
                    <RefreshCw size={11} className={recsLoading ? "animate-spin" : ""} />
                    Refresh
                  </button>
                </div>

                {recsError && (
                  <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-400">
                    {recsError}
                  </div>
                )}

                {recsLoading ? (
                  <div className="flex items-center justify-center py-10 gap-2 text-zinc-500 text-sm">
                    <RefreshCw size={14} className="animate-spin" />
                    Analyzing historical patterns…
                  </div>
                ) : recs.length === 0 ? (
                  <div className="text-center py-8 text-zinc-500 text-xs">
                    No recommendations yet. Record outcomes to unlock personalized suggestions.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {recs.map((rec) => (
                      <RecommendationCard key={rec.recommendation_id} rec={rec} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Measure Tab */}
            {activeTab === "measure" && (
              <div className="space-y-4">
                <p className="text-[11px] text-zinc-500">
                  Measure metric changes associated with a Phase 8.8 action.
                  Observed changes are reported — causation is never claimed.
                </p>

                {/* Input Form */}
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                      Action ID
                    </label>
                    <input
                      type="text"
                      value={actionIdInput}
                      onChange={(e) => setActionIdInput(e.target.value)}
                      placeholder="e.g. act_abc123..."
                      className="w-full rounded-xl bg-black/40 border border-white/[0.08] text-xs text-white px-3 py-2.5 placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/50 transition-colors font-mono"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                      Measurement Window
                    </label>
                    <select
                      value={windowInput}
                      onChange={(e) => setWindowInput(e.target.value)}
                      className="w-full rounded-xl bg-black/40 border border-white/[0.08] text-xs text-white px-3 py-2.5 focus:outline-none focus:border-violet-500/50 transition-colors"
                    >
                      <option value="24h">24 Hours</option>
                      <option value="7d">7 Days</option>
                      <option value="14d">14 Days</option>
                      <option value="30d">30 Days</option>
                    </select>
                  </div>

                  <button
                    onClick={handleMeasure}
                    disabled={measuring || !actionIdInput.trim()}
                    className="w-full py-2.5 rounded-xl bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-semibold hover:bg-violet-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {measuring ? (
                      <>
                        <RefreshCw size={12} className="animate-spin" />
                        Measuring…
                      </>
                    ) : (
                      <>
                        <BarChart3 size={12} />
                        Measure Outcome
                      </>
                    )}
                  </button>
                </div>

                {measureError && (
                  <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-400">
                    {measureError}
                  </div>
                )}

                {/* Analysis Results */}
                {analysis && (
                  <div className="space-y-4">
                    {/* Overall Summary */}
                    <div className="rounded-xl border border-white/[0.08] bg-black/30 p-4 space-y-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${effectivenessColor(
                            analysis.overall_effectiveness
                          )}`}
                        >
                          {effectivenessIcon(analysis.overall_effectiveness)}
                          <span className="ml-1">{analysis.overall_effectiveness.replace("_", " ")}</span>
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${confidenceBadge(analysis.overall_confidence)}`}>
                          {analysis.overall_confidence} confidence
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-300">{analysis.summary}</p>
                      <p className="text-[10px] text-zinc-600 italic">{analysis.disclaimer}</p>
                    </div>

                    {/* Measurements */}
                    {analysis.measurements && analysis.measurements.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                          Metric Measurements ({analysis.measurements.length})
                        </p>
                        {analysis.measurements.map((m) => (
                          <MeasurementRow key={m.measurement_id} m={m} />
                        ))}
                      </div>
                    )}

                    {/* Data Gaps */}
                    {analysis.data_gaps && analysis.data_gaps.length > 0 && (
                      <div className="rounded-xl border border-zinc-700 bg-zinc-900/30 p-3 space-y-1">
                        <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                          Data Gaps
                        </p>
                        {analysis.data_gaps.map((g, i) => (
                          <p key={i} className="text-[10px] text-zinc-500">
                            • {g}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
