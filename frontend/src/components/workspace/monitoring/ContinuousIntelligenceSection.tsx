import React, { useState, useCallback } from "react";
import {
  Activity,
  AlertTriangle,
  AlertCircle,
  Info,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Plug,
  Clock,
  Zap,
  BarChart2,
  TrendingUp,
  Search,
} from "lucide-react";
import {
  runMonitoringScan,
  getMonitoringSummary,
} from "../../../services/api";
import type {
  MonitoringItem,
  ExecutiveSummary,
  MonitoringSeverity,
} from "../../../types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function severityIcon(sev: MonitoringSeverity | string) {
  if (sev === "critical")
    return <AlertCircle size={14} className="text-red-400 flex-shrink-0" />;
  if (sev === "warning")
    return <AlertTriangle size={14} className="text-amber-400 flex-shrink-0" />;
  return <Info size={14} className="text-blue-400 flex-shrink-0" />;
}

function severityBadge(sev: MonitoringSeverity | string) {
  const cls =
    sev === "critical"
      ? "bg-red-500/10 border-red-500/30 text-red-400"
      : sev === "warning"
      ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
      : "bg-blue-500/10 border-blue-500/20 text-blue-400";
  return (
    <span
      className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded border ${cls}`}
    >
      {sev}
    </span>
  );
}

function statusColor(status: string) {
  if (status === "critical") return "text-red-400";
  if (status === "attention_needed") return "text-amber-400";
  return "text-emerald-400";
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ── Sub-component: single monitoring item card ────────────────────────────────

function MonitoringItemCard({
  item,
  onInvestigate,
}: {
  item: MonitoringItem;
  onInvestigate?: (item: MonitoringItem) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0f1014] overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left p-4 flex items-start gap-3 hover:bg-white/[0.02] transition-colors"
      >
        <div className="mt-0.5">{severityIcon(item.severity)}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-white truncate">
              {item.title}
            </span>
            {severityBadge(item.severity)}
            <span className="text-[10px] font-mono text-zinc-500 px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.06]">
              {item.item_type.replace(/_/g, " ")}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1 line-clamp-2">
            {item.observed_change}
          </p>
        </div>
        <div className="mt-0.5 text-zinc-500">
          {expanded ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronRight size={14} />
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-white/[0.06]">
          {/* Business Impact */}
          <div className="pt-3 space-y-1">
            <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
              Business Impact
            </p>
            <p className="text-xs text-zinc-300 leading-relaxed">
              {item.business_impact}
            </p>
          </div>

          {/* Possible Explanation */}
          <div className="space-y-1">
            <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
              Possible Explanation
            </p>
            <p className="text-xs text-zinc-400 leading-relaxed italic">
              {item.possible_explanation}
            </p>
          </div>

          {/* Recommended Next Step */}
          <div className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/15 space-y-1">
            <p className="text-[10px] font-semibold text-emerald-400 uppercase tracking-wider">
              Recommended Next Step
            </p>
            <p className="text-xs text-emerald-300 leading-relaxed">
              {item.recommended_next_step}
            </p>
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-between pt-1">
            {item.source_component && (
              <p className="text-[10px] font-mono text-zinc-600">
                Source: {item.source_component.replace(/_/g, " ")}
              </p>
            )}
            {onInvestigate && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onInvestigate(item);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium text-cyan-300 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 transition-all cursor-pointer ml-auto"
              >
                <Search size={12} />
                Investigate Root Cause
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-component: executive summary panel ────────────────────────────────────

function ExecutiveSummaryPanel({
  es,
  scannedAt,
  scanMs,
}: {
  es: ExecutiveSummary;
  scannedAt: string;
  scanMs?: number;
}) {
  const ts = new Date(scannedAt).toLocaleString();
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#0d1117] p-5 space-y-4">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <p
            className={`text-base font-bold leading-snug ${statusColor(es.overall_status)}`}
          >
            {es.overall_status === "healthy"
              ? "✓ Healthy"
              : es.overall_status === "critical"
              ? "⚠ Critical"
              : "⚡ Attention Needed"}
          </p>
          <p className="text-sm text-zinc-300 mt-1 leading-relaxed">
            {es.headline}
          </p>
        </div>
      </div>

      {/* Counts */}
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-xl bg-red-500/5 border border-red-500/15 text-center">
          <p className="text-xl font-bold text-red-400">{es.critical_count}</p>
          <p className="text-[10px] text-zinc-500 mt-0.5">Critical</p>
        </div>
        <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/15 text-center">
          <p className="text-xl font-bold text-amber-400">{es.warning_count}</p>
          <p className="text-[10px] text-zinc-500 mt-0.5">Warning</p>
        </div>
        <div className="p-3 rounded-xl bg-blue-500/5 border border-blue-500/15 text-center">
          <p className="text-xl font-bold text-blue-400">{es.info_count}</p>
          <p className="text-[10px] text-zinc-500 mt-0.5">Info</p>
        </div>
      </div>

      {/* Risks */}
      {es.top_risks.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle size={11} className="text-red-400" />
            Top Risks
          </p>
          <ul className="space-y-1">
            {es.top_risks.map((r, i) => (
              <li key={i} className="text-xs text-zinc-300 flex gap-2">
                <span className="text-red-400 font-bold shrink-0">•</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Opportunities */}
      {es.top_opportunities.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <TrendingUp size={11} className="text-emerald-400" />
            Opportunities
          </p>
          <ul className="space-y-1">
            {es.top_opportunities.map((o, i) => (
              <li key={i} className="text-xs text-zinc-300 flex gap-2">
                <span className="text-emerald-400 font-bold shrink-0">•</span>
                <span>{o}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center gap-3 text-[10px] text-zinc-600 border-t border-white/[0.05] pt-3">
        <Clock size={11} />
        <span>Scanned: {ts}</span>
        {scanMs !== undefined && (
          <>
            <span>·</span>
            <span>{formatDuration(scanMs)}</span>
          </>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  dbConnected: boolean;
  onConnectDatabase?: () => void;
  onInvestigateSignal?: (item: MonitoringItem) => void;
}

export default function ContinuousIntelligenceSection({
  dbConnected,
  onConnectDatabase,
  onInvestigateSignal,
}: Props) {
  const [scanning, setScanning] = useState(false);
  const [executiveSummary, setExecutiveSummary] =
    useState<ExecutiveSummary | null>(null);
  const [items, setItems] = useState<MonitoringItem[]>([]);
  const [scannedAt, setScannedAt] = useState<string | null>(null);
  const [scanMs, setScanMs] = useState<number | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "critical" | "warning" | "info">(
    "all"
  );

  const handleScan = useCallback(async () => {
    if (!dbConnected || scanning) return;
    setScanning(true);
    setError(null);
    try {
      const result = await runMonitoringScan();
      if (result.status === "disconnected") {
        setError("No database connected. Please connect a database first.");
        return;
      }
      if (result.status === "error") {
        setError(result.message || "Scan failed.");
        return;
      }
      if (result.report) {
        setExecutiveSummary(result.report.executive_summary);
        setItems(result.report.items);
        setScannedAt(result.report.scanned_at);
        setScanMs(result.report.scan_duration_ms);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unexpected error during scan.");
    } finally {
      setScanning(false);
    }
  }, [dbConnected, scanning]);

  const filteredItems =
    filter === "all"
      ? items
      : items.filter((i) => i.severity === filter);

  const hasResults = executiveSummary !== null;

  return (
    <div className="space-y-4">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-violet-500/15 border border-violet-500/30 flex items-center justify-center text-violet-400">
            <Activity size={14} />
          </div>
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
            Continuous Intelligence
          </h3>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-violet-500/10 border border-violet-500/20 text-violet-300">
            Phase 8.6
          </span>
        </div>

        <button
          onClick={handleScan}
          disabled={!dbConnected || scanning}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
            !dbConnected || scanning
              ? "bg-white/[0.04] text-zinc-500 cursor-not-allowed"
              : "bg-violet-600/80 hover:bg-violet-600 text-white shadow-lg shadow-violet-500/10"
          }`}
        >
          {scanning ? (
            <>
              <RefreshCw size={12} className="animate-spin" />
              Scanning…
            </>
          ) : (
            <>
              <Zap size={12} />
              Run Intelligence Scan
            </>
          )}
        </button>
      </div>

      {/* Not connected */}
      {!dbConnected && (
        <div className="p-5 rounded-2xl border border-dashed border-white/[0.08] text-center space-y-3">
          <Plug size={20} className="mx-auto text-zinc-600" />
          <p className="text-sm text-zinc-400">
            Connect a database to run a continuous intelligence scan.
          </p>
          {onConnectDatabase && (
            <button
              onClick={onConnectDatabase}
              className="px-4 py-2 rounded-xl bg-violet-600/80 hover:bg-violet-600 text-xs font-semibold text-white transition-colors"
            >
              Connect Database
            </button>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/20 flex items-start gap-2">
          <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {/* Idle state (connected, no scan yet) */}
      {dbConnected && !hasResults && !error && !scanning && (
        <div className="p-5 rounded-2xl border border-dashed border-violet-500/15 bg-violet-500/5 text-center space-y-2">
          <BarChart2 size={20} className="mx-auto text-violet-400" />
          <p className="text-sm text-zinc-400">
            Click <span className="text-violet-300 font-semibold">Run Intelligence Scan</span> to evaluate
            your database across all intelligence subsystems.
          </p>
          <p className="text-[11px] text-zinc-600">
            Scans are on-demand. No data is modified.
          </p>
        </div>
      )}

      {/* Results */}
      {hasResults && executiveSummary && (
        <div className="space-y-4">
          {/* Executive Summary */}
          <ExecutiveSummaryPanel
            es={executiveSummary}
            scannedAt={scannedAt!}
            scanMs={scanMs}
          />

          {/* Item list */}
          {items.length > 0 && (
            <div className="space-y-3">
              {/* Filter tabs */}
              <div className="flex items-center gap-2">
                <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
                  Signals ({items.length})
                </p>
                <div className="flex gap-1 ml-auto">
                  {(["all", "critical", "warning", "info"] as const).map(
                    (f) => (
                      <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`text-[10px] font-semibold px-2 py-1 rounded-lg transition-colors ${
                          filter === f
                            ? "bg-white/[0.1] text-white"
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        {f.charAt(0).toUpperCase() + f.slice(1)}
                      </button>
                    )
                  )}
                </div>
              </div>

              {filteredItems.length === 0 ? (
                <div className="p-4 rounded-xl border border-white/[0.06] text-center">
                  <CheckCircle2
                    size={16}
                    className="mx-auto text-emerald-400 mb-1"
                  />
                  <p className="text-xs text-zinc-400">
                    No {filter} signals detected.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredItems.map((item) => (
                    <MonitoringItemCard
                      key={item.item_id}
                      item={item}
                      onInvestigate={onInvestigateSignal}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {items.length === 0 && (
            <div className="p-4 rounded-xl border border-white/[0.06] bg-emerald-500/5 text-center">
              <CheckCircle2
                size={16}
                className="mx-auto text-emerald-400 mb-1"
              />
              <p className="text-xs text-zinc-300">
                No significant signals detected in the connected database.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
