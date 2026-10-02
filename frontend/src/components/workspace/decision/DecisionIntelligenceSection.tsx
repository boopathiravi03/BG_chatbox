import React, { useState } from "react";
import {
  BrainCircuit,
  Search,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Lightbulb,
  CheckCircle2,
  FileCode2,
  Layers,
  ChevronRight,
  RotateCcw,
  Sparkles,
  Info,
  ExternalLink,
} from "lucide-react";
import { queryDecisionIntelligence, getAuthToken } from "../../../services/api";
import type {
  DecisionAnalysisResponse,
  DecisionEvidenceItem,
} from "../../../types";

interface DecisionIntelligenceSectionProps {
  dbConnected: boolean;
  onConnectDatabase: () => void;
  onNavigateToAgents?: (prompt: string, agent?: string) => void;
}

const EXAMPLE_QUESTIONS = [
  "Why is revenue declining?",
  "What is causing order cancellations?",
  "Which products need attention?",
  "What changed recently?",
  "What is the biggest business risk?",
];

export default function DecisionIntelligenceSection({
  dbConnected,
  onConnectDatabase,
  onNavigateToAgents,
}: DecisionIntelligenceSectionProps) {
  const [question, setQuestion] = useState<string>("Why is revenue declining?");
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [analysis, setAnalysis] = useState<DecisionAnalysisResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<DecisionEvidenceItem | null>(null);

  const handleRunAnalysis = async (qToRun?: string) => {
    const q = (qToRun || question || "").trim();
    if (!q || !dbConnected || !getAuthToken()) return;

    setAnalyzing(true);
    setErrorMessage(null);

    try {
      const resp = await queryDecisionIntelligence(q);
      if (resp && resp.status === "disconnected") {
        setErrorMessage("Database is disconnected. Please connect a database to run decision planning.");
        setAnalysis(null);
      } else if (resp && resp.status === "error") {
        setErrorMessage(resp.message || "Failed to analyze decision question.");
        setAnalysis(null);
      } else {
        setAnalysis(resp);
      }
    } catch (err: any) {
      if (err.status === 401) {
        setErrorMessage("Authentication session expired. Please sign in again.");
      } else if (err.status === 429) {
        setErrorMessage("Rate limit reached (10 queries/minute). Please wait a moment before trying again.");
      } else {
        setErrorMessage(err.message || "Failed to synthesize decision intelligence.");
      }
    } finally {
      setAnalyzing(false);
    }
  };

  const renderSafeValue = (val: any): React.ReactNode => {
    if (val === null || val === undefined) return <span className="text-zinc-500 italic">null</span>;
    if (typeof val === "boolean") return <span>{val ? "true" : "false"}</span>;
    if (typeof val === "number") return <span>{val.toLocaleString()}</span>;
    if (typeof val === "string") return <span>{val}</span>;
    if (Array.isArray(val)) {
      if (val.every((item) => typeof item === "string" || typeof item === "number")) {
        return <span>[{val.join(", ")}]</span>;
      }
      return (
        <pre className="text-[10px] text-zinc-300 bg-black/40 p-1.5 rounded overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(val, null, 2)}
        </pre>
      );
    }
    if (typeof val === "object") {
      return (
        <pre className="text-[10px] text-zinc-300 bg-black/40 p-1.5 rounded overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(val, null, 2)}
        </pre>
      );
    }
    return <span>{String(val)}</span>;
  };

  if (!dbConnected) {
    return (
      <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
            <BrainCircuit size={20} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              AI Decision & Planning Intelligence
            </h3>
            <p className="text-xs text-zinc-400">
              Connect a database to ask strategic questions and generate evidence-backed decision plans.
            </p>
          </div>
        </div>
        <button
          onClick={onConnectDatabase}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer shrink-0"
        >
          <span>Connect Database</span>
          <ArrowRight size={13} />
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header & Query Input Box */}
      <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-4">
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0 mt-0.5">
            <BrainCircuit size={20} />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white tracking-tight">
                AI Decision & Planning Intelligence
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300 font-semibold">
                PHASE 8.4
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Synthesizes automated BI, cross-table lineage, anomalies, and proactive alerts into verified decision roadmaps.
            </p>
          </div>
        </div>

        {/* Input bar */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !analyzing && handleRunAnalysis()}
                placeholder="Ask a strategic business question (e.g., Why are sales declining?)"
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-black/40 border border-white/[0.08] focus:border-purple-500 text-xs text-white placeholder-zinc-500 outline-none transition-all"
              />
            </div>
            <button
              onClick={() => handleRunAnalysis()}
              disabled={analyzing || !question.trim()}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-md shadow-purple-600/20 transition-all cursor-pointer disabled:opacity-50 shrink-0"
            >
              {analyzing ? (
                <>
                  <RotateCcw size={13} className="animate-spin" />
                  <span>Synthesizing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={13} />
                  <span>Analyze & Plan</span>
                </>
              )}
            </button>
          </div>

          {/* Example prompt pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] text-zinc-500 font-medium mr-1">Examples:</span>
            {EXAMPLE_QUESTIONS.map((eq) => (
              <button
                key={eq}
                onClick={() => {
                  setQuestion(eq);
                  handleRunAnalysis(eq);
                }}
                disabled={analyzing}
                className="px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.06] text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
              >
                {eq}
              </button>
            ))}
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between">
            <span>{errorMessage}</span>
            <button onClick={() => setErrorMessage(null)} className="text-rose-400 hover:text-white text-xs font-bold">
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Analysis Results View */}
      {analysis && (
        <div className="space-y-4">
          {/* Problem Statement & Confidence Banner */}
          <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
                  Core Problem Statement
                </span>
                <h4 className="text-base font-bold text-white tracking-tight mt-0.5">
                  {analysis.problem_statement}
                </h4>
              </div>

              {/* Confidence Badge */}
              {analysis.confidence && (
                <div className="flex items-center gap-2 p-2 rounded-xl bg-black/40 border border-white/[0.06] shrink-0">
                  <ShieldCheck
                    size={18}
                    className={
                      analysis.confidence.level === "HIGH"
                        ? "text-emerald-400"
                        : analysis.confidence.level === "MODERATE"
                        ? "text-amber-400"
                        : "text-zinc-400"
                    }
                  />
                  <div className="text-left">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-mono text-zinc-400 uppercase">Evidence Confidence:</span>
                      <span
                        className={`text-[11px] font-mono font-bold ${
                          analysis.confidence.level === "HIGH"
                            ? "text-emerald-400"
                            : analysis.confidence.level === "MODERATE"
                            ? "text-amber-400"
                            : "text-zinc-400"
                        }`}
                      >
                        {analysis.confidence.level}
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-500 block truncate max-w-[280px]">
                      {analysis.confidence.signal_count} verified signal(s) across {analysis.confidence.corroborating_sources.length} subsystem(s)
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Confidence Rationale */}
            {analysis.confidence?.rationale && (
              <p className="text-xs text-zinc-400 leading-relaxed">
                {analysis.confidence.rationale}
              </p>
            )}
          </div>

          {/* Observed Findings & Supporting Evidence Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Observed Findings */}
            <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-400" />
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    Observed Findings ({analysis.findings.length})
                  </h4>
                </div>
                <span className="text-[10px] font-mono text-zinc-500">100% Deterministic</span>
              </div>

              <div className="space-y-2">
                {analysis.findings.map((f, idx) => (
                  <div
                    key={f.finding_id || idx}
                    className="p-3 rounded-xl bg-black/40 border border-white/[0.04] space-y-1 text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                          f.severity === "CRITICAL"
                            ? "bg-rose-500/15 text-rose-300 border border-rose-500/30"
                            : f.severity === "WARNING"
                            ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                            : "bg-sky-500/15 text-sky-300 border border-sky-500/30"
                        }`}
                      >
                        {f.severity}
                      </span>
                      <span className="text-[10px] font-mono text-zinc-500 truncate">
                        {f.category}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-200 leading-relaxed font-medium">
                      {f.statement}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Candidate Hypotheses (Epistemic Hygiene) */}
            <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Lightbulb size={16} className="text-amber-400" />
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    Candidate Hypotheses ({analysis.hypotheses.length})
                  </h4>
                </div>
                <span className="text-[10px] font-mono text-amber-400/80 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                  Unconfirmed
                </span>
              </div>

              <div className="space-y-2">
                {analysis.hypotheses.map((h, idx) => (
                  <div
                    key={h.hypothesis_id || idx}
                    className="p-3 rounded-xl bg-black/40 border border-amber-500/15 space-y-1.5 text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                        HYPOTHESIS ({h.likelihood})
                      </span>
                    </div>
                    <p className="text-xs text-zinc-300 leading-relaxed">
                      {h.statement}
                    </p>
                    <p className="text-[10px] text-zinc-500 italic">
                      ⚠️ {h.causality_caveat}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Supporting Evidence Items List */}
          {analysis.evidence.length > 0 && (
            <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers size={16} className="text-indigo-400" />
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    Verifiable Database Evidence ({analysis.evidence.length})
                  </h4>
                </div>
                <span className="text-[10px] text-zinc-400">Click any card to inspect SQL & lineage</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {analysis.evidence.map((ev) => (
                  <div
                    key={ev.evidence_id}
                    onClick={() => setSelectedEvidence(ev)}
                    className="p-3.5 rounded-xl bg-black/40 border border-white/[0.06] hover:border-indigo-500/40 cursor-pointer transition-all space-y-2 text-left"
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-zinc-400 truncate">
                        {ev.source_system}
                      </span>
                      {ev.delta_percent !== null && ev.delta_percent !== undefined && (
                        <span
                          className={`text-[10px] font-mono font-bold ${
                            ev.delta_percent > 0 ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {ev.delta_percent > 0 ? "+" : ""}
                          {ev.delta_percent.toFixed(1)}%
                        </span>
                      )}
                    </div>

                    <h5 className="text-xs font-semibold text-white truncate">{ev.title}</h5>

                    <div className="text-[11px] font-mono text-zinc-300 flex items-center justify-between">
                      <span className="text-zinc-500">Value:</span>
                      <span className="text-indigo-300 font-semibold">{renderSafeValue(ev.current_value)}</span>
                    </div>

                    {ev.sql && (
                      <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                        <FileCode2 size={11} className="text-emerald-400" />
                        <span>SQL available</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommended Investigations & Sequential Decision Plan */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Recommended Investigations */}
            <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
              <div className="flex items-center gap-2">
                <Search size={16} className="text-sky-400" />
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                  Recommended Investigations
                </h4>
              </div>

              <div className="space-y-2">
                {analysis.recommended_investigations.map((inv, idx) => (
                  <div
                    key={inv.investigation_id || idx}
                    className="p-3 rounded-xl bg-black/40 border border-white/[0.04] space-y-1 text-left"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-sky-300">
                        #{inv.priority} {inv.title}
                      </span>
                      {inv.target_table && (
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                          {inv.target_table}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-zinc-300 leading-relaxed">{inv.rationale}</p>
                    {inv.suggested_focus && (
                      <p className="text-[10px] font-mono text-zinc-500 truncate pt-0.5">
                        Focus: {inv.suggested_focus}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Sequential Decision Plan */}
            <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ChevronRight size={16} className="text-purple-400" />
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    Sequential Decision Plan
                  </h4>
                </div>
                <span className="text-[10px] font-mono text-zinc-500">Human-in-the-Loop</span>
              </div>

              <div className="space-y-2">
                {analysis.decision_plan.map((step) => (
                  <div
                    key={step.step_number}
                    className="p-3 rounded-xl bg-black/40 border border-white/[0.04] space-y-1 text-left"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">
                        Step {step.step_number}: {step.title}
                      </span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-purple-500/15 border border-purple-500/30 text-purple-300">
                        {step.action_type}
                      </span>
                    </div>

                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      {step.description}
                    </p>

                    {step.requires_confirmation && (
                      <div className="pt-1 flex items-center justify-between gap-2">
                        <span className="text-[10px] text-amber-300 flex items-center gap-1">
                          <AlertTriangle size={11} className="text-amber-400" />
                          <span>Human confirmation required</span>
                        </span>

                        {step.safe_action_eligible && onNavigateToAgents && (
                          <button
                            onClick={() =>
                              onNavigateToAgents(
                                `Review and verify corrective decision action for ${step.target_table || "database"}`,
                                "action_agent"
                              )
                            }
                            className="inline-flex items-center gap-1 text-[10px] font-semibold text-indigo-400 hover:text-indigo-300 cursor-pointer"
                          >
                            <span>Agent Center</span>
                            <ExternalLink size={10} />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Evidence Inspection Modal */}
      {selectedEvidence && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={() => setSelectedEvidence(null)}
          onKeyDown={(e) => e.key === "Escape" && setSelectedEvidence(null)}
        >
          <div
            className="relative w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[#121216] border border-white/10 shadow-2xl p-6 space-y-4 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 font-semibold">
                  EVIDENCE DETAILS
                </span>
                <h3 className="text-base font-bold text-white mt-1">{selectedEvidence.title}</h3>
                <p className="text-xs text-zinc-400">Source: {selectedEvidence.source_system}</p>
              </div>

              <button
                onClick={() => setSelectedEvidence(null)}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold text-zinc-400 hover:text-white bg-white/5 cursor-pointer"
              >
                Close
              </button>
            </div>

            <div className="space-y-2 text-xs font-mono">
              <div className="p-3 rounded-xl bg-black/40 border border-white/[0.06] space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500">Metric:</span>
                  <span className="text-zinc-200">{selectedEvidence.metric}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500">Current Value:</span>
                  <span className="text-emerald-400 font-bold">{renderSafeValue(selectedEvidence.current_value)}</span>
                </div>
                {selectedEvidence.previous_value !== undefined && selectedEvidence.previous_value !== null && (
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-500">Previous Value:</span>
                    <span className="text-zinc-300">{renderSafeValue(selectedEvidence.previous_value)}</span>
                  </div>
                )}
                {selectedEvidence.delta_percent !== undefined && selectedEvidence.delta_percent !== null && (
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-500">Change:</span>
                    <span className="text-indigo-400 font-semibold">{selectedEvidence.delta_percent.toFixed(1)}%</span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500">Source Tables:</span>
                  <span className="text-zinc-200">{selectedEvidence.source_tables.join(", ") || "None"}</span>
                </div>
              </div>

              {selectedEvidence.calculation && (
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase font-semibold">Calculation & Lineage</span>
                  <div className="p-2.5 rounded-xl bg-black/60 border border-white/[0.06] text-zinc-300 text-xs whitespace-pre-wrap">
                    {selectedEvidence.calculation}
                  </div>
                </div>
              )}

              {selectedEvidence.sql && (
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-500 uppercase font-semibold">Reproducible SQL</span>
                  <div className="p-2.5 rounded-xl bg-black/60 border border-white/[0.06] text-emerald-300 text-xs overflow-x-auto whitespace-pre-wrap">
                    {selectedEvidence.sql}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
