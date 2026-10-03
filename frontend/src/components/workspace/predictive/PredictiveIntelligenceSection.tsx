import React, { useState, useEffect } from "react";
import {
  TrendingUp,
  Sliders,
  GitCompare,
  FileText,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  Sparkles,
  ArrowRight,
  Database,
  RefreshCw,
  Info,
  Calendar,
  Layers,
  ChevronDown,
} from "lucide-react";
import {
  getPredictCandidates,
  predictMetric,
  simulateScenario,
  compareScenarios,
  explainPrediction,
} from "../../../services/api";
import type {
  PredictionResult,
  ScenarioResult,
  ScenarioComparison,
  PredictionExplanation,
  PredictCandidate,
} from "../../../types";

interface PredictiveIntelligenceSectionProps {
  dbConnected: boolean;
  onConnectDatabase?: () => void;
}

export const PredictiveIntelligenceSection: React.FC<PredictiveIntelligenceSectionProps> = ({
  dbConnected,
  onConnectDatabase,
}) => {
  const [activeTab, setActiveTab] = useState<"forecast" | "whatif" | "compare" | "evidence">("forecast");
  const [candidates, setCandidates] = useState<PredictCandidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<PredictCandidate | null>(null);
  const [horizonDays, setHorizonDays] = useState<number>(30);
  const [loading, setLoading] = useState<boolean>(false);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [explanation, setExplanation] = useState<PredictionExplanation | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // What-If State
  const [changePercent, setChangePercent] = useState<number>(10);
  const [scenarioName, setScenarioName] = useState<string>("Growth Scenario (+10%)");
  const [scenarioType, setScenarioType] = useState<string>("GROWTH");
  const [scenarioLoading, setScenarioLoading] = useState<boolean>(false);
  const [currentScenario, setCurrentScenario] = useState<ScenarioResult | null>(null);

  // Comparison State
  const [comparison, setComparison] = useState<ScenarioComparison | null>(null);
  const [compareLoading, setCompareLoading] = useState<boolean>(false);

  // Load candidate time-series metrics on mount or when dbConnected changes
  useEffect(() => {
    if (!dbConnected) {
      setCandidates([]);
      setSelectedCandidate(null);
      return;
    }
    const fetchCandidates = async () => {
      try {
        const res = await getPredictCandidates();
        if (res.status === "success" && res.candidates?.length > 0) {
          setCandidates(res.candidates);
          setSelectedCandidate(res.candidates[0]);
        }
      } catch (err: any) {
        console.error("Failed to load prediction candidates", err);
      }
    };
    fetchCandidates();
  }, [dbConnected]);

  // Run Prediction
  const handleRunPrediction = async () => {
    if (!selectedCandidate) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await predictMetric({
        table: selectedCandidate.table,
        date_column: selectedCandidate.date_column,
        metric_column: selectedCandidate.metric_column || undefined,
        metric_name: selectedCandidate.metric_name,
        aggregation: selectedCandidate.aggregation,
        frequency: selectedCandidate.frequency,
        horizon_days: horizonDays,
      });

      if (res.status === "success" && res.prediction) {
        setPrediction(res.prediction);
        setCurrentScenario(null);
        setComparison(null);
        // Fetch explanation
        try {
          const expRes = await explainPrediction(res.prediction.prediction_id);
          if (expRes.status === "success") {
            setExplanation(expRes.explanation);
          }
        } catch {
          // Non-critical explanation failure
        }
      } else {
        setErrorMsg(res.prediction?.error_message || res.message || "Failed to generate prediction.");
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "An error occurred during prediction.");
    } finally {
      setLoading(false);
    }
  };

  // Run What-If Scenario
  const handleRunScenario = async () => {
    if (!prediction) return;
    setScenarioLoading(true);
    try {
      const res = await simulateScenario({
        prediction_id: prediction.prediction_id,
        change_percent: changePercent,
        scenario_name: scenarioName,
        scenario_type: scenarioType,
      });
      if (res.status === "success" && res.scenario) {
        setCurrentScenario(res.scenario);
      }
    } catch (err: any) {
      console.error("Simulation error", err);
    } finally {
      setScenarioLoading(false);
    }
  };

  // Run Scenario Comparison
  const handleRunComparison = async () => {
    if (!prediction) return;
    setCompareLoading(true);
    try {
      const res = await compareScenarios({
        prediction_id: prediction.prediction_id,
        scenarios: [
          { scenario_name: "Conservative (+5%)", change_percent: 5, scenario_type: "GROWTH" },
          { scenario_name: "Accelerated (+15%)", change_percent: 15, scenario_type: "UPLIFT" },
          { scenario_name: "Headwind (-10%)", change_percent: -10, scenario_type: "REDUCTION" },
        ],
      });
      if (res.status === "success" && res.comparison) {
        setComparison(res.comparison);
      }
    } catch (err: any) {
      console.error("Comparison error", err);
    } finally {
      setCompareLoading(false);
    }
  };

  // Helper styles
  const getConfidenceBadge = (tier: string) => {
    if (tier === "HIGH") {
      return (
        <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          HIGH CONFIDENCE
        </span>
      );
    }
    if (tier === "MODERATE") {
      return (
        <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/30">
          MODERATE CONFIDENCE
        </span>
      );
    }
    return (
      <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
        LIMITED CONFIDENCE
      </span>
    );
  };

  const getTrendBadge = (trend: string) => {
    if (trend === "INCREASING") {
      return <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-medium">↑ Increasing</span>;
    }
    if (trend === "DECREASING") {
      return <span className="text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-medium">↓ Decreasing</span>;
    }
    if (trend === "VOLATILE") {
      return <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-medium">~ Volatile</span>;
    }
    return <span className="text-xs px-2 py-0.5 rounded bg-slate-500/20 text-slate-300 font-medium">→ Stable</span>;
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl mb-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-5 border-b border-slate-800 gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <TrendingUp size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white tracking-wide">
                Advanced Predictive & Simulation Intelligence
              </h2>
              <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-indigo-500/20 text-indigo-300 rounded border border-indigo-500/30">
                Phase 9.0
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Evidence-based forecasting, statistical holdout backtesting, and what-if scenario simulations
            </p>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex bg-slate-950/60 p-1 rounded-lg border border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab("forecast")}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "forecast" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <TrendingUp size={14} /> Forecasts
          </button>
          <button
            onClick={() => setActiveTab("whatif")}
            disabled={!prediction}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "whatif"
                ? "bg-indigo-600 text-white"
                : prediction
                ? "text-slate-400 hover:text-slate-200"
                : "text-slate-600 cursor-not-allowed"
            }`}
          >
            <Sliders size={14} /> What-If
          </button>
          <button
            onClick={() => {
              setActiveTab("compare");
              if (!comparison && prediction) handleRunComparison();
            }}
            disabled={!prediction}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "compare"
                ? "bg-indigo-600 text-white"
                : prediction
                ? "text-slate-400 hover:text-slate-200"
                : "text-slate-600 cursor-not-allowed"
            }`}
          >
            <GitCompare size={14} /> Compare
          </button>
          <button
            onClick={() => setActiveTab("evidence")}
            disabled={!prediction}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "evidence"
                ? "bg-indigo-600 text-white"
                : prediction
                ? "text-slate-400 hover:text-slate-200"
                : "text-slate-600 cursor-not-allowed"
            }`}
          >
            <FileText size={14} /> Evidence
          </button>
        </div>
      </div>

      {/* Disconnected State */}
      {!dbConnected ? (
        <div className="py-12 text-center">
          <Database size={40} className="mx-auto text-slate-600 mb-3" />
          <h3 className="text-sm font-semibold text-slate-300">Database Connection Required</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">
            Predictive modeling and what-if simulation run exclusively on real connected database tables. Connect a database to discover forecast candidates.
          </p>
          {onConnectDatabase && (
            <button
              onClick={onConnectDatabase}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition-colors inline-flex items-center gap-2"
            >
              <Database size={14} /> Connect Database
            </button>
          )}
        </div>
      ) : (
        <div className="mt-5 space-y-6">
          {/* Controls Bar */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-950/40 p-3.5 rounded-lg border border-slate-800">
            <div className="md:col-span-2">
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                Candidate Metric
              </label>
              {candidates.length > 0 ? (
                <div className="relative">
                  <select
                    value={selectedCandidate ? `${selectedCandidate.table}:${selectedCandidate.date_column}:${selectedCandidate.metric_column || ""}` : ""}
                    onChange={(e) => {
                      const [t, d, m] = e.target.value.split(":");
                      const found = candidates.find(
                        (c) => c.table === t && c.date_column === d && (c.metric_column || "") === m
                      );
                      if (found) setSelectedCandidate(found);
                    }}
                    className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-3 py-2 appearance-none focus:outline-none focus:border-indigo-500"
                  >
                    {candidates.map((c, i) => (
                      <option
                        key={i}
                        value={`${c.table}:${c.date_column}:${c.metric_column || ""}`}
                      >
                        {c.metric_name} ({c.table}.{c.date_column})
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-3 text-slate-400 pointer-events-none" />
                </div>
              ) : (
                <div className="text-xs text-slate-500 py-2">No temporal tables detected in schema.</div>
              )}
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                Forecast Horizon
              </label>
              <select
                value={horizonDays}
                onChange={(e) => setHorizonDays(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
              >
                <option value={7}>7 Days Ahead</option>
                <option value={14}>14 Days Ahead</option>
                <option value={30}>30 Days Ahead</option>
                <option value={90}>90 Days Ahead</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={handleRunPrediction}
                disabled={loading || !selectedCandidate}
                className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg px-4 py-2 transition-colors flex items-center justify-center gap-2"
              >
                {loading ? <RefreshCw size={14} className="animate-spin" /> : <Sparkles size={14} />}
                Generate Forecast
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {errorMsg && (
            <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-3 text-xs text-amber-300">
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-400" />
              <div>
                <p className="font-semibold">Prediction Status Note</p>
                <p className="mt-0.5 text-amber-200/80">{errorMsg}</p>
              </div>
            </div>
          )}

          {/* TAB 1: FORECASTS */}
          {activeTab === "forecast" && prediction && (
            <div className="space-y-5">
              {/* Metric Summary Card */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-5">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-white">{prediction.metric_name}</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Source: <span className="font-mono text-slate-300">{prediction.source_table}</span> (via{" "}
                      <span className="font-mono text-slate-300">{prediction.date_column}</span>)
                    </p>
                  </div>
                  <div className="flex items-center gap-2.5">
                    {getTrendBadge(prediction.trend_direction)}
                    {getConfidenceBadge(prediction.confidence_tier)}
                  </div>
                </div>

                {/* Sub-badges */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-slate-800 text-xs">
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase font-semibold">Method</span>
                    <span className="font-medium text-slate-200">
                      {prediction.selected_method.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase font-semibold">Frequency</span>
                    <span className="font-medium text-slate-200 capitalize">{prediction.frequency}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase font-semibold">History Length</span>
                    <span className="font-medium text-slate-200">
                      {prediction.points.filter((p) => !p.is_forecast).length} periods
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase font-semibold">Forecast Steps</span>
                    <span className="font-medium text-slate-200">
                      {prediction.points.filter((p) => p.is_forecast).length} periods ahead
                    </span>
                  </div>
                </div>

                {/* Seasonality Note */}
                <div className="mt-3.5 p-2.5 bg-slate-900/60 rounded border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                  <Info size={14} className="text-indigo-400 shrink-0" />
                  <span>{prediction.seasonality_summary}</span>
                </div>
              </div>

              {/* Data Table / Visualization */}
              <div className="bg-slate-950/40 border border-slate-800 rounded-lg overflow-hidden">
                <div className="px-4 py-3 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
                  <span>Chronological Time Series & Projections</span>
                  <span className="text-slate-500 font-normal">95% Nominal Prediction Bounds</span>
                </div>
                <div className="max-h-72 overflow-y-auto divide-y divide-slate-800/60 text-xs">
                  {prediction.points.map((pt, i) => (
                    <div
                      key={i}
                      className={`px-4 py-2.5 flex items-center justify-between ${
                        pt.is_forecast ? "bg-indigo-950/15 text-indigo-200 font-medium" : "text-slate-300"
                      }`}
                    >
                      <div className="flex items-center gap-3 w-1/3">
                        <span className="font-mono text-[11px] text-slate-400">{pt.period}</span>
                        {pt.is_forecast && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                            Forecast
                          </span>
                        )}
                      </div>
                      <div className="w-1/3 text-right font-mono font-semibold">
                        {pt.value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                      <div className="w-1/3 text-right text-[11px] text-slate-500 font-mono">
                        {pt.is_forecast && pt.lower_bound != null && pt.upper_bound != null ? (
                          <span>
                            [{pt.lower_bound.toLocaleString()} — {pt.upper_bound.toLocaleString()}]
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Epistemic Guardrail Notice */}
              <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
                <AlertTriangle size={14} className="text-slate-400 mt-0.5 shrink-0" />
                <div>
                  <span className="font-semibold text-slate-300">Epistemic Standard:</span> All projections are
                  statistical extrapolations based on historical observations. Unforeseen market shifts, policy
                  adjustments, and external shocks are not modeled. Projections widen uncertainty over longer horizons.
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: WHAT-IF ANALYSIS */}
          {activeTab === "whatif" && prediction && (
            <div className="space-y-5">
              <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Sliders size={16} className="text-indigo-400" />
                    Simulate What-If Parameter Adjustment
                  </h3>
                  <span className="text-xs text-slate-400">Baseline Metric: {prediction.metric_name}</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                      Percentage Change (%)
                    </label>
                    <input
                      type="number"
                      value={changePercent}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        setChangePercent(val);
                        setScenarioName(`Growth Scenario (${val >= 0 ? "+" : ""}${val}%)`);
                      }}
                      className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-3 py-2"
                      min="-100"
                      max="1000"
                      step="1"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                      Scenario Name
                    </label>
                    <input
                      type="text"
                      value={scenarioName}
                      onChange={(e) => setScenarioName(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 text-white text-xs rounded-lg px-3 py-2"
                    />
                  </div>

                  <div className="flex items-end">
                    <button
                      onClick={handleRunScenario}
                      disabled={scenarioLoading}
                      className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg px-4 py-2 transition-colors flex items-center justify-center gap-2"
                    >
                      {scenarioLoading ? <RefreshCw size={14} className="animate-spin" /> : <PlayIcon />}
                      Run Simulation
                    </button>
                  </div>
                </div>

                {/* Simulation Result */}
                {currentScenario && (
                  <div className="mt-5 p-4 bg-slate-900/80 border border-slate-800 rounded-lg space-y-3">
                    <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                      <span className="text-xs font-bold text-white">{currentScenario.scenario_name}</span>
                      <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300">
                        {currentScenario.delta_percent >= 0 ? "+" : ""}
                        {currentScenario.delta_percent.toFixed(1)}% Projected Shift
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-3 text-center">
                      <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase font-semibold block">Baseline Total</span>
                        <span className="text-sm font-mono font-bold text-slate-300">
                          {currentScenario.baseline_projected_total.toLocaleString()}
                        </span>
                      </div>
                      <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase font-semibold block">Simulated Total</span>
                        <span className="text-sm font-mono font-bold text-indigo-300">
                          {currentScenario.scenario_projected_total.toLocaleString()}
                        </span>
                      </div>
                      <div className="p-3 bg-slate-950/60 rounded border border-slate-800">
                        <span className="text-[10px] text-slate-500 uppercase font-semibold block">Projected Delta</span>
                        <span className={`text-sm font-mono font-bold ${currentScenario.delta_total >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {currentScenario.delta_total >= 0 ? "+" : ""}
                          {currentScenario.delta_total.toLocaleString()}
                        </span>
                      </div>
                    </div>

                    {/* Causal disclaimer */}
                    <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded text-[11px] text-amber-300/90 flex items-start gap-2">
                      <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
                      <span>{currentScenario.causal_disclaimer}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: SCENARIO COMPARISON */}
          {activeTab === "compare" && prediction && (
            <div className="space-y-5">
              <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <GitCompare size={16} className="text-indigo-400" />
                    Multi-Scenario Comparative Matrix
                  </h3>
                  <button
                    onClick={handleRunComparison}
                    disabled={compareLoading}
                    className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                  >
                    <RefreshCw size={12} className={compareLoading ? "animate-spin" : ""} /> Re-compare
                  </button>
                </div>

                {comparison ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase">
                          <th className="py-2.5 px-3">Scenario</th>
                          <th className="py-2.5 px-3">Assumption</th>
                          <th className="py-2.5 px-3 text-right">Projected Total</th>
                          <th className="py-2.5 px-3 text-right">Shift from Baseline</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {comparison.summary_table.map((row, i) => (
                          <tr key={i} className={row.type === "BASELINE" ? "bg-slate-900/60 font-semibold text-white" : "text-slate-300"}>
                            <td className="py-2.5 px-3">{row.scenario_name}</td>
                            <td className="py-2.5 px-3 text-slate-400">{row.assumption}</td>
                            <td className="py-2.5 px-3 text-right font-mono font-semibold">
                              {row.projected_total.toLocaleString()}
                            </td>
                            <td className="py-2.5 px-3 text-right font-mono">
                              <span className={row.delta_percent > 0 ? "text-emerald-400" : row.delta_percent < 0 ? "text-rose-400" : "text-slate-400"}>
                                {row.delta_percent >= 0 ? "+" : ""}
                                {row.delta_percent.toFixed(1)}%
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-8 text-xs text-slate-500">
                    Loading comparative simulations...
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: EVIDENCE & LINEAGE */}
          {activeTab === "evidence" && prediction && (
            <div className="space-y-4">
              <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-5 space-y-4 text-xs">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <FileText size={16} className="text-indigo-400" />
                  Evidence Lineage & Model Backtesting
                </h3>

                {/* Backtesting Evaluations */}
                {prediction.model_evaluations?.length > 0 && (
                  <div>
                    <h4 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Holdout Strategy Backtesting Results
                    </h4>
                    <div className="overflow-x-auto border border-slate-800 rounded-lg">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-900/80 border-b border-slate-800 text-[10px] font-semibold text-slate-400 uppercase">
                          <tr>
                            <th className="py-2 px-3">Method</th>
                            <th className="py-2 px-3 text-right">Holdout RMSE</th>
                            <th className="py-2 px-3 text-right">Holdout MAE</th>
                            <th className="py-2 px-3 text-right">Holdout MAPE</th>
                            <th className="py-2 px-3">Selection Decision</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800">
                          {prediction.model_evaluations.map((m, i) => (
                            <tr key={i} className={m.selected ? "bg-indigo-950/30 text-indigo-200 font-medium" : "text-slate-300"}>
                              <td className="py-2 px-3">{m.method.replace(/_/g, " ")}</td>
                              <td className="py-2 px-3 text-right font-mono">{m.rmse !== null ? m.rmse : "—"}</td>
                              <td className="py-2 px-3 text-right font-mono">{m.mae !== null ? m.mae : "—"}</td>
                              <td className="py-2 px-3 text-right font-mono">{m.mape !== null ? `${m.mape}%` : "—"}</td>
                              <td className="py-2 px-3 text-[11px]">
                                {m.selected ? (
                                  <span className="text-emerald-400 font-semibold flex items-center gap-1">
                                    <CheckCircle size={12} /> Selected
                                  </span>
                                ) : (
                                  <span className="text-slate-500">Candidate</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* SQL Lineage */}
                {prediction.evidence?.sql_lineage && (
                  <div>
                    <h4 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                      Data Extraction SQL Query (Read-Only)
                    </h4>
                    <pre className="p-3 bg-slate-950 rounded border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                      {prediction.evidence.sql_lineage}
                    </pre>
                  </div>
                )}

                {/* Historical Outcome Integration (Phase 8.9 / Phase 8.5) */}
                {prediction.evidence?.historical_outcome_support &&
                  prediction.evidence.historical_outcome_support.length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                        Phase 8.9 Measured Action Outcomes Support
                      </h4>
                      <div className="space-y-1.5">
                        {prediction.evidence.historical_outcome_support.map((sig, i) => (
                          <div key={i} className="p-2.5 bg-slate-900 rounded border border-slate-800 text-[11px] text-slate-300 flex items-center gap-2">
                            <CheckCircle size={12} className="text-indigo-400 shrink-0" />
                            <span>{sig.note}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Limitations */}
                <div>
                  <h4 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                    Limitations & Assumptions
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-slate-400 text-[11px]">
                    {prediction.limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const PlayIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M8 5v14l11-7z" />
  </svg>
);

export default PredictiveIntelligenceSection;
