import { useState, useEffect } from "react";
import { X, Server, CheckCircle, Database } from "lucide-react";
import { connectDatabase, getDatabaseInfo } from "../../services/api";

interface Props {
  onClose: () => void;
  onConnected?: () => void;
  defaultType?: "mysql" | "postgres";
}

type DbType = "mysql" | "postgres";

export default function ConnectDatabaseModal({ onClose, onConnected, defaultType = "mysql" }: Props) {
  const [dbType, setDbType] = useState<DbType>(defaultType);
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState("");
  const [connected, setConnected] = useState(false);

  const [form, setForm] = useState({
    host: "localhost",
    port: defaultType === "mysql" ? "3306" : "5432",
    database: "",
    username: defaultType === "mysql" ? "root" : "postgres",
    password: "",
  });

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      port: defaultType === "mysql" ? "3306" : "5432",
      username: defaultType === "mysql" ? "root" : "postgres",
    }));
  }, [defaultType]);

  const handleConnect = async () => {
    setConnecting(true);
    setMessage("");

    try {
      const data = await connectDatabase({
        db_type: dbType,
        host: form.host,
        port: parseInt(form.port),
        database: form.database,
        username: form.username,
        password: form.password,
      });

      if (data.status === "success") {
        setMessage(`✅ Connected to ${dbType === "mysql" ? "MySQL" : "PostgreSQL"}`);
        setConnected(true);
        setTimeout(() => {
          onClose();
          onConnected?.();
        }, 1500);
      } else {
        setMessage(`❌ Error: ${data.message || "Connection failed"}`);
      }
    } catch (error) {
      setMessage("❌ Error connecting to database");
    } finally {
      setConnecting(false);
    }
  };

  const updateForm = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Server size={20} />
            Connect {dbType === "mysql" ? "MySQL" : "PostgreSQL"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Host</label>
            <input
              type="text"
              value={form.host}
              onChange={(e) => updateForm("host", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Port</label>
            <input
              type="text"
              value={form.port}
              onChange={(e) => updateForm("port", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Database</label>
            <input
              type="text"
              value={form.database}
              onChange={(e) => updateForm("database", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Username</label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => updateForm("username", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Password</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => updateForm("password", e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={handleConnect}
            disabled={connecting || !form.database}
            className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
          >
            <Server size={16} />
            {connecting ? "Connecting..." : "Connect"}
          </button>
        </div>

        {message && (
          <p className="mt-4 text-sm text-center">{message}</p>
        )}
      </div>
    </div>
  );
}
