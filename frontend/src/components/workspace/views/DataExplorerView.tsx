import React, { useState, useEffect } from "react";
import {
  Table,
  Search,
  Key,
  Shield,
  Layers,
  ArrowRight,
  Database,
  Terminal,
  BarChart2,
  Plug,
  ExternalLink,
  Hash,
  Type,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { getSchema } from "../../../services/api";

interface DataExplorerViewProps {
  dbConnected: boolean;
  onOpenSqlLabWithTable?: (tableName: string) => void;
  onConnectDatabase?: () => void;
}

interface ColumnDetail {
  name: string;
  type: string;
  isPk?: boolean;
  nullable?: boolean;
}

export default function DataExplorerView({
  dbConnected,
  onOpenSqlLabWithTable,
  onConnectDatabase,
}: DataExplorerViewProps) {
  const [schema, setSchema] = useState<Record<string, Record<string, string>>>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"columns" | "preview" | "relationships">("columns");

  useEffect(() => {
    if (!dbConnected) {
      setSchema({});
      setSelectedTable(null);
      setLoading(false);
      return;
    }

    const fetchSchema = async () => {
      setLoading(true);
      try {
        const data = await getSchema();
        if (data && typeof data === "object" && !data.error) {
          setSchema(data);
          const tableNames = Object.keys(data).filter((k) => k !== "status");
          if (tableNames.length > 0) {
            setSelectedTable(tableNames[0]);
          }
        }
      } catch (err) {
        console.error("Failed to load schema:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchSchema();
  }, [dbConnected]);

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

  const tableNames = Object.keys(schema).filter(
    (name) => name !== "status" && name.toLowerCase().includes(search.toLowerCase()),
  );

  const selectedColumns = selectedTable && schema[selectedTable] ? schema[selectedTable] : {};
  const columnCount = Object.keys(selectedColumns).length;

  return (
    <div className="h-full flex flex-col md:flex-row overflow-hidden bg-[#09090b]">
      {/* Left Tables Sidebar */}
      <div className="w-full md:w-64 lg:w-72 border-b md:border-b-0 md:border-r border-white/[0.08] bg-[#0d0d11] flex flex-col shrink-0">
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
              className="w-full bg-[#141418] border border-white/[0.08] rounded-xl pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 focus:outline-none focus:border-indigo-500/50"
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
              const cols = schema[name] ? Object.keys(schema[name]).length : 0;
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
                    <span className="truncate font-medium">{name}</span>
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
                      {selectedTable}
                    </h2>
                    <p className="text-xs text-zinc-400">
                      Entity table &bull; {columnCount} attributes defined
                    </p>
                  </div>
                </div>
              </div>

              {onOpenSqlLabWithTable && (
                <button
                  onClick={() => onOpenSqlLabWithTable(selectedTable)}
                  className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
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
                    {Object.entries(selectedColumns).map(([colName, colType]) => {
                      const isPrimaryKey =
                        colName.toLowerCase() === "id" ||
                        colName.toLowerCase() === `${selectedTable.toLowerCase()}_id` ||
                        colName.toLowerCase().endsWith("_pk");

                      const isForeignKey =
                        !isPrimaryKey &&
                        (colName.toLowerCase().endsWith("_id") ||
                          colName.toLowerCase().endsWith("id"));

                      return (
                        <tr
                          key={colName}
                          className="hover:bg-white/[0.02] transition-colors"
                        >
                          <td className="px-4 py-3 font-mono font-medium text-white flex items-center gap-2">
                            {isPrimaryKey && (
                              <Key size={13} className="text-amber-400 shrink-0" />
                            )}
                            {isForeignKey && (
                              <Layers size={13} className="text-indigo-400 shrink-0" />
                            )}
                            <span>{colName}</span>
                          </td>
                          <td className="px-4 py-3 font-mono text-zinc-400 text-[11px]">
                            {colType}
                          </td>
                          <td className="px-4 py-3">
                            {isPrimaryKey ? (
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300">
                                Primary Key
                              </span>
                            ) : isForeignKey ? (
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
                            {isPrimaryKey ? "NOT NULL UNIQUE" : "Standard"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
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
