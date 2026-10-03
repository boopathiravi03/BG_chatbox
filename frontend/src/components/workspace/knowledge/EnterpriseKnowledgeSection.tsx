import React, { useState, useEffect } from "react";
import {
  BookOpen,
  Layers,
  ShieldCheck,
  GitBranch,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Sparkles,
  Plus,
  Search,
  RefreshCw,
  Database,
  ArrowRight,
  Info,
  Check,
  X,
  Sliders,
  FileCode,
} from "lucide-react";
import {
  getKnowledgeSummary,
  parseBusinessContext,
  confirmKnowledgeItem,
  disableKnowledgeItem,
  resolveKnowledgeConflict,
  getKnowledgeLineage,
  searchKnowledge,
} from "../../../services/api";
import type {
  BusinessEntity,
  BusinessMetric,
  BusinessRule,
  KnowledgeConflict,
  KnowledgeLineage,
  KnowledgeSummary,
  ContextParseResult,
} from "../../../types";

interface EnterpriseKnowledgeSectionProps {
  dbConnected: boolean;
  onConnectDatabase?: () => void;
}

export const EnterpriseKnowledgeSection: React.FC<EnterpriseKnowledgeSectionProps> = ({
  dbConnected,
  onConnectDatabase,
}) => {
  const [activeTab, setActiveTab] = useState<"context" | "metrics" | "rules" | "lineage">("context");
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Core Data
  const [summary, setSummary] = useState<KnowledgeSummary | null>(null);
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [metrics, setMetrics] = useState<BusinessMetric[]>([]);
  const [rules, setRules] = useState<BusinessRule[]>([]);
  const [conflicts, setConflicts] = useState<KnowledgeConflict[]>([]);

  // Add Context Modal State
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [contextInput, setContextInput] = useState<string>("");
  const [parsingContext, setParsingContext] = useState<boolean>(false);
  const [parseResult, setParseResult] = useState<ContextParseResult | null>(null);

  // Lineage State
  const [selectedMetricId, setSelectedMetricId] = useState<string>("");
  const [lineage, setLineage] = useState<KnowledgeLineage | null>(null);
  const [lineageLoading, setLineageLoading] = useState<boolean>(false);

  // Search State
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResult, setSearchResult] = useState<any | null>(null);
  const [searching, setSearching] = useState<boolean>(false);

  // Conflict Resolution State
  const [resolvingConflict, setResolvingConflict] = useState<KnowledgeConflict | null>(null);

  const fetchKnowledge = async () => {
    if (!dbConnected) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await getKnowledgeSummary();
      if (res.status === "success") {
        setSummary(res.summary || null);
        setEntities(res.entities || []);
        setMetrics(res.metrics || []);
        setRules(res.rules || []);
        setConflicts(res.conflicts || []);
        if (res.metrics && res.metrics.length > 0 && !selectedMetricId) {
          setSelectedMetricId(res.metrics[0].metric_id);
        }
      } else {
        setErrorMsg(res.message || "Failed to load enterprise knowledge.");
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to connect to knowledge service.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKnowledge();
  }, [dbConnected]);

  // Load Lineage when tab changes or metric selected
  useEffect(() => {
    if (activeTab === "lineage" && selectedMetricId) {
      loadLineage(selectedMetricId);
    }
  }, [activeTab, selectedMetricId]);

  const loadLineage = async (metricId: string) => {
    setLineageLoading(true);
    try {
      const res = await getKnowledgeLineage(metricId);
      if (res.status === "success" && res.lineage) {
        setLineage(res.lineage);
      }
    } catch {
      // Graceful fallback
    } finally {
      setLineageLoading(false);
    }
  };

  const handleParseContext = async () => {
    if (!contextInput.trim()) return;
    setParsingContext(true);
    try {
      const res = await parseBusinessContext(contextInput);
      if (res.status === "success" && res.parse_result) {
        setParseResult(res.parse_result);
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to parse context statement.");
    } finally {
      setParsingContext(false);
    }
  };

  const handleConfirmItem = async (itemId: string) => {
    try {
      await confirmKnowledgeItem(itemId);
      await fetchKnowledge();
      if (parseResult && parseResult.proposed_rule?.rule_id === itemId) {
        setShowAddModal(false);
        setParseResult(null);
        setContextInput("");
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to confirm knowledge item.");
    }
  };

  const handleDisableItem = async (itemId: string) => {
    try {
      await disableKnowledgeItem(itemId);
      await fetchKnowledge();
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to disable knowledge item.");
    }
  };

  const handleResolveConflict = async (choice: string) => {
    if (!resolvingConflict) return;
    try {
      await resolveKnowledgeConflict(resolvingConflict.conflict_id, {
        resolution_choice: choice,
        resolution_notes: `Resolved via UI choice: ${choice}`,
      });
      setResolvingConflict(null);
      await fetchKnowledge();
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to resolve conflict.");
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await searchKnowledge(searchQuery);
      setSearchResult(res);
    } catch {
      setSearchResult({ found: false, answer: "Search request failed." });
    } finally {
      setSearching(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "CONFIRMED":
      case "ACTIVE":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
            <CheckCircle2 size={10} /> Confirmed
          </span>
        );
      case "PROPOSED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/15 border border-amber-500/30 text-amber-400">
            <AlertTriangle size={10} /> Proposed
          </span>
        );
      case "CONFLICTED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-rose-500/15 border border-rose-500/30 text-rose-400">
            <AlertTriangle size={10} /> Conflicted
          </span>
        );
      case "DISABLED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-500/15 border border-slate-500/30 text-slate-400">
            Disabled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-700 text-slate-300">
            {status}
          </span>
        );
    }
  };

  const getProvenanceBadge = (provenance: string) => {
    switch (provenance) {
      case "USER_PROVIDED":
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/15 border border-blue-500/30 text-blue-300">
            User Provided
          </span>
        );
      case "SCHEMA_DERIVED":
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/15 border border-purple-500/30 text-purple-300">
            Schema Fact
          </span>
        );
      case "DATA_OBSERVED":
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
            Data Observed
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400">
            {provenance}
          </span>
        );
    }
  };

  if (!dbConnected) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <BookOpen size={16} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Enterprise Knowledge & Context</h3>
            <p className="text-xs text-slate-400">
              Connect a database to explore business entities, confirmed definitions, and rule lineage.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <BookOpen size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Enterprise Knowledge & Context Intelligence
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                Phase 9.1
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Discovers business entities, binds confirmed rules to metrics, and traces evidence lineage.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-900/30 transition-all"
          >
            <Plus size={14} /> Add Business Context
          </button>
          <button
            onClick={fetchKnowledge}
            disabled={loading}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh Knowledge"
          >
            <RefreshCw size={14} className={loading ? "animate-spin text-emerald-400" : ""} />
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-[11px] text-slate-400">Discovered Entities</div>
            <div className="text-lg font-bold text-white">{summary.total_entities}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-[11px] text-slate-400">Defined Metrics</div>
            <div className="text-lg font-bold text-emerald-400">{summary.total_metrics}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-[11px] text-slate-400">Confirmed Rules</div>
            <div className="text-lg font-bold text-blue-400">{summary.confirmed_rules_count}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-[11px] text-slate-400">Proposed Rules</div>
            <div className="text-lg font-bold text-amber-400">{summary.proposed_rules_count}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <div className="text-[11px] text-slate-400">Conflicts Detected</div>
            <div className={`text-lg font-bold ${summary.conflicts_count > 0 ? "text-rose-400" : "text-slate-400"}`}>
              {summary.conflicts_count}
            </div>
          </div>
        </div>
      )}

      {/* Conflicted Rules Banner */}
      {conflicts.length > 0 && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-950/20 p-4 space-y-2">
          <div className="flex items-center gap-2 text-rose-400 text-xs font-semibold">
            <AlertTriangle size={15} /> Semantic Conflict Detected
          </div>
          <p className="text-xs text-rose-200">
            {conflicts.length} knowledge definition(s) have conflicting logic. Conflicted definitions are excluded from calculations until explicitly resolved.
          </p>
          <div className="space-y-2 mt-2">
            {conflicts.map((c) => (
              <div key={c.conflict_id} className="p-3 rounded bg-slate-900/80 border border-slate-800 flex items-center justify-between">
                <div className="text-xs space-y-0.5">
                  <div className="font-semibold text-white">{c.target_name}</div>
                  <div className="text-slate-400">{c.description}</div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-400">
                    <span>A: <code className="text-amber-300">{c.statement_a}</code></span>
                    <span>B: <code className="text-amber-300">{c.statement_b}</code></span>
                  </div>
                </div>
                <button
                  onClick={() => setResolvingConflict(c)}
                  className="px-2.5 py-1 text-xs rounded bg-rose-600 hover:bg-rose-500 text-white font-medium transition"
                >
                  Resolve
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 gap-6 text-xs">
        <button
          onClick={() => setActiveTab("context")}
          className={`pb-2.5 font-medium flex items-center gap-2 transition-all ${
            activeTab === "context"
              ? "text-emerald-400 border-b-2 border-emerald-400"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Layers size={14} /> Business Context
        </button>
        <button
          onClick={() => setActiveTab("metrics")}
          className={`pb-2.5 font-medium flex items-center gap-2 transition-all ${
            activeTab === "metrics"
              ? "text-emerald-400 border-b-2 border-emerald-400"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <FileCode size={14} /> Metrics & Definitions
        </button>
        <button
          onClick={() => setActiveTab("rules")}
          className={`pb-2.5 font-medium flex items-center gap-2 transition-all ${
            activeTab === "rules"
              ? "text-emerald-400 border-b-2 border-emerald-400"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <ShieldCheck size={14} /> Business Rules
        </button>
        <button
          onClick={() => setActiveTab("lineage")}
          className={`pb-2.5 font-medium flex items-center gap-2 transition-all ${
            activeTab === "lineage"
              ? "text-emerald-400 border-b-2 border-emerald-400"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <GitBranch size={14} /> Knowledge Lineage & Search
        </button>
      </div>

      {/* Tab 1: Business Context (Entities) */}
      {activeTab === "context" && (
        <div className="space-y-4">
          <div className="text-xs text-slate-400">
            Discovered business entities derived from database schema and table relationships. Proposed entities require confirmation.
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {entities.map((ent) => (
              <div
                key={ent.entity_id}
                className="p-4 rounded-lg border border-slate-800 bg-slate-950/40 hover:border-slate-700 transition space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm font-semibold text-white">{ent.name}</div>
                    <div className="text-xs text-slate-500 font-mono">table: {ent.table_name}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    {getStatusBadge(ent.status)}
                    {getProvenanceBadge(ent.provenance)}
                  </div>
                </div>

                <p className="text-xs text-slate-300">{ent.description}</p>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                  <span>Importance: <strong className="text-slate-200">{ent.importance}</strong></span>
                  {ent.status === "PROPOSED" && (
                    <button
                      onClick={() => handleConfirmItem(ent.entity_id)}
                      className="px-2 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 font-medium transition"
                    >
                      Confirm
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Metrics & Definitions */}
      {activeTab === "metrics" && (
        <div className="space-y-4">
          <div className="text-xs text-slate-400">
            Formulas and rule bindings. Metrics bound to confirmed business rules automatically filter calculations.
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="p-3">Metric Name</th>
                  <th className="p-3">Formula / Target</th>
                  <th className="p-3">Confirmed Filter</th>
                  <th className="p-3">Provenance</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-900/30">
                {metrics.map((m) => (
                  <tr key={m.metric_id} className="hover:bg-slate-800/30 transition">
                    <td className="p-3 font-semibold text-white">
                      {m.name}
                      <div className="text-[10px] text-slate-500 font-normal">v{m.version}</div>
                    </td>
                    <td className="p-3 text-slate-300 font-mono text-[11px]">
                      {m.aggregation}({m.table_name}.{m.column_name || "*"})
                    </td>
                    <td className="p-3">
                      {m.filter_expression ? (
                        <span className="font-mono text-emerald-300 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                          {m.filter_expression}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">No active filter</span>
                      )}
                    </td>
                    <td className="p-3">{getProvenanceBadge(m.provenance)}</td>
                    <td className="p-3">{getStatusBadge(m.status)}</td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => {
                          setSelectedMetricId(m.metric_id);
                          setActiveTab("lineage");
                        }}
                        className="text-xs text-emerald-400 hover:text-emerald-300 font-medium transition"
                      >
                        Inspect Lineage →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Business Rules */}
      {activeTab === "rules" && (
        <div className="space-y-4">
          <div className="text-xs text-slate-400">
            Rules define data exclusions, inclusions, or thresholds. Only <strong>CONFIRMED</strong> rules affect metric calculations.
          </div>
          <div className="space-y-3">
            {rules.map((r) => (
              <div
                key={r.rule_id}
                className="p-4 rounded-lg border border-slate-800 bg-slate-950/40 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white text-xs">{r.name}</span>
                    {getStatusBadge(r.status)}
                    {getProvenanceBadge(r.provenance)}
                  </div>
                  <p className="text-xs text-slate-400">{r.description}</p>
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 font-mono">
                    <span>Target: {r.target_table}.{r.target_column || "*"}</span>
                    <span>Condition: <code className="text-amber-300">{r.expression}</code></span>
                    <span>Scope: {r.scope}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {r.status === "PROPOSED" && (
                    <button
                      onClick={() => handleConfirmItem(r.rule_id)}
                      className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition"
                    >
                      Confirm & Activate
                    </button>
                  )}
                  {r.status === "CONFIRMED" && (
                    <button
                      onClick={() => handleDisableItem(r.rule_id)}
                      className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition"
                    >
                      Disable
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Knowledge Lineage & Search */}
      {activeTab === "lineage" && (
        <div className="space-y-6">
          {/* Query Search */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-3 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ask about business definitions (e.g. 'What does revenue mean?', 'Explain orders')..."
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
              />
            </div>
            <button
              type="submit"
              disabled={searching}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition"
            >
              {searching ? "Searching..." : "Search"}
            </button>
          </form>

          {searchResult && (
            <div className="p-4 rounded-lg border border-slate-800 bg-slate-950/60 space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
                <Sparkles size={14} /> Knowledge Answer
              </div>
              <p className="text-xs text-slate-200">{searchResult.answer}</p>
            </div>
          )}

          {/* Metric Selector for Lineage */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-slate-400">Select Metric to Inspect Lineage:</label>
            <select
              value={selectedMetricId}
              onChange={(e) => setSelectedMetricId(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-emerald-500"
            >
              {metrics.map((m) => (
                <option key={m.metric_id} value={m.metric_id}>
                  {m.name} ({m.table_name})
                </option>
              ))}
            </select>
          </div>

          {/* Lineage Graph Flow */}
          {lineage && (
            <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <div className="text-xs font-semibold text-white">
                  Lineage Trace: {lineage.target_name}
                </div>
                <div className="flex items-center gap-2">
                  {getStatusBadge(lineage.status)}
                  {getProvenanceBadge(lineage.provenance)}
                </div>
              </div>

              <div className="space-y-3">
                {lineage.nodes.map((node, idx) => (
                  <div key={idx} className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-xs font-bold shrink-0 mt-0.5">
                      {idx + 1}
                    </div>
                    <div className="flex-1 p-3 rounded-lg border border-slate-800/80 bg-slate-900/60 text-xs space-y-1">
                      <div className="font-semibold text-white">{node.label}</div>
                      {node.details && (
                        <div className="text-[11px] text-slate-400 font-mono">
                          {Object.entries(node.details).map(([k, v]) => (
                            <span key={k} className="mr-3">
                              {k}: <span className="text-slate-300">{JSON.stringify(v)}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {lineage.sql_expression && (
                <div className="p-3 rounded bg-slate-900 border border-slate-800 font-mono text-[11px] text-emerald-300">
                  <div className="text-[10px] text-slate-500 mb-1 uppercase tracking-wider font-sans">Resolved SQL Expression:</div>
                  {lineage.sql_expression}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Add Context Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Plus size={16} className="text-emerald-400" /> Add Business Context
              </h3>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setParseResult(null);
                  setContextInput("");
                }}
                className="text-slate-500 hover:text-slate-300"
              >
                <X size={16} />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Enter a business rule or definition in plain language. BG AI will parse the referenced schema elements and propose a structured rule requiring your confirmation.
            </p>

            <div className="space-y-2">
              <textarea
                value={contextInput}
                onChange={(e) => setContextInput(e.target.value)}
                placeholder="e.g. Cancelled orders should not count toward revenue..."
                rows={3}
                className="w-full p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                onClick={handleParseContext}
                disabled={parsingContext || !contextInput.trim()}
                className="w-full py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition"
              >
                {parsingContext ? "Parsing..." : "Parse Statement"}
              </button>
            </div>

            {/* Parsed Result Preview */}
            {parseResult && parseResult.proposed_rule && (
              <div className="p-4 rounded-lg border border-slate-800 bg-slate-950/60 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold text-white">Parsed Proposed Rule</div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-medium">
                    Awaiting Confirmation
                  </span>
                </div>

                <div className="text-xs space-y-1 font-mono text-[11px]">
                  <div>Target Table: <span className="text-slate-300">{parseResult.proposed_rule.target_table}</span></div>
                  <div>Condition: <code className="text-amber-300">{parseResult.proposed_rule.expression}</code></div>
                  <div>Affected Metrics: <span className="text-slate-300">{parseResult.affected_metrics.join(", ")}</span></div>
                </div>

                {parseResult.assumptions.length > 0 && (
                  <div className="text-[11px] text-slate-400 space-y-0.5 pt-2 border-t border-slate-800">
                    <div className="text-slate-500 font-medium">Assumptions:</div>
                    {parseResult.assumptions.map((asm, i) => (
                      <div key={i}>• {asm}</div>
                    ))}
                  </div>
                )}

                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => handleConfirmItem(parseResult.proposed_rule!.rule_id)}
                    className="flex-1 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition"
                  >
                    Confirm & Activate Rule
                  </button>
                  <button
                    onClick={() => {
                      setShowAddModal(false);
                      setParseResult(null);
                      setContextInput("");
                      fetchKnowledge();
                    }}
                    className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
                  >
                    Keep as Proposed
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Conflict Resolution Modal */}
      {resolvingConflict && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <AlertTriangle size={16} className="text-rose-400" /> Resolve Knowledge Conflict
              </h3>
              <button onClick={() => setResolvingConflict(null)} className="text-slate-500 hover:text-slate-300">
                <X size={16} />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Select which definition should take precedence for <strong>{resolvingConflict.target_name}</strong>:
            </p>

            <div className="space-y-2">
              <button
                onClick={() => handleResolveConflict("CHOOSE_A")}
                className="w-full p-3 rounded-lg border border-slate-800 bg-slate-950 text-left hover:border-emerald-500/50 transition space-y-1"
              >
                <div className="text-xs font-semibold text-white">Definition A ({resolvingConflict.source_a})</div>
                <div className="text-[11px] font-mono text-amber-300">{resolvingConflict.statement_a}</div>
              </button>

              <button
                onClick={() => handleResolveConflict("CHOOSE_B")}
                className="w-full p-3 rounded-lg border border-slate-800 bg-slate-950 text-left hover:border-emerald-500/50 transition space-y-1"
              >
                <div className="text-xs font-semibold text-white">Definition B ({resolvingConflict.source_b})</div>
                <div className="text-[11px] font-mono text-amber-300">{resolvingConflict.statement_b}</div>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EnterpriseKnowledgeSection;
