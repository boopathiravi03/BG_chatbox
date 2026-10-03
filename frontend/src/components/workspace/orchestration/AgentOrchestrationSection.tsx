import React, { useState, useEffect } from "react";
import {
  Layers,
  Sparkles,
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Shield,
  ArrowRight,
  Database,
  Cpu,
  RefreshCw,
  Search,
  Check,
  AlertCircle,
  FileText,
  ChevronDown,
  ChevronUp,
  XCircle,
  Flame,
  Zap,
} from "lucide-react";
import {
  initiateOrchestration,
  listOrchestrations,
  listOrchestrationAgents,
} from "../../../services/api";
import type {
  OrchestrationRunItem,
  SpecialistAgentItem,
  PlanStepItem,
  OrchestrationEvidenceLedgerItem,
  OrchestrationConflictItem,
} from "../../../types";

interface AgentOrchestrationSectionProps {
  dbConnected: boolean;
  onConnectDatabase: () => void;
  onNavigateToAction?: (actionId: string) => void;
}

export default function AgentOrchestrationSection({
  dbConnected,
  onConnectDatabase,
  onNavigateToAction,
}: AgentOrchestrationSectionProps) {
  const [goal, setGoal] = useState("");
  const [loading, setLoading] = useState(false);
  const [runs, setRuns] = useState<OrchestrationRunItem[]>([]);
  const [activeRun, setActiveRun] = useState<OrchestrationRunItem | null>(null);
  const [agents, setAgents] = useState<SpecialistAgentItem[]>([]);
  const [showAgentsModal, setShowAgentsModal] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedStepId, setExpandedStepId] = useState<string | null>(null);

  const SUGGESTIONS = [
    "Investigate why order volume decreased and suggest root causes",
    "Forecast quarterly revenue projections with uncertainty bounds",
    "Audit database health score and active anomaly signals",
    "Propose operational cleanup action for stale customer carts",
  ];

  const fetchData = async () => {
    if (!dbConnected) return;
    try {
      const [runsRes, agentsRes] = await Promise.all([
        listOrchestrations(10),
        listOrchestrationAgents(),
      ]);
      if (runsRes?.runs) {
        setRuns(runsRes.runs);
        if (runsRes.runs.length > 0 && !activeRun) {
          setActiveRun(runsRes.runs[0]);
        }
      }
      if (agentsRes?.agents) {
        setAgents(agentsRes.agents);
      }
    } catch (err: any) {
      console.error("Failed to load orchestration data:", err);
    }
  };

  useEffect(() => {
    fetchData();
  }, [dbConnected]);

  const handleRunOrchestration = async (targetGoal?: string) => {
    const goalToRun = targetGoal || goal;
    if (!goalToRun.trim()) return;

    setLoading(true);
    setErrorMsg(null);

    try {
      const res = await initiateOrchestration(goalToRun);
      if (res.status === "success" && res.orchestration) {
        setActiveRun(res.orchestration);
        setRuns((prev) => [res.orchestration, ...prev]);
        setGoal("");
      } else {
        setErrorMsg(res.message || "Failed to orchestrate goal.");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "An unexpected error occurred during orchestration.");
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "bg-emerald-500/15 border-emerald-500/30 text-emerald-400";
      case "WAITING_FOR_CONFIRMATION":
        return "bg-amber-500/15 border-amber-500/30 text-amber-300";
      case "PARTIALLY_COMPLETED":
        return "bg-sky-500/15 border-sky-500/30 text-sky-300";
      case "FAILED":
      case "BLOCKED":
        return "bg-rose-500/15 border-rose-500/30 text-rose-400";
      default:
        return "bg-indigo-500/15 border-indigo-500/30 text-indigo-300";
    }
  };

  return (
    <section className="space-y-6 pt-4 border-t border-white/[0.08]">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Layers size={16} />
            </div>
            <h2 className="text-base font-bold text-white tracking-wide">
              Advanced Agent Orchestration
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
              Phase 9.2 Coordinated Multi-Agent
            </span>
          </div>
          <p className="text-xs text-zinc-400">
            Coordinates safe, evidence-grounded specialist agents across Knowledge, BI, Forecasting, Investigation, and Actions.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowAgentsModal(true)}
            className="px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-semibold text-zinc-300 hover:text-white transition-all flex items-center gap-1.5"
          >
            <Cpu size={13} className="text-indigo-400" />
            <span>View 9 Specialists</span>
          </button>
          <button
            onClick={fetchData}
            className="p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-400 hover:text-white transition-all"
            title="Refresh History"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {!dbConnected ? (
        <div className="p-8 rounded-2xl bg-[#121216] border border-white/[0.08] text-center space-y-4">
          <Database size={32} className="mx-auto text-indigo-400/80" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-white">Database Required for Orchestration</h3>
            <p className="text-xs text-zinc-400 max-w-md mx-auto">
              Multi-agent orchestration strictly operates against real connected database facts. Connect a database to execute coordinated workflows.
            </p>
          </div>
          <button
            onClick={onConnectDatabase}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition-colors"
          >
            Connect Database
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Goal Input Card */}
          <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-4">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-amber-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Orchestrate Goal or Strategic Objective
              </h3>
            </div>

            <div className="flex flex-col sm:flex-row gap-2.5">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleRunOrchestration()}
                  placeholder="e.g. Investigate why customer revenue dropped 20% last month..."
                  className="w-full px-4 py-2.5 rounded-xl bg-black/40 border border-white/[0.08] focus:border-indigo-500 focus:outline-none text-xs text-white placeholder-zinc-500"
                />
              </div>
              <button
                onClick={() => handleRunOrchestration()}
                disabled={loading || !goal.trim()}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white transition-all flex items-center justify-center gap-2 shrink-0"
              >
                {loading ? (
                  <>
                    <RefreshCw size={13} className="animate-spin" />
                    <span>Planning & Orchestrating...</span>
                  </>
                ) : (
                  <>
                    <Play size={13} className="fill-white" />
                    <span>Orchestrate</span>
                  </>
                )}
              </button>
            </div>

            {/* Quick Suggestions */}
            <div className="space-y-1.5 pt-1">
              <p className="text-[11px] font-medium text-zinc-500">Suggested Autonomous Workflows:</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((sug, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleRunOrchestration(sug)}
                    className="px-2.5 py-1 rounded-lg bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.05] hover:border-white/[0.12] text-[11px] text-zinc-400 hover:text-white transition-all text-left"
                  >
                    ↳ {sug}
                  </button>
                ))}
              </div>
            </div>

            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
          </div>

          {/* Active Run View */}
          {activeRun && (
            <div className="p-6 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-6">
              {/* Run Meta Header */}
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-zinc-500 uppercase">
                      ID: {activeRun.orchestration_id}
                    </span>
                    <span
                      className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${getStatusBadge(
                        activeRun.status
                      )}`}
                    >
                      {activeRun.status}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300">
                      Confidence: {activeRun.confidence_tier}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-400">
                      {activeRun.duration_ms}ms
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-white">{activeRun.goal}</h3>
                </div>

                {/* Runs Selector */}
                {runs.length > 1 && (
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-zinc-500">History:</span>
                    <select
                      value={activeRun.orchestration_id}
                      onChange={(e) => {
                        const selected = runs.find((r) => r.orchestration_id === e.target.value);
                        if (selected) setActiveRun(selected);
                      }}
                      className="px-2.5 py-1 rounded-lg bg-black/40 border border-white/[0.08] text-xs text-zinc-300 focus:outline-none"
                    >
                      {runs.map((r) => (
                        <option key={r.orchestration_id} value={r.orchestration_id}>
                          {r.goal.slice(0, 30)}... ({r.status})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Executive Summary */}
              {activeRun.executive_summary && (
                <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Shield size={14} className="text-indigo-400" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">
                      Synthesized Executive Summary
                    </span>
                  </div>
                  <p className="text-xs text-zinc-200 leading-relaxed">
                    {activeRun.executive_summary}
                  </p>
                </div>
              )}

              {/* DAG Execution Timeline */}
              {activeRun.task_graph?.steps && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                      <Layers size={13} className="text-indigo-400" />
                      <span>Coordinated Plan Execution ({activeRun.task_graph.steps.length} Steps)</span>
                    </h4>
                    <span className="text-[10px] font-mono text-zinc-500">
                      Max Depth: {activeRun.task_graph.max_depth}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {activeRun.task_graph.steps.map((step) => {
                      const isExpanded = expandedStepId === step.step_id;
                      return (
                        <div
                          key={step.step_id}
                          className="p-3.5 rounded-xl bg-black/40 border border-white/[0.06] hover:border-white/[0.12] transition-all space-y-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="w-5 h-5 rounded-full bg-white/[0.06] text-[10px] font-mono flex items-center justify-center text-zinc-300 shrink-0">
                                {step.step_id.replace("step_", "")}
                              </span>
                              <span className="text-xs font-bold text-white truncate">
                                {step.name}
                              </span>
                            </div>
                            <span
                              className={`text-[9px] font-mono px-1.5 py-0.5 rounded border uppercase shrink-0 ${
                                step.status === "COMPLETED"
                                  ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                                  : step.status === "BLOCKED"
                                  ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                                  : "bg-zinc-800 border-zinc-700 text-zinc-400"
                              }`}
                            >
                              {step.status}
                            </span>
                          </div>

                          <div className="flex items-center justify-between text-[10px] text-zinc-400">
                            <span className="font-mono text-indigo-400">@{step.agent_id}</span>
                            <span>{step.duration_ms}ms</span>
                          </div>

                          <p className="text-[11px] text-zinc-400 leading-snug">{step.purpose}</p>

                          {step.dependencies.length > 0 && (
                            <div className="text-[10px] font-mono text-zinc-500">
                              Depends on: {step.dependencies.join(", ")}
                            </div>
                          )}

                          {step.output && (
                            <div className="pt-2 border-t border-white/[0.04]">
                              <button
                                onClick={() =>
                                  setExpandedStepId(isExpanded ? null : step.step_id)
                                }
                                className="text-[10px] text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                              >
                                <span>{isExpanded ? "Hide Output" : "View Output"}</span>
                                {isExpanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                              </button>
                              {isExpanded && (
                                <pre className="mt-2 p-2 rounded bg-black/60 border border-white/[0.04] text-[10px] font-mono text-zinc-300 overflow-x-auto max-h-40">
                                  {JSON.stringify(step.output, null, 2)}
                                </pre>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Evidence Ledger Section */}
              {activeRun.evidence_ledger && activeRun.evidence_ledger.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
                      <CheckCircle2 size={13} className="text-emerald-400" />
                      <span>Verified Evidence Ledger ({activeRun.evidence_ledger.length} Items)</span>
                    </h4>
                  </div>

                  <div className="space-y-2">
                    {activeRun.evidence_ledger.map((item) => (
                      <div
                        key={item.evidence_id}
                        className="p-3.5 rounded-xl bg-black/30 border border-white/[0.05] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-zinc-300">
                              {item.evidence_type}
                            </span>
                            <span className="font-semibold text-white">{item.title}</span>
                            <span className="text-[10px] font-mono text-indigo-400">
                              via @{item.source_agent}
                            </span>
                          </div>
                          <p className="text-[11px] text-zinc-400">{item.summary}</p>
                          {item.table_references && item.table_references.length > 0 && (
                            <span className="text-[10px] font-mono text-zinc-500">
                              Tables: {item.table_references.join(", ")}
                            </span>
                          )}
                        </div>

                        <div className="shrink-0 flex items-center gap-2">
                          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                            {item.confidence}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Detected Conflicts Section */}
              {activeRun.conflicts && activeRun.conflicts.length > 0 && (
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-2">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={14} className="text-amber-400" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-amber-300">
                      Surfaced Multi-Agent Discrepancies ({activeRun.conflicts.length})
                    </span>
                  </div>
                  <div className="space-y-2 pt-1">
                    {activeRun.conflicts.map((c) => (
                      <div
                        key={c.conflict_id}
                        className="p-2.5 rounded-lg bg-black/40 border border-white/[0.04] text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-amber-300">
                            {c.conflict_type}
                          </span>
                          <span className="text-[10px] text-zinc-400 font-mono">
                            Strategy: {c.resolution_strategy}
                          </span>
                        </div>
                        <p className="text-zinc-200 text-[11px]">{c.description}</p>
                        <p className="text-zinc-400 text-[10px]">
                          <strong>Resolution: </strong>
                          {c.resolution_details}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Proposed Action Card */}
              {activeRun.proposed_action && (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Zap size={15} className="text-emerald-400" />
                      <span className="text-xs font-bold text-white">
                        Controlled Action Proposal
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      Confirmation Required
                    </span>
                  </div>

                  <div className="space-y-1">
                    <h5 className="text-xs font-bold text-emerald-300">
                      {activeRun.proposed_action.title}
                    </h5>
                    <p className="text-[11px] text-zinc-300">
                      {activeRun.proposed_action.description}
                    </p>
                  </div>

                  <div className="p-3 rounded-lg bg-black/40 border border-white/[0.05] text-[11px] font-mono text-zinc-300">
                    <div className="flex justify-between">
                      <span className="text-zinc-500">Status:</span>
                      <span className="text-amber-400">{activeRun.proposed_action.status}</span>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-zinc-500">Safety Guarantee:</span>
                      <span className="text-emerald-400">Zero mutation without explicit human confirmation</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Specialist Agents Modal */}
      {showAgentsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-3xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[#121216] border border-white/10 shadow-2xl p-6 space-y-4 text-left">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Cpu size={16} className="text-indigo-400" />
                  <span>9 Specialist Agents & Permission Boundaries</span>
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Static deterministic registration of specialized intelligence sub-engines.
                </p>
              </div>
              <button
                onClick={() => setShowAgentsModal(false)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
              >
                <XCircle size={18} />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {agents.map((agent) => (
                <div
                  key={agent.agent_id}
                  className="p-3.5 rounded-xl bg-black/40 border border-white/[0.06] space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-white truncate">{agent.name}</span>
                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded border uppercase shrink-0 ${
                        agent.permission === "READ_ONLY"
                          ? "bg-sky-500/15 border-sky-500/30 text-sky-300"
                          : agent.permission === "ANALYTICAL"
                          ? "bg-indigo-500/15 border-indigo-500/30 text-indigo-300"
                          : "bg-amber-500/15 border-amber-500/30 text-amber-300"
                      }`}
                    >
                      {agent.permission}
                    </span>
                  </div>

                  <p className="text-[11px] text-zinc-400">{agent.description}</p>

                  <div className="pt-2 border-t border-white/[0.04] flex flex-wrap gap-1">
                    {agent.capabilities.map((cap, idx) => (
                      <span
                        key={idx}
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-white/[0.08] flex justify-end">
              <button
                onClick={() => setShowAgentsModal(false)}
                className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-white transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
