import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  ShieldAlert,
  AlertCircle,
  Info,
  CheckCircle2,
  Plug,
  RefreshCw,
  Search,
  Terminal,
  Sparkles,
  ArrowRight,
  Filter,
  Layers,
  Database,
  Calendar,
} from "lucide-react";
import type { WorkspaceTab } from "../WorkspaceSidebar";
import type { AnomalyFinding, AnomalyScanReport } from "../../../types";
import { getAnomalyReport } from "../../../services/api";

interface AnomalyCenterViewProps {
  dbConnected: boolean;
  onConnectDatabase: () => void;
  onTabChange?: (tab: WorkspaceTab) => void;
  onOpenSqlLabWithQuery?: (query: string) => void;
  onOpenExplorerWithTable?: (tableName: string) => void;
  onRunAnalysis?: (question?: string) => void;
}

export default function AnomalyCenterView({
  dbConnected,
  onConnectDatabase,
  onTabChange,
  onOpenSqlLabWithQuery,
  onOpenExplorerWithTable,
  onRunAnalysis,
}: AnomalyCenterViewProps) {
  const [report, setReport] = useState<AnomalyScanReport | null>(null);
  const [activeFilter, setActiveFilter] = useState<"ALL" | "CRITICAL" | "WARNING" | "INFO">("ALL");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnomalies = async (forceRefresh = false) => {
    if (!dbConnected) {
      setReport(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getAnomalyReport(forceRefresh);
      setReport(data);
    } catch (err: any) {
      setError(err.message || "Failed to scan for anomalies.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnomalies(false);
  }, [dbConnected]);

  if (!dbConnected) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl shadow-xl">
        <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 mx-auto">
          <AlertTriangle size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your database to run automatic anomaly detection across numeric measures, temporal changes, and data quality integrity.
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

  const anomalies = report?.anomalies || [];
  const filteredAnomalies = anomalies.filter((a) => {
    if (activeFilter === "ALL") return true;
    return a.severity === activeFilter;
  });

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-[#141218] via-[#16141a] to-[#121216] border border-white/[0.08] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1.5 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] font-medium">
            <AlertTriangle size={12} />
            <span>Explainable Outlier & Drift Detection</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
            Anomaly Center
          </h2>
          <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
            Continuous statistical audit detecting numeric outliers (IQR), sudden chronological shifts, and relational integrity breaches.
          </p>
        </div>

        <button
          onClick={() => fetchAnomalies(true)}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-200 text-xs font-semibold transition-all cursor-pointer shrink-0"
        >
          <RefreshCw size={13} className={loading ? "animate-spin text-indigo-400" : ""} />
          <span>{loading ? "Scanning..." : "Rescan Database"}</span>
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div
          onClick={() => setActiveFilter("ALL")}
          className={`p-4 rounded-xl border transition-all cursor-pointer ${
            activeFilter === "ALL"
              ? "bg-white/[0.06] border-white/20 shadow-md"
              : "bg-[#121216] border-white/[0.06] hover:border-white/[0.12]"
          }`}
        >
          <div className="flex items-center justify-between text-zinc-400 text-xs">
            <span>Total Anomalies</span>
            <Filter size={14} className="text-zinc-400" />
          </div>
          <p className="text-2xl font-bold text-white font-mono mt-1">
            {report?.total_anomalies ?? 0}
          </p>
          <p className="text-[10px] text-zinc-500">All severity levels</p>
        </div>

        <div
          onClick={() => setActiveFilter("CRITICAL")}
          className={`p-4 rounded-xl border transition-all cursor-pointer ${
            activeFilter === "CRITICAL"
              ? "bg-rose-500/[0.1] border-rose-500/40 shadow-md shadow-rose-500/10"
              : "bg-[#121216] border-white/[0.06] hover:border-rose-500/20"
          }`}
        >
          <div className="flex items-center justify-between text-rose-400 text-xs">
            <span>Critical</span>
            <ShieldAlert size={14} className="text-rose-400" />
          </div>
          <p className="text-2xl font-bold text-rose-400 font-mono mt-1">
            {report?.critical_count ?? 0}
          </p>
          <p className="text-[10px] text-zinc-500">Integrity breaches</p>
        </div>

        <div
          onClick={() => setActiveFilter("WARNING")}
          className={`p-4 rounded-xl border transition-all cursor-pointer ${
            activeFilter === "WARNING"
              ? "bg-amber-500/[0.1] border-amber-500/40 shadow-md shadow-amber-500/10"
              : "bg-[#121216] border-white/[0.06] hover:border-amber-500/20"
          }`}
        >
          <div className="flex items-center justify-between text-amber-400 text-xs">
            <span>Warnings</span>
            <AlertTriangle size={14} className="text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-amber-400 font-mono mt-1">
            {report?.warning_count ?? 0}
          </p>
          <p className="text-[10px] text-zinc-500">Severe outliers & drops</p>
        </div>

        <div
          onClick={() => setActiveFilter("INFO")}
          className={`p-4 rounded-xl border transition-all cursor-pointer ${
            activeFilter === "INFO"
              ? "bg-sky-500/[0.1] border-sky-500/40 shadow-md shadow-sky-500/10"
              : "bg-[#121216] border-white/[0.06] hover:border-sky-500/20"
          }`}
        >
          <div className="flex items-center justify-between text-sky-400 text-xs">
            <span>Informational</span>
            <Info size={14} className="text-sky-400" />
          </div>
          <p className="text-2xl font-bold text-sky-400 font-mono mt-1">
            {report?.info_count ?? 0}
          </p>
          <p className="text-[10px] text-zinc-500">Minor deviations</p>
        </div>
      </div>

      {/* Filter Tabs & Count */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#121216] border border-white/[0.06]">
          {(["ALL", "CRITICAL", "WARNING", "INFO"] as const).map((lvl) => (
            <button
              key={lvl}
              onClick={() => setActiveFilter(lvl)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeFilter === lvl
                  ? "bg-white/[0.1] text-white shadow"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>

        <span className="text-xs text-zinc-500 font-mono">
          Showing {filteredAnomalies.length} of {anomalies.length} items
        </span>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Anomaly Cards Grid */}
      {loading ? (
        <div className="p-12 text-center text-xs text-zinc-500 space-y-2">
          <RefreshCw size={18} className="animate-spin text-indigo-400 mx-auto" />
          <p>Running statistical and integrity scans...</p>
        </div>
      ) : filteredAnomalies.length === 0 ? (
        <div className="p-12 rounded-2xl bg-[#121216] border border-white/[0.06] text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mx-auto">
            <CheckCircle2 size={24} />
          </div>
          <h4 className="text-sm font-bold text-white">All Systems Healthy</h4>
          <p className="text-xs text-zinc-400 max-w-md mx-auto">
            No anomalies detected matching filter "{activeFilter}". All scanned numerical distributions and relationships align with standard baseline thresholds.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredAnomalies.map((item) => {
            const isCrit = item.severity === "CRITICAL";
            const isWarn = item.severity === "WARNING";

            return (
              <div
                key={item.id}
                className="p-5 rounded-2xl bg-[#121216] border border-white/[0.06] hover:border-white/[0.12] transition-all space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className={`text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full border ${
                        isCrit
                          ? "bg-rose-500/10 border-rose-500/30 text-rose-400"
                          : isWarn
                          ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                          : "bg-sky-500/10 border-sky-500/30 text-sky-400"
                      }`}
                    >
                      {item.severity}
                    </span>

                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-400">
                      {item.detection_method}
                    </span>

                    <h4 className="text-sm font-bold text-white truncate">{item.metric}</h4>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
                    <span className="px-2 py-0.5 rounded bg-black/40 border border-white/[0.04]">
                      {item.table}{item.column ? `.${item.column}` : ""}
                    </span>
                    {item.time_period && (
                      <span className="flex items-center gap-1 text-[11px] text-zinc-500">
                        <Calendar size={11} />
                        <span>{item.time_period}</span>
                      </span>
                    )}
                  </div>
                </div>

                {/* Evidence Metrics */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 p-3 rounded-xl bg-white/[0.015] border border-white/[0.04] text-xs">
                  <div className="space-y-0.5">
                    <p className="text-[10px] uppercase font-semibold text-zinc-500">Observed Value</p>
                    <p className="font-bold text-white font-mono">
                      {typeof item.observed_value === "number"
                        ? item.observed_value.toLocaleString()
                        : String(item.observed_value || "-")}
                    </p>
                  </div>

                  <div className="space-y-0.5">
                    <p className="text-[10px] uppercase font-semibold text-zinc-500">Expected Baseline</p>
                    <p className="font-mono text-zinc-300">
                      {typeof item.expected_value === "number"
                        ? item.expected_value.toLocaleString()
                        : String(item.expected_value || "-")}
                    </p>
                  </div>

                  <div className="space-y-0.5">
                    <p className="text-[10px] uppercase font-semibold text-zinc-500">Variance / Deviation</p>
                    <p
                      className={`font-mono font-semibold ${
                        isCrit ? "text-rose-400" : isWarn ? "text-amber-400" : "text-sky-400"
                      }`}
                    >
                      {item.deviation_str || "-"}
                    </p>
                  </div>
                </div>

                {/* Explanation */}
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {item.explanation}
                </p>

                {/* Action Buttons */}
                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-white/[0.04]">
                  {onOpenExplorerWithTable && (
                    <button
                      onClick={() => onOpenExplorerWithTable(item.table)}
                      className="px-3 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-[11px] font-medium text-zinc-300 inline-flex items-center gap-1.5 cursor-pointer transition-all"
                    >
                      <Search size={12} className="text-sky-400" />
                      <span>Inspect '{item.table}' in Explorer</span>
                    </button>
                  )}

                  {onOpenSqlLabWithQuery && (
                    <button
                      onClick={() =>
                        onOpenSqlLabWithQuery(
                          `SELECT * FROM "${item.table}" ${item.column ? `WHERE "${item.column}" IS NOT NULL` : ""} LIMIT 50;`
                        )
                      }
                      className="px-3 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-[11px] font-medium text-zinc-300 inline-flex items-center gap-1.5 cursor-pointer transition-all"
                    >
                      <Terminal size={12} className="text-indigo-400" />
                      <span>Query in SQL Lab</span>
                    </button>
                  )}

                  {onRunAnalysis && (
                    <button
                      onClick={() =>
                        onRunAnalysis(
                          `Analyze anomaly: why is ${item.metric} unusual in ${item.table}?`
                        )
                      }
                      className="px-3 py-1.5 rounded-lg bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/20 text-[11px] font-semibold text-indigo-300 inline-flex items-center gap-1.5 cursor-pointer transition-all ml-auto"
                    >
                      <Sparkles size={12} />
                      <span>Investigate with AI Analyst</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
