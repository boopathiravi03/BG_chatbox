import React, { useState, useCallback, useEffect } from "react";
import {
  Search,
  Sparkles,
  GitFork,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowRight,
  Database,
  Layers,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Plug,
  HelpCircle,
  FileCode2,
  TrendingDown,
  TrendingUp,
  BarChart2,
  ShieldAlert,
} from "lucide-react";
import { investigateSignal } from "../../../services/api";
import type {
  InvestigationResult,
  InvestigationConfidenceLevel,
  MonitoringItem,
} from "../../../types";

interface Props {
  dbConnected: boolean;
  onConnectDatabase?: () => void;
  selectedSignal?: MonitoringItem | null;
  onClearSelectedSignal?: () => void;
}

function formatPercent(val?: number | null): string {
  if (val === undefined || val === null) return "";
  return `${val > 0 ? "+" : ""}${val.toFixed(1)}%`;
}

function confidenceBadge(level?: InvestigationConfidenceLevel | string) {
  const lvl = level || "MODERATE";
  const cls =
    lvl === "HIGH"
      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
      : lvl === "MODERATE"
      ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
      : "bg-blue-500/10 border-blue-500/20 text-blue-400";
  return (
    <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${cls}`}>
      {lvl} CONFIDENCE
    </span>
  );
}

function impactBadge(type: string) {
  const cls =
    type === "negative"
      ? "bg-red-500/10 border-red-500/30 text-red-400"
      : type === "positive"
      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
      : "bg-zinc-500/10 border-zinc-500/30 text-zinc-300";
  return (
    <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border uppercase ${cls}`}>
      {type}
    </span>
  );
}

