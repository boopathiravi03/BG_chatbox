import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  RefreshCw,
  GitMerge,
  FileCode2,
  ShieldAlert,
  ArrowRight,
  X,
  ExternalLink,
  SlidersHorizontal,
  Clock,
  Database,
} from "lucide-react";
import {
  getProactiveAlerts,
  evaluateProactive,
  acknowledgeProactiveAlert,
  resolveProactiveAlert,
  proposeProactiveAction,
  getAnomalySummary,
  getAuthToken,
} from "../../../services/api";
import type {
  ProactiveAlert,
  ProactiveActionProposal,
  AnomalySummary,
} from "../../../types";

interface ProactiveIntelligenceSectionProps {
  dbConnected: boolean;
  activeDbName?: string;
  activeConnectionId?: string | null;
  onConnectDatabase: () => void;
  onNavigateToAgents?: (prompt: string, agent?: string) => void;
  onNavigateToAnomalyCenter?: () => void;
  onScanCompleted?: () => void;
}

export type ScanState =
  | "not_scanned"
  | "scanning"
  | "completed_no_findings"
  | "completed_with_findings"
  | "scan_failed";

export default function ProactiveIntelligenceSection({
  dbConnected,
  activeDbName,
  activeConnectionId,
  onConnectDatabase,
  onNavigateToAgents,
  onNavigateToAnomalyCenter,
  onScanCompleted,
}: ProactiveIntelligenceSectionProps) {
  const [alerts, setAlerts] = useState<ProactiveAlert[]>([]);
  const [anomalySummary, setAnomalySummary] = useState<AnomalySummary | null>(null);
  const [scanState, setScanState] = useState<ScanState>("not_scanned");
  const [loading, setLoading] = useState<boolean>(false);
  const [scanning, setScanning] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"ACTIVE" | "ALL" | "RESOLVED">("ACTIVE");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");

  // Modals state
  const [selectedAlert, setSelectedAlert] = useState<ProactiveAlert | null>(null);
  const [actionProposal, setActionProposal] = useState<{
    proposal: ProactiveActionProposal;
    alertTitle: string;
  } | null>(null);
  const [proposingActionId, setProposingActionId] = useState<string | null>(null);

  // Fetch unified alerts and anomaly summary for active database
  const fetchData = useCallback(async (forceRefresh = false) => {
    if (!dbConnected || !getAuthToken()) {
      setAlerts([]);
      setAnomalySummary(null);
      setScanState("not_scanned");
      return;
    }
    setLoading(true);
    setErrorMessage(null);
    try {
      const [alertsResp, anomResp] = await Promise.allSettled([
        getProactiveAlerts({ limit: 50 }),
        getAnomalySummary(forceRefresh, activeConnectionId),
      ]);

      let loadedAlerts: ProactiveAlert[] = [];
      if (alertsResp.status === "fulfilled" && alertsResp.value && Array.isArray(alertsResp.value.alerts)) {
        loadedAlerts = alertsResp.value.alerts;
        setAlerts(loadedAlerts);
      }

      if (anomResp.status === "fulfilled" && anomResp.value) {
        const summary = anomResp.value;
        setAnomalySummary(summary);
        const total = summary.total_anomalies ?? summary.total_count ?? summary.total ?? 0;
        if (summary.scan_state) {
          setScanState(summary.scan_state as ScanState);
        } else {
          setScanState(total > 0 || loadedAlerts.length > 0 ? "completed_with_findings" : "completed_no_findings");
        }
      } else if (loadedAlerts.length > 0) {
        setScanState("completed_with_findings");
      } else {
        setScanState("completed_no_findings");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load proactive alerts.");
      setScanState("scan_failed");
    } finally {
      setLoading(false);
    }
  }, [dbConnected, activeConnectionId]);

  useEffect(() => {
    fetchData(false);
  }, [fetchData]);

  // Handle on-demand proactive scan
  const handleScanNow = async () => {
    if (scanning || !dbConnected) return;
    setScanning(true);
    setScanState("scanning");
    setErrorMessage(null);
    try {
      const [evalResp, anomResp] = await Promise.allSettled([
        evaluateProactive(),
        getAnomalySummary(true, activeConnectionId),
      ]);

      let loadedAlerts: ProactiveAlert[] = [];
      if (evalResp.status === "fulfilled" && evalResp.value) {
        const resp = evalResp.value;
        if (resp.status === "disconnected") {
          setErrorMessage("Database is currently disconnected. Please connect a database.");
          setAlerts([]);
        } else if (resp.status === "insufficient_data") {
          // Insufficient historical records for time-series shifts, but anomalies may still be discovered
        } else if (resp.alerts) {
          loadedAlerts = resp.alerts;
          setAlerts(loadedAlerts);
        }
      }

      if (anomResp.status === "fulfilled" && anomResp.value) {
        const summary = anomResp.value;
        setAnomalySummary(summary);
        const total = summary.total_anomalies ?? summary.total_count ?? summary.total ?? 0;
        setScanState(total > 0 || loadedAlerts.length > 0 ? "completed_with_findings" : "completed_no_findings");
      } else if (loadedAlerts.length > 0) {
        setScanState("completed_with_findings");
      } else {
        setScanState("completed_no_findings");
      }
      onScanCompleted?.();
    } catch (err: any) {
      if (err.message && err.message.includes("429")) {
        setErrorMessage("Scan rate limit reached (max 10 scans/min). Please try again shortly.");
      } else {
        setErrorMessage(err.message || "Proactive scan failed.");
      }
      setScanState("scan_failed");
    } finally {
      setScanning(false);
    }
  };

  // Handle acknowledge
  const handleAcknowledge = async (alertId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      const resp = await acknowledgeProactiveAlert(alertId);
      if (resp?.alert) {
        setAlerts((prev) =>
          prev.map((a) => (a.alert_id === alertId ? resp.alert : a))
        );
        if (selectedAlert?.alert_id === alertId) {
          setSelectedAlert(resp.alert);
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to acknowledge alert.");
    }
  };

  // Handle resolve
  const handleResolve = async (alertId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      const resp = await resolveProactiveAlert(alertId);
      if (resp?.alert) {
        setAlerts((prev) =>
          prev.map((a) => (a.alert_id === alertId ? resp.alert : a))
        );
        if (selectedAlert?.alert_id === alertId) {
          setSelectedAlert(resp.alert);
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to resolve alert.");
    }
  };

  // Handle Prepare Safe Action proposal
  const handlePrepareAction = async (alert: ProactiveAlert, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setProposingActionId(alert.alert_id);
    try {
      const resp = await proposeProactiveAction(alert.alert_id);
      if (resp.available && resp.proposal) {
        setActionProposal({
          proposal: resp.proposal,
          alertTitle: alert.title,
        });
      } else {
        setErrorMessage(resp.reason || "No supported safe action is available for this alert.");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to prepare action proposal.");
    } finally {
      setProposingActionId(null);
    }
  };

  // Filtered alerts
  const filteredAlerts = alerts.filter((a) => {
    if (statusFilter === "ACTIVE" && a.status === "RESOLVED") return false;
    if (statusFilter === "RESOLVED" && a.status !== "RESOLVED") return false;
    if (severityFilter !== "ALL" && a.severity.toUpperCase() !== severityFilter) return false;
    return true;
  });

  // Accurate Summary Counts strictly derived from API responses
  const activeAlerts = alerts.filter((a) => a.status !== "RESOLVED");

  // Derived from unified anomaly summary or active alerts
  const totalAnomalies =
    anomalySummary?.total_anomalies ??
    anomalySummary?.total_count ??
    anomalySummary?.total ??
    0;
  const totalActive = Math.max(totalAnomalies, activeAlerts.length);

  const criticalCount = Math.max(
    anomalySummary?.critical_count ?? anomalySummary?.critical ?? 0,
    activeAlerts.filter((a) => a.severity.toUpperCase() === "CRITICAL").length
  );

  const warningCount = Math.max(
    anomalySummary?.warning_count ?? anomalySummary?.warning ?? 0,
    activeAlerts.filter((a) => a.severity.toUpperCase() === "WARNING").length
  );

  const infoCount = Math.max(
    anomalySummary?.info_count ?? anomalySummary?.info ?? 0,
    activeAlerts.filter((a) => a.severity.toUpperCase() === "INFO").length
  );

  const connectionIdentity =
    anomalySummary?.database_name && anomalySummary.database_name !== "Not Connected"
      ? anomalySummary.database_name
      : activeDbName || "Active Database";

  const scanTimestamp = anomalySummary?.scan_timestamp;

  const formatTimestamp = (ts?: string | null) => {
    if (!ts) return null;
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return ts;
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return ts;
    }
  };

  // Safe helper to render evidence values without ever rendering an object directly into JSX
  const renderSafeValue = (val: any): React.ReactNode => {
    if (val === null || val === undefined) {
      return <span className="text-zinc-500 italic">null</span>;
    }
    if (typeof val === "boolean") {
      return <span>{val ? "true" : "false"}</span>;
    }
    if (typeof val === "number") {
      return <span>{val.toLocaleString()}</span>;
    }
    if (typeof val === "string") {
      return <span>{val}</span>;
    }
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
          <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
            <Sparkles size={20} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-tight">
              Proactive Intelligence
            </h3>
            <p className="text-xs text-zinc-400">
              Connect a database to enable on-demand proactive detection and anomaly scanning.
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
      {/* Section Header */}
      <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
            <Sparkles size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-bold text-white tracking-tight">
                Proactive Intelligence
              </h3>
              {/* Scan State Badge */}
              {scanState === "scanning" ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 font-semibold flex items-center gap-1">
                  <RefreshCw size={10} className="animate-spin" /> SCANNING...
                </span>
              ) : scanState === "completed_with_findings" ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 font-semibold">
                  SCAN COMPLETED ({totalActive} FINDINGS)
                </span>
              ) : scanState === "completed_no_findings" ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold">
                  SCAN COMPLETED (CLEAN)
                </span>
              ) : scanState === "scan_failed" ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-300 font-semibold">
                  SCAN FAILED
                </span>
              ) : (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-500/15 border border-zinc-500/30 text-zinc-400 font-semibold">
                  NOT SCANNED
                </span>
              )}

              {/* Active Connection Identity */}
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-300 flex items-center gap-1">
                <Database size={11} className="text-zinc-400" />
                <span>{connectionIdentity}</span>
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs text-zinc-400 mt-1 flex-wrap">
              <span>Detected changes and data-quality issues in your connected data.</span>
              {scanTimestamp && (
                <span className="text-[11px] text-zinc-500 font-mono flex items-center gap-1">
                  <Clock size={11} />
                  <span>Last scan: {formatTimestamp(scanTimestamp)}</span>
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end md:self-center">
          {onNavigateToAnomalyCenter && (
            <button
              onClick={onNavigateToAnomalyCenter}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 hover:text-white text-xs font-medium transition-all cursor-pointer"
            >
              <span>Anomaly Center</span>
              <ArrowRight size={12} />
            </button>
          )}

          <button
            onClick={handleScanNow}
            disabled={scanning}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            <RefreshCw size={13} className={scanning ? "animate-spin text-white" : ""} />
            <span>{scanning ? "Scanning Data..." : "Scan Now"}</span>
          </button>
        </div>
      </div>

      {/* Error banner if present */}
      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-between gap-3 text-xs text-rose-300">
          <div className="flex items-center gap-2">
            <AlertCircle size={15} className="shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-rose-400 hover:text-white p-1"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Summary KPI Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div
          onClick={() => onNavigateToAnomalyCenter?.()}
          className={`p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] flex items-center justify-between ${
            onNavigateToAnomalyCenter ? "hover:border-white/[0.15] cursor-pointer" : ""
          }`}
        >
          <div className="space-y-0.5">
            <span className="text-[11px] text-zinc-400">Total Active</span>
            <p className="text-xl font-bold font-mono text-white">{totalActive}</p>
          </div>
          <div className="w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-zinc-300">
            <SlidersHorizontal size={15} />
          </div>
        </div>

        <div
          onClick={() => onNavigateToAnomalyCenter?.()}
          className={`p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] flex items-center justify-between ${
            onNavigateToAnomalyCenter ? "hover:border-rose-500/30 cursor-pointer" : ""
          }`}
        >
          <div className="space-y-0.5">
            <span className="text-[11px] text-rose-400 font-medium">Critical</span>
            <p className="text-xl font-bold font-mono text-rose-400">{criticalCount}</p>
          </div>
          <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
            <ShieldAlert size={15} />
          </div>
        </div>

        <div
          onClick={() => onNavigateToAnomalyCenter?.()}
          className={`p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] flex items-center justify-between ${
            onNavigateToAnomalyCenter ? "hover:border-amber-500/30 cursor-pointer" : ""
          }`}
        >
          <div className="space-y-0.5">
            <span className="text-[11px] text-amber-400 font-medium">Warning</span>
            <p className="text-xl font-bold font-mono text-amber-400">{warningCount}</p>
          </div>
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <AlertTriangle size={15} />
          </div>
        </div>

        <div
          onClick={() => onNavigateToAnomalyCenter?.()}
          className={`p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] flex items-center justify-between ${
            onNavigateToAnomalyCenter ? "hover:border-sky-500/30 cursor-pointer" : ""
          }`}
        >
          <div className="space-y-0.5">
            <span className="text-[11px] text-sky-400 font-medium">Informational</span>
            <p className="text-xl font-bold font-mono text-sky-400">{infoCount}</p>
          </div>
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Info size={15} />
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      {alerts.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 pb-1">
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            {(["ACTIVE", "ALL", "RESOLVED"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setStatusFilter(tab)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                  statusFilter === tab
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {tab === "ACTIVE" ? `Active (${totalActive})` : tab === "RESOLVED" ? "Resolved" : `All (${alerts.length})`}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            {["ALL", "CRITICAL", "WARNING", "INFO"].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-mono font-medium transition-all cursor-pointer ${
                  severityFilter === sev
                    ? "bg-white/[0.1] text-white"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* State: Not Scanned */}
      {scanState === "not_scanned" && !loading && (
        <div className="p-8 rounded-2xl bg-[#121216] border border-white/[0.06] text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-zinc-500/10 border border-zinc-500/20 flex items-center justify-center text-zinc-400 mx-auto">
            <Sparkles size={24} />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h4 className="text-sm font-bold text-white">Database Not Scanned Yet</h4>
            <p className="text-xs text-zinc-400">
              Run an initial proactive scan to inspect null density, numeric distributions, and referential integrity across your tables.
            </p>
          </div>
          <div className="pt-2">
            <button
              onClick={handleScanNow}
              disabled={scanning}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition-all cursor-pointer shadow-md shadow-indigo-600/20"
            >
              <RefreshCw size={13} className={scanning ? "animate-spin text-white" : ""} />
              <span>{scanning ? "Scanning..." : "Scan Database Now"}</span>
            </button>
          </div>
        </div>
      )}

      {/* State: Scanning */}
      {scanState === "scanning" && (
        <div className="p-8 rounded-2xl bg-[#121216] border border-white/[0.06] text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mx-auto animate-pulse">
            <RefreshCw size={24} className="animate-spin text-indigo-400" />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h4 className="text-sm font-bold text-white">Scanning Database...</h4>
            <p className="text-xs text-zinc-400">
              Evaluating statistical measures, outlier boundaries, and referential constraints in {connectionIdentity}...
            </p>
          </div>
        </div>
      )}

      {/* State: Scan Failed */}
      {scanState === "scan_failed" && !scanning && (
        <div className="p-8 rounded-2xl bg-[#121216] border border-rose-500/20 text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 mx-auto">
            <AlertTriangle size={24} />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h4 className="text-sm font-bold text-white">Scan Failed</h4>
            <p className="text-xs text-rose-300">
              {errorMessage || "An error occurred while evaluating database metrics."}
            </p>
          </div>
          <div className="pt-2">
            <button
              onClick={handleScanNow}
              disabled={scanning}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] text-xs font-semibold text-white transition-all cursor-pointer"
            >
              <RefreshCw size={13} className={scanning ? "animate-spin text-white" : ""} />
              <span>Retry Scan</span>
            </button>
          </div>
        </div>
      )}

      {/* State: Completed Clean (No findings) */}
      {scanState === "completed_no_findings" && totalActive === 0 && !loading && (
        <div className="p-8 rounded-2xl bg-[#121216] border border-white/[0.06] text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mx-auto">
            <CheckCircle2 size={24} />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h4 className="text-sm font-bold text-white">No significant issues detected.</h4>
            <p className="text-xs text-zinc-400">
              All scanned tables in {connectionIdentity} passed statistical validation with zero integrity breaches or outliers.
            </p>
          </div>
          <div className="pt-2">
            <button
              onClick={handleScanNow}
              disabled={scanning}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] text-xs font-semibold text-white transition-all cursor-pointer"
            >
              <RefreshCw size={13} className={scanning ? "animate-spin text-white" : ""} />
              <span>{scanning ? "Scanning..." : "Re-run Proactive Scan"}</span>
            </button>
          </div>
        </div>
      )}

      {/* State: Completed with Findings, but alerts store is empty while anomaly detector found issues */}
      {totalActive > 0 && alerts.length === 0 && !loading && (
        <div className="p-6 rounded-2xl bg-[#121216] border border-amber-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 shrink-0">
              <AlertTriangle size={20} />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">
                {totalActive} Anomaly Finding{totalActive > 1 ? "s" : ""} Detected
              </h4>
              <p className="text-xs text-zinc-400">
                Found {criticalCount} critical, {warningCount} warning, and {infoCount} informational findings across active tables.
              </p>
            </div>
          </div>
          {onNavigateToAnomalyCenter && (
            <button
              onClick={onNavigateToAnomalyCenter}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-md shadow-amber-600/20 transition-all cursor-pointer shrink-0"
            >
              <span>Inspect in Anomaly Center</span>
              <ArrowRight size={13} />
            </button>
          )}
        </div>
      )}

      {/* Filtered Empty State */}
      {alerts.length > 0 && filteredAlerts.length === 0 && (
        <div className="p-6 rounded-2xl bg-[#121216] border border-white/[0.06] text-center space-y-2">
          <p className="text-xs text-zinc-400">No alerts match the selected status or severity filter.</p>
          <button
            onClick={() => {
              setStatusFilter("ALL");
              setSeverityFilter("ALL");
            }}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium underline"
          >
            Clear filters
          </button>
        </div>
      )}

      {/* Alert Cards Grid */}
      {filteredAlerts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredAlerts.map((alert) => {
            const sev = alert.severity.toUpperCase();
            const severityClass =
              sev === "CRITICAL"
                ? "bg-rose-500/15 border-rose-500/30 text-rose-300"
                : sev === "WARNING"
                ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
                : "bg-sky-500/15 border-sky-500/30 text-sky-300";

            const statusClass =
              alert.status === "RESOLVED"
                ? "bg-zinc-500/15 border-zinc-500/30 text-zinc-400"
                : alert.status === "ACKNOWLEDGED"
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                : "bg-indigo-500/15 border-indigo-500/30 text-indigo-300";

            const hasDelta = alert.delta_percent !== null && alert.delta_percent !== undefined;
            const deltaPositive = hasDelta && (alert.delta_percent ?? 0) > 0;

            const isEligibleForSafeAction =
              alert.category === "data_quality_degradation" &&
              alert.evidence?.orphan_count &&
              Number(alert.evidence.orphan_count) > 0;

            return (
              <div
                key={alert.alert_id}
                className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] hover:border-white/[0.16] transition-all flex flex-col justify-between space-y-3.5 text-left"
              >
                <div className="space-y-2.5">
                  {/* Badges Header */}
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${severityClass}`}>
                        {sev}
                      </span>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-zinc-300">
                        {alert.category.replace(/_/g, " ")}
                      </span>
                    </div>

                    <span className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${statusClass}`}>
                      {alert.status}
                    </span>
                  </div>

                  {/* Title & Metric */}
                  <div>
                    <h4 className="text-sm font-bold text-white tracking-tight leading-snug">
                      {alert.title}
                    </h4>
                    <p className="text-[11px] font-mono text-zinc-400 mt-0.5 truncate">
                      {alert.metric}
                    </p>
                  </div>

                  {/* Delta & Values Preview */}
                  {(alert.previous_value !== null || alert.current_value !== null || hasDelta) && (
                    <div className="flex items-center gap-3 p-2.5 rounded-xl bg-black/40 border border-white/[0.04] text-xs font-mono">
                      {alert.previous_value !== null && alert.current_value !== null && (
                        <div className="flex items-center gap-1.5 text-zinc-300">
                          <span>{alert.previous_value?.toLocaleString()}</span>
                          <span className="text-zinc-500">→</span>
                          <span className="font-semibold text-white">{alert.current_value?.toLocaleString()}</span>
                        </div>
                      )}
                      {hasDelta && (
                        <span
                          className={`font-semibold px-1.5 py-0.5 rounded text-[11px] ${
                            deltaPositive ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
                          }`}
                        >
                          {deltaPositive ? "+" : ""}
                          {alert.delta_percent?.toFixed(1)}%
                        </span>
                      )}
                      {alert.threshold_applied && (
                        <span className="text-[10px] text-zinc-500 truncate ml-auto">
                          Threshold: {alert.threshold_applied}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Explanation text */}
                  <p className="text-xs text-zinc-300 leading-relaxed line-clamp-3">
                    {alert.explanation}
                  </p>
                </div>

                {/* Card Action Footer */}
                <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    {alert.status === "NEW" && (
                      <button
                        onClick={(e) => handleAcknowledge(alert.alert_id, e)}
                        className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-[11px] font-medium text-zinc-300 hover:text-white transition-colors cursor-pointer"
                        title="Mark as Acknowledged"
                      >
                        Acknowledge
                      </button>
                    )}
                    {alert.status !== "RESOLVED" && (
                      <button
                        onClick={(e) => handleResolve(alert.alert_id, e)}
                        className="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/25 text-[11px] font-medium text-emerald-300 transition-colors cursor-pointer"
                        title="Mark as Resolved"
                      >
                        Resolve
                      </button>
                    )}
                    {isEligibleForSafeAction && alert.status !== "RESOLVED" && (
                      <button
                        onClick={(e) => handlePrepareAction(alert, e)}
                        disabled={proposingActionId === alert.alert_id}
                        className="px-2.5 py-1 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/30 text-[11px] font-medium text-indigo-300 transition-colors cursor-pointer disabled:opacity-50"
                      >
                        {proposingActionId === alert.alert_id ? "Preparing..." : "Prepare Safe Action"}
                      </button>
                    )}
                  </div>

                  <button
                    onClick={() => setSelectedAlert(alert)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold inline-flex items-center gap-1 cursor-pointer transition-colors"
                  >
                    <span>Investigate</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Detailed Investigation Modal */}
      {selectedAlert && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={() => setSelectedAlert(null)}
          onKeyDown={(e) => e.key === "Escape" && setSelectedAlert(null)}
        >
          <div
            className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[#121216] border border-white/10 shadow-2xl p-6 space-y-5 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                      selectedAlert.severity.toUpperCase() === "CRITICAL"
                        ? "bg-rose-500/15 border-rose-500/30 text-rose-300"
                        : selectedAlert.severity.toUpperCase() === "WARNING"
                        ? "bg-amber-500/15 border-amber-500/30 text-amber-300"
                        : "bg-sky-500/15 border-sky-500/30 text-sky-300"
                    }`}
                  >
                    {selectedAlert.severity}
                  </span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-zinc-300">
                    {selectedAlert.category.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.06] text-zinc-400">
                    STATUS: {selectedAlert.status}
                  </span>
                </div>
                <h3 className="text-base font-bold text-white tracking-tight">
                  {selectedAlert.title}
                </h3>
                <p className="text-xs font-mono text-zinc-400">{selectedAlert.metric}</p>
              </div>

              <button
                onClick={() => setSelectedAlert(null)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Section 1: What happened */}
            <div className="space-y-1.5">
              <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                What Happened
              </h4>
              <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] text-xs text-zinc-200 leading-relaxed">
                {selectedAlert.explanation}
              </div>
            </div>

            {/* Section 2: Evidence */}
            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                Observed Evidence & Metrics
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div className="p-2.5 rounded-xl bg-black/40 border border-white/[0.05]">
                  <span className="text-[10px] text-zinc-500 block">Baseline / Previous</span>
                  <span className="font-semibold text-zinc-300">
                    {selectedAlert.previous_value !== null && selectedAlert.previous_value !== undefined
                      ? selectedAlert.previous_value.toLocaleString()
                      : "N/A"}
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-black/40 border border-white/[0.05]">
                  <span className="text-[10px] text-zinc-500 block">Observed / Current</span>
                  <span className="font-semibold text-white">
                    {selectedAlert.current_value !== null && selectedAlert.current_value !== undefined
                      ? selectedAlert.current_value.toLocaleString()
                      : "N/A"}
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-black/40 border border-white/[0.05]">
                  <span className="text-[10px] text-zinc-500 block">Delta</span>
                  <span className="font-semibold text-zinc-300">
                    {selectedAlert.delta !== null && selectedAlert.delta !== undefined
                      ? selectedAlert.delta.toLocaleString()
                      : "N/A"}
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-black/40 border border-white/[0.05]">
                  <span className="text-[10px] text-zinc-500 block">Delta %</span>
                  <span className="font-semibold text-indigo-400">
                    {selectedAlert.delta_percent !== null && selectedAlert.delta_percent !== undefined
                      ? `${selectedAlert.delta_percent.toFixed(1)}%`
                      : "N/A"}
                  </span>
                </div>
              </div>

              {selectedAlert.threshold_applied && (
                <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.05] text-[11px] text-zinc-400 flex items-center justify-between">
                  <span>Threshold Applied:</span>
                  <span className="font-mono text-zinc-200">{selectedAlert.threshold_applied}</span>
                </div>
              )}

              {/* Structured evidence table (safely rendered) */}
              {selectedAlert.evidence && Object.keys(selectedAlert.evidence).length > 0 && (
                <div className="p-3 rounded-xl bg-black/50 border border-white/[0.06] space-y-1.5">
                  <span className="text-[10px] font-mono uppercase text-zinc-400 font-semibold block">
                    Detailed Evidence Parameters
                  </span>
                  <div className="space-y-1 divide-y divide-white/[0.04]">
                    {Object.entries(selectedAlert.evidence).map(([k, v]) => (
                      <div key={k} className="flex items-start justify-between gap-3 pt-1 text-[11px] font-mono">
                        <span className="text-zinc-400">{k}:</span>
                        <div className="text-right text-zinc-200">{renderSafeValue(v)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Section 3: Data Lineage */}
            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                <GitMerge size={12} className="text-indigo-400" />
                <span>Data Lineage & Source Tables</span>
              </h4>
              <div className="p-3.5 rounded-xl bg-black/50 border border-white/[0.06] font-mono text-xs space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-zinc-400 text-[11px]">Tables:</span>
                  {(selectedAlert.source_tables || []).length > 0 ? (
                    (selectedAlert.source_tables || []).map((t: string) => (
                      <span key={t} className="px-2 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/25 text-indigo-200 text-[11px]">
                        {t}
                      </span>
                    ))
                  ) : (
                    <span className="text-zinc-500 text-[11px]">None recorded</span>
                  )}
                </div>

                {(selectedAlert.source_columns || []).length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 border-t border-white/[0.04] pt-2">
                    <span className="text-zinc-400 text-[11px]">Columns:</span>
                    {(selectedAlert.source_columns || []).map((c: string) => (
                      <span key={c} className="px-2 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-zinc-300 text-[11px]">
                        {c}
                      </span>
                    ))}
                  </div>
                )}

                <div className="space-y-1 border-t border-white/[0.06] pt-2">
                  {(selectedAlert.lineage_steps || selectedAlert.lineage || []).length > 0 ? (
                    (selectedAlert.lineage_steps || selectedAlert.lineage || []).map((step: string, idx: number) => (
                      <div key={idx} className="flex items-start gap-2 text-zinc-300 text-[11px]">
                        <span className="text-indigo-400 font-bold">[{idx + 1}]</span>
                        <span>{step}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-[11px] text-zinc-500 italic">No lineage path available for this metric.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Section 4: SQL Lineage (Strictly Read-Only) */}
            {selectedAlert.sql && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                    <FileCode2 size={12} className="text-emerald-400" />
                    <span>Reproducible SQL Query (Evidence Only)</span>
                  </h4>
                  <span className="text-[10px] font-mono text-zinc-500">Read-Only</span>
                </div>
                <div className="p-3 rounded-xl bg-black/60 border border-white/[0.06] font-mono text-xs text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                  {selectedAlert.sql}
                </div>
              </div>
            )}

            {/* Section 5: Recommendation */}
            {selectedAlert.recommendation && (
              <div className="space-y-1.5">
                <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                  Recommended Action
                </h4>
                <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-200 leading-relaxed">
                  {selectedAlert.recommendation}
                </div>
              </div>
            )}

            {/* Modal Footer Controls */}
            <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                {selectedAlert.status === "NEW" && (
                  <button
                    onClick={() => handleAcknowledge(selectedAlert.alert_id)}
                    className="px-3 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-white transition-colors cursor-pointer"
                  >
                    Acknowledge
                  </button>
                )}
                {selectedAlert.status !== "RESOLVED" && (
                  <button
                    onClick={() => handleResolve(selectedAlert.alert_id)}
                    className="px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-xs font-semibold text-emerald-300 transition-colors cursor-pointer"
                  >
                    Resolve Alert
                  </button>
                )}
                {selectedAlert.category === "data_quality_degradation" &&
                  selectedAlert.evidence?.orphan_count &&
                  Number(selectedAlert.evidence.orphan_count) > 0 &&
                  selectedAlert.status !== "RESOLVED" && (
                    <button
                      onClick={() => handlePrepareAction(selectedAlert)}
                      disabled={proposingActionId === selectedAlert.alert_id}
                      className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition-colors cursor-pointer disabled:opacity-50"
                    >
                      {proposingActionId === selectedAlert.alert_id ? "Preparing..." : "Prepare Safe Action"}
                    </button>
                  )}
              </div>

              <button
                onClick={() => setSelectedAlert(null)}
                className="px-4 py-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-white transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Safe Action Proposal Preview Modal */}
      {actionProposal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={() => setActionProposal(null)}
          onKeyDown={(e) => e.key === "Escape" && setActionProposal(null)}
        >
          <div
            className="relative w-full max-w-xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[#121216] border border-indigo-500/30 shadow-2xl p-6 space-y-4 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
                  SAFE ACTION PROPOSAL
                </span>
                <h3 className="text-base font-bold text-white">
                  {actionProposal.proposal.description}
                </h3>
                <p className="text-xs text-zinc-400">Source: {actionProposal.alertTitle}</p>
              </div>

              <button
                onClick={() => setActionProposal(null)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Human Confirmation Requirement Badge */}
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-2.5 text-xs text-amber-300">
              <AlertTriangle size={16} className="shrink-0 mt-0.5 text-amber-400" />
              <div>
                <strong className="block font-semibold">Human Confirmation Required</strong>
                <p className="text-[11px] text-amber-200/80 mt-0.5">
                  {actionProposal.proposal.safety_notes ||
                    "This operation requires explicit human confirmation. It will execute inside a transactional block with automated rollback if post-verification fails."}
                </p>
              </div>
            </div>

            {/* Action Details */}
            <div className="space-y-2 text-xs font-mono">
              <div className="p-3 rounded-xl bg-black/40 border border-white/[0.06] space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Action Type:</span>
                  <span className="text-rose-400 font-bold">{actionProposal.proposal.action_type}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Target Table:</span>
                  <span className="text-white">{actionProposal.proposal.target_table}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Estimated Rows Affected:</span>
                  <span className="text-indigo-400 font-bold">
                    {actionProposal.proposal.estimated_affected_rows} record(s)
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Status:</span>
                  <span className="text-amber-400">AWAITING_CONFIRMATION</span>
                </div>
              </div>

              {/* Proposed SQL (Read-only) */}
              {actionProposal.proposal.proposed_sql && (
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-400 uppercase font-semibold">Proposed SQL</span>
                  <div className="p-3 rounded-xl bg-black/60 border border-white/[0.06] text-rose-300 text-xs overflow-x-auto whitespace-pre-wrap">
                    {actionProposal.proposal.proposed_sql}
                  </div>
                </div>
              )}

              {/* Verification SQL */}
              {actionProposal.proposal.verification_sql && (
                <div className="space-y-1">
                  <span className="text-[10px] text-zinc-400 uppercase font-semibold">Post-Execution Verification SQL</span>
                  <div className="p-3 rounded-xl bg-black/60 border border-white/[0.06] text-emerald-400 text-xs overflow-x-auto whitespace-pre-wrap">
                    {actionProposal.proposal.verification_sql}
                  </div>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-white/[0.08] flex items-center justify-between gap-3">
              {onNavigateToAgents ? (
                <button
                  onClick={() => {
                    const actId = actionProposal.proposal.action_id;
                    setActionProposal(null);
                    onNavigateToAgents(
                      `Review and confirm safe action ${actId} for ${actionProposal.proposal.target_table}`,
                      "action_agent"
                    );
                  }}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
                >
                  <span>Go to Agent Center to Confirm</span>
                  <ExternalLink size={13} />
                </button>
              ) : (
                <span className="text-[11px] text-zinc-400 italic">
                  Non-mutating proposal. No database records modified.
                </span>
              )}

              <button
                onClick={() => setActionProposal(null)}
                className="px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-white transition-colors cursor-pointer ml-auto"
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
