import React, { useState, useEffect } from "react";
import {
  Table,
  Search,
  Key,
  Layers,
  Database,
  Terminal,
  Plug,
} from "lucide-react";
import { getSchema } from "../../../services/api";

import type { DatabaseConnectionItem } from "../../../types";

interface DataExplorerViewProps {
  dbConnected: boolean;
  connections?: DatabaseConnectionItem[];
  activeConnectionId?: string | null;
  onOpenSqlLabWithTable?: (tableName: string, connectionId?: string) => void;
  onConnectDatabase?: () => void;
}

interface ColumnMetadata {
  type?: string;
  nullable?: boolean;
  primary_key?: boolean;
  default?: unknown;
}

type ColumnDefinition = string | ColumnMetadata;

/**
 * Safely converts any primitive, array, or object into a displayable string
 * to prevent React "Objects are not valid as a React child" rendering errors.
 */
function formatDisplayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(formatDisplayValue).join(", ");
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    if ("type" in obj && typeof obj.type === "string") {
      return obj.type;
    }
    return JSON.stringify(value);
  }
  return String(value);
}

interface ParsedColumnInfo {
  type: string;
  isPrimaryKey: boolean;
  isForeignKey: boolean;
  isNullable: boolean;
  defaultValue: unknown;
  constraint: string;
}

/**
 * Extracts and normalizes column metadata from either legacy string types
 * or modern structured metadata objects { type, nullable, primary_key, default }.
 */
function parseColumnInfo(
  colName: string,
  colDef: unknown,
  tableName: string
): ParsedColumnInfo {
  let type = "UNKNOWN";
  let isPrimaryKey = false;
  let isNullable = true;
  let defaultValue: unknown = null;

  if (typeof colDef === "string") {
    type = colDef;
  } else if (typeof colDef === "object" && colDef !== null) {
    const meta = colDef as ColumnMetadata;
    type = typeof meta.type === "string" ? meta.type : formatDisplayValue(meta.type);
    isPrimaryKey = Boolean(meta.primary_key);
    isNullable = meta.nullable !== false;
    defaultValue = meta.default;
  }

  // Fallback heuristics if primary_key was not explicitly defined
  if (!isPrimaryKey) {
    const lowerCol = colName.toLowerCase();
    const lowerTable = tableName.toLowerCase();
    isPrimaryKey =
      lowerCol === "id" ||
      lowerCol === `${lowerTable}_id` ||
      lowerCol.endsWith("_pk");
  }

  const isForeignKey =
    !isPrimaryKey &&
    (colName.toLowerCase().endsWith("_id") || colName.toLowerCase().endsWith("id"));

  let constraint = "Standard";
  if (isPrimaryKey) {
    constraint = "PRIMARY KEY NOT NULL";
  } else if (!isNullable) {
    constraint =
      defaultValue !== null && defaultValue !== undefined
        ? `NOT NULL DEFAULT ${formatDisplayValue(defaultValue)}`
        : "NOT NULL";
  } else if (defaultValue !== null && defaultValue !== undefined) {
    constraint = `DEFAULT ${formatDisplayValue(defaultValue)}`;
  } else {
    constraint = "NULLABLE";
  }

  return {
    type,
    isPrimaryKey,
    isForeignKey,
    isNullable,
    defaultValue,
    constraint,
  };
}