export default function RootCauseInvestigationSection({
  dbConnected,
  onConnectDatabase,
  selectedSignal,
  onClearSelectedSignal,
}: Props) {
  const [investigating, setInvestigating] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedSql, setExpandedSql] = useState<Record<string, boolean>>({});
  const [showLineage, setShowLineage] = useState(false);
  const [customMetric, setCustomMetric] = useState("");

  const toggleSql = (id: string) => {
    setExpandedSql((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const runInvestigation = useCallback(
    async (signalId?: string, metricName?: string) => {
      if (!dbConnected || investigating) return;
      setInvestigating(true);
      setError(null);

      try {
        const payload: { signal_id?: string; metric?: string } = {};
        if (signalId) payload.signal_id = signalId;
        if (metricName) payload.metric = metricName;

        const res = await investigateSignal(payload);
        if (res.status === "disconnected") {
          setError("No database is currently connected.");
        } else if (res.status === "error") {
          setError(res.message || "Investigation failed.");
        } else if (res.investigation) {
          setResult(res.investigation);
        } else {
          setError("No investigation data returned.");
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Investigation failed.");
      } finally {
        setInvestigating(false);
      }
    },
    [dbConnected, investigating]
  );

  // Auto-investigate if a signal was passed from monitoring card
  useEffect(() => {
    if (selectedSignal && dbConnected) {
      runInvestigation(selectedSignal.item_id, selectedSignal.title);
    }
  }, [selectedSignal, dbConnected, runInvestigation]);

  return (
    <div className="space-y-4" id="investigation-section">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Search size={14} />
          </div>
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
            Root-Cause & Investigation Intelligence
          </h3>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
            Phase 8.7
          </span>
        </div>

        <div className="flex items-center gap-2">
          {selectedSignal && onClearSelectedSignal && (
            <button
              onClick={onClearSelectedSignal}
              className="text-[11px] text-zinc-400 hover:text-white px-2 py-1"
            >
              Clear Selected Signal
            </button>
          )}

          <button
            onClick={() => runInvestigation(selectedSignal?.item_id, customMetric || undefined)}
            disabled={!dbConnected || investigating}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              !dbConnected || investigating
                ? "bg-white/[0.04] text-zinc-500 cursor-not-allowed"
                : "bg-indigo-600/80 hover:bg-indigo-600 text-white shadow-lg shadow-indigo-500/10"
            }`}
          >
            {investigating ? (
              <>
                <RefreshCw size={12} className="animate-spin" />
                Investigating Evidence…
              </>
            ) : (
              <>
                <Search size={12} />
                {selectedSignal ? "Investigate Selected Signal" : "Investigate Root Cause"}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Disconnected state */}
      {!dbConnected && (
        <div className="p-5 rounded-2xl border border-dashed border-white/[0.08] text-center space-y-3">
          <Plug size={20} className="mx-auto text-zinc-600" />
          <p className="text-sm text-zinc-400">
            Connect a database to run evidence-backed root-cause investigations.
          </p>
          {onConnectDatabase && (
            <button
              onClick={onConnectDatabase}
              className="px-4 py-2 rounded-xl bg-indigo-600/80 hover:bg-indigo-600 text-xs font-semibold text-white transition-colors"
            >
              Connect Database
            </button>
          )}
        </div>
      )}

      {/* Error notice */}
      {error && (
        <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/20 flex items-start gap-2">
          <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {/* Idle / Target Selection Prompt */}
      {dbConnected && !result && !investigating && (
        <div className="p-5 rounded-2xl border border-dashed border-indigo-500/15 bg-indigo-500/5 text-center space-y-3">
          <GitFork size={20} className="mx-auto text-indigo-400" />
          <div className="max-w-md mx-auto space-y-1">
            <p className="text-sm text-zinc-300 font-semibold">
              {selectedSignal
                ? `Ready to investigate: "${selectedSignal.title}"`
                : "Select an intelligence signal to investigate, or run root-cause analysis on connected KPIs."}
            </p>
            <p className="text-xs text-zinc-500">
              Evaluates multi-table joins, dimensional shifts, and evidence-backed hypotheses. Never asserts causation without proof.
            </p>
          </div>

          <div className="flex items-center justify-center gap-2 max-w-sm mx-auto pt-1">
            <input
              type="text"
              placeholder="Target metric (e.g. revenue, quantity)..."
              value={customMetric}
              onChange={(e) => setCustomMetric(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-black/40 border border-white/[0.08] text-xs text-white placeholder-zinc-500 flex-1 outline-none focus:border-indigo-500/40"
            />
            <button
              onClick={() => runInvestigation(undefined, customMetric || undefined)}
              className="px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-white transition-colors"
            >
              Analyze
            </button>
          </div>
        </div>
      )}

      {/* Results View */}
      {result && (
        <div className="space-y-4">
          {/* Headline Briefing Banner */}
          <div className="p-5 rounded-2xl border border-white/[0.08] bg-[#0d1117] space-y-4">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono uppercase tracking-wider text-indigo-400 font-semibold">
                    Signal Investigation
                  </span>
                  {confidenceBadge(result.confidence?.level)}
                  <span className="text-[10px] font-mono text-zinc-500">
                    ID: {result.investigation_id}
                  </span>
                </div>
                <h4 className="text-base font-bold text-white tracking-tight">
                  {result.signal_title}
                </h4>
              </div>

              {result.observed_change && (
                <div className="flex items-center gap-4 bg-black/40 px-4 py-2 rounded-xl border border-white/[0.05]">
                  <div>
                    <span className="text-[10px] text-zinc-500 uppercase block">Previous</span>
                    <span className="text-xs font-mono font-semibold text-zinc-300">
                      {String(result.observed_change.previous_value ?? "N/A")}
                    </span>
                  </div>
                  <ArrowRight size={12} className="text-zinc-600" />
                  <div>
                    <span className="text-[10px] text-zinc-500 uppercase block">Current</span>
                    <span className="text-xs font-mono font-semibold text-white">
                      {String(result.observed_change.current_value ?? "N/A")}
                    </span>
                  </div>
                  {result.observed_change.delta_percent !== undefined && result.observed_change.delta_percent !== null && (
                    <div className="pl-2 border-l border-white/[0.08]">
                      <span className="text-[10px] text-zinc-500 uppercase block">Change</span>
                      <span
                        className={`text-xs font-mono font-bold flex items-center gap-0.5 ${
                          result.observed_change.delta_percent < 0
                            ? "text-red-400"
                            : result.observed_change.delta_percent > 0
                            ? "text-emerald-400"
                            : "text-zinc-400"
                        }`}
                      >
                        {result.observed_change.delta_percent < 0 ? (
                          <TrendingDown size={11} />
                        ) : (
                          <TrendingUp size={11} />
                        )}
                        {formatPercent(result.observed_change.delta_percent)}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Executive Summary */}
            <p className="text-xs text-zinc-300 leading-relaxed border-t border-white/[0.05] pt-3">
              {result.summary}
            </p>
          </div>

          {/* Insufficient Evidence Notice */}
          {result.status === "insufficient_evidence" && (
            <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2">
              <div className="flex items-center gap-2 text-amber-400">
                <HelpCircle size={14} />
                <span className="text-xs font-bold uppercase tracking-wider">
                  Insufficient Evidence Detected
                </span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed">
                The connected database does not contain sufficient multi-period chronological records or categorical dimensions to isolate a definitive root cause.
              </p>
              {Array.isArray(result.missing_evidence?.reasons) && (
                <ul className="text-[11px] text-zinc-400 list-disc list-inside space-y-0.5 pt-1">
                  {(result.missing_evidence!.reasons as string[]).map((r, i) => (
                    <li key={i}>{String(r)}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* ── Evidence & Contributing Factors Grid ─────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left: Verifiable Evidence Items */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Database size={11} className="text-indigo-400" />
                  Observed Evidence ({result.evidence.length})
                </p>
              </div>

              {result.evidence.length === 0 ? (
                <div className="p-4 rounded-xl border border-white/[0.06] text-center text-xs text-zinc-500">
                  No quantitative evidence items available.
                </div>
              ) : (
                <div className="space-y-2">
                  {result.evidence.map((ev) => (
                    <div
                      key={ev.evidence_id}
                      className="p-3.5 rounded-xl border border-white/[0.06] bg-[#0f1014] space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-white">{ev.metric}</span>
                        {ev.delta_percent !== undefined && ev.delta_percent !== null && (
                          <span
                            className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                              ev.delta_percent < 0
                                ? "bg-red-500/10 text-red-400"
                                : "bg-emerald-500/10 text-emerald-400"
                            }`}
                          >
                            {formatPercent(ev.delta_percent)}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 text-[11px] font-mono text-zinc-400">
                        <span>Curr: <strong className="text-zinc-200">{String(ev.current_value)}</strong></span>
                        {ev.previous_value !== undefined && ev.previous_value !== null && (
                          <span>Prev: <strong className="text-zinc-400">{String(ev.previous_value)}</strong></span>
                        )}
                        <span className="text-zinc-600">Source: {ev.source_table}</span>
                      </div>

                      <p className="text-[11px] text-zinc-400 italic">
                        {ev.calculation_description}
                      </p>

                      {/* SQL Lineage Accordion */}
                      {ev.sql_lineage && (
                        <div className="pt-1">
                          <button
                            onClick={() => toggleSql(ev.evidence_id)}
                            className="text-[10px] font-mono text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                          >
                            <FileCode2 size={10} />
                            {expandedSql[ev.evidence_id] ? "Hide SQL Query" : "Inspect SQL Query"}
                          </button>
                          {expandedSql[ev.evidence_id] && (
                            <pre className="mt-1.5 p-2 rounded-lg bg-black/60 border border-white/[0.04] text-[10px] font-mono text-zinc-400 overflow-x-auto whitespace-pre-wrap">
                              {ev.sql_lineage}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Right: Contributing Factors */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Layers size={11} className="text-indigo-400" />
                  Contributing Factors ({result.contributing_factors.length})
                </p>
              </div>

              {result.contributing_factors.length === 0 ? (
                <div className="p-4 rounded-xl border border-white/[0.06] text-center text-xs text-zinc-500">
                  No dimensional shifts or contributors detected.
                </div>
              ) : (
                <div className="space-y-2">
                  {result.contributing_factors.map((cf, idx) => (
                    <div
                      key={cf.factor_id}
                      className="p-3.5 rounded-xl border border-white/[0.06] bg-[#0f1014] flex items-start gap-3"
                    >
                      <span className="w-5 h-5 rounded-md bg-white/[0.05] border border-white/[0.08] text-[10px] font-mono font-bold text-zinc-400 flex items-center justify-center shrink-0">
                        {idx + 1}
                      </span>
                      <div className="flex-1 space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-semibold text-white">
                            {cf.dimension}
                          </span>
                          {impactBadge(cf.impact_type)}
                          {cf.contribution_percent !== undefined && cf.contribution_percent !== null && (
                            <span className="text-[10px] font-mono font-bold text-zinc-300">
                              {formatPercent(cf.contribution_percent)}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed">
                          {cf.observed_change}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── Hypotheses (Unconfirmed) ────────────────────────────────────── */}
          {result.hypotheses.length > 0 && (
            <div className="p-4 rounded-2xl border border-white/[0.08] bg-[#0f1014] space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-amber-400" />
                <h5 className="text-xs font-bold text-white uppercase tracking-wider">
                  Evidence-Backed Hypotheses
                </h5>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300 font-semibold">
                  STATUS: UNCONFIRMED
                </span>
              </div>

              <div className="space-y-2">
                {result.hypotheses.map((h) => (
                  <div
                    key={h.hypothesis_id}
                    className="p-3.5 rounded-xl bg-black/40 border border-white/[0.04] space-y-2"
                  >
                    <p className="text-xs text-zinc-200 font-medium leading-relaxed">
                      "{h.statement}"
                    </p>
                    <div className="flex items-center justify-between text-[10px] text-zinc-500 border-t border-white/[0.04] pt-2">
                      <span className="text-amber-400/90 font-medium">
                        ⚠ {h.causality_caveat}
                      </span>
                      {h.supporting_evidence_ids.length > 0 && (
                        <span>
                          Supported by {h.supporting_evidence_ids.length} verified signal(s)
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Recommended Next Investigations ─────────────────────────────── */}
          {result.recommended_investigations.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                Recommended Next Investigations
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {result.recommended_investigations.map((rec) => (
                  <div
                    key={rec.recommendation_id}
                    className="p-3.5 rounded-xl border border-white/[0.06] bg-[#0f1014] space-y-2 flex flex-col justify-between"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] font-mono uppercase font-bold text-indigo-400">
                          {rec.priority} priority
                        </span>
                      </div>
                      <h6 className="text-xs font-bold text-white leading-snug">
                        {rec.action_title}
                      </h6>
                      <p className="text-[11px] text-zinc-400 leading-relaxed">
                        {rec.reason}
                      </p>
                    </div>

                    <div className="pt-2 border-t border-white/[0.04] space-y-1">
                      <p className="text-[10px] font-mono text-zinc-500 truncate">
                        Target: <span className="text-zinc-300">{rec.target_data}</span>
                      </p>
                      <p className="text-[10px] text-zinc-500">
                        {rec.expected_information_gained}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Lineage & Confidence Footer ─────────────────────────────────── */}
          <div className="flex items-center justify-between border-t border-white/[0.05] pt-3 text-xs text-zinc-500">
            <div className="flex items-center gap-2">
              <Clock size={11} />
              <span className="text-[11px]">
                Investigated: {new Date(result.created_at).toLocaleString()}
              </span>
            </div>

            {result.lineage && (
              <button
                onClick={() => setShowLineage((v) => !v)}
                className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
              >
                <GitFork size={12} />
                {showLineage ? "Hide Evidence Lineage" : "View Evidence Lineage"}
              </button>
            )}
          </div>

          {/* Lineage Drawer */}
          {showLineage && result.lineage && (
            <div className="p-4 rounded-xl border border-white/[0.06] bg-black/50 space-y-3 font-mono text-[11px]">
              <div>
                <span className="text-zinc-500 block uppercase text-[10px]">Source Tables</span>
                <span className="text-zinc-300">{result.lineage.source_tables.join(", ") || "None"}</span>
              </div>
              {result.lineage.join_path && (
                <div>
                  <span className="text-zinc-500 block uppercase text-[10px]">Join Path</span>
                  <span className="text-indigo-300">{result.lineage.join_path}</span>
                </div>
              )}
              {result.lineage.columns_analyzed.length > 0 && (
                <div>
                  <span className="text-zinc-500 block uppercase text-[10px]">Columns Analyzed</span>
                  <span className="text-zinc-400">{result.lineage.columns_analyzed.join(", ")}</span>
                </div>
              )}
              {result.lineage.calculations.length > 0 && (
                <div>
                  <span className="text-zinc-500 block uppercase text-[10px]">Calculations</span>
                  <ul className="text-zinc-400 space-y-0.5 list-disc list-inside">
                    {result.lineage.calculations.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
