import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Table,
  Search,
  Key,
  Layers,
  Database,
  Terminal,
  Plug,
  Plus,
  Trash2,
  Edit2,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  FolderPlus,
  Settings,
  X,
  Check,
  ShieldAlert,
} from "lucide-react";
import {
  getSchema,
  getDatabaseRecords,
  createDatabaseRecord,
  updateDatabaseRecord,
  deleteDatabaseRecord,
  createDatabaseEntity,
  renameDatabaseEntity,
  dropDatabaseEntity,
} from "../../../services/api";
import { useToast } from "../../../context/ToastContext";
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

  if (!isPrimaryKey) {
    const lowerCol = colName.toLowerCase();
    const lowerTable = tableName.toLowerCase();
    isPrimaryKey =
      lowerCol === "id" ||
      lowerCol === "_id" ||
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
  const toast = useToast();

  const [selectedConnId, setSelectedConnId] = useState<string | null>(
    activeConnectionId || connections[0]?.connection_id || null
  );
  const [schema, setSchema] = useState<Record<string, Record<string, ColumnDefinition>>>({});
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [tableSearch, setTableSearch] = useState("");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"records" | "columns" | "preview">("records");

  // Records & Grid State
  const [records, setRecords] = useState<Record<string, any>[]>([]);
  const [recordColumns, setRecordColumns] = useState<string[]>([]);
  const [primaryKeys, setPrimaryKeys] = useState<string[]>([]);
  const [isReadOnly, setIsReadOnly] = useState<boolean>(false);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [recordSearch, setRecordSearch] = useState("");
  const [activeRecordSearch, setActiveRecordSearch] = useState("");
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Modals State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Record<string, any> | null>(null);
  const [deletingRecord, setDeletingRecord] = useState<Record<string, any> | null>(null);
  const [isStructureMenuOpen, setIsStructureMenuOpen] = useState(false);
  const [isCreateEntityOpen, setIsCreateEntityOpen] = useState(false);
  const [isRenameEntityOpen, setIsRenameEntityOpen] = useState(false);
  const [isDropEntityOpen, setIsDropEntityOpen] = useState(false);

  // Form states for modals
  const [modalFormData, setModalFormData] = useState<Record<string, string>>({});
  const [modalLoading, setModalLoading] = useState(false);
  const [newEntityName, setNewEntityName] = useState("");
  const [renameTargetName, setRenameTargetName] = useState("");
  const [dropConfirmationText, setDropConfirmationText] = useState("");

  useEffect(() => {
    if (activeConnectionId) {
      setSelectedConnId(activeConnectionId);
    } else if (connections.length > 0 && !selectedConnId) {
      setSelectedConnId(connections[0].connection_id);
    }
  }, [activeConnectionId, connections]);

  // Fetch Database Schema
  const fetchSchema = useCallback(async () => {
    if (!dbConnected && connections.length === 0) {
      setSchema({});
      setSelectedTable(null);
      setSchemaLoading(false);
      return;
    }

    setSchemaLoading(true);
    try {
      const data = await getSchema(selectedConnId || undefined);
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
          setSelectedTable((prev) => (prev && tableNames.includes(prev) ? prev : tableNames[0]));
        } else {
          setSelectedTable(null);
        }
      } else {
        setSchema({});
        setSelectedTable(null);
      }
    } catch (err: any) {
      console.error("Failed to load schema:", err);
      toast.error(err.message || "Failed to load database schema");
    } finally {
      setSchemaLoading(false);
    }
  }, [dbConnected, connections.length, selectedConnId]);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  // Fetch Records for Selected Table
  const fetchRecords = useCallback(async () => {
    if (!selectedTable) {
      setRecords([]);
      setRecordColumns([]);
      setTotalCount(0);
      return;
    }

    setRecordsLoading(true);
    try {
      const offset = (page - 1) * pageSize;
      const res = await getDatabaseRecords({
        table: selectedTable,
        connectionId: selectedConnId || undefined,
        limit: pageSize,
        offset,
        sort_by: sortBy || undefined,
        sort_dir: sortDir,
        search: activeRecordSearch || undefined,
      });

      if (res && res.success !== false) {
        setRecords(res.records || []);
        setRecordColumns(res.columns || []);
        setTotalCount(res.total_count ?? res.records?.length ?? 0);
        setPrimaryKeys(res.primary_keys || []);
        setIsReadOnly(Boolean(res.is_read_only));
      } else {
        setRecords([]);
        setRecordColumns([]);
        setTotalCount(0);
        if (res.error) toast.error(res.error);
      }
    } catch (err: any) {
      console.error("Failed to load records:", err);
      toast.error(err.message || "Failed to load table records");
      setRecords([]);
    } finally {
      setRecordsLoading(false);
    }
  }, [selectedTable, selectedConnId, page, pageSize, sortBy, sortDir, activeRecordSearch]);

  useEffect(() => {
    if (activeTab === "records" && selectedTable) {
      fetchRecords();
    }
  }, [activeTab, selectedTable, fetchRecords]);

  // Reset pagination when table or search changes
  useEffect(() => {
    setPage(1);
  }, [selectedTable, activeRecordSearch]);

  // Debounce record search input (300ms) for hyper-responsive filtering
  useEffect(() => {
    const handler = setTimeout(() => {
      setActiveRecordSearch(recordSearch.trim());
    }, 300);
    return () => clearTimeout(handler);
  }, [recordSearch]);

  const handleTableSelect = (tableName: string) => {
    setSelectedTable(tableName);
    setRecordSearch("");
    setActiveRecordSearch("");
    setSortBy(null);
    setSortDir("asc");
  };

  const handleSortToggle = (colName: string) => {
    if (sortBy === colName) {
      if (sortDir === "asc") {
        setSortDir("desc");
      } else {
        setSortBy(null);
        setSortDir("asc");
      }
    } else {
      setSortBy(colName);
      setSortDir("asc");
    }
  };

  const handleRecordSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setActiveRecordSearch(recordSearch.trim());
  };

  const handleRecordSearchClear = () => {
    setRecordSearch("");
    setActiveRecordSearch("");
  };

  // Extract primary key helper for record mutation
  const getRecordPrimaryKey = (record: Record<string, any>): Record<string, any> => {
    if (primaryKeys.length > 0) {
      const pkObj: Record<string, any> = {};
      for (const pk of primaryKeys) {
        if (record[pk] !== undefined) {
          pkObj[pk] = record[pk];
        }
      }
      if (Object.keys(pkObj).length > 0) return pkObj;
    }

    if ("_id" in record) {
      return { _id: record._id };
    }
    if ("id" in record) {
      return { id: record.id };
    }
    const tableId = `${(selectedTable || "").toLowerCase()}_id`;
    if (tableId in record) {
      return { [tableId]: record[tableId] };
    }

    // Heuristic: check schema columns marked as primary key
    if (selectedTable && schema[selectedTable]) {
      for (const [col, def] of Object.entries(schema[selectedTable])) {
        if (typeof def === "object" && def !== null && (def as ColumnMetadata).primary_key) {
          if (record[col] !== undefined) {
            return { [col]: record[col] };
          }
        }
      }
    }

    // Fallback: first column
    const firstCol = recordColumns[0];
    if (firstCol && record[firstCol] !== undefined) {
      return { [firstCol]: record[firstCol] };
    }
    return record;
  };

  // Open Create Record Modal
  const handleOpenAddModal = () => {
    if (isReadOnly) {
      toast.error("This connection is read-only. Record creation is disabled.");
      return;
    }
    const initialData: Record<string, string> = {};
    const cols =
      selectedTable && schema[selectedTable]
        ? Object.keys(schema[selectedTable])
        : recordColumns;

    for (const col of cols) {
      if (col.toLowerCase() !== "_id") {
        initialData[col] = "";
      }
    }
    setModalFormData(initialData);
    setIsAddModalOpen(true);
  };

  // Submit Create Record
  const handleCreateRecordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTable) return;

    setModalLoading(true);
    try {
      const cleanData: Record<string, any> = {};
      for (const [k, v] of Object.entries(modalFormData)) {
        if (v === "" || v === undefined) continue;
        // Attempt parsing JSON if value starts with { or [
        if (v.startsWith("{") || v.startsWith("[")) {
          try {
            cleanData[k] = JSON.parse(v);
            continue;
          } catch {}
        }
        cleanData[k] = v;
      }

      await createDatabaseRecord({
        table: selectedTable,
        data: cleanData,
        connectionId: selectedConnId || undefined,
      });

      toast.success(`Record created in '${selectedTable}' successfully`);
      setIsAddModalOpen(false);
      fetchRecords();
    } catch (err: any) {
      console.error("Create record error:", err);
      toast.error(err.message || "Failed to create record");
    } finally {
      setModalLoading(false);
    }
  };

  // Open Edit Record Modal
  const handleOpenEditModal = (rec: Record<string, any>) => {
    if (isReadOnly) {
      toast.error("This connection is read-only. Editing is disabled.");
      return;
    }
    setEditingRecord(rec);
    const initialData: Record<string, string> = {};
    for (const [k, v] of Object.entries(rec)) {
      initialData[k] = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
    }
    setModalFormData(initialData);
  };

  // Submit Edit Record
  const handleUpdateRecordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTable || !editingRecord) return;

    setModalLoading(true);
    try {
      const pkObj = getRecordPrimaryKey(editingRecord);
      const updatedFields: Record<string, any> = {};

      for (const [k, v] of Object.entries(modalFormData)) {
        if (k in pkObj) continue; // Keep PK untouched

        if (v === "") {
          updatedFields[k] = null;
        } else if (v.startsWith("{") || v.startsWith("[")) {
          try {
            updatedFields[k] = JSON.parse(v);
          } catch {
            updatedFields[k] = v;
          }
        } else {
          updatedFields[k] = v;
        }
      }

      await updateDatabaseRecord({
        table: selectedTable,
        primary_key: pkObj,
        data: updatedFields,
        connectionId: selectedConnId || undefined,
      });

      toast.success(`Record updated in '${selectedTable}' successfully`);
      setEditingRecord(null);
      fetchRecords();
    } catch (err: any) {
      console.error("Update record error:", err);
      toast.error(err.message || "Failed to update record");
    } finally {
      setModalLoading(false);
    }
  };

  // Delete Record Submit
  const handleDeleteRecordSubmit = async () => {
    if (!selectedTable || !deletingRecord) return;

    setModalLoading(true);
    try {
      const pkObj = getRecordPrimaryKey(deletingRecord);
      await deleteDatabaseRecord({
        table: selectedTable,
        primary_key: pkObj,
        connectionId: selectedConnId || undefined,
      });

      toast.success(`Record deleted from '${selectedTable}'`);
      setDeletingRecord(null);
      fetchRecords();
    } catch (err: any) {
      console.error("Delete record error:", err);
      toast.error(err.message || "Failed to delete record");
    } finally {
      setModalLoading(false);
    }
  };

  // Structure: Create Entity
  const handleCreateEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEntityName.trim()) return;

    setModalLoading(true);
    try {
      await createDatabaseEntity({
        name: newEntityName.trim(),
        connectionId: selectedConnId || undefined,
      });
      toast.success(`Table/Collection '${newEntityName.trim()}' created`);
      setIsCreateEntityOpen(false);
      setNewEntityName("");
      await fetchSchema();
      setSelectedTable(newEntityName.trim());
    } catch (err: any) {
      toast.error(err.message || "Failed to create table/collection");
    } finally {
      setModalLoading(false);
    }
  };

  // Structure: Rename Entity
  const handleRenameEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTable || !renameTargetName.trim()) return;

    setModalLoading(true);
    try {
      await renameDatabaseEntity({
        old_name: selectedTable,
        new_name: renameTargetName.trim(),
        connectionId: selectedConnId || undefined,
      });
      toast.success(`Renamed '${selectedTable}' to '${renameTargetName.trim()}'`);
      const updated = renameTargetName.trim();
      setIsRenameEntityOpen(false);
      setRenameTargetName("");
      await fetchSchema();
      setSelectedTable(updated);
    } catch (err: any) {
      toast.error(err.message || "Failed to rename table/collection");
    } finally {
      setModalLoading(false);
    }
  };

  // Structure: Drop Entity
  const handleDropEntity = async () => {
    if (!selectedTable) return;
    if (dropConfirmationText.trim() !== selectedTable) {
      toast.error(`Please type '${selectedTable}' exactly to confirm drop.`);
      return;
    }

    setModalLoading(true);
    try {
      await dropDatabaseEntity({
        name: selectedTable,
        connectionId: selectedConnId || undefined,
      });
      toast.success(`Dropped '${selectedTable}' successfully`);
      setIsDropEntityOpen(false);
      setDropConfirmationText("");
      setSelectedTable(null);
      await fetchSchema();
    } catch (err: any) {
      toast.error(err.message || "Failed to drop table/collection");
    } finally {
      setModalLoading(false);
    }
  };

  if (!dbConnected && connections.length === 0) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mx-auto">
          <Database size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your SQLite, MySQL, PostgreSQL, or MongoDB database to visually explore
          tables, inspect schemas, and manage records directly.
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

  if (schemaLoading) {
    return (
      <div className="h-full flex items-center justify-center p-12 text-zinc-400 text-xs gap-2.5 bg-[#09090b]">
        <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <span>Reading database catalog and schemas...</span>
      </div>
    );
  }

  const tableNames = Object.keys(schema).filter(
    (name) =>
      name !== "status" &&
      name !== "message" &&
      typeof schema[name] === "object" &&
      schema[name] !== null &&
      name.toLowerCase().includes(tableSearch.toLowerCase())
  );

  const selectedColumns =
    selectedTable && schema[selectedTable] && typeof schema[selectedTable] === "object"
      ? schema[selectedTable]
      : {};
  const columnCount = Object.keys(selectedColumns).length;
  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="h-full flex flex-col md:flex-row overflow-hidden bg-[#09090b]">
      {/* Left Sidebar: Tables & Collections */}
      <div className="w-full md:w-64 lg:w-72 border-b md:border-b-0 md:border-r border-white/[0.08] bg-[#0d0d11] flex flex-col shrink-0">
        {/* Source Selector */}
        {connections.length > 1 && (
          <div className="p-3 border-b border-white/[0.06] bg-[#141418]/60">
            <label className="block text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">
              Data Source
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

        {/* Search Bar & Header */}
        <div className="p-3 border-b border-white/[0.06] flex items-center gap-2">
          <div className="relative flex-1">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
            />
            <input
              type="text"
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              placeholder="Filter tables..."
              className="w-full bg-[#141418] border border-white/[0.08] rounded-xl pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-400 focus:outline-none focus:border-violet-500/50"
            />
          </div>
          <button
            onClick={() => setIsCreateEntityOpen(true)}
            title="Create Table / Collection"
            className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 hover:text-white transition-all cursor-pointer shrink-0"
          >
            <Plus size={14} />
          </button>
        </div>

        {/* Tables List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
          <div className="px-2 py-1 flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-zinc-400">
            <span>Entities ({tableNames.length})</span>
            <button
              onClick={fetchSchema}
              className="hover:text-white transition-colors cursor-pointer"
              title="Refresh Catalog"
            >
              <RefreshCw size={11} />
            </button>
          </div>

          {tableNames.length === 0 ? (
            <div className="p-4 text-center text-xs text-zinc-400">
              No matching tables or collections found
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
                  onClick={() => handleTableSelect(name)}
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

      {/* Main Table Explorer & Grid View */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#09090b]">
        {selectedTable ? (
          <div className="flex-1 flex flex-col overflow-hidden p-4 sm:p-6 space-y-4">
            {/* Header Card */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-2xl bg-[#121216] border border-white/[0.08] shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 shrink-0">
                  <Table size={20} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                      {formatDisplayValue(selectedTable)}
                    </h2>
                    {isReadOnly && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300">
                        Read-Only
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-400">
                    {columnCount} fields/columns &bull; {totalCount.toLocaleString()} total records
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 flex-wrap">
                {/* Add Record Button */}
                <button
                  onClick={handleOpenAddModal}
                  disabled={isReadOnly}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold shadow-md transition-all cursor-pointer"
                >
                  <Plus size={14} />
                  <span>Add Record</span>
                </button>

                {/* Query in SQL Lab */}
                {onOpenSqlLabWithTable && (
                  <button
                    onClick={() =>
                      onOpenSqlLabWithTable(selectedTable, selectedConnId || undefined)
                    }
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-200 text-xs font-medium transition-all cursor-pointer"
                  >
                    <Terminal size={14} className="text-violet-400" />
                    <span className="hidden sm:inline">Query in Lab</span>
                  </button>
                )}

                {/* Structure Operations Dropdown */}
                <div className="relative">
                  <button
                    onClick={() => setIsStructureMenuOpen((prev) => !prev)}
                    className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 transition-all cursor-pointer"
                    title="Manage Structure"
                  >
                    <Settings size={15} />
                  </button>

                  {isStructureMenuOpen && (
                    <div className="absolute right-0 top-full mt-1.5 w-48 bg-[#14141a] border border-white/[0.1] rounded-xl shadow-2xl p-1 z-30 space-y-0.5">
                      <button
                        onClick={() => {
                          setIsStructureMenuOpen(false);
                          setRenameTargetName(selectedTable);
                          setIsRenameEntityOpen(true);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-zinc-300 hover:text-white hover:bg-white/[0.06] rounded-lg transition-colors text-left cursor-pointer"
                      >
                        <Edit2 size={13} className="text-indigo-400" />
                        <span>Rename Entity</span>
                      </button>
                      <button
                        onClick={() => {
                          setIsStructureMenuOpen(false);
                          setDropConfirmationText("");
                          setIsDropEntityOpen(true);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded-lg transition-colors text-left cursor-pointer"
                      >
                        <Trash2 size={13} />
                        <span>Drop Table / Collection</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Refresh */}
                <button
                  onClick={fetchRecords}
                  disabled={recordsLoading}
                  className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 transition-all cursor-pointer"
                  title="Refresh Records"
                >
                  <RefreshCw size={15} className={recordsLoading ? "animate-spin text-indigo-400" : ""} />
                </button>
              </div>
            </div>

            {/* View Tabs */}
            <div className="flex items-center gap-2 border-b border-white/[0.08] pb-1 shrink-0">
              <button
                onClick={() => setActiveTab("records")}
                className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  activeTab === "records"
                    ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Records & Data Grid ({totalCount.toLocaleString()})
              </button>
              <button
                onClick={() => setActiveTab("columns")}
                className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  activeTab === "columns"
                    ? "bg-white/[0.08] text-white border border-white/[0.1]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Columns Schema ({columnCount})
              </button>
              <button
                onClick={() => setActiveTab("preview")}
                className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  activeTab === "preview"
                    ? "bg-white/[0.08] text-white border border-white/[0.1]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Attributes & Constraints
              </button>
            </div>

            {/* TAB CONTENT */}
            {activeTab === "records" && (
              <div className="flex-1 flex flex-col overflow-hidden bg-[#121216] border border-white/[0.08] rounded-xl shadow-xl">
                {/* Search & Filter Toolbar */}
                <div className="p-3 border-b border-white/[0.06] flex items-center justify-between gap-3 bg-[#14141a]">
                  <form onSubmit={handleRecordSearchSubmit} className="flex items-center gap-2 max-w-sm flex-1">
                    <div className="relative w-full">
                      <Search
                        size={13}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
                      />
                      <input
                        type="text"
                        value={recordSearch}
                        onChange={(e) => setRecordSearch(e.target.value)}
                        placeholder="Search records by keyword..."
                        className="w-full bg-[#0d0d12] border border-white/[0.08] rounded-xl pl-8 pr-7 py-1 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50"
                      />
                      {recordSearch && (
                        <button
                          type="button"
                          onClick={handleRecordSearchClear}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white"
                        >
                          <X size={12} />
                        </button>
                      )}
                    </div>
                    <button
                      type="submit"
                      className="px-2.5 py-1 bg-white/[0.06] hover:bg-white/[0.1] text-xs text-zinc-200 rounded-xl border border-white/[0.08] cursor-pointer"
                    >
                      Filter
                    </button>
                  </form>

                  {/* Page Size Selector */}
                  <div className="flex items-center gap-2 text-xs text-zinc-400">
                    <span className="hidden sm:inline">Rows per page:</span>
                    <select
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(Number(e.target.value));
                        setPage(1);
                      }}
                      className="bg-[#0d0d12] border border-white/[0.08] text-zinc-200 text-xs rounded-lg px-2 py-1 focus:outline-none cursor-pointer"
                    >
                      <option value={10}>10</option>
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </div>
                </div>

                {/* Table Data Grid */}
                <div className="flex-1 overflow-auto relative scrollbar-thin">
                  {recordsLoading ? (
                    <div className="h-64 flex items-center justify-center text-xs text-zinc-400 gap-2">
                      <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                      <span>Loading records...</span>
                    </div>
                  ) : records.length === 0 ? (
                    <div className="h-64 flex flex-col items-center justify-center p-8 text-center space-y-2">
                      <Table size={28} className="text-zinc-600" />
                      <p className="text-xs text-zinc-400">No records found in '{selectedTable}'</p>
                      <button
                        onClick={handleOpenAddModal}
                        disabled={isReadOnly}
                        className="px-3 py-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium mt-2 cursor-pointer shadow"
                      >
                        Insert First Record
                      </button>
                    </div>
                  ) : (
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="sticky top-0 bg-[#16161e] border-b border-white/[0.08] z-10 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                        <tr>
                          <th className="px-3 py-2.5 w-16 text-center border-r border-white/[0.04]">Actions</th>
                          {recordColumns.map((col) => {
                            const isPK =
                              primaryKeys.includes(col) ||
                              col.toLowerCase() === "_id" ||
                              col.toLowerCase() === "id";
                            const isCurrentSort = sortBy === col;

                            return (
                              <th
                                key={col}
                                onClick={() => handleSortToggle(col)}
                                className="px-3 py-2.5 cursor-pointer hover:bg-white/[0.04] transition-colors border-r border-white/[0.04] whitespace-nowrap select-none"
                              >
                                <div className="flex items-center gap-1.5">
                                  {isPK && <Key size={11} className="text-amber-400 shrink-0" />}
                                  <span className="font-mono text-zinc-200">{col}</span>
                                  {isCurrentSort ? (
                                    sortDir === "asc" ? (
                                      <ArrowUp size={12} className="text-indigo-400" />
                                    ) : (
                                      <ArrowDown size={12} className="text-indigo-400" />
                                    )
                                  ) : (
                                    <ArrowUpDown size={11} className="text-zinc-600 opacity-60" />
                                  )}
                                </div>
                              </th>
                            );
                          })}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.04]">
                        {records.map((row, idx) => (
                          <tr
                            key={idx}
                            className="hover:bg-white/[0.02] transition-colors group"
                          >
                            {/* Action Buttons */}
                            <td className="px-3 py-2 text-center border-r border-white/[0.04] whitespace-nowrap">
                              <div className="flex items-center justify-center gap-1.5">
                                <button
                                  onClick={() => handleOpenEditModal(row)}
                                  disabled={isReadOnly}
                                  title="Edit Record"
                                  className="p-1 rounded hover:bg-indigo-600/20 text-zinc-400 hover:text-indigo-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                                >
                                  <Edit2 size={13} />
                                </button>
                                <button
                                  onClick={() => setDeletingRecord(row)}
                                  disabled={isReadOnly}
                                  title="Delete Record"
                                  className="p-1 rounded hover:bg-rose-600/20 text-zinc-400 hover:text-rose-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                                >
                                  <Trash2 size={13} />
                                </button>
                              </div>
                            </td>

                            {/* Column Values */}
                            {recordColumns.map((col) => {
                              const val = row[col];
                              const isNull = val === null || val === undefined;
                              const isPK =
                                primaryKeys.includes(col) ||
                                col.toLowerCase() === "_id" ||
                                col.toLowerCase() === "id";

                              return (
                                <td
                                  key={col}
                                  className={`px-3 py-2 font-mono text-[11px] border-r border-white/[0.04] max-w-xs truncate ${
                                    isPK ? "text-amber-200/90 font-semibold" : "text-zinc-300"
                                  }`}
                                  title={isNull ? "NULL" : typeof val === "object" ? JSON.stringify(val) : String(val)}
                                >
                                  {isNull ? (
                                    <span className="text-zinc-600 italic">null</span>
                                  ) : typeof val === "boolean" ? (
                                    <span
                                      className={`px-1.5 py-0.5 rounded text-[10px] ${
                                        val
                                          ? "bg-emerald-500/15 text-emerald-400"
                                          : "bg-rose-500/15 text-rose-400"
                                      }`}
                                    >
                                      {String(val)}
                                    </span>
                                  ) : typeof val === "object" ? (
                                    <span className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-300 text-[10px]">
                                      {JSON.stringify(val)}
                                    </span>
                                  ) : (
                                    String(val)
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>

                {/* Pagination Controls */}
                <div className="p-3 bg-[#14141a] border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-400">
                  <div>
                    Showing{" "}
                    <span className="font-medium text-white">
                      {totalCount === 0 ? 0 : (page - 1) * pageSize + 1}
                    </span>{" "}
                    to{" "}
                    <span className="font-medium text-white">
                      {Math.min(page * pageSize, totalCount)}
                    </span>{" "}
                    of <span className="font-medium text-white">{totalCount.toLocaleString()}</span> records
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1 || recordsLoading}
                      className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 hover:text-white transition-all cursor-pointer"
                    >
                      <ChevronLeft size={14} />
                    </button>
                    <span className="px-2 text-zinc-300">
                      Page {page} of {totalPages}
                    </span>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages || recordsLoading}
                      className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 hover:text-white transition-all cursor-pointer"
                    >
                      <ChevronRight size={14} />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT: Columns Schema */}
            {activeTab === "columns" && (
              <div className="flex-1 overflow-auto rounded-xl border border-white/[0.08] bg-[#121216]">
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
                        <tr key={colName} className="hover:bg-white/[0.02] transition-colors">
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
              </div>
            )}

            {/* TAB CONTENT: Attributes & Constraints */}
            {activeTab === "preview" && (
              <div className="flex-1 overflow-auto rounded-xl border border-white/[0.08] bg-[#121216]">
                <table className="w-full text-left text-xs text-zinc-300">
                  <thead className="bg-[#14141a] text-[11px] font-semibold text-zinc-400 uppercase tracking-wider border-b border-white/[0.06]">
                    <tr>
                      <th className="px-4 py-3">Column Name</th>
                      <th className="px-4 py-3">SQL / Storage Type</th>
                      <th className="px-4 py-3">Nullable</th>
                      <th className="px-4 py-3">Primary Key</th>
                      <th className="px-4 py-3">Default Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {Object.entries(selectedColumns).map(([colName, colDef]) => {
                      const info = parseColumnInfo(colName, colDef, selectedTable);

                      return (
                        <tr key={colName} className="hover:bg-white/[0.02] transition-colors">
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
              </div>
            )}
          </div>
        ) : (
          <div className="p-12 text-center text-zinc-400 text-xs flex-1 flex flex-col items-center justify-center">
            <Database size={32} className="text-zinc-600 mb-2" />
            <p>Select a table or collection from the sidebar to inspect records and schemas.</p>
          </div>
        )}
      </div>

      {/* MODAL: ADD RECORD */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#14141a] border border-white/[0.1] rounded-2xl w-full max-w-xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Plus size={16} className="text-indigo-400" />
                  <span>Insert Record into '{selectedTable}'</span>
                </h3>
                <p className="text-[11px] text-zinc-400 mt-0.5">
                  Supply column values. Auto-generated IDs may be left empty.
                </p>
              </div>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-zinc-400 hover:text-white p-1"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateRecordSubmit} className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 overflow-y-auto p-5 space-y-3 scrollbar-thin">
                {Object.keys(modalFormData).map((col) => (
                  <div key={col} className="space-y-1">
                    <label className="block text-[11px] font-mono text-zinc-300">
                      {col}
                    </label>
                    <input
                      type="text"
                      value={modalFormData[col]}
                      onChange={(e) =>
                        setModalFormData((prev) => ({ ...prev, [col]: e.target.value }))
                      }
                      placeholder={`Enter value for ${col}...`}
                      className="w-full bg-[#0d0d12] border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500/50 font-mono"
                    />
                  </div>
                ))}
              </div>

              <div className="p-4 bg-[#101014] border-t border-white/[0.06] flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 text-xs text-zinc-400 hover:text-white rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading}
                  className="px-4 py-2 text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-semibold shadow-md flex items-center gap-1.5 cursor-pointer"
                >
                  {modalLoading && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                  <span>Save Record</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: EDIT RECORD */}
      {editingRecord && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#14141a] border border-white/[0.1] rounded-2xl w-full max-w-xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-white/[0.08] flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Edit2 size={16} className="text-indigo-400" />
                  <span>Edit Record in '{selectedTable}'</span>
                </h3>
                <p className="text-[11px] text-zinc-400 mt-0.5">
                  Update field values and save mutations directly to the database.
                </p>
              </div>
              <button
                onClick={() => setEditingRecord(null)}
                className="text-zinc-400 hover:text-white p-1"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleUpdateRecordSubmit} className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 overflow-y-auto p-5 space-y-3 scrollbar-thin">
                {Object.keys(modalFormData).map((col) => {
                  const pkObj = getRecordPrimaryKey(editingRecord);
                  const isPK = col in pkObj;

                  return (
                    <div key={col} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-[11px] font-mono text-zinc-300 flex items-center gap-1.5">
                          {isPK && <Key size={11} className="text-amber-400" />}
                          <span>{col}</span>
                        </label>
                        {isPK && (
                          <span className="text-[10px] text-amber-400/80 font-mono">Primary Key (Locked)</span>
                        )}
                      </div>
                      <input
                        type="text"
                        disabled={isPK}
                        value={modalFormData[col]}
                        onChange={(e) =>
                          setModalFormData((prev) => ({ ...prev, [col]: e.target.value }))
                        }
                        className={`w-full bg-[#0d0d12] border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs font-mono focus:outline-none ${
                          isPK
                            ? "text-zinc-500 cursor-not-allowed bg-white/[0.02]"
                            : "text-white focus:border-indigo-500/50"
                        }`}
                      />
                    </div>
                  );
                })}
              </div>

              <div className="p-4 bg-[#101014] border-t border-white/[0.06] flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingRecord(null)}
                  className="px-4 py-2 text-xs text-zinc-400 hover:text-white rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading}
                  className="px-4 py-2 text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-semibold shadow-md flex items-center gap-1.5 cursor-pointer"
                >
                  {modalLoading && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                  <span>Save Changes</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: DELETE CONFIRMATION */}
      {deletingRecord && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#14141a] border border-rose-500/30 rounded-2xl w-full max-w-md p-5 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-400">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Delete Record</h3>
                <p className="text-xs text-zinc-400">
                  Confirm permanent removal from '{selectedTable}'
                </p>
              </div>
            </div>

            <p className="text-xs text-zinc-300 leading-relaxed bg-[#0d0d12] p-3 rounded-xl border border-white/[0.06] font-mono break-all">
              {JSON.stringify(getRecordPrimaryKey(deletingRecord))}
            </p>

            <p className="text-xs text-rose-400">
              Warning: This action will permanently remove this record from the active database.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeletingRecord(null)}
                className="px-4 py-2 text-xs text-zinc-400 hover:text-white rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteRecordSubmit}
                disabled={modalLoading}
                className="px-4 py-2 text-xs bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white rounded-xl font-semibold shadow-md flex items-center gap-1.5 cursor-pointer"
              >
                {modalLoading && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                <span>Delete Record</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: CREATE TABLE / COLLECTION */}
      {isCreateEntityOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#14141a] border border-white/[0.1] rounded-2xl w-full max-w-md p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <FolderPlus size={16} className="text-indigo-400" />
                <span>Create Table / Collection</span>
              </h3>
              <button
                onClick={() => setIsCreateEntityOpen(false)}
                className="text-zinc-400 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateEntity} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs text-zinc-300">Name</label>
                <input
                  type="text"
                  value={newEntityName}
                  onChange={(e) => setNewEntityName(e.target.value)}
                  placeholder="e.g. products or activity_logs"
                  className="w-full bg-[#0d0d12] border border-white/[0.08] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateEntityOpen(false)}
                  className="px-4 py-2 text-xs text-zinc-400 hover:text-white rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading || !newEntityName.trim()}
                  className="px-4 py-2 text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-semibold shadow-md flex items-center gap-1.5 cursor-pointer"
                >
                  {modalLoading && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                  <span>Create</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: RENAME TABLE / COLLECTION */}
      {isRenameEntityOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#14141a] border border-white/[0.1] rounded-2xl w-full max-w-md p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Edit2 size={16} className="text-indigo-400" />
                <span>Rename '{selectedTable}'</span>
              </h3>
              <button
                onClick={() => setIsRenameEntityOpen(false)}
                className="text-zinc-400 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleRenameEntity} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs text-zinc-300">New Name</label>
                <input
                  type="text"
                  value={renameTargetName}
                  onChange={(e) => setRenameTargetName(e.target.value)}
                  placeholder="Enter new table/collection name..."
                  className="w-full bg-[#0d0d12] border border-white/[0.08] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500/50"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsRenameEntityOpen(false)}
                  className="px-4 py-2 text-xs text-zinc-400 hover:text-white rounded-xl cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading || !renameTargetName.trim()}
                  className="px-4 py-2 text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-semibold shadow-md flex items-center gap-1.5 cursor-pointer"
                >
                  {modalLoading && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                  <span>Rename</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: DROP TABLE / COLLECTION */}
      {isDropEntityOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#14141a] border border-rose-500/30 rounded-2xl w-full max-w-md p-5 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-400">
                <ShieldAlert size={20} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Drop '{selectedTable}'</h3>
                <p className="text-xs text-zinc-400">Permanent destruction of entity and all data</p>
              </div>
            </div>

            <p className="text-xs text-rose-300 leading-relaxed">
              This action will permanently delete the entire table/collection and all associated rows. To prevent accidental deletion, type{" "}
              <strong className="text-white font-mono">{selectedTable}</strong> below:
            </p>

            <input
              type="text"
              value={dropConfirmationText}
              onChange={(e) => setDropConfirmationText(e.target.value)}
              placeholder={`Type "${selectedTable}" to confirm`}
              className="w-full bg-[#0d0d12] border border-white/[0.08] rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-rose-500/50 font-mono"
            />

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsDropEntityOpen(false)}
                className="px-4 py-2 text-xs text-zinc-400 hover:text-white rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDropEntity}
                disabled={modalLoading || dropConfirmationText.trim() !== selectedTable}
                className="px-4 py-2 text-xs bg-rose-600 hover:bg-rose-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl font-semibold shadow-md flex items-center gap-1.5 cursor-pointer"
              >
                {modalLoading && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                <span>Drop Entity</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
