import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Server,
  Database,
  Layers,
  Loader2,
  FileUp,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  HardDrive,
} from "lucide-react";
import { connectDatabase, API_BASE } from "../../services/api";
import {
  modalBackdropVariants,
  modalContainerVariants,
} from "../../lib/motion";
import { useToast } from "../../context/ToastContext";
import ClickSpark from "../reactbits/ClickSpark";
import SpotlightCard from "../reactbits/SpotlightCard";

interface Props {
  onClose: () => void;
  onConnected?: () => void;
  defaultType?: "sqlite" | "mysql" | "postgres";
}

type DbType = "sqlite" | "mysql" | "postgres";
type ConnectionStage =
  | "idle"
  | "connecting"
  | "verifying"
  | "connected"
  | "error";

export default function ConnectDatabaseModal({
  onClose,
  onConnected,
  defaultType = "sqlite",
}: Props) {
  const [dbType, setDbType] = useState<DbType>(defaultType);
  const [stage, setStage] = useState<ConnectionStage>("idle");
  const [stageMessage, setStageMessage] = useState<string>("");
  const [connectedSummary, setConnectedSummary] = useState<{
    name: string;
    engine: string;
    details?: string;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [isDragOver, setIsDragOver] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const toast = useToast();

  const [form, setForm] = useState({
    host: "localhost",
    port: defaultType === "postgres" ? "5432" : "3306",
    database: defaultType === "postgres" ? "postgres" : "bg_ai_db",
    username: defaultType === "postgres" ? "postgres" : "root",
    password: "",
  });

  // Close on Escape key (if not currently connecting)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === "Escape" &&
        stage !== "connecting" &&
        stage !== "verifying"
      ) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, stage]);

  // Update default ports and credentials when tab switches
  useEffect(() => {
    setErrorMessage(null);
    if (dbType === "mysql") {
      setForm((prev) => ({
        ...prev,
        port: prev.port === "5432" || !prev.port ? "3306" : prev.port,
        database:
          prev.database === "postgres"
            ? "bg_ai_db"
            : prev.database || "bg_ai_db",
        username:
          prev.username === "postgres" ? "root" : prev.username || "root",
      }));
    } else if (dbType === "postgres") {
      setForm((prev) => ({
        ...prev,
        port: prev.port === "3306" || !prev.port ? "5432" : prev.port,
        database:
          prev.database === "bg_ai_db"
            ? "postgres"
            : prev.database || "postgres",
        username:
          prev.username === "root" ? "postgres" : prev.username || "postgres",
      }));
    }
  }, [dbType]);

  // Connect MySQL or PostgreSQL with multi-stage progress
  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setStage("connecting");
    setStageMessage(
      `Connecting to ${dbType === "mysql" ? "MySQL" : "PostgreSQL"} server at ${form.host}:${form.port}...`,
    );

    try {
      // Step 2 progression simulation while request executes
      const verifyTimer = setTimeout(() => {
        setStage("verifying");
        setStageMessage(
          `Verifying credentials & introspecting schema for "${form.database}"...`,
        );
      }, 500);

      const data = await connectDatabase({
        db_type: dbType,
        host: form.host,
        port: parseInt(form.port) || (dbType === "mysql" ? 3306 : 5432),
        database: form.database,
        username: form.username,
        password: form.password,
      });

      clearTimeout(verifyTimer);

      if (data.status === "success") {
        setStage("connected");
        setConnectedSummary({
          name: form.database,
          engine: dbType === "mysql" ? "MySQL" : "PostgreSQL",
          details: `${form.host}:${form.port} • Catalog Loaded`,
        });
        toast.success(
          `Connected to ${dbType === "mysql" ? "MySQL" : "PostgreSQL"} successfully!`,
        );
        setTimeout(() => {
          onClose();
          onConnected?.();
        }, 900);
      } else {
        setStage("error");
        setErrorMessage(
          data.message ||
            "Connection failed. Please check credentials and server status.",
        );
        toast.error(
          data.message || "Connection failed. Please check credentials.",
        );
      }
    } catch {
      setStage("error");
      setErrorMessage(
        "Network or database connection error. Verify if the database server is running.",
      );
      toast.error("Network or database connection error.");
    }
  };

  // Upload SQLite File with multi-stage progress
  const handleFileUpload = async (file: File) => {
    if (
      !file.name.endsWith(".db") &&
      !file.name.endsWith(".sqlite") &&
      !file.name.endsWith(".sqlite3")
    ) {
      toast.error(
        "Please upload a valid SQLite file (.db, .sqlite, or .sqlite3)",
      );
      return;
    }

    setErrorMessage(null);
    setStage("connecting");
    setStageMessage(`Reading SQLite file "${file.name}"...`);

    try {
      const verifyTimer = setTimeout(() => {
        setStage("verifying");
        setStageMessage("Validating database schema and indexing tables...");
      }, 400);

      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      clearTimeout(verifyTimer);
      const data = await response.json();

      if (response.ok && data.status === "success") {
        setStage("connected");
        setConnectedSummary({
          name: file.name,
          engine: "SQLite",
          details: `${(file.size / 1024).toFixed(1)} KB • Session Ready`,
        });
        toast.success(`SQLite database "${file.name}" connected successfully!`);
        setTimeout(() => {
          onClose();
          onConnected?.();
        }, 900);
      } else {
        setStage("error");
        setErrorMessage(data.message || "Failed to parse database file.");
        toast.error(data.message || "Failed to parse database file.");
      }
    } catch {
      setStage("error");
      setErrorMessage(
        "Failed to upload database file. Network error occurred.",
      );
      toast.error("Failed to upload database file.");
    }
  };

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const isBusy = stage === "connecting" || stage === "verifying";

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
        {/* Glass Backdrop */}
        <motion.div
          key="connect-backdrop"
          variants={modalBackdropVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={isBusy ? undefined : onClose}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
        />

        {/* Modal Window */}
        <motion.div
          key="connect-container"
          variants={modalContainerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="relative w-full max-w-xl rounded-2xl bg-[#121216] border border-white/10 shadow-2xl shadow-black/90 overflow-hidden z-10 my-auto"
        >
          {/* Subtle Top Indigo Glow Accent */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-teal-500" />

          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4.5 border-b border-white/[0.08] bg-[#16161b]">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0">
                <Database size={20} />
              </div>
              <div>
                <h2 className="text-base sm:text-lg font-bold text-white tracking-tight flex items-center gap-2">
                  <span>Connect Database</span>
                  <span className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-md bg-indigo-500/15 text-indigo-300 border border-indigo-500/20">
                    Live Session
                  </span>
                </h2>
                <p className="text-xs text-zinc-400">
                  Select database engine and configure connection parameters
                </p>
              </div>
            </div>

            {!isBusy && (
              <button
                onClick={onClose}
                className="p-1.5 rounded-xl text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                title="Close (Esc)"
              >
                <X size={18} />
              </button>
            )}
          </div>

          {/* Connection Progress Stage Overlay */}
          <AnimatePresence>
            {isBusy && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                className="p-8 sm:p-10 flex flex-col items-center justify-center text-center space-y-4"
              >
                <div className="relative flex items-center justify-center w-20 h-20">
                  {/* Concentric pulsing rings */}
                  <motion.div
                    animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.7, 0.3] }}
                    transition={{
                      repeat: Infinity,
                      duration: 2,
                      ease: "easeInOut",
                    }}
                    className="absolute inset-0 rounded-full bg-indigo-500/20 border border-indigo-500/40"
                  />
                  <div className="relative z-10 w-14 h-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-lg shadow-indigo-500/20">
                    <Loader2
                      size={28}
                      className="animate-spin text-indigo-400"
                    />
                  </div>
                </div>

                <div className="space-y-1.5 max-w-sm">
                  <h3 className="text-base font-bold text-white tracking-tight">
                    {stage === "connecting"
                      ? "Connecting Database..."
                      : "Verifying Connection..."}
                  </h3>
                  <p className="text-xs text-zinc-400 leading-relaxed font-mono">
                    {stageMessage}
                  </p>
                </div>

                {/* Progress bar */}
                <div className="w-48 bg-white/[0.06] h-1.5 rounded-full overflow-hidden mt-2">
                  <motion.div
                    className="h-full bg-indigo-500"
                    initial={{ width: "15%" }}
                    animate={{ width: stage === "verifying" ? "80%" : "45%" }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Connection Success State Overlay */}
          <AnimatePresence>
            {stage === "connected" && connectedSummary && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="p-8 sm:p-10 flex flex-col items-center justify-center text-center space-y-4"
              >
                <motion.div
                  initial={{ scale: 0.5, rotate: -20 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ type: "spring", damping: 12, stiffness: 200 }}
                  className="w-20 h-20 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-xl shadow-emerald-500/20"
                >
                  <CheckCircle2 size={36} className="text-emerald-400" />
                </motion.div>

                <div className="space-y-1">
                  <h3 className="text-lg font-bold text-white tracking-tight">
                    Connected Successfully!
                  </h3>
                  <p className="text-xs text-emerald-400 font-medium">
                    Schema verified and indexed for conversational queries.
                  </p>
                </div>

                <div className="p-3 px-4 rounded-xl bg-white/[0.03] border border-white/[0.08] flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <div className="text-left">
                    <p className="text-xs font-semibold text-zinc-100 font-mono">
                      {connectedSummary.name}
                    </p>
                    <p className="text-[11px] text-zinc-400">
                      {connectedSummary.engine} • {connectedSummary.details}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form and Selection View (Hidden during active connecting/success sequence) */}
          {!isBusy && stage !== "connected" && (
            <>
              {/* Database Engine Selection Cards */}
              <div className="px-6 pt-5 pb-3">
                <div className="grid grid-cols-3 gap-3">
                  {[
                    {
                      id: "sqlite",
                      title: "SQLite",
                      badge: "File DB",
                      desc: "Local .db file",
                      icon: HardDrive,
                      color: "text-indigo-400",
                      glow: "rgba(99, 102, 241, 0.25)",
                    },
                    {
                      id: "mysql",
                      title: "MySQL",
                      badge: "Port 3306",
                      desc: "Relational DB",
                      icon: Server,
                      color: "text-teal-400",
                      glow: "rgba(20, 184, 166, 0.25)",
                    },
                    {
                      id: "postgres",
                      title: "PostgreSQL",
                      badge: "Port 5432",
                      desc: "Advanced SQL",
                      icon: Layers,
                      color: "text-sky-400",
                      glow: "rgba(14, 165, 233, 0.25)",
                    },
                  ].map((engine) => {
                    const Icon = engine.icon;
                    const active = dbType === engine.id;
                    return (
                      <button
                        key={engine.id}
                        type="button"
                        onClick={() => {
                          setDbType(engine.id as DbType);
                          setErrorMessage(null);
                        }}
                        className={`relative p-3.5 rounded-xl border text-left transition-all duration-200 cursor-pointer ${
                          active
                            ? "bg-white/[0.06] border-indigo-500 shadow-md shadow-indigo-500/10 ring-1 ring-indigo-500/50"
                            : "bg-white/[0.02] hover:bg-white/[0.04] border-white/[0.08] hover:border-white/20"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div
                            className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                              active
                                ? "bg-indigo-500/20 text-indigo-300"
                                : "bg-white/[0.04] text-zinc-400"
                            }`}
                          >
                            <Icon
                              size={16}
                              className={active ? engine.color : ""}
                            />
                          </div>
                          <span
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                              active
                                ? "bg-indigo-500/20 text-indigo-300 font-medium"
                                : "bg-white/[0.04] text-zinc-500"
                            }`}
                          >
                            {engine.badge}
                          </span>
                        </div>

                        <p className="text-xs font-bold text-white tracking-tight">
                          {engine.title}
                        </p>
                        <p className="text-[11px] text-zinc-400 truncate mt-0.5">
                          {engine.desc}
                        </p>

                        {active && (
                          <motion.div
                            layoutId="activeEngineIndicator"
                            className="absolute bottom-0 left-3 right-3 h-0.5 bg-indigo-500 rounded-full"
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Error Alert if previously failed */}
              {errorMessage && (
                <div className="mx-6 mb-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 flex items-start gap-2.5 text-rose-300 text-xs leading-relaxed">
                  <AlertCircle
                    size={16}
                    className="text-rose-400 shrink-0 mt-0.5"
                  />
                  <div className="flex-1">
                    <p className="font-semibold text-rose-200">
                      Connection Failed
                    </p>
                    <p className="text-rose-300/90 mt-0.5">{errorMessage}</p>
                  </div>
                </div>
              )}

              {/* Tab Content: SQLite Upload */}
              {dbType === "sqlite" && (
                <div className="p-6 pt-2 space-y-4">
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragOver(true);
                    }}
                    onDragLeave={() => setIsDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDragOver(false);
                      const file = e.dataTransfer.files?.[0];
                      if (file) handleFileUpload(file);
                    }}
                    className={`border-2 border-dashed rounded-2xl p-7 text-center transition-all ${
                      isDragOver
                        ? "border-indigo-500 bg-indigo-500/10 scale-[1.01]"
                        : "border-white/[0.12] bg-white/[0.02] hover:border-white/[0.22]"
                    }`}
                  >
                    <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 mx-auto flex items-center justify-center mb-3">
                      <FileUp size={24} />
                    </div>

                    <h4 className="text-sm font-bold text-white">
                      Drop your SQLite database file here
                    </h4>

                    <p className="text-xs text-zinc-400 mt-1 max-w-xs mx-auto">
                      Drag and drop any SQLite file, or browse from your
                      computer
                    </p>

                    <div className="flex items-center justify-center gap-1.5 mt-3">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                        .db
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                        .sqlite
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                        .sqlite3
                      </span>
                    </div>

                    <div className="mt-5">
                      <label className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.08] hover:bg-white/[0.14] border border-white/10 text-xs sm:text-sm font-semibold text-zinc-100 cursor-pointer transition-colors shadow-sm">
                        <FileUp size={15} />
                        <span>Browse SQLite File</span>
                        <input
                          type="file"
                          accept=".db,.sqlite,.sqlite3"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleFileUpload(file);
                          }}
                        />
                      </label>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-zinc-400 px-1">
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck size={13} className="text-emerald-400" />
                      Session sandbox isolation
                    </span>
                    <span>Max recommended file: 100MB</span>
                  </div>
                </div>
              )}

              {/* Tab Content: MySQL / PostgreSQL Connection Form */}
              {(dbType === "mysql" || dbType === "postgres") && (
                <form onSubmit={handleConnect} className="p-6 pt-2 space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="col-span-2">
                      <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                        Host / Server Address
                      </label>
                      <input
                        type="text"
                        value={form.host}
                        onChange={(e) => updateField("host", e.target.value)}
                        placeholder="localhost"
                        required
                        className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 transition-colors"
                      />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <label className="block text-xs font-semibold text-zinc-300">
                          Port
                        </label>
                        <button
                          type="button"
                          onClick={() =>
                            updateField(
                              "port",
                              dbType === "mysql" ? "3306" : "5432",
                            )
                          }
                          className="text-[10px] text-indigo-400 hover:text-indigo-300 font-mono underline"
                        >
                          Default
                        </button>
                      </div>
                      <input
                        type="text"
                        value={form.port}
                        onChange={(e) => updateField("port", e.target.value)}
                        required
                        className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-sm text-zinc-100 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 transition-colors font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                      Database Name
                    </label>
                    <input
                      type="text"
                      value={form.database}
                      onChange={(e) => updateField("database", e.target.value)}
                      placeholder={dbType === "mysql" ? "bg_ai_db" : "postgres"}
                      required
                      className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 transition-colors font-mono"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                        Username
                      </label>
                      <input
                        type="text"
                        value={form.username}
                        onChange={(e) =>
                          updateField("username", e.target.value)
                        }
                        placeholder={dbType === "mysql" ? "root" : "postgres"}
                        required
                        className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 transition-colors font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                        Password
                      </label>
                      <div className="relative">
                        <input
                          type={showPassword ? "text" : "password"}
                          value={form.password}
                          onChange={(e) =>
                            updateField("password", e.target.value)
                          }
                          placeholder="••••••••"
                          className="w-full pl-3.5 pr-10 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/40 transition-colors font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
                          title={
                            showPassword ? "Hide password" : "Show password"
                          }
                        >
                          {showPassword ? (
                            <EyeOff size={15} />
                          ) : (
                            <Eye size={15} />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2">
                    <ClickSpark
                      sparkColor="#818cf8"
                      sparkCount={6}
                      sparkRadius={18}
                      className="w-full"
                    >
                      <button
                        type="submit"
                        className="w-full flex items-center justify-center gap-2.5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold shadow-lg shadow-indigo-600/20 transition-all cursor-pointer group"
                      >
                        <span>
                          Connect {dbType === "mysql" ? "MySQL" : "PostgreSQL"}{" "}
                          Database
                        </span>
                        <ArrowRight
                          size={15}
                          className="group-hover:translate-x-0.5 transition-transform"
                        />
                      </button>
                    </ClickSpark>
                  </div>
                </form>
              )}
            </>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
