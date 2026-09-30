import React, { useEffect, useState } from "react";
import {
  Database,
  Table,
  Layers,
  Activity,
  ArrowRight,
  Sparkles,
  Plug,
  Terminal,
  BarChart3,
  Search,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Lightbulb,
  RefreshCw,
  FileCode2,
  X,
} from "lucide-react";
import type { WorkspaceTab } from "../WorkspaceSidebar";
import {
  getDatabaseInfo,
  getSchema,
  getIntelligenceReport,
  getAnomalySummary,
  getBusinessInsights,
  refreshBusinessInsights,
} from "../../../services/api";
import type { BusinessInsight } from "../../../types";

interface OverviewViewProps {
  dbConnected: boolean;
  dbType: string | null;
  onTabChange: (tab: WorkspaceTab) => void;
  onConnectDatabase: () => void;
  onRunAnalysis: () => void;
  onNavigateToAgents?: (prompt: string, agent?: string) => void;
}

export default function OverviewView({
  dbConnected,
  dbType,
  onTabChange,
  onConnectDatabase,
  onRunAnalysis,
  onNavigateToAgents,
}: OverviewViewProps) {
  const [dbInfo, setDbInfo] = useState<{
    database?: string;
    tables?: number;
    rows?: number;
    size?: string;
  }>({});
  const [tableCount, setTableCount] = useState<number>(0);
  const [tablesList, setTablesList] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [healthScore, setHealthScore] = useState<number | null>(null);
  const [anomalySummary, setAnomalySummary] = useState<{
    total: number;
    critical: number;
    warning: number;
  } | null>(null);
  const [qualityIssues, setQualityIssues] = useState<number>(0);
  const [perfIssues, setPerfIssues] = useState<number>(0);

  // Phase 8.1 Automated Business Intelligence
  const [insights, setInsights] = useState<BusinessInsight[]>([]);
  const [insightsLoading, setInsightsLoading] = useState<boolean>(false);
  const [selectedInsight, setSelectedInsight] = useState<BusinessInsight | null>(null);

  useEffect(() => {
    if (!dbConnected) {
      setDbInfo({});
      setTableCount(0);
      setTablesList([]);
      setHealthScore(null);
      setAnomalySummary(null);
      setQualityIssues(0);
      setPerfIssues(0);
      setInsights([]);
      return;
    }

    const loadData = async () => {
      setLoading(true);
      try {
        const [info, schema, report, anomaly, biResp] = await Promise.allSettled([
          getDatabaseInfo(),
          getSchema(),
          getIntelligenceReport(),
          getAnomalySummary(),
          getBusinessInsights(),
        ]);

        if (info.status === "fulfilled" && info.value) {
          setDbInfo(info.value);
        }
        if (schema.status === "fulfilled" && schema.value && typeof schema.value === "object") {
          const names = Object.keys(schema.value).filter((k) => k !== "status");
          setTablesList(names);
          setTableCount(names.length);
        }
        if (report.status === "fulfilled" && report.value) {
          const r = report.value;
          setHealthScore(r.health_score ?? null);
          setQualityIssues(
            (r.data_quality?.null_heavy_columns?.length || 0) +
            (r.data_quality?.orphan_foreign_keys?.length || 0) +
            (r.data_quality?.empty_tables?.length || 0)
          );
          setPerfIssues(r.performance_findings?.length || 0);
        }
        if (anomaly.status === "fulfilled" && anomaly.value) {
          setAnomalySummary({
            total: anomaly.value.total_count ?? anomaly.value.total ?? 0,
            critical: anomaly.value.critical_count ?? anomaly.value.critical ?? 0,
            warning: anomaly.value.warning_count ?? anomaly.value.warning ?? 0,
          });
        }
        if (biResp.status === "fulfilled" && biResp.value && biResp.value.insights) {
          setInsights(biResp.value.insights);
        }
      } catch (err) {
        console.error("Error loading overview data:", err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [dbConnected]);

  const handleRefreshInsights = async () => {
    setInsightsLoading(true);
    try {
      const resp = await refreshBusinessInsights();
      if (resp && resp.insights) {
        setInsights(resp.insights);
      }
    } catch {
      // Keep existing insights on transient error
    } finally {
      setInsightsLoading(false);
    }
  };

  // If no database connected, render professional empty state
  if (!dbConnected) {
    return (
      <div className="p-6 md:p-10 max-w-5xl mx-auto space-y-8">
        {/* Hero Banner */}
        <div className="p-8 sm:p-10 rounded-2xl bg-gradient-to-b from-[#16161f] via-[#121217] to-[#0c0c10] border border-white/[0.08] shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

          <div className="max-w-2xl space-y-4 relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs font-medium">
              <Sparkles size={13} />
              <span>AI Data Intelligence Workspace</span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-tight">
              Connect your database to start analyzing with AI.
            </h2>

            <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
              BG AI automatically profiles your tables, detects key business metrics,
              discovers revenue and volume trends, and allows you to run natural-language queries
              with complete enterprise safety.
            </p>

            <div className="pt-2 flex flex-wrap items-center gap-3">
              <button
                onClick={onConnectDatabase}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-semibold shadow-lg shadow-indigo-600/20 transition-all cursor-pointer"
              >
                <Plug size={15} />
                <span>Connect Database</span>
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-indigo-400">
              <Search size={16} />
            </div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Data Explorer
            </h3>
            <p className="text-xs text-zinc-400 leading-normal">
              Visual schema hierarchy, column types, null densities, and relationship graphs.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center text-emerald-400">
              <BarChart3 size={16} />
            </div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Auto Dashboard
            </h3>
            <p className="text-xs text-zinc-400 leading-normal">
              Instant KPI cards, trend distributions, and chart visualizations.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/25 flex items-center justify-center text-amber-400">
              <Activity size={16} />
            </div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Data Health Doctor
            </h3>
            <p className="text-xs text-zinc-400 leading-normal">
              Continuous audit of nulls, duplicates, empty tables, and orphan foreign keys.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-500/15 border border-sky-500/25 flex items-center justify-center text-sky-400">
              <Terminal size={16} />
            </div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              AI SQL Lab
            </h3>
            <p className="text-xs text-zinc-400 leading-normal">
              Interactive query IDE with AI optimizer, validator, and results viewer.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Database is connected: Render full BI overview
  const totalRows = dbInfo.rows || 0;
  const dbEngine = (dbType || "Connected DB").toUpperCase();

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Top Banner Status */}
      <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
            <Database size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white tracking-tight">
                {dbInfo.database || "Active Database"}
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold">
                LIVE {dbEngine}
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Connected and synchronized for AI analysis and visual queries.
            </p>
          </div>
        </div>

        <button
          onClick={onRunAnalysis}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer shrink-0"
        >
          <Sparkles size={14} />
          <span>Analyze Business with AI</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Total Tables</span>
            <Table size={15} className="text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-white font-mono">
            {tableCount > 0 ? tableCount.toLocaleString() : "-"}
          </p>
          <p className="text-[11px] text-zinc-400">Live schema entities</p>
        </div>

        <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Total Records</span>
            <Layers size={15} className="text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white font-mono">
            {totalRows > 0 ? totalRows.toLocaleString() : "Profiled"}
          </p>
          <p className="text-[11px] text-zinc-400">Verified row counts</p>
        </div>

        <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Data Health</span>
            <ShieldCheck size={15} className="text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-emerald-400 font-mono">
            {healthScore !== null ? `${healthScore}/100` : "Healthy"}
          </p>
          <p className="text-[11px] text-zinc-400">
            {qualityIssues > 0 ? `${qualityIssues} items flagged` : "Zero critical issues"}
          </p>
        </div>

        <div className="p-5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Engine</span>
            <Activity size={15} className="text-sky-400" />
          </div>
          <p className="text-2xl font-bold text-white font-mono">{dbEngine}</p>
          <p className="text-[11px] text-zinc-400">SQLAlchemy driver</p>
        </div>
      </div>

      {/* Phase 8.1: Automated Business Intelligence Insights */}
      {insights.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Lightbulb size={14} />
              </div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Automated Business Insights
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.06] text-zinc-300">
                {insights.length} Verified
              </span>
            </div>

            <button
              onClick={handleRefreshInsights}
              disabled={insightsLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 text-xs font-medium transition-all cursor-pointer disabled:opacity-50"
            >
              <RefreshCw size={12} className={insightsLoading ? "animate-spin text-indigo-400" : ""} />
              <span>Refresh Insights</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {insights.slice(0, 4).map((ins) => {
              const severityColor =
                ins.severity === "CRITICAL"
                  ? "bg-rose-500/15 border-rose-500/30 text-rose-300"
                  : ins.severity === "WARNING"
                  ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
                  : "bg-blue-500/15 border-blue-500/30 text-blue-300";

              return (
                <div
                  key={ins.id}
                  className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] hover:border-white/[0.16] transition-all flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-white/[0.06] text-zinc-300">
                        {ins.category}
                      </span>
                      <span className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${severityColor}`}>
                        {ins.severity}
                      </span>
                    </div>

                    <h4 className="text-sm font-bold text-white tracking-tight">
                      {ins.title}
                    </h4>

                    <p className="text-xs text-zinc-300 leading-relaxed">
                      {ins.summary}
                    </p>

                    {ins.recommended_next_step && (
                      <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.05] text-[11px] text-zinc-400">
                        <strong className="text-zinc-200">Recommended Next Step: </strong>
                        {ins.recommended_next_step}
                      </div>
                    )}
                  </div>

                  <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
                    <button
                      onClick={() => setSelectedInsight(ins)}
                      className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1.5 cursor-pointer"
                    >
                      <FileCode2 size={13} />
                      <span>Inspect Evidence & SQL</span>
                    </button>

                    {onNavigateToAgents && (
                      <button
                        onClick={() =>
                          onNavigateToAgents(
                            `Analyze and act on insight: ${ins.title}. Recommended action: ${ins.recommended_next_step}`
                          )
                        }
                        className="text-[11px] text-zinc-400 hover:text-white inline-flex items-center gap-1 cursor-pointer transition-colors"
                      >
                        <span>Take Action</span>
                        <ArrowRight size={11} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Quick Action Buttons */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
          Workspace Quick Actions
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <button
            onClick={onRunAnalysis}
            className="p-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] hover:border-indigo-500/30 text-left transition-all cursor-pointer group"
          >
            <Sparkles size={16} className="text-indigo-400 mb-2 group-hover:scale-110 transition-transform" />
            <p className="text-xs font-bold text-white truncate">AI Analyst</p>
            <p className="text-[10px] text-zinc-400 mt-0.5 truncate">Full business audit</p>
          </button>

          <button
            onClick={() => onTabChange("explorer")}
            className="p-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] hover:border-indigo-500/30 text-left transition-all cursor-pointer group"
          >
            <Search size={16} className="text-sky-400 mb-2 group-hover:scale-110 transition-transform" />
            <p className="text-xs font-bold text-white truncate">Explore Data</p>
            <p className="text-[10px] text-zinc-400 mt-0.5 truncate">Inspect tables & columns</p>
          </button>

          <button
            onClick={() => onTabChange("analytics")}
            className="p-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] hover:border-indigo-500/30 text-left transition-all cursor-pointer group"
          >
            <BarChart3 size={16} className="text-emerald-400 mb-2 group-hover:scale-110 transition-transform" />
            <p className="text-xs font-bold text-white truncate">Dashboards</p>
            <p className="text-[10px] text-zinc-400 mt-0.5 truncate">Visual charts & metrics</p>
          </button>

          <button
            onClick={() => onTabChange("sqllab")}
            className="p-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] hover:border-indigo-500/30 text-left transition-all cursor-pointer group"
          >
            <Terminal size={16} className="text-amber-400 mb-2 group-hover:scale-110 transition-transform" />
            <p className="text-xs font-bold text-white truncate">SQL Lab</p>
            <p className="text-[10px] text-zinc-400 mt-0.5 truncate">Write & optimize SQL</p>
          </button>

          <button
            onClick={() => onTabChange("health")}
            className="p-3.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] hover:border-indigo-500/30 text-left transition-all cursor-pointer group"
          >
            <Activity size={16} className="text-rose-400 mb-2 group-hover:scale-110 transition-transform" />
            <p className="text-xs font-bold text-white truncate">Data Health</p>
            <p className="text-[10px] text-zinc-400 mt-0.5 truncate">Diagnostics & clean up</p>
          </button>
        </div>
      </div>

      {/* Discovered Tables Grid */}
      {tablesList.length > 0 && (
        <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span>Discovered Database Tables</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.06] text-zinc-400">
                {tablesList.length} Tables
              </span>
            </h3>

            <button
              onClick={() => onTabChange("explorer")}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1 cursor-pointer"
            >
              <span>View All</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
            {tablesList.slice(0, 9).map((tableName) => (
              <button
                key={tableName}
                onClick={() => onTabChange("explorer")}
                className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] text-left transition-all cursor-pointer group"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Table size={14} className="text-indigo-400 shrink-0" />
                  <span className="text-xs font-medium text-zinc-200 group-hover:text-white truncate">
                    {tableName}
                  </span>
                </div>
                <ArrowRight
                  size={12}
                  className="text-zinc-500 group-hover:text-white group-hover:translate-x-0.5 transition-all shrink-0 ml-2"
                />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Evidence & SQL Inspection Modal */}
      {selectedInsight && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[#121216] border border-white/10 shadow-2xl p-6 space-y-4 text-left">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-white/[0.06] text-zinc-300">
                  {selectedInsight.category}
                </span>
                <h3 className="text-base font-bold text-white mt-1.5">
                  {selectedInsight.title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedInsight(null)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <p className="text-xs text-zinc-300 leading-relaxed">
              {selectedInsight.summary}
            </p>

            {/* Lineage SQL */}
            {selectedInsight.sql && (
              <div className="space-y-1.5">
                <p className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                  Reproducible SQL Query
                </p>
                <div className="p-3 rounded-xl bg-black/50 border border-white/[0.06] font-mono text-xs text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                  {selectedInsight.sql}
                </div>
              </div>
            )}

            {/* Structured Evidence */}
            {selectedInsight.evidence && Object.keys(selectedInsight.evidence).length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                  Verified Evidence
                </p>
                <div className="p-3 rounded-xl bg-black/40 border border-white/[0.06] font-mono text-[11px] text-zinc-300 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(selectedInsight.evidence, null, 2)}
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-white/[0.08] flex justify-end">
              <button
                onClick={() => setSelectedInsight(null)}
                className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-white transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
