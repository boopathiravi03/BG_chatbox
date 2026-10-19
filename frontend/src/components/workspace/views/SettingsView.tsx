import React, { useState, useEffect } from "react";
import {
  Settings,
  Database,
  Unplug,
  Plug,
  Download,
  Upload,
  ShieldCheck,
  Cpu,
  Lock,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import {
  getDatabaseInfo,
  getDatabaseType,
  createBackup,
  restoreDatabase,
  downloadBackup,
  disconnectDatabase,
} from "../../../services/api";
import { useToast } from "../../../context/ToastContext";

interface SettingsViewProps {
  dbConnected: boolean;
  dbType: string | null;
  onConnectDatabase: () => void;
  onDisconnect: () => void;
}

export default function SettingsView({
  dbConnected,
  dbType,
  onConnectDatabase,
  onDisconnect,
}: SettingsViewProps) {
  const [dbInfo, setDbInfo] = useState<any>({});
  const [backupLoading, setBackupLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (dbConnected) {
      getDatabaseInfo()
        .then((info) => setDbInfo(info || {}))
        .catch(() => {});
    } else {
      setDbInfo({});
    }
  }, [dbConnected]);

  const handleBackup = async () => {
    setBackupLoading(true);
    try {
      const res = await createBackup();
      if (res && res.status !== "error") {
        toast.success("Database backup snapshot created");
      } else {
        toast.error(res?.message || "Failed to create backup");
      }
    } catch {
      toast.error("Backup creation failed");
    } finally {
      setBackupLoading(false);
    }
  };

  const handleDownloadBackup = async () => {
    try {
      const res = await downloadBackup();
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `backup_${Date.now()}.db`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success("Backup downloaded to your device");
    } catch {
      toast.error("No backup available to download");
    }
  };

  const handleRestoreFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRestoreLoading(true);
    try {
      const res = await restoreDatabase(file);
      if (res && res.status !== "error") {
        toast.success("Database restored successfully");
      } else {
        toast.error(res?.message || "Restore failed");
      }
    } catch {
      toast.error("Failed to restore database file");
    } finally {
      setRestoreLoading(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
      {/* Settings Header */}
      <div>
        <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
          <Settings size={20} className="text-indigo-400" />
          <span>Workspace & Database Settings</span>
        </h2>
        <p className="text-xs text-zinc-400 mt-0.5">
          Manage active connections, snapshot backups, and AI governance parameters.
        </p>
      </div>

      {/* Database Connection Panel */}
      <div className="p-6 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-5">
        <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/25 text-indigo-400">
              <Database size={20} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Active Database Connection</h3>
              <p className="text-xs text-zinc-400">SQLAlchemy multi-dialect engine</p>
            </div>
          </div>

          {dbConnected ? (
            <button
              onClick={onDisconnect}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-semibold transition-all cursor-pointer"
            >
              <Unplug size={14} />
              <span>Disconnect</span>
            </button>
          ) : (
            <button
              onClick={onConnectDatabase}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all cursor-pointer"
            >
              <Plug size={14} />
              <span>Connect Database</span>
            </button>
          )}
        </div>

        {dbConnected ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-1">
              <span className="text-zinc-500">Engine Type</span>
              <p className="font-mono font-semibold text-white uppercase">{dbType || "SQLite"}</p>
            </div>

            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-1">
              <span className="text-zinc-500">Database Name / Path</span>
              <p className="font-mono font-semibold text-white truncate">
                {dbInfo.database || "Active Session"}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-1">
              <span className="text-zinc-500">Total Entities</span>
              <p className="font-mono font-semibold text-white">
                {dbInfo.tables !== undefined ? `${dbInfo.tables} tables` : "Profiled"}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-1">
              <span className="text-zinc-500">Security Credentials</span>
              <p className="font-mono font-semibold text-emerald-400 flex items-center gap-1">
                <Lock size={12} />
                <span>Masked & Protected (Zero storage)</span>
              </p>
            </div>
          </div>
        ) : (
          <div className="p-6 text-center text-xs text-zinc-500">
            No database currently connected.
          </div>
        )}
      </div>

      {/* Snapshot Backup & Restore */}
      <div className="p-6 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Download size={16} className="text-indigo-400" />
          <span>Snapshots & Database Backups</span>
        </h3>
        <p className="text-xs text-zinc-400">
          Create snapshots or restore previous database archives for safety.
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            onClick={handleBackup}
            disabled={!dbConnected || backupLoading}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] disabled:opacity-50 border border-white/[0.08] text-xs font-semibold text-zinc-200 transition-all cursor-pointer"
          >
            <Download size={14} />
            <span>{backupLoading ? "Creating..." : "Create Backup"}</span>
          </button>

          <button
            onClick={handleDownloadBackup}
            disabled={!dbConnected}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] disabled:opacity-50 border border-white/[0.08] text-xs font-semibold text-zinc-200 transition-all cursor-pointer"
          >
            <Download size={14} />
            <span>Download Latest Backup</span>
          </button>

          <label className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-semibold text-zinc-200 transition-all cursor-pointer">
            <Upload size={14} />
            <span>{restoreLoading ? "Restoring..." : "Restore Snapshot"}</span>
            <input
              type="file"
              accept=".db,.sqlite,.sqlite3"
              onChange={handleRestoreFile}
              className="hidden"
            />
          </label>
        </div>
      </div>

      {/* AI Intelligence Engine & Governance */}
      <div className="p-6 rounded-2xl bg-[#121216] border border-white/[0.08] space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Cpu size={16} className="text-indigo-400" />
          <span>AI Intelligence Engine</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-1">
            <span className="text-zinc-500">Active LLM Model</span>
            <p className="font-mono font-semibold text-white">BG AI</p>
            <p className="text-[11px] text-zinc-500">Groq ultra-low-latency inference</p>
          </div>

          <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-1">
            <span className="text-zinc-500">Write Safeguards</span>
            <p className="font-mono font-semibold text-emerald-400 flex items-center gap-1">
              <ShieldCheck size={13} />
              <span>Two-Stage Confirmation Active</span>
            </p>
            <p className="text-[11px] text-zinc-500">INSERT/UPDATE/DELETE requires confirmation</p>
          </div>
        </div>
      </div>
    </div>
  );
}
