import { useState } from "react";
import { Database, Upload, X, Server } from "lucide-react";
import { API_BASE, connectDatabase } from "../../services/api";

interface Props {
  onClose: () => void;
  onUploadComplete?: () => void;
}

type DbType = "sqlite" | "mysql" | "postgres";

export default function DatabaseUploader({ onClose, onUploadComplete }: Props) {
  const [dbType, setDbType] = useState<DbType>("sqlite");
  const [uploading, setUploading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState("");

  const [mysqlForm, setMysqlForm] = useState({
    host: "localhost",
    port: "3306",
    database: "",
    username: "root",
    password: "",
  });

  const [postgresForm, setPostgresForm] = useState({
    host: "localhost",
    port: "5432",
    database: "postgres",
    username: "postgres",
    password: "",
  });

  const handleSqliteUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMessage("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setMessage("✅ SQLite Connected");
        setTimeout(() => {
          onClose();
          onUploadComplete?.();
        }, 1500);
      } else {
        setMessage(`❌ Error: ${data.message || "Upload failed"}`);
      }
    } catch (error) {
      setMessage("❌ Error uploading database");
    } finally {
      setUploading(false);
    }
  };

  const handleConnect = async () => {
    setConnecting(true);
    setMessage("");

    try {
      const form = dbType === "mysql" ? mysqlForm : postgresForm;
      const data = await connectDatabase({
        db_type: dbType === "mysql" ? "mysql" : "postgres",
        host: form.host,
        port: parseInt(form.port),
        database: form.database,
        username: form.username,
        password: form.password,
      });

      if (data.status === "success") {
        setMessage(`✅ Connected to ${dbType === "mysql" ? "MySQL" : "PostgreSQL"}`);
        setTimeout(() => {
          onClose();
          onUploadComplete?.();
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

  const updateForm = (form: typeof mysqlForm | typeof postgresForm, field: string, value: string) => {
    if (dbType === "mysql") {
      setMysqlForm((prev) => ({ ...prev, [field]: value }));
    } else {
      setPostgresForm((prev) => ({ ...prev, [field]: value }));
    }
  };

  const currentForm = dbType === "mysql" ? mysqlForm : postgresForm;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Database size={20} />
            Connect Database
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        <div className="flex gap-2 mb-4">
          {[
            { key: "sqlite", label: "SQLite (.db)" },
            { key: "mysql", label: "MySQL" },
            { key: "postgres", label: "PostgreSQL" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setDbType(tab.key as DbType)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                dbType === tab.key
                  ? "bg-blue-600 text-white"
                  : "bg-white/5 text-gray-400 hover:bg-white/10"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {dbType === "sqlite" ? (
          <div className="border-2 border-dashed border-white/10 rounded-xl p-8 text-center hover:border-white/20 transition-colors">
            <Upload size={48} className="mx-auto mb-4 text-gray-400" />
            <p className="text-sm text-gray-400 mb-4">
              Drop your SQLite file here or click to browse
            </p>
            <label className="cursor-pointer">
              <input
                type="file"
                accept=".db,.sqlite,.sqlite3"
                onChange={handleSqliteUpload}
                className="hidden"
                disabled={uploading}
              />
              <span className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors">
                {uploading ? "Uploading..." : "Choose File"}
              </span>
            </label>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Host</label>
              <input
                type="text"
                value={currentForm.host}
                onChange={(e) => updateForm(currentForm, "host", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Port</label>
              <input
                type="text"
                value={currentForm.port}
                onChange={(e) => updateForm(currentForm, "port", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Database</label>
              <input
                type="text"
                value={currentForm.database}
                onChange={(e) => updateForm(currentForm, "database", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Username</label>
              <input
                type="text"
                value={currentForm.username}
                onChange={(e) => updateForm(currentForm, "username", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Password</label>
              <input
                type="password"
                value={currentForm.password}
                onChange={(e) => updateForm(currentForm, "password", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white outline-none focus:border-blue-500"
              />
            </div>
            <button
              onClick={handleConnect}
              disabled={connecting || !currentForm.database}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
            >
              <Server size={16} />
              {connecting ? "Connecting..." : "Connect"}
            </button>
          </div>
        )}

        {message && (
          <p className="mt-4 text-sm text-center">{message}</p>
        )}
      </div>
    </div>
  );
}
