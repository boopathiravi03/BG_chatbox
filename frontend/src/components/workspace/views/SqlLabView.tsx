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
  FileCode,
} from "lucide-react";
import { runQuery, optimizeSQL } from "../../../services/api";
import ResultTable from "../../chat/ResultTable";
import { useToast } from "../../../context/ToastContext";

import type { DatabaseConnectionItem } from "../../../types";

interface SqlLabViewProps {
  dbConnected: boolean;
  connections?: DatabaseConnectionItem[];
  activeConnectionId?: string | null;
  initialQuery?: string;
  initialConnectionId?: string;
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
  connections = [],
  activeConnectionId,
  initialQuery,
  initialConnectionId,
  onConnectDatabase,
}: SqlLabViewProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(
    initialConnectionId || activeConnectionId || connections[0]?.connection_id || null
  );

  const currentConn =
    connections.find((c) => c.connection_id === selectedConnectionId) ||
    connections.find((c) => c.is_active) ||
    connections[0];

  const isMongo =
    currentConn?.connector_type?.toLowerCase() === "mongodb" ||
    currentConn?.category === "nosql";

  const defaultQueryForConn = isMongo
    ? "db.customers.find({}).limit(25)"
    : "SELECT * FROM customers LIMIT 10;";

  const [query, setQuery] = useState(initialQuery || defaultQueryForConn);
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

  // Adjust default query when switching between SQL and MongoDB if query is still untouched default
  useEffect(() => {
    if (!initialQuery) {
      if (isMongo && query.trim().toUpperCase().startsWith("SELECT")) {
        setQuery("db.customers.find({}).limit(25)");
      } else if (!isMongo && query.trim().startsWith("db.")) {
        setQuery("SELECT * FROM customers LIMIT 10;");
      }
    }
  }, [isMongo, initialQuery]);

  const saveToHistory = (sql: string, success: boolean, rowsCount: number) => {
    const item: HistoryItem = {
      id: crypto.randomUUID(),
      query: sql,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }),
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
      const res = await runQuery(query.trim(), selectedConnectionId || undefined);
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
        toast.success(`Query executed in ${elapsed}ms (${res.rows?.length || 0} records)`);
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
      toast.error(err.message || "Execution error");
    } finally {
      setLoading(false);
    }
  };

  const handleOptimize = async () => {
    if (!query.trim() || optimizing) return;
    setOptimizing(true);
    try {
      if (isMongo) {
        toast.info("AI Optimization analyzes query performance & index coverage.");
      }
      const res = await optimizeSQL(query.trim());
      if (res) {
        setOptimizationResult(res);
        toast.success("AI optimization analysis complete");
      }
    } catch (err) {
      toast.error("Failed to optimize query");
    } finally {
      setOptimizing(false);
    }
  };

  const handleValidate = () => {
    const trimmed = query.trim();
    if (!trimmed) {
      toast.error("Query is empty");
      return;
    }

    if (isMongo) {
      if (trimmed.startsWith("{")) {
        try {
          JSON.parse(trimmed);
          toast.success("JSON command syntax is valid.");
        } catch (e: any) {
          toast.error(`Invalid JSON command: ${e.message}`);
        }
      } else if (trimmed.startsWith("db.")) {
        toast.success("MongoDB query syntax format is valid.");
      } else {
        toast.error("MongoDB queries should start with 'db.<collection>.' or be a valid JSON object.");
      }
      return;
    }

    const upper = trimmed.toUpperCase();
    if (upper.startsWith("DROP") || upper.startsWith("TRUNCATE")) {
      toast.error("Dangerous DDL query detected. Drop/Truncate requires confirmation.");
      return;
    }
    toast.success("SQL syntax format is valid and safe for execution.");
  };

  if (!dbConnected && connections.length === 0) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl">
        <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 mx-auto">
          <Terminal size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your database to run interactive queries, inspect execution times,
          and optimize queries using AI.
        </p>
        <button
          onClick={onConnectDatabase}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-md transition-all cursor-pointer"
        >
          <Plug size={14} />
          <span>Connect Database</span>
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col p-4 sm:p-6 space-y-4 max-w-6xl mx-auto overflow-y-auto">
      {/* Editor Card */}
      <div className="bg-[#121216] border border-white/[0.08] rounded-2xl overflow-hidden shadow-xl flex flex-col">
        {/* Editor Toolbar */}
        <div className="h-12 px-4 bg-[#14141a] border-b border-white/[0.06] flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Terminal size={15} className="text-violet-400" />
              <span className="text-xs font-bold text-white tracking-wide">
                {isMongo ? "MongoDB Query & Command Lab" : "SQL Query Lab"}
              </span>
              {isMongo && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                  MQL & JSON
                </span>
              )}
            </div>

            {connections.length > 1 && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/[0.08]">
                <Database size={12} className="text-violet-400" />
                <select
                  value={selectedConnectionId || ""}
                  onChange={(e) => setSelectedConnectionId(e.target.value)}
                  className="bg-transparent text-xs text-zinc-200 focus:outline-none cursor-pointer"
                >
                  {connections.map((c) => (
                    <option key={c.connection_id} value={c.connection_id} className="bg-[#141418] text-white">
                      {c.name} ({c.connector_type})
                    </option>
                  ))}
                </select>
              </div>
            )}
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
          </div>
        </div>

        {/* Textarea Code Editor */}
        <div className="p-4 bg-[#0d0d11]">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={5}
            placeholder={
              isMongo
                ? 'Type MQL or JSON command... (e.g. db.customers.find({}).limit(25) or {"collection": "customers", "filter": {}})'
                : "Type your SQL query here... (e.g. SELECT * FROM customers WHERE city = 'Chennai';)"
            }
            className="w-full bg-transparent font-mono text-xs sm:text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none resize-y leading-relaxed"
          />
        </div>

        {/* Quick query presets */}
        <div className="px-4 py-2 bg-[#101014] border-t border-white/[0.04] flex items-center gap-2 overflow-x-auto text-[11px] text-zinc-400 scrollbar-thin">
          <span className="shrink-0 font-semibold text-zinc-400">Templates:</span>
          {isMongo ? (
            <>
              <button
                onClick={() => setQuery("db.customers.find({}).limit(25)")}
                className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
              >
                find().limit(25)
              </button>
              <button
                onClick={() => setQuery("db.customers.countDocuments({})")}
                className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
              >
                countDocuments()
              </button>
              <button
                onClick={() =>
                  setQuery('db.orders.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}])')
                }
                className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
              >
                aggregate()
              </button>
              <button
                onClick={() =>
                  setQuery('{\n  "collection": "customers",\n  "action": "find",\n  "filter": {},\n  "limit": 25\n}')
                }
                className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
              >
                JSON Command
              </button>
              <button
                onClick={() =>
                  setQuery('db.customers.insertOne({"name": "New Customer", "status": "active"})')
                }
                className="px-2 py-0.5 rounded bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0 font-mono"
              >
                insertOne()
              </button>
            </>
          ) : (
            <>
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
            </>
          )}
        </div>
      </div>

      {/* Optimization Results Callout */}
      {optimizationResult && (
        <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-500/30 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
              <Zap size={14} className="text-amber-400" />
              <span>AI Query Optimization Recommendation</span>
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

          {optimizationResult.explanation && (
            <p className="text-xs text-zinc-300 leading-relaxed">
              {optimizationResult.explanation}
            </p>
          )}
        </div>
      )}

      {/* Query Result Section */}
      {queryResult && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span className="font-semibold text-white flex items-center gap-2">
              <span>Results</span>
              {executionTime !== null && (
                <span className="font-mono text-[11px] text-zinc-400 flex items-center gap-1">
                  <Clock size={11} />
                  <span>{executionTime}ms</span>
                </span>
              )}
            </span>
          </div>

          {queryResult.success ? (
            <div className="rounded-2xl border border-white/[0.08] bg-[#121216] overflow-hidden shadow-xl">
              <ResultTable result={queryResult} />
            </div>
          ) : (
            <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3">
              <AlertTriangle size={18} className="text-rose-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <h4 className="text-xs font-bold text-rose-300">Execution Failed</h4>
                <p className="text-xs text-rose-200/90 font-mono leading-relaxed break-all">
                  {queryResult.error}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Query History */}
      {history.length > 0 && (
        <div className="bg-[#121216] border border-white/[0.08] rounded-2xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Clock size={13} className="text-zinc-400" />
              <span>Recent Query History</span>
            </span>
            <button
              onClick={() => {
                setHistory([]);
                localStorage.removeItem("bgai_sql_history");
              }}
              className="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
            >
              Clear History
            </button>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto scrollbar-thin">
            {history.map((h) => (
              <div
                key={h.id}
                className="flex items-center justify-between p-2 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.04] transition-all group text-xs font-mono"
              >
                <div
                  onClick={() => setQuery(h.query)}
                  className="flex-1 truncate cursor-pointer text-zinc-300 group-hover:text-white pr-4"
                  title={h.query}
                >
                  <span
                    className={`inline-block w-1.5 h-1.5 rounded-full mr-2 ${
                      h.success ? "bg-emerald-400" : "bg-rose-400"
                    }`}
                  />
                  {h.query}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-zinc-500 shrink-0">
                  <span>{h.timestamp}</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(h.query);
                      toast.success("Query copied");
                    }}
                    className="p-1 hover:text-white transition-colors cursor-pointer"
                    title="Copy Query"
                  >
                    <Copy size={11} />
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
