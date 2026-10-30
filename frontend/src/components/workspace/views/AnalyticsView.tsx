import React, { useState, useEffect, Suspense, lazy } from "react";
import {
  Sparkles,
  BarChart3,
  Database,
  Plug,
  RefreshCw,
  Search,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  History,
  CheckCircle2,
  HelpCircle,
  Clock,
  Layers,
  ChevronRight,
  Trash2,
  Eye,
  Info,
  ShieldAlert,
} from "lucide-react";
import {
  startBusinessInvestigation,
  listInvestigationReports,
  getInvestigationReport,
  deleteInvestigationReport,
} from "../../../services/api";
import type {
  BusinessInvestigationResult,
  BusinessInvestigationReportItem,
  DatabaseConnectionItem,
} from "../../../types";
import { useToast } from "../../../context/ToastContext";

const AnalyticsDashboard = lazy(
  () => import("../../dashboard/AnalyticsDashboard"),
);

interface AnalyticsViewProps {
  dbConnected: boolean;
  activeConnectionId?: string | null;
  connections?: DatabaseConnectionItem[];
  onRunAnalysis: () => void;
  onConnectDatabase: () => void;
  onTabChange?: (tab: any) => void;
  onOpenExplorerWithTable?: (tableName: string) => void;
}

export default function AnalyticsView({
  dbConnected,
  activeConnectionId,
  connections = [],
  onRunAnalysis,
  onConnectDatabase,
  onTabChange,
  onOpenExplorerWithTable,
}: AnalyticsViewProps) {
  // Main view tab: "investigator" (AI Business Investigator) or "dashboard" (Visual Distributions)
  const [activeTab, setActiveTab] = useState<"investigator" | "dashboard">("investigator");

  // Investigation input state
  const [question, setQuestion] = useState("");
  const [investigating, setInvestigating] = useState(false);
  const [currentReport, setCurrentReport] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Past reports history state
  const [historyReports, setHistoryReports] = useState<BusinessInvestigationReportItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const toast = useToast();

  const loadHistory = async () => {
    if (!dbConnected) return;
    setLoadingHistory(true);
    try {
      const res = await listInvestigationReports(activeConnectionId || undefined, 20);
      if (res.status === "success" && res.reports) {
        setHistoryReports(res.reports);
      }
    } catch {
      // Non-blocking history load
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [dbConnected, activeConnectionId]);

  const handleStartInvestigation = async (queryText?: string) => {
    const q = queryText || question;
    if (!q.trim()) {
      toast.info("Please enter a business investigation question.");
      return;
    }

    setInvestigating(true);
    setError(null);
    try {
      const res = await startBusinessInvestigation({
        question: q.trim(),
        connection_id: activeConnectionId || undefined,
      });

      if (res.status === "disconnected") {
        toast.error("Database is disconnected. Connect a database to run investigations.");
      } else if (res.report) {
        setCurrentReport(res.report);
        toast.success(`Investigation completed: ${res.report.title || "Report generated"}`);
        loadHistory();
      } else {
        setError(res.summary || "Investigation returned no results.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to execute investigation.");
      toast.error(err.message || "Investigation failed.");
    } finally {
      setInvestigating(false);
    }
  };

  const handleSelectPastReport = async (reportId: string) => {
    try {
      const res = await getInvestigationReport(reportId);
      if (res.status === "success" && res.report && res.report.report) {
        setCurrentReport(res.report.report);
        setQuestion(res.report.question || "");
        setShowHistory(false);
        toast.info("Loaded previous investigation report.");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load past report.");
    }
  };

  const handleDeleteReport = async (e: React.MouseEvent, reportId: string) => {
    e.stopPropagation();
    try {
      const res = await deleteInvestigationReport(reportId);
      if (res.status === "success") {
        setHistoryReports((prev) => prev.filter((r) => r.report_id !== reportId));
        if (currentReport?.investigation_id === reportId) {
          setCurrentReport(null);
        }
        toast.info("Investigation report deleted.");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to delete report.");
    }
  };

  if (!dbConnected) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mx-auto">
          <BarChart3 size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your database to run evidence-based AI business investigations, discover contributing factors, and inspect live visual distributions.
        </p>
        <button
          onClick={onConnectDatabase}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all cursor-pointer"
        >
          <Plug size={14} />
          <span>Connect Database</span>
        </button>
      </div>
    );
  }

  const promptSuggestions = [
    "Why did revenue decrease this month?",
    "Which products contributed most to the decline?",
    "Which regions or customer groups changed the most?",
    "Are order volumes changing alongside revenue?",
    "Which customers have become inactive?",
    "Is this change unusual compared with historical patterns?",
  ];

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Top Header & Tab Switcher */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/[0.08] pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-white tracking-tight">AI Business Analytics</h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 font-semibold uppercase">
              Sprint 3 Investigator
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Root-cause investigation engine, reproducible data evidence, and visual distributions.
          </p>
        </div>

        <div className="flex items-center gap-1.5 bg-[#121216] p-1 rounded-xl border border-white/[0.08]">
          <button
            onClick={() => setActiveTab("investigator")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "investigator"
                ? "bg-indigo-600 text-white shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Sparkles size={13} className="text-indigo-300" />
            <span>AI Investigator</span>
          </button>
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === "dashboard"
                ? "bg-indigo-600 text-white shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <BarChart3 size={13} />
            <span>Visual Distributions</span>
          </button>
        </div>
      </div>

      {/* Tab 1: AI Business Investigator */}
      {activeTab === "investigator" && (
        <div className="space-y-6">
          {/* Natural Language Question Bar */}
          <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Search size={14} className="text-indigo-400" />
                <span>Ask a Business Investigation Question</span>
              </span>
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="text-xs text-zinc-400 hover:text-white flex items-center gap-1 transition-all cursor-pointer"
              >
                <History size={13} />
                <span>Past Reports ({historyReports.length})</span>
              </button>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-2">
              <div className="relative flex-1 w-full">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !investigating) {
                      handleStartInvestigation();
                    }
                  }}
                  placeholder="e.g. Why did revenue decrease this month? Which products contributed most?"
                  className="w-full px-4 py-2.5 rounded-xl bg-[#09090b] border border-white/[0.1] text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500 transition-all font-medium"
                />
              </div>
              <button
                onClick={() => handleStartInvestigation()}
                disabled={investigating}
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all cursor-pointer shrink-0"
              >
                <Sparkles size={14} className={investigating ? "animate-spin" : ""} />
                <span>{investigating ? "Investigating..." : "Investigate"}</span>
              </button>
            </div>

            {/* Quick Prompt Suggestions */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[11px] text-zinc-500 mr-1">Try:</span>
              {promptSuggestions.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setQuestion(prompt);
                    handleStartInvestigation(prompt);
                  }}
                  className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-[11px] text-zinc-300 hover:text-white transition-all cursor-pointer border border-white/[0.04]"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {/* Past Reports Drawer (if open) */}
          {showHistory && (
            <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.08] space-y-3">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                  <History size={13} className="text-indigo-400" />
                  <span>Prior Investigation Reports</span>
                </h3>
                <span className="text-[11px] text-zinc-500">{historyReports.length} saved reports</span>
              </div>
              {historyReports.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-60 overflow-y-auto">
                  {historyReports.map((r) => (
                    <div
                      key={r.report_id}
                      onClick={() => handleSelectPastReport(r.report_id)}
                      className="p-3 rounded-lg bg-[#09090b] hover:bg-[#181820] border border-white/[0.06] flex items-start justify-between gap-2 cursor-pointer transition-all"
                    >
                      <div className="space-y-1 overflow-hidden">
                        <p className="text-xs font-semibold text-white truncate">{r.question}</p>
                        <p className="text-[11px] text-zinc-400 line-clamp-1">{r.summary}</p>
                        <span className="text-[10px] text-zinc-500 font-mono">
                          {new Date(r.created_at).toLocaleDateString()} &bull; {r.status}
                        </span>
                      </div>
                      <button
                        onClick={(e) => handleDeleteReport(e, r.report_id)}
                        className="p-1 text-zinc-500 hover:text-rose-400 transition-all rounded"
                        title="Delete report"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-500 py-2">No prior investigations saved.</p>
              )}
            </div>
          )}

          {/* Investigation Result Report */}
          {investigating ? (
            <div className="p-12 text-center bg-[#121216] border border-white/[0.08] rounded-2xl space-y-3">
              <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mx-auto" />
              <h3 className="text-sm font-bold text-white">Running Evidence-Based Investigation...</h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto">
                Executing bounded analytical queries, evaluating metric deltas, and ranking dimensional contributors.
              </p>
            </div>
          ) : currentReport ? (
            <div className="space-y-6">
              {/* Report Header & Executive Summary */}
              <div className="p-6 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.06] pb-3">
                  <div>
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 font-semibold border border-indigo-500/30">
                      Investigation Report
                    </span>
                    <h2 className="text-base font-bold text-white mt-1">{currentReport.title}</h2>
                  </div>
                  <span className="text-xs text-zinc-500 font-mono">
                    {new Date(currentReport.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="space-y-2">
                  <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Executive Summary</span>
                  <p className="text-xs sm:text-sm text-zinc-200 leading-relaxed font-sans">
                    {currentReport.summary}
                  </p>
                </div>
              </div>

              {/* Observed Metric Comparison Card */}
              {currentReport.observed_change && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.08]">
                    <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Target Metric</span>
                    <div className="text-lg font-bold font-mono text-white mt-1">
                      {currentReport.observed_change.metric}
                    </div>
                    <span className="text-xs text-zinc-500">From table '{currentReport.primary_table}'</span>
                  </div>

                  <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.08]">
                    <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Observed Movement</span>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span className="text-lg font-bold font-mono text-white">
                        {currentReport.observed_change.formatted_change}
                      </span>
                    </div>
                    <span className="text-xs text-zinc-500">
                      Period: {currentReport.observed_change.time_period}
                    </span>
                  </div>

                  <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.08]">
                    <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">Values Compared</span>
                    <div className="text-xs font-mono text-zinc-300 mt-1">
                      Current: <strong className="text-white">{currentReport.observed_change.current_value}</strong>
                    </div>
                    <div className="text-xs font-mono text-zinc-400 mt-0.5">
                      Previous: <strong className="text-zinc-300">{currentReport.observed_change.previous_value}</strong>
                    </div>
                  </div>
                </div>
              )}

              {/* Dynamic Visualization Charts */}
              {currentReport.charts && currentReport.charts.length > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {currentReport.charts.map((chart: any, cIdx: number) => (
                    <div key={cIdx} className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
                      <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <BarChart3 size={14} className="text-indigo-400" />
                        <span>{chart.title}</span>
                      </h4>

                      {/* Responsive Styled Bar/Point Chart */}
                      <div className="space-y-2 pt-2">
                        {chart.data?.map((pt: any, ptIdx: number) => {
                          const val = pt.amount ?? pt.value ?? pt.share_percent ?? 0;
                          const label = pt.dimension ?? pt.period ?? `Item ${ptIdx + 1}`;
                          const maxVal = Math.max(...chart.data.map((d: any) => d.amount ?? d.value ?? d.share_percent ?? 1));
                          const widthPct = Math.min(100, Math.max(5, (Math.abs(val) / (maxVal || 1)) * 100));

                          return (
                            <div key={ptIdx} className="space-y-1">
                              <div className="flex justify-between text-xs font-mono">
                                <span className="text-zinc-300 truncate max-w-[200px]">{label}</span>
                                <span className="text-white font-bold">{val.toLocaleString()}</span>
                              </div>
                              <div className="w-full bg-[#09090b] h-2 rounded-full overflow-hidden border border-white/[0.04]">
                                <div
                                  className={`h-full rounded-full ${val < 0 ? "bg-rose-500" : "bg-indigo-500"}`}
                                  style={{ width: `${widthPct}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Contributing Factors & Ranked Contributors */}
              {currentReport.contributing_factors && currentReport.contributing_factors.length > 0 && (
                <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <TrendingDown size={14} className="text-rose-400" />
                    <span>Ranked Contributing Factors</span>
                  </h4>
                  <div className="divide-y divide-white/[0.04]">
                    {currentReport.contributing_factors.map((cf: any, cfIdx: number) => (
                      <div key={cf.factor_id || cfIdx} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{cf.dimension_value}</span>
                            <span className="font-mono text-zinc-400 text-[11px]">{cf.dimension}</span>
                          </div>
                          <p className="text-zinc-400 text-[11px]">{cf.observed_change}</p>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <span className={`font-mono font-bold px-2.5 py-1 rounded-full text-xs ${
                            cf.impact_type === "negative"
                              ? "bg-rose-500/15 text-rose-300 border border-rose-500/30"
                              : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                          }`}>
                            {cf.contribution_percent}% share
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hypotheses & Epistemic Guardrail */}
              {currentReport.hypotheses && currentReport.hypotheses.length > 0 && (
                <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <HelpCircle size={14} className="text-amber-400" />
                    <span>Formulated Hypotheses & Causal Caveats</span>
                  </h4>
                  <div className="space-y-3">
                    {currentReport.hypotheses.map((hyp: any, hIdx: number) => (
                      <div key={hyp.hypothesis_id || hIdx} className="p-3.5 rounded-xl bg-[#09090b] border border-white/[0.06] space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-white">{hyp.statement}</span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 uppercase">
                            Confidence: {hyp.confidence_level}
                          </span>
                        </div>
                        <div className="text-[11px] text-amber-300/80 italic flex items-center gap-1.5">
                          <ShieldAlert size={12} className="shrink-0" />
                          <span>{hyp.causality_caveat}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended Follow-Up Investigations */}
              {currentReport.recommendations && currentReport.recommendations.length > 0 && (
                <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <ArrowRight size={14} className="text-indigo-400" />
                    <span>Recommended Next Investigation Steps</span>
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {currentReport.recommendations.map((rec: any, rIdx: number) => (
                      <div
                        key={rec.recommendation_id || rIdx}
                        className="p-3.5 rounded-xl bg-[#09090b] border border-white/[0.06] flex flex-col justify-between gap-3 text-xs"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-white">{rec.action_title}</span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded uppercase ${
                              rec.priority === "high" ? "bg-rose-500/20 text-rose-300" : "bg-zinc-800 text-zinc-400"
                            }`}>
                              {rec.priority}
                            </span>
                          </div>
                          <p className="text-zinc-400 text-[11px]">{rec.reason}</p>
                          <span className="text-[10px] font-mono text-zinc-500">Target: {rec.target_data}</span>
                        </div>
                        <button
                          onClick={() => {
                            setQuestion(rec.action_title);
                            handleStartInvestigation(rec.action_title);
                          }}
                          className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer border border-indigo-500/25"
                        >
                          <Sparkles size={12} />
                          <span>Investigate This Next</span>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Data-Quality & Missing Information Caveats */}
              {currentReport.missing_reasons && currentReport.missing_reasons.length > 0 && (
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-1.5 text-xs text-amber-300">
                  <span className="font-bold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <AlertTriangle size={13} />
                    <span>Schema & Data Quality Notes</span>
                  </span>
                  <ul className="list-disc list-inside space-y-0.5 text-amber-200/90 text-[11px]">
                    {currentReport.missing_reasons.map((mr: string, idx: number) => (
                      <li key={idx}>{mr}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Evidence Provenance Lineage */}
              {currentReport.provenance && (
                <div className="p-4 rounded-xl bg-[#09090b] border border-white/[0.06] space-y-2 text-xs">
                  <span className="font-semibold text-zinc-400 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                    <Database size={12} className="text-indigo-400" />
                    <span>Calculation Provenance & SQL Lineage</span>
                  </span>
                  <div className="text-[11px] text-zinc-400 font-mono space-y-1">
                    <div>Connection: <strong className="text-zinc-200">{currentReport.provenance.connection_id}</strong> ({currentReport.provenance.database_type})</div>
                    <div>Tables Inspected: <strong className="text-zinc-200">{currentReport.provenance.tables_inspected?.join(", ")}</strong></div>
                    {currentReport.provenance.lineage_steps?.map((step: string, sIdx: number) => (
                      <div key={sIdx} className="text-zinc-500">&bull; {step}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-12 text-center bg-[#121216] border border-white/[0.08] rounded-2xl space-y-3">
              <Sparkles size={28} className="text-indigo-400 mx-auto" />
              <h3 className="text-sm font-bold text-white">Ask Any Business Question to Investigate</h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto">
                BG AI performs read-only analytical SQL audits, calculates period-over-period metric movements, ranks dimensional contributors, and produces verifiable reports with reproducible evidence.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Visual Distributions (Existing Dashboard) */}
      {activeTab === "dashboard" && (
        <div className="bg-[#121216] border border-white/[0.08] rounded-2xl p-4 sm:p-6 overflow-hidden">
          <Suspense
            fallback={
              <div className="p-12 text-center text-zinc-400 text-xs flex items-center justify-center gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
                <span>Loading visual analytics...</span>
              </div>
            }
          >
            <AnalyticsDashboard />
          </Suspense>
        </div>
      )}
    </div>
  );
}
