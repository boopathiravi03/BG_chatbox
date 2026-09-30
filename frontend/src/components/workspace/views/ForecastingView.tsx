import React, { useState, useEffect, lazy, Suspense } from "react";
import {
  TrendingUp,
  Sparkles,
  Plug,
  RefreshCw,
  Calendar,
  Layers,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  Terminal,
  Search,
  Info,
  Sliders,
  BarChart2,
  ShieldAlert,
} from "lucide-react";
import type { WorkspaceTab } from "../WorkspaceSidebar";
import type { ForecastCandidate, ForecastResult } from "../../../types";
import { getForecastingCandidates, generateForecast } from "../../../services/api";

const ChartRenderer = lazy(() => import("../../chat/ChartRenderer"));

interface ForecastingViewProps {
  dbConnected: boolean;
  onConnectDatabase: () => void;
  onTabChange?: (tab: WorkspaceTab) => void;
  onOpenSqlLabWithQuery?: (query: string) => void;
  onOpenExplorerWithTable?: (tableName: string) => void;
}

export default function ForecastingView({
  dbConnected,
  onConnectDatabase,
  onTabChange,
  onOpenSqlLabWithQuery,
  onOpenExplorerWithTable,
}: ForecastingViewProps) {
  const [candidates, setCandidates] = useState<ForecastCandidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<ForecastCandidate | null>(null);
  const [frequency, setFrequency] = useState<"daily" | "weekly" | "monthly">("monthly");
  const [horizon, setHorizon] = useState<number>(3);
  const [aggregation, setAggregation] = useState<string>("SUM");
  const [result, setResult] = useState<ForecastResult | null>(null);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailableMessage, setUnavailableMessage] = useState<string | null>(null);

  // Load eligible time-series candidates on mount
  useEffect(() => {
    if (!dbConnected) {
      setCandidates([]);
      setSelectedCandidate(null);
      setResult(null);
      return;
    }

    const fetchCandidates = async () => {
      setLoadingCandidates(true);
      setError(null);
      try {
        const data = await getForecastingCandidates();
        if (data.candidates && data.candidates.length > 0) {
          setCandidates(data.candidates);
          setSelectedCandidate(data.candidates[0]);
          setFrequency(data.candidates[0].frequency || "monthly");
          setUnavailableMessage(null);
        } else {
          setCandidates([]);
          setSelectedCandidate(null);
          setUnavailableMessage(
            data.message || "Forecasting unavailable: no suitable time-series data was detected in connected tables."
          );
        }
      } catch (err: any) {
        setError(err.message || "Failed to load forecast candidates.");
      } finally {
        setLoadingCandidates(false);
      }
    };

    fetchCandidates();
  }, [dbConnected]);

  const handleGenerate = async (candidateOverride?: ForecastCandidate) => {
    const candidate = candidateOverride || selectedCandidate;
    if (!candidate) return;

    setGenerating(true);
    setError(null);
    try {
      const forecast = await generateForecast({
        table: candidate.table,
        date_column: candidate.date_column,
        metric_column: candidate.metric_column,
        frequency,
        horizon,
        aggregation,
      });

      if (forecast.status === "error" || forecast.status === "insufficient_data") {
        setError(forecast.error_message || "Insufficient historical data for forecasting.");
        setResult(forecast);
      } else {
        setResult(forecast);
      }
    } catch (err: any) {
      setError(err.message || "Failed to generate statistical forecast.");
    } finally {
      setGenerating(false);
    }
  };

  // 1. Not Connected State
  if (!dbConnected) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl shadow-xl">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mx-auto">
          <TrendingUp size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect a database containing historical time-series data (orders, sales, metrics with dates) to generate statistical forecasts.
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

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-8">
      {/* Studio Header */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-[#121218] via-[#14141f] to-[#121218] border border-white/[0.08] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1.5 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-[11px] font-medium">
            <TrendingUp size={12} />
            <span>Statistical Time-Series Projections</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-white tracking-tight">
            Forecasting Studio
          </h2>
          <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
            Use historical database records to project future trends with statistical exponential smoothing and 95% uncertainty intervals.
          </p>
        </div>

        {selectedCandidate && (
          <button
            onClick={() => handleGenerate()}
            disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all cursor-pointer shrink-0"
          >
            {generating ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            <span>{generating ? "Computing Projections..." : "Generate Forecast"}</span>
          </button>
        )}
      </div>

      {/* Discovered Candidates Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
            <span>Eligible Time-Series Candidates</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.06] text-zinc-400">
              {candidates.length} Discovered
            </span>
          </h3>
        </div>

        {loadingCandidates ? (
          <div className="p-8 rounded-xl bg-white/[0.02] border border-white/[0.06] text-center text-xs text-zinc-500 flex items-center justify-center gap-2">
            <RefreshCw size={14} className="animate-spin text-indigo-400" />
            <span>Scanning database for temporal density and numeric measures...</span>
          </div>
        ) : unavailableMessage ? (
          <div className="p-6 rounded-2xl bg-[#14141a] border border-amber-500/20 text-zinc-300 text-xs flex items-start gap-3">
            <AlertCircle size={18} className="text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold text-amber-300">Forecasting Unavailable</p>
              <p className="text-zinc-400 leading-relaxed">{unavailableMessage}</p>
              <p className="text-[11px] text-zinc-500 mt-2">
                Tip: Ensure your database has at least one populated table with a date/timestamp field and numeric metrics (or activity rows) across multiple distinct periods.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {candidates.map((cand, idx) => {
              const isSelected =
                selectedCandidate?.table === cand.table &&
                selectedCandidate?.metric_column === cand.metric_column &&
                selectedCandidate?.date_column === cand.date_column;

              return (
                <div
                  key={`${cand.table}_${cand.metric_column}_${idx}`}
                  onClick={() => {
                    setSelectedCandidate(cand);
                    setFrequency(cand.frequency);
                  }}
                  className={`p-4 rounded-xl border transition-all cursor-pointer text-left space-y-3 ${
                    isSelected
                      ? "bg-indigo-600/[0.08] border-indigo-500/50 shadow-md shadow-indigo-500/10"
                      : "bg-[#121216] border-white/[0.06] hover:border-white/[0.15]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5 min-w-0">
                      <p className="text-xs font-bold text-white truncate">{cand.metric_label}</p>
                      <p className="text-[11px] font-mono text-indigo-400 truncate">
                        {cand.table}.{cand.metric_column || "*"}
                      </p>
                    </div>
                    <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded bg-white/[0.06] text-zinc-400 shrink-0">
                      {cand.frequency}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-1 border-t border-white/[0.04]">
                    <span className="flex items-center gap-1">
                      <Calendar size={12} className="text-zinc-500" />
                      <span>{cand.historical_points_count} periods</span>
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCandidate(cand);
                        setFrequency(cand.frequency);
                        handleGenerate(cand);
                      }}
                      className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold inline-flex items-center gap-1 cursor-pointer"
                    >
                      <span>Forecast</span>
                      <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Forecast Configuration Card */}
      {selectedCandidate && (
        <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Sliders size={14} className="text-indigo-400" />
              <span>Forecast Configuration</span>
            </h3>
            <span className="text-xs text-zinc-400">
              Selected Target: <strong className="text-white">{selectedCandidate.table}</strong> ({selectedCandidate.metric_label})
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            {/* Frequency Selection */}
            <div className="space-y-1.5">
              <label className="text-[11px] text-zinc-400 uppercase font-semibold">Frequency</label>
              <div className="flex rounded-lg bg-black/40 p-1 border border-white/[0.06]">
                {(["monthly", "weekly", "daily"] as const).map((freq) => (
                  <button
                    key={freq}
                    onClick={() => setFrequency(freq)}
                    className={`flex-1 py-1 text-xs rounded font-medium capitalize transition-all cursor-pointer ${
                      frequency === freq
                        ? "bg-indigo-600 text-white shadow"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    {freq}
                  </button>
                ))}
              </div>
            </div>

            {/* Horizon Selection */}
            <div className="space-y-1.5">
              <label className="text-[11px] text-zinc-400 uppercase font-semibold">
                Forecast Horizon ({frequency === "monthly" ? "Months" : "Days"})
              </label>
              <div className="flex rounded-lg bg-black/40 p-1 border border-white/[0.06]">
                {(frequency === "monthly" ? [3, 6, 12] : [7, 14, 30]).map((h) => (
                  <button
                    key={h}
                    onClick={() => setHorizon(h)}
                    className={`flex-1 py-1 text-xs rounded font-medium transition-all cursor-pointer ${
                      horizon === h
                        ? "bg-indigo-600 text-white shadow"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    {h} {frequency === "monthly" ? "mo" : "d"}
                  </button>
                ))}
              </div>
            </div>

            {/* Aggregation Selection */}
            <div className="space-y-1.5">
              <label className="text-[11px] text-zinc-400 uppercase font-semibold">Aggregation</label>
              <div className="flex rounded-lg bg-black/40 p-1 border border-white/[0.06]">
                {(["SUM", "AVG", "COUNT"] as const).map((agg) => (
                  <button
                    key={agg}
                    onClick={() => setAggregation(agg)}
                    className={`flex-1 py-1 text-xs rounded font-medium transition-all cursor-pointer ${
                      aggregation === agg
                        ? "bg-indigo-600 text-white shadow"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    {agg}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Forecast Result Deck */}
      {result && result.status === "success" && (
        <div className="space-y-6">
          {/* Executive AI Narrative Card */}
          <div className="p-6 rounded-2xl bg-[#121218] border border-indigo-500/30 shadow-xl relative overflow-hidden space-y-3">
            <div className="flex items-center justify-between">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs font-semibold">
                <Sparkles size={13} />
                <span>Executive Projections Summary</span>
              </div>

              {result.sql_query && onOpenSqlLabWithQuery && (
                <button
                  onClick={() => onOpenSqlLabWithQuery(result.sql_query!)}
                  className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <Terminal size={12} />
                  <span>Inspect SQL in Lab</span>
                </button>
              )}
            </div>

            <p className="text-sm sm:text-base text-zinc-100 font-medium leading-relaxed">
              {result.ai_explanation}
            </p>
          </div>

          {/* Visual Forecast Chart */}
          {result.chart && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                  Visual Forecast & Projections
                </h4>
                <div className="flex items-center gap-4 text-[11px] text-zinc-400">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 inline-block" />
                    <span>Combined Trajectory</span>
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-sm bg-indigo-400/20 border border-indigo-400 inline-block" />
                    <span>95% Uncertainty Interval</span>
                  </span>
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-[#14141a] border border-white/[0.06]">
                <Suspense fallback={<div className="h-64 flex items-center justify-center text-zinc-500 text-xs">Rendering forecast visualization...</div>}>
                  <ChartRenderer chart={result.chart} />
                </Suspense>
              </div>
            </div>
          )}

          {/* Model Information & Holdout Validation Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
              <p className="text-[10px] text-zinc-400 uppercase font-semibold">Model Method</p>
              <p className="text-xs font-bold text-white truncate">{result.method}</p>
              <p className="text-[10px] text-zinc-500 font-mono">Damped trend (0.9)</p>
            </div>

            <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
              <p className="text-[10px] text-zinc-400 uppercase font-semibold">Training Range</p>
              <p className="text-xs font-bold text-zinc-200 truncate font-mono">
                {result.historical_range.start} – {result.historical_range.end}
              </p>
              <p className="text-[10px] text-zinc-500 font-mono">
                {result.observations.filter((o) => !o.is_forecast).length} historical periods
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
              <p className="text-[10px] text-zinc-400 uppercase font-semibold">Validation Error (MAE)</p>
              <p className="text-xs font-bold text-emerald-400 font-mono">
                {result.validation.mae !== null && result.validation.mae !== undefined
                  ? result.validation.mae.toLocaleString()
                  : "N/A (Short history)"}
              </p>
              <p className="text-[10px] text-zinc-500 font-mono">
                {result.validation.mape ? `${result.validation.mape}% MAPE` : "Holdout evaluation"}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
              <p className="text-[10px] text-zinc-400 uppercase font-semibold">Forecast Horizon</p>
              <p className="text-xs font-bold text-white font-mono">
                {result.forecast_horizon} {result.horizon_unit}
              </p>
              <p className="text-[10px] text-zinc-500 font-mono">Projected forward</p>
            </div>
          </div>

          {/* Projected Data Table */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
              Projected Numerical Values
            </h4>

            <div className="rounded-xl border border-white/[0.06] overflow-hidden bg-white/[0.01]">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/[0.03] text-[11px] text-zinc-400 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-2.5">Period</th>
                    <th className="px-4 py-2.5">Type</th>
                    <th className="px-4 py-2.5 text-right">Value</th>
                    <th className="px-4 py-2.5 text-right">Lower Bound (95%)</th>
                    <th className="px-4 py-2.5 text-right">Upper Bound (95%)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {result.observations.map((obs) => (
                    <tr
                      key={obs.period}
                      className={obs.is_forecast ? "bg-indigo-500/[0.03]" : ""}
                    >
                      <td className="px-4 py-2.5 font-mono text-zinc-300">{obs.period}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`text-[10px] uppercase font-semibold px-2 py-0.5 rounded ${
                            obs.is_forecast
                              ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                              : "bg-white/[0.06] text-zinc-400"
                          }`}
                        >
                          {obs.is_forecast ? "Forecast" : "Observed"}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono font-bold text-white">
                        {obs.value.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-zinc-400">
                        {obs.lower_bound !== null && obs.lower_bound !== undefined
                          ? obs.lower_bound.toLocaleString()
                          : "-"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-zinc-400">
                        {obs.upper_bound !== null && obs.upper_bound !== undefined
                          ? obs.upper_bound.toLocaleString()
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Limitations & Statistical Integrity Callout */}
          <div className="p-4 rounded-xl bg-white/[0.015] border border-white/[0.06] space-y-2">
            <h5 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
              <Info size={13} className="text-indigo-400" />
              <span>Model Limitations & Statistical Integrity</span>
            </h5>
            <ul className="text-[11px] text-zinc-400 space-y-1 list-disc list-inside leading-relaxed">
              {result.limitations.map((lim, i) => (
                <li key={i}>{lim}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
