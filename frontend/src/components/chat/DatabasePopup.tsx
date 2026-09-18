import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database,
  X,
  Table,
  Download,
  Upload,
  Save,
  Unplug,
  AlertTriangle,
  Loader2,
  Search,
} from "lucide-react";
import {
  getSchema,
  getDatabaseInfo,
  createBackup,
  restoreDatabase,
  downloadBackup,
  disconnectDatabase,
} from "../../services/api";
import {
  modalBackdropVariants,
  modalContainerVariants,
} from "../../lib/motion";
import { useToast } from "../../context/ToastContext";

import DisconnectConfirmationModal from "./DisconnectConfirmationModal";

interface Props {
  onClose: () => void;
  onDisconnected?: () => void;
}

export default function DatabasePopup({ onClose, onDisconnected }: Props) {
  const [schema, setSchema] = useState<Record<string, any>>({});
  const [dbInfo, setDbInfo] = useState<{
    database?: string;
    tables?: number;
    rows?: number;
    size?: string;
  }>({});
  const [loading, setLoading] = useState(true);
  const [backupLoading, setBackupLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [showDisconnectConfirmModal, setShowDisconnectConfirmModal] =
    useState(false);
  const [tableSearch, setTableSearch] = useState("");
  const toast = useToast();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [schemaData, infoData] = await Promise.all([
          getSchema(),
          getDatabaseInfo(),
        ]);
        setSchema(schemaData || {});
        setDbInfo(infoData || {});
      } catch (error) {
        console.error("Failed to fetch database info:", error);
        toast.error("Could not load database details.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const tables = Object.keys(schema);
  const filteredTables = tables.filter((t) =>
    t.toLowerCase().includes(tableSearch.toLowerCase()),
  );

  const handleBackup = async () => {
    setBackupLoading(true);
    try {
      const data = await createBackup();
      if (data.status === "success") {
        toast.success(`Backup created: ${data.size || "saved"}`);
      } else {
        toast.error(data.message || "Backup failed");
      }
    } catch {
      toast.error("Backup operation encountered an error.");
    } finally {
      setBackupLoading(false);
    }
  };

  const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setRestoreLoading(true);
    try {
      const data = await restoreDatabase(file);
      if (data.status === "success") {
        toast.success("Database restored successfully.");
        setTimeout(() => {
          onClose();
          window.location.reload();
        }, 1200);
      } else {
        toast.error(data.message || "Restore failed");
      }
    } catch {
      toast.error("Database restore failed.");
    } finally {
      setRestoreLoading(false);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await downloadBackup();
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download =
        response.headers
          .get("Content-Disposition")
          ?.split("filename=")[1]
          ?.replace(/"/g, "") || "backup.db";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast.success("Backup downloaded.");
    } catch {
      toast.error("Download failed.");
    }
  };

  const handleDisconnectConfirm = async () => {
    try {
      await disconnectDatabase();
      toast.info("Database disconnected.");
      onDisconnected?.();
      onClose();
    } catch {
      toast.error("Failed to disconnect database.");
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
        {/* Backdrop */}
        <motion.div
          key="db-modal-backdrop"
          variants={modalBackdropVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={onClose}
          className="fixed inset-0 bg-black/75 backdrop-blur-sm"
        />

        {/* Modal Container */}
        <motion.div
          key="db-modal-container"
          variants={modalContainerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="relative w-full max-w-2xl rounded-2xl bg-[#121215] border border-white/10 shadow-2xl shadow-black/90 overflow-hidden z-10 flex flex-col max-h-[90vh]"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 sm:py-5 border-b border-white/[0.08]">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0">
                <Database size={20} />
              </div>
              <div>
                <div className="flex items-center gap-2.5">
                  <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                    Connected Database
                  </h2>
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-[11px] font-medium text-emerald-400 font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Online
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-zinc-300 font-mono truncate max-w-[320px] mt-0.5">
                  {dbInfo.database || "Active Session"}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Body */}
          <div className="p-6 overflow-y-auto space-y-6">
            {/* Metric Cards */}
            <div className="grid grid-cols-3 gap-3.5">
              <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <p className="text-xs sm:text-sm text-zinc-400 mb-1 font-medium">
                  Tables
                </p>
                <p className="text-2xl sm:text-3xl font-bold text-white">
                  {loading ? "..." : (dbInfo.tables ?? tables.length)}
                </p>
              </div>
              <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <p className="text-xs sm:text-sm text-zinc-400 mb-1 font-medium">
                  Total Rows
                </p>
                <p className="text-2xl sm:text-3xl font-bold text-white">
                  {loading ? "..." : (dbInfo.rows ?? 0).toLocaleString()}
                </p>
              </div>
              <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                <p className="text-xs sm:text-sm text-zinc-400 mb-1 font-medium">
                  Storage
                </p>
                <p className="text-2xl sm:text-3xl font-bold text-white">
                  {loading ? "..." : dbInfo.size || "Local"}
                </p>
              </div>
            </div>

            {/* Tables Section */}
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <label className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                  <Table size={15} className="text-indigo-400" />
                  Schema Tables
                </label>
                <span className="text-xs font-mono text-zinc-400">
                  {tables.length} {tables.length === 1 ? "table" : "tables"}
                </span>
              </div>

              {tables.length > 5 && (
                <div className="relative mb-2.5">
                  <Search
                    size={15}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400"
                  />
                  <input
                    type="text"
                    placeholder="Search tables..."
                    value={tableSearch}
                    onChange={(e) => setTableSearch(e.target.value)}
                    className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500/50 transition-colors"
                  />
                </div>
              )}

              {loading ? (
                <div className="py-10 flex items-center justify-center gap-2.5 text-sm text-zinc-400">
                  <Loader2 size={16} className="animate-spin text-indigo-400" />
                  Reading database catalog...
                </div>
              ) : tables.length === 0 ? (
                <div className="py-8 text-center text-sm text-zinc-400 border border-dashed border-white/[0.08] rounded-xl">
                  No tables found in this database.
                </div>
              ) : (
                <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                  {filteredTables.map((tbl) => {
                    const colCount = schema[tbl]
                      ? Object.keys(schema[tbl]).length
                      : 0;
                    return (
                      <div
                        key={tbl}
                        className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.04] transition-colors"
                      >
                        <span className="text-sm font-mono text-zinc-200 truncate">
                          {tbl}
                        </span>
                        <span className="text-xs text-zinc-300 bg-white/[0.05] px-2.5 py-1 rounded-md font-mono">
                          {colCount} cols
                        </span>
                      </div>
                    );
                  })}
                  {filteredTables.length === 0 && (
                    <p className="text-sm text-zinc-500 py-4 text-center">
                      No matching tables found.
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Operations Section */}
            <div className="pt-2 border-t border-white/[0.06]">
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
                Operations & Maintenance
              </p>
              <div className="grid grid-cols-3 gap-2.5">
                <button
                  onClick={handleBackup}
                  disabled={backupLoading}
                  className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-sm font-medium text-zinc-100 transition-all disabled:opacity-50"
                >
                  {backupLoading ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Save size={15} />
                  )}
                  <span>Backup</span>
                </button>

                <label className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-sm font-medium text-zinc-100 transition-all cursor-pointer disabled:opacity-50">
                  {restoreLoading ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Upload size={15} />
                  )}
                  <span>Restore</span>
                  <input
                    type="file"
                    accept=".db"
                    onChange={handleRestore}
                    className="hidden"
                    disabled={restoreLoading}
                  />
                </label>

                <button
                  onClick={handleDownload}
                  className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-sm font-medium text-zinc-100 transition-all"
                >
                  <Download size={15} />
                  <span>Download</span>
                </button>
              </div>
            </div>
          </div>

          {/* Footer with Disconnect Action */}
          <div className="p-4 sm:p-5 border-t border-white/[0.08] bg-black/25 flex items-center justify-between">
            <button
              onClick={() => setShowDisconnectConfirmModal(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/20 transition-all cursor-pointer group"
            >
              <Unplug
                size={15}
                className="group-hover:rotate-[-12deg] transition-transform"
              />
              <span>Disconnect Database</span>
            </button>

            <button
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl bg-white/[0.08] hover:bg-white/[0.12] text-sm font-semibold text-white transition-colors cursor-pointer"
            >
              Done
            </button>
          </div>
        </motion.div>

        {/* Dedicated Animated Disconnect Confirmation Modal */}
        <DisconnectConfirmationModal
          isOpen={showDisconnectConfirmModal}
          onClose={() => setShowDisconnectConfirmModal(false)}
          onConfirm={handleDisconnectConfirm}
          dbType={dbInfo.database?.includes(".db") ? "sqlite" : "database"}
          dbName={dbInfo.database}
        />
      </div>
    </AnimatePresence>
  );
}
