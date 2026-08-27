import { useState, useEffect } from "react";
import { Database, X, Table, Download, Upload, Save, Unplug } from "lucide-react";
import { getSchema, getDatabaseInfo, createBackup, restoreDatabase, downloadBackup, disconnectDatabase } from "../../services/api";

interface Props {
  onClose: () => void;
  onDisconnected?: () => void;
}

interface SchemaTable {
  table_name: string;
}

export default function DatabasePopup({ onClose, onDisconnected }: Props) {
  const [schema, setSchema] = useState<Record<string, any>>({});
  const [dbInfo, setDbInfo] = useState<{ database?: string; tables?: number; rows?: number; size?: string }>({});
  const [loading, setLoading] = useState(true);
  const [backupLoading, setBackupLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [disconnecting, setDisconnecting] = useState(false);

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
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const tables = Object.keys(schema);

  const handleBackup = async () => {
    setBackupLoading(true);
    setMessage("");
    try {
      const data = await createBackup();
      if (data.status === "success") {
        setMessage(`✅ ${data.message} (${data.size})`);
      } else {
        setMessage(`❌ ${data.message}`);
      }
    } catch (error) {
      setMessage("❌ Backup failed");
    } finally {
      setBackupLoading(false);
    }
  };

  const handleRestore = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setRestoreLoading(true);
    setMessage("");
    try {
      const data = await restoreDatabase(file);
      if (data.status === "success") {
        setMessage(`✅ ${data.message}`);
        setTimeout(() => {
          onClose();
          window.location.reload();
        }, 1500);
      } else {
        setMessage(`❌ ${data.message}`);
      }
    } catch (error) {
      setMessage("❌ Restore failed");
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
      a.download = response.headers.get("Content-Disposition")?.split("filename=")[1]?.replace(/"/g, "") || "backup.db";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      setMessage("✅ Backup downloaded");
    } catch (error) {
      setMessage("❌ Download failed");
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    setMessage("");
    try {
      await disconnectDatabase();
      onDisconnected?.();
      onClose();
    } catch (error) {
      setMessage("❌ Disconnect failed");
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="dark:bg-[#1a1a1a] bg-white border border-white/10 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Database size={20} />
            Current Database
          </h2>
          <button onClick={onClose} className="dark:text-gray-400 text-gray-700 hover:text-black dark:hover:text-white">
            <X size={20} />
          </button>
        </div>

        <div className="mb-4">
          <p className="text-sm dark:text-gray-400 text-gray-700 mb-2">Database</p>
          <p className="text-sm font-mono dark:bg-white/5 bg-gray-100 rounded-lg px-3 py-2 dark:text-white text-black">
            {dbInfo.database || "Not Connected"}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="dark:bg-white/5 bg-gray-100 rounded-xl p-3">
            <p className="text-xs dark:text-gray-400 text-gray-500 mb-1">Tables</p>
            <p className="text-lg font-semibold dark:text-white text-black">{dbInfo.tables ?? tables.length}</p>
          </div>
          <div className="dark:bg-white/5 bg-gray-100 rounded-xl p-3">
            <p className="text-xs dark:text-gray-400 text-gray-500 mb-1">Rows</p>
            <p className="text-lg font-semibold dark:text-white text-black">{dbInfo.rows ?? 0}</p>
          </div>
        </div>

        <div className="mb-4">
          <p className="text-sm dark:text-gray-400 text-gray-700 mb-2 flex items-center gap-2">
            <Table size={14} />
            Tables
          </p>
          {loading ? (
            <p className="text-sm dark:text-gray-500 text-gray-500">Loading...</p>
          ) : tables.length === 0 ? (
            <p className="text-sm dark:text-gray-500 text-gray-500">No tables found</p>
          ) : (
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {tables.map((table) => (
                <div
                  key={table}
                  className="text-sm dark:bg-white/5 bg-gray-100 rounded-lg px-3 py-2 dark:text-white text-black"
                >
                  {table}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="border-t border-white/10 dark:border-gray-700 pt-4 space-y-2">
          <p className="text-xs dark:text-gray-400 text-gray-500 mb-2">Backup & Restore</p>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <button
              onClick={handleBackup}
              disabled={backupLoading}
              className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm"
            >
              <Save size={14} />
              {backupLoading ? "Saving..." : "Backup"}
            </button>
            <label className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm cursor-pointer">
              <Upload size={14} />
              {restoreLoading ? "Restoring..." : "Restore"}
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
              className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm"
            >
              <Download size={14} />
              Download
            </button>
          </div>

          <button
            onClick={handleDisconnect}
            disabled={disconnecting}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/30 disabled:opacity-50 text-red-400 text-sm border border-red-500/20"
          >
            <Unplug size={14} />
            {disconnecting ? "Disconnecting..." : "Disconnect Database"}
          </button>
        </div>

        {message && (
          <p className="mt-4 text-sm text-center">{message}</p>
        )}
      </div>
    </div>
  );
}
