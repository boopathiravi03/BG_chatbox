import { useEffect, useState } from "react";
import { Database, Table, FileText, Columns, HardDrive, CheckCircle, XCircle, Unplug } from "lucide-react";
import { disconnectDatabase } from "../../services/api";

interface DatabaseInfo {
  database: string;
  tables: number;
  rows: number;
  columns: number;
  size: string;
  error?: string;
}

interface Props {
  onClose?: () => void;
  onDisconnected?: () => void;
}

export default function DatabaseStats({ onClose, onDisconnected }: Props) {
  const [info, setInfo] = useState<DatabaseInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState(false);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8001/database-info");
        const data = await response.json();
        setInfo(data);
      } catch (error) {
        setInfo({
          database: "Unknown",
          tables: 0,
          rows: 0,
          columns: 0,
          size: "0 MB",
          error: "Failed to load database info",
        });
      } finally {
        setLoading(false);
      }
    };

    fetchInfo();
  }, []);

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await disconnectDatabase();
      onDisconnected?.();
      onClose?.();
    } catch (error) {
      console.error("Failed to disconnect:", error);
    } finally {
      setDisconnecting(false);
    }
  };

  if (loading) {
    return (
      <div className="dark:bg-[#1a1a1a] bg-white border border-white/10 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-center py-8">
          <div className="dark:text-gray-400 text-gray-700">Loading database info...</div>
        </div>
      </div>
    );
  }

  if (info?.error) {
    return (
      <div className="dark:bg-[#1a1a1a] bg-white border border-red-500/30 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Database size={20} />
            Database Overview
          </h2>
          {onClose && (
            <button onClick={onClose} className="dark:text-gray-400 text-gray-700 hover:text-black dark:hover:text-white">×</button>
          )}
        </div>
        <p className="text-red-400 text-sm">{info.error}</p>
      </div>
    );
  }

  return (
    <div className="dark:bg-[#1a1a1a] bg-white border border-white/10 rounded-2xl p-6 w-full max-w-md">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Database size={20} />
          Database Overview
        </h2>
        {onClose && (
          <button onClick={onClose} className="dark:text-gray-400 text-gray-700 hover:text-black dark:hover:text-white">×</button>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 dark:bg-white/5 bg-gray-100 rounded-xl">
          <div className="flex items-center gap-2 dark:text-gray-400 text-gray-700">
            <Database size={16} />
            <span className="text-sm">Database</span>
          </div>
          <span className="text-sm font-mono dark:text-white text-black">{info?.database}</span>
        </div>

        <div className="flex items-center justify-between p-3 dark:bg-white/5 bg-gray-100 rounded-xl">
          <div className="flex items-center gap-2 dark:text-gray-400 text-gray-700">
            <Table size={16} />
            <span className="text-sm">Tables</span>
          </div>
          <span className="text-sm font-semibold dark:text-white text-black">{info?.tables}</span>
        </div>

        <div className="flex items-center justify-between p-3 dark:bg-white/5 bg-gray-100 rounded-xl">
          <div className="flex items-center gap-2 dark:text-gray-400 text-gray-700">
            <FileText size={16} />
            <span className="text-sm">Rows</span>
          </div>
          <span className="text-sm font-semibold dark:text-white text-black">{info?.rows?.toLocaleString()}</span>
        </div>

        <div className="flex items-center justify-between p-3 dark:bg-white/5 bg-gray-100 rounded-xl">
          <div className="flex items-center gap-2 dark:text-gray-400 text-gray-700">
            <Columns size={16} />
            <span className="text-sm">Columns</span>
          </div>
          <span className="text-sm font-semibold dark:text-white text-black">{info?.columns}</span>
        </div>

        <div className="flex items-center justify-between p-3 dark:bg-white/5 bg-gray-100 rounded-xl">
          <div className="flex items-center gap-2 dark:text-gray-400 text-gray-700">
            <HardDrive size={16} />
            <span className="text-sm">Size</span>
          </div>
          <span className="text-sm font-semibold dark:text-white text-black">{info?.size}</span>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-4">
        <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/20 rounded-xl flex-1">
          <CheckCircle size={16} className="text-green-400" />
          <span className="text-sm text-green-400">Connected</span>
        </div>
        <button
          onClick={handleDisconnect}
          disabled={disconnecting}
          className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl hover:bg-red-500/20 transition-colors disabled:opacity-50"
          title="Disconnect database"
        >
          <Unplug size={16} className="text-red-400" />
        </button>
      </div>
    </div>
  );
}
