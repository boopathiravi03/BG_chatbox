import React, { useState, useEffect } from "react";
import {
  Database,
  Plus,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertTriangle,
  Layers,
  FileSpreadsheet,
  FileText,
  FileJson,
  Cpu,
  ShieldCheck,
  Zap,
  Activity,
  Trash2,
  Eye,
  Radio,
  ExternalLink,
  Server,
  Loader2,
  HardDrive,
  Unplug,
} from "lucide-react";
import type { DatabaseConnectionItem } from "../../../types";
import {
  listDatabaseConnections,
  setActiveDatabaseConnection,
  testDatabaseConnection,
  reconnectDatabaseConnection,
  deleteDatabaseConnection,
  disconnectAllDatabaseConnections,
  updateConnectionSettings,
} from "../../../services/api";
import { useToast } from "../../../context/ToastContext";
import AddConnectionModal from "./AddConnectionModal";
import SchemaInspectorModal from "./SchemaInspectorModal";

interface DatabaseConnectionsManagerProps {
  onConnectionsChanged?: () => void;
  onOpenSqlLabWithTable?: (tableName: string, connectionId: string) => void;
}

export default function DatabaseConnectionsManager({
  onConnectionsChanged,
  onOpenSqlLabWithTable,
}: DatabaseConnectionsManagerProps) {
  const toast = useToast();
  const [connections, setConnections] = useState<DatabaseConnectionItem[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false);
  const [inspectConnection, setInspectConnection] =
    useState<DatabaseConnectionItem | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [reconnectingId, setReconnectingId] = useState<string | null>(null);

  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    try {
      const data = await listDatabaseConnections();
      setConnections(data.connections || []);
      setActiveConnectionId(data.active_connection_id || null);
    } catch (err) {
      console.error("Failed to list connections", err);
      toast.error("Could not fetch database connections.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchConnections();
  };

  const handleSetActive = async (connectionId: string) => {
    try {
      await setActiveDatabaseConnection(connectionId);
      setActiveConnectionId(connectionId);
      setConnections((prev) =>
        prev.map((c) => ({
          ...c,
          is_active: c.connection_id === connectionId,
        }))
      );
      toast.success("Active database context updated.");
      onConnectionsChanged?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to set active connection.");
    }
  };

  const handleTestConnection = async (connectionId: string) => {
    setTestingId(connectionId);
    try {
      const res = await testDatabaseConnection(connectionId);
      if (res.status === "ok" || res.test?.connected) {
        toast.success(
          `Connection healthy (${res.test?.latency_ms ? res.test.latency_ms.toFixed(1) : "<1"}ms latency)`
        );
      } else {
        toast.error(
          `Connection check failed: ${res.test?.error || res.test?.message || "unreachable"}`
        );
      }
    } catch (err: any) {
      toast.error(err.message || "Test connection failed.");
    } finally {
      setTestingId(null);
    }
  };

  const handleReconnect = async (connectionId: string) => {
    setReconnectingId(connectionId);
    try {
      const res = await reconnectDatabaseConnection(connectionId);
      if (res.status === "ok") {
        toast.success("Successfully reconnected.");
        fetchConnections();
        onConnectionsChanged?.();
      } else {
        toast.error(res.message || "Reconnection failed.");
      }
    } catch (err: any) {
      toast.error(err.message || "Reconnect failed.");
    } finally {
      setReconnectingId(null);
    }
  };

  const handleDelete = async (connectionId: string, name: string) => {
    if (!confirm(`Are you sure you want to disconnect and remove "${name}"?`)) {
      return;
    }
    try {
      await deleteDatabaseConnection(connectionId);
      toast.success(`Removed ${name}`);
      fetchConnections();
      onConnectionsChanged?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to remove connection.");
    }
  };

  const handleDisconnectAll = async () => {
    if (
      !confirm(
        "Are you sure you want to disconnect ALL connected databases? This will clear all active connections."
      )
    ) {
      return;
    }
    try {
      await disconnectAllDatabaseConnections();
      toast.success("All database connections disconnected.");
      fetchConnections();
      onConnectionsChanged?.();
    } catch (err: any) {
      toast.error(err.message || "Failed to disconnect all databases.");
    }
  };

  const handleToggleReadOnly = async (conn: DatabaseConnectionItem) => {
    try {
      const nextReadOnly = !conn.is_read_only;
      const res = await updateConnectionSettings(conn.connection_id, {
        is_read_only: nextReadOnly,
      });
      if (res.status === "success") {
        toast.success(
          `Connection '${conn.name}' switched to ${nextReadOnly ? "Read-Only" : "Read/Write"} mode.`
        );
        fetchConnections();
        onConnectionsChanged?.();
      } else {
        toast.error("Failed to update connection mode.");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to update connection mode.");
    }
  };

  const getConnectorIcon = (type: string, category: string) => {
    if (category === "file") {
      if (type === "csv") return <FileText className="w-5 h-5 text-emerald-400" />;
      if (type === "excel") return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
      return <FileJson className="w-5 h-5 text-amber-400" />;
    }
    if (category === "vector") {
      return <Cpu className="w-5 h-5 text-violet-400" />;
    }
    if (type === "mongodb") {
      return <Layers className="w-5 h-5 text-emerald-400" />;
    }
    return <Database className="w-5 h-5 text-indigo-400" />;
  };

  const filteredConnections = connections.filter((conn) => {
    const matchesCategory =
      categoryFilter === "all" || conn.category === categoryFilter;
    const matchesSearch =
      !searchQuery ||
      conn.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      conn.connector_type.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const activeConnection = connections.find(
    (c) => c.connection_id === activeConnectionId || c.is_active
  );

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 max-w-7xl mx-auto w-full select-none">
      {/* Overview Stats Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Connections */}
        <div className="p-4 rounded-2xl bg-[#141418] border border-white/[0.08] flex items-center justify-between">
          <div>
            <span className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">
              Total Sources
            </span>
            <div className="text-2xl font-bold text-white mt-1">
              {connections.length}
            </div>
          </div>
          <div className="p-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
            <Database size={22} />
          </div>
        </div>

        {/* Active Primary Connection */}
        <div className="p-4 rounded-2xl bg-[#141418] border border-white/[0.08] flex items-center justify-between">
          <div className="truncate mr-2">
            <span className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">
              Active Context
            </span>
            <div className="text-sm font-semibold text-white mt-1 truncate">
              {activeConnection ? activeConnection.name : "None Selected"}
            </div>
            {activeConnection && (
              <span className="text-[10px] font-mono text-violet-300 uppercase">
                {activeConnection.connector_type}
              </span>
            )}
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0">
            <Radio size={22} />
          </div>
        </div>

        {/* Category Breakdown */}
        <div className="p-4 rounded-2xl bg-[#141418] border border-white/[0.08] flex items-center justify-between">
          <div>
            <span className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">
              Source Diversity
            </span>
            <div className="flex items-center gap-1.5 mt-1 text-xs text-zinc-300">
              <span className="px-1.5 py-0.5 rounded bg-white/[0.04] text-[10px] font-mono">
                {connections.filter((c) => c.category === "relational").length} SQL
              </span>
              <span className="px-1.5 py-0.5 rounded bg-white/[0.04] text-[10px] font-mono">
                {connections.filter((c) => c.category === "vector").length} Vector
              </span>
              <span className="px-1.5 py-0.5 rounded bg-white/[0.04] text-[10px] font-mono">
                {connections.filter((c) => c.category === "file").length} File
              </span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Layers size={22} />
          </div>
        </div>

        {/* Global Security & Mode */}
        <div className="p-4 rounded-2xl bg-[#141418] border border-white/[0.08] flex items-center justify-between">
          <div>
            <span className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">
              Access Governance
            </span>
            <div className="flex items-center gap-2 mt-1">
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400">
                <ShieldCheck size={14} /> {connections.filter((c) => !c.is_read_only).length} Read/Write
              </span>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-400">
                {connections.filter((c) => c.is_read_only).length} Read-Only
              </span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <ShieldCheck size={22} />
          </div>
        </div>
      </div>

      {/* Action & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
        {/* Category Filter Pills */}
        <div className="flex items-center gap-1.5 p-1 bg-[#141418] rounded-xl border border-white/[0.06] overflow-x-auto">
          {(
            [
              { id: "all", label: "All Sources" },
              { id: "relational", label: "Relational" },
              { id: "document", label: "Document" },
              { id: "vector", label: "Vector" },
              { id: "file", label: "Files" },
            ] as const
          ).map((cat) => (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                categoryFilter === cat.id
                  ? "bg-violet-600 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Right: Search + Buttons */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 sm:w-60">
            <Search
              size={13}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
            />
            <input
              type="text"
              placeholder="Search connected sources..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none"
            />
          </div>

          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="p-2 rounded-xl bg-[#141418] hover:bg-white/[0.06] border border-white/[0.08] text-zinc-300 hover:text-white transition-colors cursor-pointer"
            title="Refresh connection status"
          >
            <RefreshCw
              size={14}
              className={refreshing ? "animate-spin text-violet-400" : ""}
            />
          </button>

          {connections.length > 0 && (
            <button
              onClick={handleDisconnectAll}
              className="p-2 rounded-xl bg-[#141418] hover:bg-rose-500/10 border border-white/[0.08] hover:border-rose-500/30 text-zinc-400 hover:text-rose-400 transition-colors cursor-pointer"
              title="Disconnect all databases"
            >
              <Unplug size={14} />
            </button>
          )}

          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-lg shadow-violet-600/20 transition-all cursor-pointer whitespace-nowrap"
          >
            <Plus size={14} />
            <span>Connect Source</span>
          </button>
        </div>
      </div>

      {/* Grid of Connection Cards */}
      {loading ? (
        <div className="py-24 flex flex-col items-center justify-center gap-3 text-zinc-400">
          <Loader2 size={28} className="animate-spin text-violet-400" />
          <span className="text-xs">Loading database connections...</span>
        </div>
      ) : filteredConnections.length === 0 ? (
        /* Empty State */
        <div className="border border-dashed border-white/[0.1] rounded-2xl p-12 text-center flex flex-col items-center justify-center bg-[#141418]/30 space-y-4">
          <div className="p-4 rounded-2xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
            <Database size={36} />
          </div>
          <div className="max-w-md">
            <h3 className="text-base font-semibold text-white">
              {searchQuery || categoryFilter !== "all"
                ? "No matching sources found"
                : "No Databases Connected"}
            </h3>
            <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
              Connect multiple relational databases, vector embeddings, or flat files.
              BG AI 2.0 allows natural language cross-database queries across all active sources.
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-md shadow-violet-600/20 transition-all cursor-pointer"
          >
            <Plus size={14} />
            <span>Connect Your First Data Source</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredConnections.map((conn) => {
            const isActive =
              conn.connection_id === activeConnectionId || conn.is_active;
            const isError = conn.status === "error";
            const isDisconnected = conn.status === "disconnected";

            return (
              <div
                key={conn.connection_id}
                className={`relative flex flex-col rounded-2xl bg-[#141418] border transition-all ${
                  isActive
                    ? "border-violet-500/60 shadow-lg shadow-violet-600/10 ring-1 ring-violet-500/20"
                    : "border-white/[0.08] hover:border-white/[0.15]"
                }`}
              >
                {/* Active Indicator Top Ribbon */}
                {isActive && (
                  <div className="absolute -top-2.5 left-4 px-2 py-0.5 rounded-full bg-violet-600 text-[9px] font-bold text-white uppercase tracking-wider shadow-sm flex items-center gap-1">
                    <CheckCircle2 size={10} /> Active Context
                  </div>
                )}

                {/* Card Header */}
                <div className="p-5 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2.5 rounded-xl bg-white/[0.04] border border-white/[0.06] shrink-0">
                        {getConnectorIcon(conn.connector_type, conn.category)}
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-sm font-semibold text-white truncate" title={conn.name}>
                          {conn.name}
                        </h4>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] font-mono uppercase text-zinc-400">
                            {conn.connector_type}
                          </span>
                          <span className="text-[10px] text-zinc-600">•</span>
                          <span className="text-[10px] font-mono text-zinc-400 uppercase">
                            {conn.category}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div className="shrink-0 flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/[0.03] border border-white/[0.06]">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          isError
                            ? "bg-rose-500"
                            : isDisconnected
                            ? "bg-amber-400"
                            : "bg-emerald-400 animate-pulse"
                        }`}
                      />
                      <span className="text-[10px] font-mono uppercase text-zinc-300">
                        {conn.status}
                      </span>
                    </div>
                  </div>

                  {/* Summary Details */}
                  <div className="mt-4 pt-3 border-t border-white/[0.04] space-y-2">
                    {/* Host/Path / File Details */}
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="text-[11px] text-zinc-500">Target</span>
                      <span className="font-mono text-[11px] text-zinc-300 truncate max-w-[180px]">
                        {conn.config?.database ||
                          conn.config?.host ||
                          conn.config?.collection_name ||
                          "—"}
                      </span>
                    </div>

                    {/* Tables / Doc Count */}
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="text-[11px] text-zinc-500">Objects</span>
                      <span className="font-mono text-[11px] text-zinc-300">
                        {conn.stats?.tables !== undefined
                          ? `${conn.stats.tables} tables`
                          : conn.stats?.collections !== undefined
                          ? `${conn.stats.collections} collections`
                          : "Connected"}
                      </span>
                    </div>

                    {/* Access Mode */}
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span className="text-[11px] text-zinc-500">Access Mode</span>
                      <button
                        onClick={() => handleToggleReadOnly(conn)}
                        className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border transition-colors cursor-pointer ${
                          conn.is_read_only
                            ? "bg-amber-500/10 text-amber-300 border-amber-500/20 hover:bg-amber-500/25"
                            : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20 hover:bg-emerald-500/25"
                        }`}
                        title={`Click to switch to ${conn.is_read_only ? "Read/Write" : "Read-Only"} mode`}
                      >
                        <ShieldCheck size={10} />
                        {conn.is_read_only ? "READ-ONLY" : "READ/WRITE"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Card Footer Actions */}
                <div className="mt-auto px-5 py-3 border-t border-white/[0.06] bg-[#0d0d12]/60 rounded-b-2xl flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {!isActive && (
                      <button
                        onClick={() => handleSetActive(conn.connection_id)}
                        className="px-2.5 py-1 rounded-lg bg-violet-600/20 hover:bg-violet-600/40 text-violet-300 border border-violet-500/30 text-xs font-medium transition-colors cursor-pointer"
                        title="Set as active database context"
                      >
                        Make Active
                      </button>
                    )}

                    <button
                      onClick={() => setInspectConnection(conn)}
                      className="p-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white border border-white/[0.06] transition-colors cursor-pointer"
                      title="Inspect Schema & Preview Data"
                    >
                      <Eye size={14} />
                    </button>

                    <button
                      onClick={() => handleTestConnection(conn.connection_id)}
                      disabled={testingId === conn.connection_id}
                      className="p-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white border border-white/[0.06] transition-colors cursor-pointer"
                      title="Test live latency & health"
                    >
                      {testingId === conn.connection_id ? (
                        <Loader2 size={14} className="animate-spin text-violet-400" />
                      ) : (
                        <Activity size={14} />
                      )}
                    </button>

                    <button
                      onClick={() => handleReconnect(conn.connection_id)}
                      disabled={reconnectingId === conn.connection_id}
                      className="p-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] text-zinc-300 hover:text-white border border-white/[0.06] transition-colors cursor-pointer"
                      title="Reconnect database engine"
                    >
                      {reconnectingId === conn.connection_id ? (
                        <Loader2 size={14} className="animate-spin text-violet-400" />
                      ) : (
                        <RefreshCw size={14} />
                      )}
                    </button>
                  </div>

                  <button
                    onClick={() => handleDelete(conn.connection_id, conn.name)}
                    className="p-1.5 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                    title="Disconnect and remove source"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Connection Modal */}
      <AddConnectionModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onConnectionCreated={() => {
          fetchConnections();
          onConnectionsChanged?.();
        }}
      />

      {/* Schema Inspector Modal */}
      {inspectConnection && (
        <SchemaInspectorModal
          connection={inspectConnection}
          onClose={() => setInspectConnection(null)}
          onOpenSqlLab={(tbl, cid) => {
            onOpenSqlLabWithTable?.(tbl, cid);
          }}
        />
      )}
    </div>
  );
}

