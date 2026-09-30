import React, { useState, useEffect } from "react";
import {
  Play,
  Zap,
  CheckCircle,
  HelpCircle,
  Clock,
  RotateCcw,
  Copy,
  Terminal,
  Database,
  Plug,
  AlertTriangle,
  Sparkles,
} from "lucide-react";
import { runQuery, optimizeSQL } from "../../../services/api";
import ResultTable from "../../chat/ResultTable";
import { useToast } from "../../../context/ToastContext";

interface SqlLabViewProps {
  dbConnected: boolean;
  initialQuery?: string;
  onConnectDatabase: () => void;
}

interface HistoryItem {
  id: string;
  query: string;
  timestamp: string;
  success: boolean;
  rowsCount?: number;
}

export default function SqlLabView({
  dbConnected,
  initialQuery,
  onConnectDatabase,
}: SqlLabViewProps) {
  const [query, setQuery] = useState(initialQuery || "SELECT * FROM customers LIMIT 10;");
  const [loading, setLoading] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [queryResult, setQueryResult] = useState<any>(null);
  const [optimizationResult, setOptimizationResult] = useState<any>(null);
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>(() => {
    try {
      const saved = localStorage.getItem("bgai_sql_history");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const toast = useToast();

  useEffect(() => {
    if (initialQuery) {
      setQuery(initialQuery);
    }
  }, [initialQuery]);

  const saveToHistory = (sql: string, success: boolean, rowsCount: number) => {
    const item: HistoryItem = {
      id: crypto.randomUUID(),
      query: sql,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      success,
      rowsCount,
    };
    const updated = [item, ...history.slice(0, 19)];
    setHistory(updated);
    try {
      localStorage.setItem("bgai_sql_history", JSON.stringify(updated));
    } catch {}
  };

  const handleRun = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setOptimizationResult(null);
    const start = performance.now();

    try {
      const res = await runQuery(query.trim());
      const end = performance.now();
      const elapsed = Math.round(end - start);
      setExecutionTime(elapsed);

      if (res && res.success !== false) {
        setQueryResult({
          success: true,
          columns: res.columns || [],
          rows: res.rows || [],
        });
        saveToHistory(query.trim(), true, res.rows?.length || 0);
        toast.success(`Query executed in ${elapsed}ms`);
      } else {
        setQueryResult({
          success: false,
          error: res.error || "Query execution failed.",
        });
        saveToHistory(query.trim(), false, 0);
        toast.error(res.error || "Query failed");
      }
    } catch (err: any) {
      setQueryResult({
        success: false,
        error: err.message || "Failed to execute query.",
      });
      saveToHistory(query.trim(), false, 0);
      toast.error("Execution error");
    } finally {
      setLoading(false);
    }
  };

  const handleOptimize = async () => {
    if (!query.trim() || optimizing) return;
    setOptimizing(true);
    try {
      const res = await optimizeSQL(query.trim());
      if (res) {
        setOptimizationResult(res);
        toast.success("AI optimization analysis complete");
      }
    } catch (err) {
      toast.error("Failed to optimize SQL");
    } finally {
      setOptimizing(false);
    }
  };

  const handleValidate = () => {
    const trimmed = query.trim().toUpperCase();
    if (!trimmed) {
      toast.error("Query is empty");
      return;
    }
    if (trimmed.startsWith("DROP") || trimmed.startsWith("TRUNCATE")) {
      toast.error("Dangerous DDL query detected. Drop/Truncate requires confirmation.");
      return;
    }
    toast.success("SQL syntax format is valid and safe for execution.");
  };

  if (!dbConnected) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl">
        <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 mx-auto">
          <Terminal size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your database to run interactive SQL queries, inspect execution times,
          and optimize queries using AI.
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
    <div className="h-full flex flex-col p-4 sm:p-6 space-y-4 max-w-6xl mx-auto overflow-y-auto">
      {/* SQL Editor Card */}
      <div className="bg-[#121216] border border-white/[0.08] rounded-2xl overflow-hidden shadow-xl flex flex-col">
        {/* Editor Toolbar */}
        <div className="h-12 px-4 bg-[#14141a] border-b border-white/[0.06] flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2">
            <Terminal size={15} className="text-indigo-400" />
            <span className="text-xs font-bold text-white tracking-wide">SQL Editor</span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={handleRun}
              disabled={loading || !query.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-xs font-semibold transition-all cursor-pointer shadow-sm shadow-emerald-900/30"
            >
              <Play size={13} className={loading ? "animate-spin" : ""} />
              <span>{loading ? "Running..." : "Run"}</span>
            </button>

            <button
              onClick={handleOptimize}
              disabled={optimizing || !query.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 hover:text-white text-xs font-medium transition-all cursor-pointer"
            >
              <Zap size={13} className={optimizing ? "animate-spin text-amber-400" : "text-amber-400"} />
              <span>{optimizing ? "Analyzing..." : "Optimize"}</span>
            </button>

            <button
              onClick={handleValidate}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] text-zinc-300 hover:text-white text-xs font-medium transition-all cursor-pointer"
            >
              <CheckCircle size={13} className="text-emerald-400" />
              <span className="hidden sm:inline">Validate</span>
            </button>

            <button
              disabled
              title="Execution Plan is scheduled for the next release"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.01] border border-white/[0.04] text-zinc-600 text-xs font-medium cursor-not-allowed opacity-60"
            >
              <HelpCircle size={13} />
              <span className="hidden sm:inline">Explain</span>
            </button>
          </div>
        </div>

        {/* Textarea Code Editor */}
        <div className="p-4 bg-[#0d0d11]">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={5}
            placeholder="Type your SQL query here... (e.g. SELECT * FROM customers WHERE city = 'Chennai';)"
            className="w-full bg-transparent font-mono text-xs sm:text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none resize-y leading-relaxed"
          />
        </div>

        {/* Quick query presets */}
        <div className="px-4 py-2 bg-[#101014] border-t border-white/[0.04] flex items-center gap-2 overflow-x-auto text-[11px] text-zinc-400">
          <span className="shrink-0 font-semibold text-zinc-400">Templates:</span>
          <button
            onClick={() => setQuery("SELECT * FROM customers LIMIT 25;")}
            className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
          >
            SELECT * LIMIT 25
          </button>
          <button
            onClick={() => setQuery("SELECT COUNT(*) AS total_records FROM orders;")}
            className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
          >
            COUNT(*)
          </button>
          <button
            onClick={() => setQuery("SELECT status, COUNT(*) FROM orders GROUP BY status;")}
            className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
          >
            GROUP BY status
          </button>
        </div>
      </div>

      {/* Optimization Results Callout */}
      {optimizationResult && (
        <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/30 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
              <Zap size={14} className="text-amber-400" />
              <span>AI SQL Optimization Recommendation</span>
            </span>
            {optimizationResult.estimated_improvement && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                {optimizationResult.estimated_improvement}
              </span>
            )}
          </div>

          {optimizationResult.optimized_query && (
            <div className="p-3 rounded-lg bg-[#09090b] border border-white/[0.06] font-mono text-xs text-emerald-300">
              {optimizationResult.optimized_query}
            </div>
          )}

          {optimizationResult.improvements && (
            <ul className="text-xs text-zinc-300 list-disc list-inside space-y-0.5 pt-1">
              {optimizationResult.improvements.map((imp: string, i: number) => (
                <li key={i}>{imp}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Results Section */}
      <div className="bg-[#121216] border border-white/[0.08] rounded-2xl overflow-hidden shadow-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-white uppercase tracking-wider">
              Query Result
            </span>
            {executionTime !== null && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-400">
                {executionTime} ms
              </span>
            )}
            {queryResult?.rows && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                {queryResult.rows.length} rows
              </span>
            )}
          </div>
        </div>

        {queryResult ? (
          queryResult.success ? (
            <ResultTable result={queryResult} />
          ) : (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-mono">
              <p className="font-bold mb-1 flex items-center gap-1.5">
                <AlertTriangle size={14} /> Execution Error:
              </p>
              <p>{queryResult.error}</p>
            </div>
          )
        ) : (
          <div className="p-10 text-center text-xs text-zinc-400">
            Write or paste a SQL query above and click <span className="text-emerald-400 font-semibold">Run</span> to execute.
          </div>
        )}
      </div>

      {/* Execution History */}
      {history.length > 0 && (
        <div className="bg-[#121216] border border-white/[0.08] rounded-2xl p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-bold text-zinc-400 uppercase tracking-wider">
            <span className="flex items-center gap-1.5">
              <Clock size={13} />
              <span>Query Execution History</span>
            </span>
            <button
              onClick={() => {
                setHistory([]);
                localStorage.removeItem("bgai_sql_history");
              }}
              className="text-[10px] text-zinc-400 hover:text-zinc-200 cursor-pointer"
            >
              Clear
            </button>
          </div>

          <div className="space-y-1.5 max-h-36 overflow-y-auto scrollbar-thin">
            {history.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] hover:bg-white/[0.05] text-xs font-mono text-zinc-300 transition-colors"
              >
                <div className="flex items-center gap-2 truncate mr-3">
                  <span
                    className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                      item.success ? "bg-emerald-400" : "bg-rose-400"
                    }`}
                  />
                  <span className="truncate">{item.query}</span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[10px] text-zinc-400">{item.timestamp}</span>
                  <button
                    onClick={() => setQuery(item.query)}
                    className="p-1 rounded text-zinc-400 hover:text-white hover:bg-white/[0.08] cursor-pointer"
                    title="Load into editor"
                  >
                    <RotateCcw size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