export default function DataExplorerView({
  dbConnected,
  connections = [],
  activeConnectionId,
  onOpenSqlLabWithTable,
  onConnectDatabase,
}: DataExplorerViewProps) {
  const [selectedConnId, setSelectedConnId] = useState<string | null>(
    activeConnectionId || connections[0]?.connection_id || null
  );
  const [schema, setSchema] = useState<Record<string, Record<string, ColumnDefinition>>>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"columns" | "preview">("columns");

  useEffect(() => {
    if (activeConnectionId) {
      setSelectedConnId(activeConnectionId);
    } else if (connections.length > 0 && !selectedConnId) {
      setSelectedConnId(connections[0].connection_id);
    }
  }, [activeConnectionId, connections]);

  useEffect(() => {
    if (!dbConnected && connections.length === 0) {
      setSchema({});
      setSelectedTable(null);
      setLoading(false);
      return;
    }

    let isMounted = true;

    const fetchSchema = async () => {
      setLoading(true);
      try {
        const data = await getSchema(selectedConnId || undefined);
        if (!isMounted) return;
        if (data && typeof data === "object" && !data.error && data.status !== "error") {
          setSchema(data);
          const tableNames = Object.keys(data).filter(
            (k) =>
              k !== "status" &&
              k !== "message" &&
              typeof data[k] === "object" &&
              data[k] !== null
          );
          if (tableNames.length > 0) {
            setSelectedTable(tableNames[0]);
          } else {
            setSelectedTable(null);
          }
        } else {
          setSchema({});
          setSelectedTable(null);
        }
      } catch (err) {
        if (isMounted) {
          console.error("Failed to load schema:", err);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchSchema();

    return () => {
      isMounted = false;
    };
  }, [dbConnected, selectedConnId]);

  if (!dbConnected) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mx-auto">
          <Database size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your SQLite, MySQL, or PostgreSQL database to visually explore
          tables, examine columns, and inspect schema structures.
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

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center p-12 text-zinc-400 text-xs gap-2.5 bg-[#09090b]">
        <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <span>Reading database catalog and schema...</span>
      </div>
    );
  }

  const tableNames = Object.keys(schema).filter(
    (name) =>
      name !== "status" &&
      name !== "message" &&
      typeof schema[name] === "object" &&
      schema[name] !== null &&
      name.toLowerCase().includes(search.toLowerCase())
  );

  const selectedColumns =
    selectedTable && schema[selectedTable] && typeof schema[selectedTable] === "object"
      ? schema[selectedTable]
      : {};
  const columnCount = Object.keys(selectedColumns).length;

  return (
    <div className="h-full flex flex-col md:flex-row overflow-hidden bg-[#09090b]">
      {/* Left Tables Sidebar */}
      <div className="w-full md:w-64 lg:w-72 border-b md:border-b-0 md:border-r border-white/[0.08] bg-[#0d0d11] flex flex-col shrink-0">
        {/* Source selector dropdown if multiple connections exist */}
        {connections.length > 1 && (
          <div className="p-3 border-b border-white/[0.06] bg-[#141418]/60">
            <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">
              Select Data Source
            </label>
            <select
              value={selectedConnId || ""}
              onChange={(e) => setSelectedConnId(e.target.value)}
              className="w-full bg-[#0d0d12] border border-white/[0.08] rounded-xl px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500/50 cursor-pointer"
            >
              {connections.map((c) => (
                <option key={c.connection_id} value={c.connection_id}>
                  {c.name} ({c.connector_type})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="p-3.5 border-b border-white/[0.06]">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tables..."
              className="w-full bg-[#141418] border border-white/[0.08] rounded-xl pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 focus:outline-none focus:border-violet-500/50"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
          <div className="px-2 py-1 flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-zinc-400">
            <span>Tables ({tableNames.length})</span>
          </div>

          {tableNames.length === 0 ? (
            <div className="p-4 text-center text-xs text-zinc-400">
              No matching tables found
            </div>
          ) : (
            tableNames.map((name) => {
              const cols =
                schema[name] && typeof schema[name] === "object"
                  ? Object.keys(schema[name]).length
                  : 0;
              const isSelected = selectedTable === name;

              return (
                <button
                  key={name}
                  onClick={() => setSelectedTable(name)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left text-xs transition-all cursor-pointer ${
                    isSelected
                      ? "bg-indigo-600/20 text-white border border-indigo-500/30"
                      : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Table
                      size={14}
                      className={isSelected ? "text-indigo-400 shrink-0" : "text-zinc-400 shrink-0"}
                    />
                    <span className="truncate font-medium">{formatDisplayValue(name)}</span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400 shrink-0">
                    {cols} cols
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Main Table Details View */}
      <div className="flex-1 flex flex-col overflow-y-auto bg-[#09090b] p-6 space-y-6">
        {selectedTable ? (
          <>
            {/* Header of selected table */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl bg-[#121216] border border-white/[0.08]">
              <div>
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-400">
                    <Table size={20} />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white tracking-tight">
                      {formatDisplayValue(selectedTable)}
                    </h2>
                    <p className="text-xs text-zinc-400">
                      Entity table &bull; {columnCount} attributes defined
                    </p>
                  </div>
                </div>
              </div>

              {onOpenSqlLabWithTable && (
                <button
                  onClick={() => onOpenSqlLabWithTable(selectedTable, selectedConnId || undefined)}
                  className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-md shadow-violet-600/20 transition-all cursor-pointer"
                >
                  <Terminal size={14} />
                  <span>Query in SQL Lab</span>
                </button>
              )}
            </div>

            {/* View Tabs */}
            <div className="flex items-center gap-2 border-b border-white/[0.08] pb-1">
              <button
                onClick={() => setActiveTab("columns")}
                className={`px-3.5 py-2 text-xs font-medium rounded-lg transition-all cursor-pointer ${
                  activeTab === "columns"
                    ? "bg-white/[0.08] text-white border border-white/[0.1]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Columns ({columnCount})
              </button>
              <button
                onClick={() => setActiveTab("preview")}
                className={`px-3.5 py-2 text-xs font-medium rounded-lg transition-all cursor-pointer ${
                  activeTab === "preview"
                    ? "bg-white/[0.08] text-white border border-white/[0.1]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Data Types & Attributes
              </button>
            </div>

            {/* Table of Columns */}
            <div className="rounded-xl border border-white/[0.08] bg-[#121216] overflow-hidden">
              <div className="overflow-x-auto">
                {activeTab === "columns" ? (
                  <table className="w-full text-left text-xs text-zinc-300">
                    <thead className="bg-[#14141a] text-[11px] font-semibold text-zinc-400 uppercase tracking-wider border-b border-white/[0.06]">
                      <tr>
                        <th className="px-4 py-3">Column Name</th>
                        <th className="px-4 py-3">Data Type</th>
                        <th className="px-4 py-3">Role / Key</th>
                        <th className="px-4 py-3">Constraint</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.04]">
                      {Object.entries(selectedColumns).map(([colName, colDef]) => {
                        const info = parseColumnInfo(colName, colDef, selectedTable);

                        return (
                          <tr
                            key={colName}
                            className="hover:bg-white/[0.02] transition-colors"
                          >
                            <td className="px-4 py-3 font-mono font-medium text-white flex items-center gap-2">
                              {info.isPrimaryKey && (
                                <Key size={13} className="text-amber-400 shrink-0" />
                              )}
                              {info.isForeignKey && (
                                <Layers size={13} className="text-indigo-400 shrink-0" />
                              )}
                              <span>{formatDisplayValue(colName)}</span>
                            </td>
                            <td className="px-4 py-3 font-mono text-zinc-400 text-[11px]">
                              {formatDisplayValue(info.type)}
                            </td>
                            <td className="px-4 py-3">
                              {info.isPrimaryKey ? (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300">
                                  Primary Key
                                </span>
                              ) : info.isForeignKey ? (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
                                  Foreign Key
                                </span>
                              ) : (
                                <span className="text-[10px] text-zinc-400 font-mono">
                                  Standard Column
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-zinc-400 font-mono text-[11px]">
                              {formatDisplayValue(info.constraint)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <table className="w-full text-left text-xs text-zinc-300">
                    <thead className="bg-[#14141a] text-[11px] font-semibold text-zinc-400 uppercase tracking-wider border-b border-white/[0.06]">
                      <tr>
                        <th className="px-4 py-3">Column Name</th>
                        <th className="px-4 py-3">SQL Data Type</th>
                        <th className="px-4 py-3">Nullable</th>
                        <th className="px-4 py-3">Primary Key</th>
                        <th className="px-4 py-3">Default Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.04]">
                      {Object.entries(selectedColumns).map(([colName, colDef]) => {
                        const info = parseColumnInfo(colName, colDef, selectedTable);

                        return (
                          <tr
                            key={colName}
                            className="hover:bg-white/[0.02] transition-colors"
                          >
                            <td className="px-4 py-3 font-mono font-medium text-white flex items-center gap-2">
                              {info.isPrimaryKey && (
                                <Key size={13} className="text-amber-400 shrink-0" />
                              )}
                              {info.isForeignKey && (
                                <Layers size={13} className="text-indigo-400 shrink-0" />
                              )}
                              <span>{formatDisplayValue(colName)}</span>
                            </td>
                            <td className="px-4 py-3 font-mono text-zinc-400 text-[11px]">
                              {formatDisplayValue(info.type)}
                            </td>
                            <td className="px-4 py-3">
                              {info.isNullable ? (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                                  NULLABLE
                                </span>
                              ) : (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400">
                                  NOT NULL
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3">
                              {info.isPrimaryKey ? (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300">
                                  YES
                                </span>
                              ) : (
                                <span className="text-[10px] font-mono text-zinc-500">—</span>
                              )}
                            </td>
                            <td className="px-4 py-3 font-mono text-zinc-400 text-[11px]">
                              {formatDisplayValue(info.defaultValue)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="p-12 text-center text-zinc-400 text-xs">
            Select a table from the sidebar to inspect its columns and structure.
          </div>
        )}
      </div>
    </div>
  );
}
