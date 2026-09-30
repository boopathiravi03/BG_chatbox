import React, { useState, useEffect } from "react";
import {
  Bot,
  Shield,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowRight,
  Database,
  Search,
  Sparkles,
  Play,
  RotateCcw,
  Check,
  X,
  FileCode,
  Activity,
  BarChart3,
  TrendingUp,
  Cpu,
  Layers,
  Terminal,
  ExternalLink,
  Info,
} from "lucide-react";
import {
  getAgents,
  runAgentTask,
  getAgentActions,
  confirmAgentAction,
  cancelAgentAction,
} from "../../../services/api";
import type {
  AgentInfo,
  AgentResult,
  ActionPlan,
  AgentFinding,
} from "../../../types";

interface AgentCenterViewProps {
  dbConnected: boolean;
  dbType: string | null;
  initialPrompt?: string;
  initialAgent?: string;
  onNavigateTab?: (tab: any, target?: string) => void;
}

export default function AgentCenterView({
  dbConnected,
  dbType,
  initialPrompt = "",
  initialAgent,
  onNavigateTab,
}: AgentCenterViewProps) {
  const [activeTab, setActiveTab] = useState<"console" | "history">("console");
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [actions, setActions] = useState<ActionPlan[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(false);
  const [loadingActions, setLoadingActions] = useState(false);

  // Task execution state
  const [selectedAgent, setSelectedAgent] = useState<string>(initialAgent || "auto");
  const [taskPrompt, setTaskPrompt] = useState<string>(initialPrompt);
  const [executing, setExecuting] = useState(false);
  const [currentResult, setCurrentResult] = useState<AgentResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Action execution state
  const [confirmingActionId, setConfirmingActionId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{
    id: string;
    success: boolean;
    message: string;
  } | null>(null);

  useEffect(() => {
    loadAgents();
    loadActions();
  }, [dbConnected]);

  useEffect(() => {
    if (initialPrompt) {
      setTaskPrompt(initialPrompt);
    }
    if (initialAgent) {
      setSelectedAgent(initialAgent);
    }
  }, [initialPrompt, initialAgent]);

  const loadAgents = async () => {
    setLoadingAgents(true);
    try {
      const data = await getAgents();
      setAgents(data);
    } catch (err: any) {
      console.error("Failed to load agents:", err);
    } finally {
      setLoadingAgents(false);
    }
  };

  const loadActions = async () => {
    setLoadingActions(true);
    try {
      const data = await getAgentActions();
      setActions(data);
    } catch (err: any) {
      console.error("Failed to load actions:", err);
    } finally {
      setLoadingActions(false);
    }
  };

  const handleRunTask = async (customPrompt?: string, agentOverride?: string) => {
    const promptToUse = customPrompt || taskPrompt;
    if (!promptToUse.trim()) return;

    setExecuting(true);
    setErrorMsg(null);
    setActionFeedback(null);

    const agentToUse = agentOverride !== undefined ? agentOverride : selectedAgent;
    const resolvedAgent = agentToUse === "auto" ? null : agentToUse;

    try {
      const result = await runAgentTask(promptToUse, resolvedAgent);
      setCurrentResult(result);
      if (result.proposed_action) {
        // Refresh actions list to reflect newly staged action
        loadActions();
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute agent task");
    } finally {
      setExecuting(false);
    }
  };

  const handleConfirmAction = async (actionId: string) => {
    setConfirmingActionId(actionId);
    setActionFeedback(null);
    try {
      const res = await confirmAgentAction(actionId);
      if (res.success) {
        setActionFeedback({
          id: actionId,
          success: true,
          message: `Action executed & verified successfully! Affected ${res.actual_rows_affected ?? 0} record(s).`,
        });
        // Update currently rendered proposed_action if matches
        if (currentResult?.proposed_action?.action_id === actionId && res.action) {
          setCurrentResult({
            ...currentResult,
            proposed_action: res.action,
            status: "COMPLETED",
          });
        }
      } else {
        setActionFeedback({
          id: actionId,
          success: false,
          message: `Execution failed or rolled back: ${res.error || "Unknown error"}`,
        });
      }
      loadActions();
    } catch (err: any) {
      setActionFeedback({
        id: actionId,
        success: false,
        message: err.message || "Failed to confirm action",
      });
    } finally {
      setConfirmingActionId(null);
    }
  };

  const handleCancelAction = async (actionId: string) => {
    try {
      const res = await cancelAgentAction(actionId);
      if (res.success) {
        setActionFeedback({
          id: actionId,
          success: true,
          message: "Action cancelled. Database state was not modified.",
        });
        if (currentResult?.proposed_action?.action_id === actionId && res.action) {
          setCurrentResult({
            ...currentResult,
            proposed_action: res.action,
            status: "COMPLETED",
          });
        }
        loadActions();
      }
    } catch (err: any) {
      console.error("Cancel failed:", err);
    }
  };

  const getAgentIcon = (name: string) => {
    switch (name) {
      case "database_health_agent":
        return <Activity className="w-5 h-5 text-emerald-400" />;
      case "data_quality_agent":
        return <ShieldCheck className="w-5 h-5 text-blue-400" />;
      case "analyst_agent":
        return <BarChart3 className="w-5 h-5 text-indigo-400" />;
      case "anomaly_agent":
        return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      case "performance_agent":
        return <TrendingUp className="w-5 h-5 text-cyan-400" />;
      case "action_agent":
        return <Cpu className="w-5 h-5 text-purple-400" />;
      default:
        return <Bot className="w-5 h-5 text-slate-400" />;
    }
  };

  const starterPills = [
    {
      label: "Audit Database Health",
      prompt: "Check database health, missing primary keys, and unindexed relations",
      agent: "database_health_agent",
    },
    {
      label: "Find Data Quality Issues",
      prompt: "Audit missing values, high null ratios, and orphan references",
      agent: "data_quality_agent",
    },
    {
      label: "Investigate Outliers & Anomalies",
      prompt: "Find unusual numerical outliers and sudden chronological shifts",
      agent: "anomaly_agent",
    },
    {
      label: "Check Indexing Bottlenecks",
      prompt: "Find unindexed foreign keys and potential schema performance bottlenecks",
      agent: "performance_agent",
    },
    {
      label: "Analyze Customer Trends",
      prompt: "Analyze revenue and transaction trend patterns over historical periods",
      agent: "analyst_agent",
    },
  ];

  if (!dbConnected) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8">
        <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 shadow-xl">
          <Bot className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-white mb-2">Connect a Database to Run Specialist Agents</h2>
        <p className="text-sm text-slate-400 max-w-md mb-6">
          Specialist agents inspect real schema metadata, audit data quality, diagnose performance, and formulate safe human-approved actions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Top Navigation & Sub-Tabs */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" /> Human-in-the-Loop Safe Execution
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
              6 Specialist Workers Active
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white mt-1">Specialist AI Agents</h1>
        </div>

        <div className="flex items-center bg-slate-900 border border-slate-800 rounded-xl p-1 shadow-inner">
          <button
            onClick={() => setActiveTab("console")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "console"
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Bot className="w-4 h-4" />
            Agent Console
          </button>
          <button
            onClick={() => setActiveTab("history")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === "history"
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Clock className="w-4 h-4" />
            Action Audit Log
            {actions.filter((a) => a.status === "AWAITING_CONFIRMATION").length > 0 && (
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            )}
          </button>
        </div>
      </div>

      {actionFeedback && (
        <div
          className={`p-4 rounded-xl border flex items-start justify-between gap-3 ${
            actionFeedback.success
              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
              : "bg-rose-500/10 border-rose-500/20 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-2.5 text-sm font-medium">
            {actionFeedback.success ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            )}
            <span>{actionFeedback.message}</span>
          </div>
          <button
            onClick={() => setActionFeedback(null)}
            className="text-slate-400 hover:text-slate-200 text-xs"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {activeTab === "console" ? (
        <div className="space-y-6">
          {/* Active Specialist Cards */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                Specialist AI Workers
              </h2>
              <span className="text-xs text-slate-500">
                Click any specialist to target investigation
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map((agent) => {
                const isSelected = selectedAgent === agent.name;
                return (
                  <div
                    key={agent.name}
                    onClick={() => setSelectedAgent(agent.name)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? "bg-indigo-950/20 border-indigo-500/40 ring-1 ring-indigo-500/30 shadow-lg"
                        : "bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-lg bg-slate-800 border border-slate-700">
                          {getAgentIcon(agent.name)}
                        </div>
                        <div>
                          <h3 className="font-semibold text-sm text-white">
                            {agent.role}
                          </h3>
                          <span className="text-xs text-slate-400">
                            {agent.name}
                          </span>
                        </div>
                      </div>
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider border ${
                          agent.is_read_only
                            ? "bg-blue-500/10 border-blue-500/20 text-blue-400"
                            : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                        }`}
                      >
                        {agent.is_read_only ? "Read-Only" : "Safe Action Ready"}
                      </span>
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-2 mb-3">
                      {agent.description}
                    </p>

                    <div className="space-y-1">
                      {agent.capabilities.slice(0, 2).map((cap, i) => (
                        <div
                          key={i}
                          className="flex items-center gap-1.5 text-[11px] text-slate-300"
                        >
                          <div className="w-1 h-1 rounded-full bg-indigo-400" />
                          <span className="truncate">{cap}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Interactive Task Console */}
          <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Terminal className="w-5 h-5 text-indigo-400" />
                <span className="font-semibold text-sm text-white">
                  Agent Execution Console
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Target Specialist:</span>
                <select
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
                >
                  <option value="auto">⚡ Auto-Route by Intent (Recommended)</option>
                  {agents.map((a) => (
                    <option key={a.name} value={a.name}>
                      {a.role} ({a.is_read_only ? "Read-Only" : "Safe Action"})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Quick Starters */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-500">Quick inquiries:</span>
              {starterPills.map((pill, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setTaskPrompt(pill.prompt);
                    setSelectedAgent(pill.agent);
                    handleRunTask(pill.prompt, pill.agent);
                  }}
                  className="px-2.5 py-1 rounded-full bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 text-xs text-slate-300 hover:text-white transition-colors"
                >
                  {pill.label}
                </button>
              ))}
            </div>

            {/* Task Input */}
            <div className="space-y-2">
              <textarea
                value={taskPrompt}
                onChange={(e) => setTaskPrompt(e.target.value)}
                placeholder="Give a specialist agent an analytical task or safe action request (e.g., 'Delete orphan records from orders where customer_id = 999', 'Diagnose database health', 'Audit null ratios')..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 min-h-[90px] resize-y font-mono"
              />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>
                    No database writes execute automatically. Modifications always require human confirmation.
                  </span>
                </div>
                <button
                  onClick={() => handleRunTask()}
                  disabled={executing || !taskPrompt.trim()}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm transition-all shadow-lg shadow-indigo-600/30"
                >
                  {executing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Investigating...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-current" />
                      Run Specialist Task
                    </>
                  )}
                </button>
              </div>
            </div>

            {errorMsg && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
          </div>

          {/* Current Execution Result */}
          {currentResult && (
            <div className="space-y-6">
              {/* Proposed Action Card (Human Confirmation Gate) */}
              {currentResult.proposed_action && (
                <div className="p-6 rounded-2xl bg-gradient-to-br from-amber-950/30 via-slate-900 to-slate-900 border border-amber-500/40 shadow-2xl relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/5 rounded-full blur-2xl" />

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-400">
                        <ShieldAlert className="w-6 h-6" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                            Action Proposal — Explicit Confirmation Required
                          </span>
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase">
                            Risk: {currentResult.proposed_action.risk_level}
                          </span>
                        </div>
                        <h3 className="text-lg font-bold text-white">
                          Proposed {currentResult.proposed_action.action_type} on Table '{currentResult.proposed_action.table}'
                        </h3>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                        Est. Rows: {currentResult.proposed_action.estimated_rows}
                      </span>
                      <span className="px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                        ID: {currentResult.proposed_action.action_id}
                      </span>
                    </div>
                  </div>

                  <p className="text-sm text-slate-300 mb-4">
                    {currentResult.proposed_action.potential_consequence}
                  </p>

                  {/* SQL Preview Block */}
                  <div className="space-y-1.5 mb-4">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <FileCode className="w-3.5 h-3.5 text-indigo-400" />
                      Exact Proposed SQL
                    </span>
                    <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 font-mono text-xs text-amber-300 overflow-x-auto shadow-inner">
                      {currentResult.proposed_action.exact_sql}
                    </div>
                  </div>

                  {/* Rollback & Verification info */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6 text-xs text-slate-400">
                    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                      <span className="font-semibold text-slate-300 block mb-1">
                        Transactional Safety:
                      </span>
                      {currentResult.proposed_action.rollback_considerations}
                    </div>
                    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                      <span className="font-semibold text-slate-300 block mb-1">
                        Post-Execution Verification:
                      </span>
                      Runs verification check expecting result: '
                      {currentResult.proposed_action.expected_verification_result}'. Automatic rollback on mismatch.
                    </div>
                  </div>

                  {/* Actions Buttons */}
                  {currentResult.proposed_action.status === "AWAITING_CONFIRMATION" ||
                  currentResult.proposed_action.status === "PROPOSED" ? (
                    <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-3 border-t border-slate-800">
                      <button
                        onClick={() => handleCancelAction(currentResult.proposed_action!.action_id)}
                        className="w-full sm:w-auto px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors"
                      >
                        Cancel Proposal
                      </button>
                      <button
                        onClick={() => handleConfirmAction(currentResult.proposed_action!.action_id)}
                        disabled={confirmingActionId === currentResult.proposed_action.action_id}
                        className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm font-semibold transition-all shadow-lg shadow-amber-600/30"
                      >
                        {confirmingActionId === currentResult.proposed_action.action_id ? (
                          <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Executing & Verifying...
                          </>
                        ) : (
                          <>
                            <Check className="w-4 h-4" />
                            Confirm & Execute Action
                          </>
                        )}
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-sm font-semibold text-emerald-400 pt-2 border-t border-slate-800">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Status: {currentResult.proposed_action.status}</span>
                      {currentResult.proposed_action.actual_rows_affected !== null && (
                        <span className="text-slate-400 font-normal">
                          ({currentResult.proposed_action.actual_rows_affected} records modified)
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Specialist Findings & Analysis Result */}
              <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-slate-800 border border-slate-700">
                      {getAgentIcon(currentResult.agent_name)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-white text-base">
                          {currentResult.agent_name.replace(/_/g, " ").toUpperCase()}
                        </h3>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                            currentResult.status === "COMPLETED"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              : currentResult.status === "ACTION_REQUIRED"
                              ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                              : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                          }`}
                        >
                          {currentResult.status}
                        </span>
                      </div>
                      <span className="text-xs text-slate-400">
                        Task ID: {currentResult.task_id} • Duration: {currentResult.duration_ms}ms
                      </span>
                    </div>
                  </div>
                </div>

                {/* Executive Summary */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Executive Summary
                  </h4>
                  <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 text-sm text-slate-200 leading-relaxed">
                    {currentResult.summary}
                  </div>
                </div>

                {/* Findings Deck */}
                {currentResult.findings.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Structured Findings ({currentResult.findings.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {currentResult.findings.map((f, i) => (
                        <div
                          key={f.id || i}
                          className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition-colors space-y-1.5"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-sm text-white">
                              {f.title}
                            </span>
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                                f.severity === "CRITICAL"
                                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                  : f.severity === "WARNING"
                                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                  : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                              }`}
                            >
                              {f.severity}
                            </span>
                          </div>
                          <p className="text-xs text-slate-300 leading-normal">
                            {f.description}
                          </p>
                          {f.table && (
                            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 pt-1">
                              <Database className="w-3 h-3 text-slate-500" />
                              <span>
                                Entity: <strong className="text-slate-200">{f.table}</strong>
                                {f.column && `.${f.column}`}
                              </span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommendations */}
                {currentResult.recommendations.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Recommended Investigations & Next Steps
                    </h4>
                    <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800/80 space-y-2">
                      {currentResult.recommendations.map((rec, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                          <span>{rec}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Execution Trace */}
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Execution Trace
                  </h4>
                  <div className="p-3 rounded-lg bg-slate-950 font-mono text-[11px] text-slate-400 space-y-1">
                    {currentResult.execution_steps.map((step, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className="text-slate-600">›</span>
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Action Audit Log Tab */
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-slate-900 border border-slate-800">
            <div>
              <h2 className="text-sm font-semibold text-white">Action Audit Trail</h2>
              <p className="text-xs text-slate-400">
                Complete record of proposed, executed, verified, and cancelled actions. No secrets are stored.
              </p>
            </div>
            <button
              onClick={loadActions}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-medium transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Refresh Log
            </button>
          </div>

          {loadingActions ? (
            <div className="flex justify-center p-12">
              <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : actions.length === 0 ? (
            <div className="p-12 text-center rounded-2xl bg-slate-900/50 border border-slate-800 text-slate-400">
              <Shield className="w-8 h-8 text-slate-500 mx-auto mb-2" />
              <p className="text-sm font-medium">No actions staged or recorded yet.</p>
              <p className="text-xs text-slate-500 mt-1">
                When Safe Action Specialist formulates a database modification, it will appear here for review and auditing.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {actions.map((act) => (
                <div
                  key={act.action_id}
                  className="p-5 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase ${
                          act.status === "VERIFIED"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : act.status === "AWAITING_CONFIRMATION"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse"
                            : act.status === "CANCELLED"
                            ? "bg-slate-800 text-slate-400 border border-slate-700"
                            : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        }`}
                      >
                        {act.status}
                      </span>
                      <span className="font-bold text-sm text-white">
                        {act.action_type} on '{act.table}'
                      </span>
                      <span className="text-xs text-slate-400">
                        ({act.estimated_rows} rows estimated)
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-400">
                      <span>Risk: <strong className="text-slate-200">{act.risk_level}</strong></span>
                      <span>{new Date(act.created_at).toLocaleString()}</span>
                    </div>
                  </div>

                  <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                    {act.exact_sql}
                  </div>

                  {act.verification_details && (
                    <div className="flex items-center gap-2 text-xs text-emerald-400 font-medium bg-emerald-500/5 p-2.5 rounded-lg border border-emerald-500/10">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>
                        Verified: Expected {act.verification_details.expected}, Observed {act.verification_details.observed}.
                      </span>
                    </div>
                  )}

                  {act.error && (
                    <div className="flex items-center gap-2 text-xs text-rose-400 font-medium bg-rose-500/5 p-2.5 rounded-lg border border-rose-500/10">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>{act.error}</span>
                    </div>
                  )}

                  {/* Actions on pending items */}
                  {act.status === "AWAITING_CONFIRMATION" && (
                    <div className="flex items-center justify-end gap-2 pt-2">
                      <button
                        onClick={() => handleCancelAction(act.action_id)}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 font-medium transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleConfirmAction(act.action_id)}
                        disabled={confirmingActionId === act.action_id}
                        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-xs text-white font-semibold transition-colors"
                      >
                        {confirmingActionId === act.action_id ? "Executing..." : "Confirm & Execute"}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
