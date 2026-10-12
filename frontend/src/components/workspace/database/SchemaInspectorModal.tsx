import React, { useState, useEffect } from "react";
import {
  X,
  Database,
  Table,
  Layers,
  Search,
  CheckCircle2,
  Key,
  ShieldCheck,
  Loader2,
  Terminal,
  Activity,
  FileCode,
} from "lucide-react";
import type { DatabaseConnectionItem } from "../../../types";
import {
  getSchema,
  executeConnectionQuery,
} from "../../../services/api";
import { useToast } from "../../../context/ToastContext";

interface SchemaInspectorModalProps {
  connection: DatabaseConnectionItem | null;
  onClose: () => void;
  onOpenSqlLab?: (table: string, connectionId: string) => void;
}

export default function SchemaInspectorModal({
  connection,
  onClose,
  onOpenSqlLab,
}: SchemaInspectorModalProps) {
  const toast = useToast();
  const [schema, setSchema] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [searchTable, setSearchTable] = useState("");
  const [activeTab, setActiveTab] = useState<"columns" | "preview">("columns");
  const [previewRows, setPreviewRows] = useState<any[]>([]);
  const [previewColumns, setPreviewColumns] = useState<string[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!connection) return;
    loadSchema();
  }, [connection]);

  const loadSchema = async () => {
    if (!connection) return;
    setLoading(true);
    try {
      const data = await getSchema(connection.connection_id);
      const tables = data || {};
      setSchema(tables);
      const firstTable = Object.keys(tables)[0];
      if (firstTable) {
        setSelectedTable(firstTable);
      }
    } catch (err) {
      console.error("Failed to load schema", err);
      toast.error("Could not load schema for this connection.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!connection || !selectedTable || activeTab !== "preview") return;
    loadTablePreview();
  }, [connection, selectedTable, activeTab]);

  const loadTablePreview = async () => {
    if (!connection || !selectedTable) return;
    setPreviewLoading(true);
    try {
      const query =
        connection.category === "document"
          ? JSON.stringify({ collection: selectedTable, limit: 10 })
          : `SELECT * FROM ${selectedTable} LIMIT 10`;

      const res = await executeConnectionQuery(connection.connection_id, query);
      if (res && res.rows) {
        setPreviewRows(res.rows);
        setPreviewColumns(res.columns || (res.rows[0] ? Object.keys(res.rows[0]) : []));
      } else {
        setPreviewRows([]);
        setPreviewColumns([]);
      }
    } catch (err: any) {
      console.error("Preview load error", err);
      toast.error("Could not fetch table preview records.");
    } finally {
      setPreviewLoading(false);
    }
  };

  if (!connection) return null;

  const tables = Object.keys(schema);
  const filteredTables = tables.filter((t) =>
    t.toLowerCase().includes(searchTable.toLowerCase())
  );

  const selectedTableColumns = selectedTable ? schema[selectedTable] || {} : {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="relative w-full max-w-5xl h-[85vh] bg-[#0d0d12] border border-white/[0.08] rounded-2xl shadow-2xl flex flex-col overflow-hidden text-zinc-100">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] bg-[#141418]/60 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Database size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-white tracking-tight">
                  {connection.name}
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.06] text-zinc-300 border border-white/[0.08] uppercase">
                  {connection.connector_type}
                </span>
                {connection.is_read_only && (
                  <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300">
                    <ShieldCheck size={10} /> READ-ONLY
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400 mt-0.5 font-mono">
                {tables.length} {connection.category === "document" ? "collections" : "tables"} discovered
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body: Sidebar + Main details */}
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-zinc-400">
            <Loader2 size={28} className="animate-spin text-violet-400" />
            <span className="text-xs">Inspecting database schema...</span>
          </div>
        ) : tables.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-zinc-400">
            <Database size={40} className="text-zinc-600 mb-3" />
            <h3 className="text-sm font-semibold text-zinc-200">No tables found</h3>
            <p className="text-xs text-zinc-500 mt-1 max-w-sm">
              This connected database does not contain any accessible tables or collections yet.
            </p>
          </div>
        ) : (
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Table List */}
            <div className="w-64 border-r border-white/[0.06] bg-[#141418]/40 flex flex-col shrink-0">
              <div className="p-3 border-b border-white/[0.06]">
                <div className="relative">
                  <Search
                    size={13}
                    className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400"
                  />
                  <input
                    type="text"
                    placeholder="Search tables..."
                    value={searchTable}
                    onChange={(e) => setSearchTable(e.target.value)}
                    className="w-full pl-8 pr-2.5 py-1.5 bg-[#0d0d12] border border-white/[0.08] focus:border-violet-500/50 rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {filteredTables.map((tbl) => (
                  <button
                    key={tbl}
                    onClick={() => setSelectedTable(tbl)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors text-left cursor-pointer ${
                      selectedTable === tbl
                        ? "bg-violet-600 text-white font-medium"
                        : "text-zinc-300 hover:text-white hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      {connection.category === "document" ? (
                        <Layers size={14} className="shrink-0" />
                      ) : (
                        <Table size={14} className="shrink-0" />
                      )}
                      <span className="truncate">{tbl}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Right: Table Detail & Column Profiler */}
            <div className="flex-1 flex flex-col bg-[#0d0d12] overflow-hidden">
              {selectedTable ? (
                <>
                  {/* Table Toolbar */}
                  <div className="px-6 py-3 border-b border-white/[0.06] bg-[#141418]/30 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-white">
                          {selectedTable}
                        </span>
                        <span className="text-xs text-zinc-500">
                          ({Object.keys(selectedTableColumns).length} columns)
                        </span>
                      </div>

                      {/* Tab toggles */}
                      <div className="flex items-center p-0.5 rounded-lg bg-[#141418] border border-white/[0.06]">
                        <button
                          onClick={() => setActiveTab("columns")}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                            activeTab === "columns"
                              ? "bg-violet-600 text-white"
                              : "text-zinc-400 hover:text-zinc-200"
                          }`}
                        >
                          Columns & Types
                        </button>
                        <button
                          onClick={() => setActiveTab("preview")}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                            activeTab === "preview"
                              ? "bg-violet-600 text-white"
                              : "text-zinc-400 hover:text-zinc-200"
                          }`}
                        >
                          Data Sample
                        </button>
                      </div>
                    </div>

                    {onOpenSqlLab && (
                      <button
                        onClick={() => {
                          onOpenSqlLab(selectedTable, connection.connection_id);
                          onClose();
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-zinc-200 hover:text-white transition-colors"
                      >
                        <Terminal size={13} />
                        <span>Open in SQL Lab</span>
                      </button>
                    )}
                  </div>

                  {/* Tab Content */}
                  <div className="flex-1 overflow-y-auto p-6">
                    {activeTab === "columns" ? (
                      <div className="border border-white/[0.08] rounded-xl overflow-hidden bg-[#141418]/40">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="bg-white/[0.02] border-b border-white/[0.06] text-zinc-400 uppercase font-mono text-[10px]">
                              <th className="py-2.5 px-4 font-semibold">Column Name</th>
                              <th className="py-2.5 px-4 font-semibold">Data Type</th>
                              <th className="py-2.5 px-4 font-semibold">Attributes</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/[0.04]">
                            {Object.entries(selectedTableColumns).map(
                              ([colName, colMeta]: [string, any]) => {
                                const typeStr =
                                  typeof colMeta === "string"
                                    ? colMeta
                                    : colMeta?.type || "TEXT";
                                const isPk =
                                  typeof colMeta === "object" &&
                                  Boolean(colMeta?.primary_key);
                                const isNullable =
                                  typeof colMeta === "object"
                                    ? colMeta?.nullable !== false
                                    : true;

                                return (
                                  <tr
                                    key={colName}
                                    className="hover:bg-white/[0.02] transition-colors"
                                  >
                                    <td className="py-2.5 px-4 font-mono font-medium text-zinc-100 flex items-center gap-2">
                                      {isPk && (
                                        <span title="Primary Key">
                                          <Key size={13} className="text-amber-400 shrink-0" />
                                        </span>
                                      )}
                                      <span>{colName}</span>
                                    </td>
                                    <td className="py-2.5 px-4 font-mono text-zinc-400">
                                      {typeStr}
                                    </td>
                                    <td className="py-2.5 px-4">
                                      <div className="flex items-center gap-1.5">
                                        {isPk && (
                                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-300 border border-amber-500/20">
                                            PK
                                          </span>
                                        )}
                                        {!isNullable && (
                                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-700/50 text-zinc-300 border border-zinc-600/30">
                                            NOT NULL
                                          </span>
                                        )}
                                      </div>
                                    </td>
                                  </tr>
                                );
                              }
                            )}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      /* Preview tab */
                      <div>
                        {previewLoading ? (
                          <div className="py-20 flex flex-col items-center justify-center gap-2 text-zinc-400">
                            <Loader2 size={24} className="animate-spin text-violet-400" />
                            <span className="text-xs">Fetching sample records...</span>
                          </div>
                        ) : previewRows.length === 0 ? (
                          <div className="py-16 text-center text-zinc-500 text-xs">
                            No records found in this table.
                          </div>
                        ) : (
                          <div className="border border-white/[0.08] rounded-xl overflow-x-auto bg-[#141418]/40">
                            <table className="w-full text-left text-xs border-collapse">
                              <thead>
                                <tr className="bg-white/[0.02] border-b border-white/[0.06] text-zinc-400 font-mono text-[10px]">
                                  {previewColumns.map((col) => (
                                    <th
                                      key={col}
                                      className="py-2.5 px-4 font-semibold whitespace-nowrap"
                                    >
                                      {col}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-white/[0.04]">
                                {previewRows.map((row, rIdx) => (
                                  <tr
                                    key={rIdx}
                                    className="hover:bg-white/[0.02] transition-colors"
                                  >
                                    {previewColumns.map((col) => (
                                      <td
                                        key={col}
                                        className="py-2 px-4 font-mono text-zinc-300 whitespace-nowrap max-w-xs truncate"
                                      >
                                        {row[col] !== undefined && row[col] !== null
                                          ? String(row[col])
                                          : "NULL"}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center text-xs text-zinc-500">
                  Select a table from the sidebar to inspect
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

