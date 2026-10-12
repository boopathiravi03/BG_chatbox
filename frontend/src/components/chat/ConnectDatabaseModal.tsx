import React, { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Server,
  Database,
  Layers,
  Cpu,
  FileSpreadsheet,
  FileText,
  FileJson,
  Loader2,
  FileUp,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  Search,
  Zap,
  Activity,
  Check,
} from "lucide-react";
import {
  getConnectorCatalog,
  createDatabaseConnection,
  uploadFileSource,
  testConnectionConfig,
} from "../../services/api";
import type { ConnectorCatalogItem } from "../../types";
import {
  modalBackdropVariants,
  modalContainerVariants,
} from "../../lib/motion";
import { useToast } from "../../context/ToastContext";
import ClickSpark from "../reactbits/ClickSpark";

interface Props {
  onClose: () => void;
  onConnected?: () => void;
  defaultType?: string;
}

type ConnectionStage =
  | "idle"
  | "testing"
  | "connecting"
  | "verifying"
  | "connected"
  | "error";

// Comprehensive catalog fallback if API is warming up
const DEFAULT_CONNECTOR_CATALOG: ConnectorCatalogItem[] = [
  {
    id: "sqlite",
    name: "SQLite",
    category: "relational",
    description: "Embedded fast ACID relational database and local file databases",
    default_port: null,
    badge: "Built-in",
    status: "ready",
    fields: ["database_path"],
  },
  {
    id: "mysql",
    name: "MySQL",
    category: "relational",
    description: "World's most popular open-source relational database server",
    default_port: 3306,
    badge: "Popular",
    status: "ready",
    fields: ["host", "port", "database", "username", "password"],
  },
  {
    id: "postgres",
    name: "PostgreSQL",
    category: "relational",
    description: "Advanced enterprise-grade object-relational database",
    default_port: 5432,
    badge: "Enterprise",
    status: "ready",
    fields: ["host", "port", "database", "username", "password"],
  },
  {
    id: "mariadb",
    name: "MariaDB",
    category: "relational",
    description: "High-performance drop-in replacement for MySQL",
    default_port: 3306,
    badge: "Fast",
    status: "ready",
    fields: ["host", "port", "database", "username", "password"],
  },
  {
    id: "mssql",
    name: "Microsoft SQL Server",
    category: "relational",
    description: "Microsoft enterprise relational database management system",
    default_port: 1433,
    badge: "Enterprise",
    status: "ready",
    fields: ["host", "port", "database", "username", "password", "driver"],
  },
  {
    id: "mongodb",
    name: "MongoDB",
    category: "document",
    description: "Document-based distributed NoSQL database with flexible JSON schemas",
    default_port: 27017,
    badge: "Document",
    status: "ready",
    fields: ["host", "port", "database", "username", "password", "auth_source"],
  },
  {
    id: "redis",
    name: "Redis",
    category: "document",
    description: "Blazing-fast in-memory key-value data store, cache, and message broker",
    default_port: 6379,
    badge: "Key-Value",
    status: "ready",
    fields: ["host", "port", "password", "db", "ssl"],
  },
  {
    id: "qdrant",
    name: "Qdrant",
    category: "vector",
    description: "Vector search engine and vector database with payload filtering",
    default_port: 6333,
    badge: "Vector AI",
    status: "ready",
    fields: ["host", "port", "api_key"],
  },
  {
    id: "chroma",
    name: "Chroma DB",
    category: "vector",
    description: "Open-source AI-native embedding database for LLM applications",
    default_port: 8000,
    badge: "Embeddings",
    status: "ready",
    fields: ["host", "port", "tenant", "database"],
  },
  {
    id: "csv",
    name: "CSV Data Source",
    category: "file",
    description: "Query tabular comma/tab-separated values with full SQL capabilities",
    default_port: null,
    badge: "Tabular",
    status: "ready",
    fields: ["file_path", "delimiter"],
  },
  {
    id: "excel",
    name: "Excel Workbook",
    category: "file",
    description: "Transform sheets in .xlsx/.xls workbooks into queryable SQL tables",
    default_port: null,
    badge: "Spreadsheet",
    status: "ready",
    fields: ["file_path"],
  },
  {
    id: "json",
    name: "JSON File Source",
    category: "file",
    description: "Analyze structured and nested JSON files using relational schemas",
    default_port: null,
    badge: "Semi-structured",
    status: "ready",
    fields: ["file_path"],
  },
];

type CategoryFilter = "all" | "relational" | "nosql" | "vector" | "file";

export default function ConnectDatabaseModal({
  onClose,
  onConnected,
  defaultType = "sqlite",
}: Props) {
  const toast = useToast();
  const [catalog, setCatalog] = useState<ConnectorCatalogItem[]>(DEFAULT_CONNECTOR_CATALOG);
  const [selectedType, setSelectedType] = useState<string>(defaultType);
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [stage, setStage] = useState<ConnectionStage>("idle");
  const [stageMessage, setStageMessage] = useState<string>("");
  const [testResult, setTestResult] = useState<{
    success: boolean;
    latency_ms?: number;
    message?: string;
  } | null>(null);

  const [connectedSummary, setConnectedSummary] = useState<{
    name: string;
    engine: string;
    details?: string;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [isDragOver, setIsDragOver] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Form fields
  const [form, setForm] = useState({
    name: "",
    host: "localhost",
    port: "3306",
    database: "bg_ai_db",
    username: "root",
    password: "",
    ssl: false,
    sqlitePath: "",
    delimiter: ",",
    driver: "ODBC Driver 18 for SQL Server",
    authSource: "admin",
    connectionString: "",
    dbIndex: 0,
    apiKey: "",
    collectionName: "",
    tenant: "default_tenant",
    isReadOnly: true,
  });

  // Load backend catalog dynamically
  useEffect(() => {
    let isMounted = true;
    getConnectorCatalog()
      .then((res) => {
        if (isMounted && res && res.catalog && res.catalog.length > 0) {
          setCatalog(res.catalog);
        }
      })
      .catch((err) => {
        console.warn("Using default connector catalog:", err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Update form defaults when selected connector changes
  useEffect(() => {
    setErrorMessage(null);
    setTestResult(null);
    setSelectedFile(null);

    const item = catalog.find(
      (c) => (c.id || c.connector_type || "").toLowerCase() === selectedType.toLowerCase()
    );

    const displayName = item?.name || selectedType.toUpperCase();
    const defaultPortStr = item?.default_port ? String(item.default_port) : "";

    let defaultUser = "";
    let defaultDb = "";

    if (selectedType === "postgres") {
      defaultUser = "postgres";
      defaultDb = "postgres";
    } else if (selectedType === "mysql" || selectedType === "mariadb") {
      defaultUser = "root";
      defaultDb = "bg_ai_db";
    } else if (selectedType === "mssql") {
      defaultUser = "sa";
      defaultDb = "master";
    } else if (selectedType === "mongodb") {
      defaultDb = "bg_ai_db";
    }

    setForm((prev) => ({
      ...prev,
      name: `${displayName} Data Source`,
      port: defaultPortStr,
      username: defaultUser,
      database: defaultDb,
      authSource: selectedType === "mongodb" ? (defaultDb || "bg_ai_db") : "admin",
    }));
  }, [selectedType, catalog]);

  // Close on Escape key (if not busy)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === "Escape" &&
        stage !== "connecting" &&
        stage !== "verifying" &&
        stage !== "testing"
      ) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, stage]);

  const updateField = (field: string, value: any) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setTestResult(null);
    setErrorMessage(null);
  };

  const currentItem = useMemo(() => {
    return (
      catalog.find(
        (c) => (c.id || c.connector_type || "").toLowerCase() === selectedType.toLowerCase()
      ) || catalog[0]
    );
  }, [catalog, selectedType]);

  // Filtered catalog
  const filteredCatalog = useMemo(() => {
    return catalog.filter((item) => {
      const id = (item.id || item.connector_type || "").toLowerCase();
      const name = (item.name || item.display_name || "").toLowerCase();
      const desc = (item.description || "").toLowerCase();
      const badge = (item.badge || "").toLowerCase();

      // Category matching
      let matchesCat = true;
      if (activeCategory === "relational") {
        matchesCat = item.category === "relational";
      } else if (activeCategory === "nosql") {
        matchesCat =
          item.category === "document" ||
          item.category === "nosql" ||
          id === "mongodb" ||
          id === "redis";
      } else if (activeCategory === "vector") {
        matchesCat = item.category === "vector";
      } else if (activeCategory === "file") {
        matchesCat = item.category === "file";
      }

      // Search matching
      const query = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !query ||
        name.includes(query) ||
        id.includes(query) ||
        desc.includes(query) ||
        badge.includes(query);

      return matchesCat && matchesSearch;
    });
  }, [catalog, activeCategory, searchQuery]);

  const getEngineIcon = (id: string, category: string) => {
    if (category === "file" || id === "csv" || id === "excel" || id === "json") {
      if (id === "excel") return FileSpreadsheet;
      if (id === "json") return FileJson;
      return FileText;
    }
    if (category === "vector" || id === "qdrant" || id === "chroma") return Cpu;
    if (id === "redis") return Activity;
    if (id === "mongodb") return Layers;
    return Server;
  };

  const getEngineColor = (id: string) => {
    switch (id) {
      case "postgres":
        return "text-sky-400";
      case "mysql":
        return "text-teal-400";
      case "mariadb":
        return "text-cyan-400";
      case "mssql":
        return "text-blue-400";
      case "mongodb":
        return "text-emerald-400";
      case "redis":
        return "text-rose-400";
      case "qdrant":
        return "text-violet-400";
      case "chroma":
        return "text-fuchsia-400";
      case "csv":
        return "text-amber-400";
      case "excel":
        return "text-green-400";
      case "json":
        return "text-orange-400";
      default:
        return "text-indigo-400";
    }
  };

  // Build connection payload from current form state
  const buildConnectionPayload = () => {
    const portNum = form.port ? parseInt(form.port, 10) : currentItem.default_port || undefined;

    return {
      connector_type: selectedType,
      name: form.name.trim() || `${currentItem.name} Source`,
      is_read_only: form.isReadOnly,
      set_as_active: true,
      config: {
        host: form.host.trim(),
        port: portNum,
        database: form.database.trim(),
        username: form.username.trim(),
        password: form.password,
        ssl: form.ssl,
        file_path: form.sqlitePath.trim(),
        delimiter: form.delimiter,
        driver: form.driver,
        auth_source: form.authSource || form.database || "bg_ai_db",
        connection_string: form.connectionString.trim() || undefined,
        db: form.dbIndex,
        api_key: form.apiKey.trim() || undefined,
        collection_name: form.collectionName.trim() || undefined,
        tenant: form.tenant.trim() || undefined,
      },
    };
  };

  // Live "Test Connection" Handler
  const handleTestConnection = async () => {
    setStage("testing");
    setErrorMessage(null);
    setTestResult(null);

    try {
      const payload = buildConnectionPayload();
      const res = await testConnectionConfig(payload);

      if (res.test && res.test.connected) {
        setTestResult({
          success: true,
          latency_ms: res.test.latency_ms,
          message: res.test.details || `Successfully reached ${currentItem.name}!`,
        });
        toast.success(`Connection verified (${res.test.latency_ms || 12} ms)`);
      } else {
        const err = res.test?.error || res.message || "Failed to reach server.";
        setTestResult({
          success: false,
          message: err,
        });
        setErrorMessage(err);
        toast.error(`Test failed: ${err}`);
      }
    } catch (err: any) {
      const msg = err.message || "Test connection failed.";
      setTestResult({
        success: false,
        message: msg,
      });
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setStage("idle");
    }
  };

  // File selection
  const handleFileUpload = async (file: File) => {
    setSelectedFile(file);
    const baseName = file.name.replace(/\.[^/.]+$/, "");
    setForm((prev) => ({
      ...prev,
      name: prev.name.endsWith("Source") || !prev.name ? baseName : prev.name,
    }));
  };

  // Connect submission
  const handleConnect = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setErrorMessage(null);

    // 1. If File connector or SQLite with uploaded file
    if (currentItem.category === "file" || (selectedType === "sqlite" && selectedFile)) {
      if (!selectedFile && !form.sqlitePath.trim()) {
        setErrorMessage("Please select a file to upload or enter a database path.");
        return;
      }

      if (selectedFile) {
        setStage("connecting");
        setStageMessage(`Uploading ${selectedFile.name}...`);
        try {
          const res = await uploadFileSource(
            selectedFile,
            form.name.trim() || selectedFile.name,
            form.isReadOnly
          );
          setStage("connected");
          setConnectedSummary({
            name: form.name.trim() || selectedFile.name,
            engine: currentItem.name,
            details: `Active data source configured.`,
          });
          toast.success(`Connected to ${currentItem.name}!`);
          onConnected?.();
          return;
        } catch (err: any) {
          setStage("error");
          setErrorMessage(err.message || "File upload connection failed.");
          return;
        }
      }
    }

    // 2. Database connection via createDatabaseConnection
    setStage("connecting");
    setStageMessage(`Connecting to ${currentItem.name}...`);

    try {
      const payload = buildConnectionPayload();
      const res = await createDatabaseConnection(payload);

      if (res.status === "error") {
        throw new Error(res.message || "Connection failed.");
      }

      setStage("connected");
      setConnectedSummary({
        name: form.name.trim() || currentItem.name,
        engine: currentItem.name,
        details: `Active database connection established.`,
      });
      toast.success(`Successfully connected to ${currentItem.name}!`);
      onConnected?.();
    } catch (err: any) {
      setStage("error");
      setErrorMessage(err.message || "Could not connect to database.");
      toast.error(err.message || "Connection failed.");
    }
  };

  const isConnecting = stage === "connecting" || stage === "verifying";

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5">
        <motion.div
          variants={modalBackdropVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={isConnecting ? undefined : onClose}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
        />

        <motion.div
          variants={modalContainerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-4xl max-h-[92vh] bg-[#0d0d12] border border-white/[0.08] rounded-2xl shadow-2xl flex flex-col overflow-hidden text-zinc-100 z-10"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] bg-[#141418]/80">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400 flex items-center justify-center">
                <Database size={20} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
                  Connect Database & Data Source
                  <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-300">
                    {catalog.length} Supported
                  </span>
                </h3>
                <p className="text-xs text-zinc-400">
                  Connect independent databases, vector stores, or files simultaneously
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              disabled={isConnecting}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors disabled:opacity-40"
            >
              <X size={18} />
            </button>
          </div>

          {/* Success Screen */}
          {stage === "connected" ? (
            <div className="p-8 text-center space-y-6">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mx-auto flex items-center justify-center">
                <CheckCircle2 size={32} />
              </div>

              <div>
                <h4 className="text-lg font-bold text-white">Connection Established</h4>
                <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">
                  {connectedSummary?.name} ({connectedSummary?.engine}) is now active in BG AI.
                </p>
              </div>

              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs sm:text-sm font-semibold shadow-lg shadow-violet-600/20 transition-all cursor-pointer"
                >
                  Start Exploring Data
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto flex flex-col divide-y divide-white/[0.06]">
              {/* Top Controls: Category Tabs & Search Bar */}
              <div className="p-5 pb-3 space-y-3 bg-[#111116]">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                  {/* Category Pills */}
                  <div className="flex items-center gap-1 p-1 bg-[#16161c] rounded-xl border border-white/[0.06] overflow-x-auto">
                    {[
                      { id: "all", label: "All (12)" },
                      { id: "relational", label: "Relational (5)" },
                      { id: "nosql", label: "NoSQL & Key-Value (2)" },
                      { id: "vector", label: "Vector DBs (2)" },
                      { id: "file", label: "Files (3)" },
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        type="button"
                        onClick={() => setActiveCategory(tab.id as CategoryFilter)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                          activeCategory === tab.id
                            ? "bg-violet-600 text-white shadow-sm"
                            : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {/* Search Bar */}
                  <div className="relative w-full sm:w-64">
                    <Search
                      size={14}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
                    />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search connectors..."
                      className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-[#16161c] border border-white/[0.06] text-xs text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/40 transition-colors"
                    />
                    {searchQuery && (
                      <button
                        type="button"
                        onClick={() => setSearchQuery("")}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-200"
                      >
                        <X size={12} />
                      </button>
                    )}
                  </div>
                </div>

                {/* Connector Selector Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2 pt-1 max-h-48 overflow-y-auto pr-1">
                  {filteredCatalog.map((item) => {
                    const id = (item.id || item.connector_type || "").toLowerCase();
                    const active = selectedType.toLowerCase() === id;
                    const Icon = getEngineIcon(id, item.category);
                    const colorClass = getEngineColor(id);

                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setSelectedType(id)}
                        className={`p-2.5 rounded-xl border text-left transition-all duration-150 relative flex flex-col justify-between ${
                          active
                            ? "bg-violet-500/10 border-violet-500 ring-1 ring-violet-500/40 shadow-sm"
                            : "bg-[#141418] hover:bg-white/[0.04] border-white/[0.06] hover:border-white/15"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <div
                            className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                              active
                                ? "bg-violet-500/20 text-violet-300"
                                : "bg-white/[0.04] text-zinc-400"
                            }`}
                          >
                            <Icon size={14} className={active ? colorClass : ""} />
                          </div>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
                            {item.default_port ? `:${item.default_port}` : item.badge || "Ready"}
                          </span>
                        </div>

                        <div>
                          <p className="text-xs font-semibold text-white tracking-tight truncate">
                            {item.name}
                          </p>
                          <p className="text-[10px] text-zinc-400 truncate mt-0.5">
                            {item.badge}
                          </p>
                        </div>

                        {active && (
                          <div className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-violet-400" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Form Content Area */}
              <div className="p-6 space-y-4">
                {/* Active Connector Banner */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-[#141418] border border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 flex items-center justify-center">
                      <Database size={16} />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-white flex items-center gap-2">
                        {currentItem.name} Configuration
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300">
                          {currentItem.badge}
                        </span>
                      </h4>
                      <p className="text-[11px] text-zinc-400">{currentItem.description}</p>
                    </div>
                  </div>

                  <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.isReadOnly}
                      onChange={(e) => updateField("isReadOnly", e.target.checked)}
                      className="rounded border-zinc-700 text-violet-600 focus:ring-violet-500 bg-zinc-900"
                    />
                    <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-400">
                      <ShieldCheck size={12} /> Read-Only Mode
                    </span>
                  </label>
                </div>

                {/* Error Banner */}
                {errorMessage && (
                  <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 flex items-start gap-2.5 text-rose-300 text-xs leading-relaxed">
                    <AlertCircle size={15} className="text-rose-400 shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-semibold text-rose-200">Connection Error</p>
                      <p className="text-rose-300/90 mt-0.5">{errorMessage}</p>
                    </div>
                  </div>
                )}

                {/* Test Success Banner */}
                {testResult?.success && (
                  <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-between text-emerald-300 text-xs">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
                      <span>{testResult.message}</span>
                    </div>
                    {testResult.latency_ms !== undefined && (
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                        {testResult.latency_ms} ms latency
                      </span>
                    )}
                  </div>
                )}

                <form onSubmit={handleConnect} className="space-y-4">
                  {/* Common: Connection Display Name */}
                  <div>
                    <label className="block text-xs font-semibold text-zinc-300 mb-1">
                      Connection Display Name
                    </label>
                    <input
                      type="text"
                      value={form.name}
                      onChange={(e) => updateField("name", e.target.value)}
                      placeholder={`${currentItem.name} Data Source`}
                      required
                      className="w-full px-3.5 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs sm:text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/40 transition-colors"
                    />
                  </div>

                  {/* 1. SQLite Form */}
                  {selectedType === "sqlite" && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-semibold text-zinc-300 mb-1">
                          SQLite Database File Path (or drop file below)
                        </label>
                        <input
                          type="text"
                          value={form.sqlitePath}
                          onChange={(e) => updateField("sqlitePath", e.target.value)}
                          placeholder="database/chinook.db or /path/to/database.sqlite"
                          className="w-full px-3.5 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs sm:text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-violet-500 font-mono"
                        />
                      </div>

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
                        className={`border-2 border-dashed rounded-xl p-5 text-center transition-all ${
                          isDragOver
                            ? "border-violet-500 bg-violet-500/10"
                            : "border-white/[0.1] bg-white/[0.02] hover:border-white/[0.2]"
                        }`}
                      >
                        <FileUp size={22} className="mx-auto text-violet-400 mb-2" />
                        <p className="text-xs font-medium text-white">
                          {selectedFile ? selectedFile.name : "Drop .db / .sqlite file to upload"}
                        </p>
                        <p className="text-[10px] text-zinc-400 mt-0.5">
                          Drag and drop or browse from local filesystem
                        </p>
                        <label className="mt-2.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-zinc-200 cursor-pointer transition-colors">
                          <FileUp size={13} />
                          <span>Browse File</span>
                          <input
                            type="file"
                            accept=".db,.sqlite,.sqlite3"
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) handleFileUpload(f);
                            }}
                          />
                        </label>
                      </div>
                    </div>
                  )}

                  {/* 2. Flat File Sources: CSV, Excel, JSON */}
                  {(selectedType === "csv" || selectedType === "excel" || selectedType === "json") && (
                    <div className="space-y-3">
                      <div
                        onDragOver={(e) => {
                          e.preventDefault();
                          setIsDragOver(true);
                        }}
                        onDragLeave={() => setIsDragOver(false)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setIsDragOver(false);
                          const f = e.dataTransfer.files?.[0];
                          if (f) handleFileUpload(f);
                        }}
                        className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
                          isDragOver
                            ? "border-violet-500 bg-violet-500/10"
                            : "border-white/[0.1] bg-white/[0.02] hover:border-white/[0.2]"
                        }`}
                      >
                        <FileUp size={24} className="mx-auto text-violet-400 mb-2" />
                        <p className="text-xs font-semibold text-white">
                          {selectedFile
                            ? `Selected: ${selectedFile.name}`
                            : `Upload ${currentItem.name} File`}
                        </p>
                        <p className="text-[10px] text-zinc-400 mt-0.5">
                          {selectedType === "csv"
                            ? "Supports .csv, .tsv files"
                            : selectedType === "excel"
                            ? "Supports .xlsx, .xls spreadsheets"
                            : "Supports .json structured records"}
                        </p>
                        <label className="mt-3 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-xs font-semibold text-zinc-200 cursor-pointer transition-colors">
                          <FileUp size={13} />
                          <span>Browse Local File</span>
                          <input
                            type="file"
                            accept={
                              selectedType === "csv"
                                ? ".csv,.tsv"
                                : selectedType === "excel"
                                ? ".xlsx,.xls"
                                : ".json"
                            }
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) handleFileUpload(f);
                            }}
                          />
                        </label>
                      </div>

                      {selectedType === "csv" && (
                        <div className="w-1/2">
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            CSV Delimiter
                          </label>
                          <select
                            value={form.delimiter}
                            onChange={(e) => updateField("delimiter", e.target.value)}
                            className="w-full px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-200 outline-none"
                          >
                            <option value=",">Comma ( , )</option>
                            <option value=";">Semicolon ( ; )</option>
                            <option value="\t">Tab ( \t )</option>
                            <option value="|">Pipe ( | )</option>
                          </select>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 3. Relational Client: MySQL, PostgreSQL, MariaDB, MSSQL */}
                  {(selectedType === "mysql" ||
                    selectedType === "postgres" ||
                    selectedType === "mariadb" ||
                    selectedType === "mssql") && (
                    <div className="space-y-3">
                      <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-2">
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            Host / Server
                          </label>
                          <input
                            type="text"
                            value={form.host}
                            onChange={(e) => updateField("host", e.target.value)}
                            placeholder="localhost or db.company.com"
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none focus:border-violet-500 font-mono"
                          />
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <label className="block text-xs font-semibold text-zinc-300">Port</label>
                            <button
                              type="button"
                              onClick={() =>
                                updateField("port", String(currentItem.default_port || 3306))
                              }
                              className="text-[10px] text-violet-400 hover:underline"
                            >
                              Default
                            </button>
                          </div>
                          <input
                            type="text"
                            value={form.port}
                            onChange={(e) => updateField("port", e.target.value)}
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none focus:border-violet-500 font-mono"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            Database Name
                          </label>
                          <input
                            type="text"
                            value={form.database}
                            onChange={(e) => updateField("database", e.target.value)}
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none focus:border-violet-500 font-mono"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            Username
                          </label>
                          <input
                            type="text"
                            value={form.username}
                            onChange={(e) => updateField("username", e.target.value)}
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none focus:border-violet-500 font-mono"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            Password
                          </label>
                          <div className="relative">
                            <input
                              type={showPassword ? "text" : "password"}
                              value={form.password}
                              onChange={(e) => updateField("password", e.target.value)}
                              placeholder="••••••••"
                              className="w-full pl-3 pr-8 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none focus:border-violet-500 font-mono"
                            />
                            <button
                              type="button"
                              onClick={() => setShowPassword(!showPassword)}
                              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                            >
                              {showPassword ? <EyeOff size={13} /> : <Eye size={13} />}
                            </button>
                          </div>
                        </div>
                      </div>

                      {selectedType === "mssql" && (
                        <div>
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            ODBC Driver
                          </label>
                          <input
                            type="text"
                            value={form.driver}
                            onChange={(e) => updateField("driver", e.target.value)}
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                          />
                        </div>
                      )}
                    </div>
                  )}

                  {/* 4. Redis Form */}
                  {selectedType === "redis" && (
                    <div className="space-y-3">
                      <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-2">
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            Redis Host / Cluster
                          </label>
                          <input
                            type="text"
                            value={form.host}
                            onChange={(e) => updateField("host", e.target.value)}
                            placeholder="localhost or 127.0.0.1"
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                          />
                        </div>
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <label className="block text-xs font-semibold text-zinc-300">Port</label>
                            <button
                              type="button"
                              onClick={() => updateField("port", "6379")}
                              className="text-[10px] text-violet-400 hover:underline"
                            >
                              Default (6379)
                            </button>
                          </div>
                          <input
                            type="text"
                            value={form.port || "6379"}
                            onChange={(e) => updateField("port", e.target.value)}
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-2">
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            Auth Password (Optional)
                          </label>
                          <div className="relative">
                            <input
                              type={showPassword ? "text" : "password"}
                              value={form.password}
                              onChange={(e) => updateField("password", e.target.value)}
                              placeholder="Leave blank if no password required"
                              className="w-full pl-3 pr-8 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                            <button
                              type="button"
                              onClick={() => setShowPassword(!showPassword)}
                              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                            >
                              {showPassword ? <EyeOff size={13} /> : <Eye size={13} />}
                            </button>
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            DB Index (0-15)
                          </label>
                          <input
                            type="number"
                            min="0"
                            max="15"
                            value={form.dbIndex}
                            onChange={(e) => updateField("dbIndex", parseInt(e.target.value, 10) || 0)}
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                          />
                        </div>
                      </div>

                      <div className="flex items-center gap-2 pt-1">
                        <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={form.ssl}
                            onChange={(e) => updateField("ssl", e.target.checked)}
                            className="rounded border-zinc-700 text-violet-600 focus:ring-violet-500 bg-zinc-900"
                          />
                          <span>Use TLS / SSL Connection (rediss://)</span>
                        </label>
                      </div>
                    </div>
                  )}

                  {/* 5. MongoDB Form */}
                  {selectedType === "mongodb" && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-semibold text-zinc-300 mb-1">
                          MongoDB Connection URI (Optional shortcut)
                        </label>
                        <input
                          type="text"
                          value={form.connectionString}
                          onChange={(e) => updateField("connectionString", e.target.value)}
                          placeholder="mongodb://localhost:27017 or mongodb+srv://..."
                          className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                        />
                      </div>

                      {!form.connectionString && (
                        <div className="grid grid-cols-3 gap-3">
                          <div className="col-span-2">
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Host
                            </label>
                            <input
                              type="text"
                              value={form.host}
                              onChange={(e) => updateField("host", e.target.value)}
                              placeholder="localhost"
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Port
                            </label>
                            <input
                              type="text"
                              value={form.port || "27017"}
                              onChange={(e) => updateField("port", e.target.value)}
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                        </div>
                      )}

                      {!form.connectionString && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Database Name
                            </label>
                            <input
                              type="text"
                              value={form.database}
                              onChange={(e) => updateField("database", e.target.value)}
                              placeholder="bg_ai_db"
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Auth Source
                            </label>
                            <input
                              type="text"
                              value={form.authSource}
                              onChange={(e) => updateField("authSource", e.target.value)}
                              placeholder="bg_ai_db"
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Username
                            </label>
                            <input
                              type="text"
                              value={form.username}
                              onChange={(e) => updateField("username", e.target.value)}
                              placeholder="db user"
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Password
                            </label>
                            <div className="relative">
                              <input
                                type={showPassword ? "text" : "password"}
                                value={form.password}
                                onChange={(e) => updateField("password", e.target.value)}
                                placeholder="••••••••"
                                className="w-full pl-3 pr-8 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                              />
                              <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                              >
                                {showPassword ? <EyeOff size={13} /> : <Eye size={13} />}
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* 6. Vector: Qdrant & Chroma */}
                  {(selectedType === "qdrant" || selectedType === "chroma") && (
                    <div className="space-y-3">
                      <div className="grid grid-cols-3 gap-3">
                        <div className="col-span-2">
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">
                            Host Endpoint
                          </label>
                          <input
                            type="text"
                            value={form.host}
                            onChange={(e) => updateField("host", e.target.value)}
                            placeholder="localhost or qdrant.cloud.io"
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-zinc-300 mb-1">Port</label>
                          <input
                            type="text"
                            value={form.port || (selectedType === "qdrant" ? "6333" : "8000")}
                            onChange={(e) => updateField("port", e.target.value)}
                            required
                            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                          />
                        </div>
                      </div>

                      {selectedType === "qdrant" && (
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              API Key (Optional)
                            </label>
                            <input
                              type="password"
                              value={form.apiKey}
                              onChange={(e) => updateField("apiKey", e.target.value)}
                              placeholder="••••••••"
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Target Collection (Optional)
                            </label>
                            <input
                              type="text"
                              value={form.collectionName}
                              onChange={(e) => updateField("collectionName", e.target.value)}
                              placeholder="e.g. products_embeddings"
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                        </div>
                      )}

                      {selectedType === "chroma" && (
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Tenant Name
                            </label>
                            <input
                              type="text"
                              value={form.tenant}
                              onChange={(e) => updateField("tenant", e.target.value)}
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-zinc-300 mb-1">
                              Database Name
                            </label>
                            <input
                              type="text"
                              value={form.database}
                              onChange={(e) => updateField("database", e.target.value)}
                              placeholder="default_database"
                              className="w-full px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-zinc-100 outline-none font-mono"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Actions Footer */}
                  <div className="flex items-center justify-between pt-4 border-t border-white/[0.06]">
                    {/* Live Test Connection Button */}
                    <button
                      type="button"
                      disabled={stage === "testing" || isConnecting}
                      onClick={handleTestConnection}
                      className="px-4 py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 hover:text-white text-xs font-medium transition-colors flex items-center gap-2 disabled:opacity-50"
                    >
                      {stage === "testing" ? (
                        <>
                          <Loader2 size={13} className="animate-spin text-violet-400" />
                          <span>Testing ping...</span>
                        </>
                      ) : (
                        <>
                          <Zap size={13} className="text-amber-400" />
                          <span>Test Connection</span>
                        </>
                      )}
                    </button>

                    {/* Submit Connect Button */}
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={onClose}
                        disabled={isConnecting}
                        className="px-4 py-2.5 rounded-xl border border-white/[0.08] hover:bg-white/[0.04] text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
                      >
                        Cancel
                      </button>

                      <ClickSpark sparkColor="#a78bfa" sparkCount={6} sparkRadius={16}>
                        <button
                          type="submit"
                          disabled={isConnecting}
                          className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs sm:text-sm font-semibold shadow-lg shadow-violet-600/25 transition-all flex items-center gap-2 disabled:opacity-50 cursor-pointer"
                        >
                          {isConnecting ? (
                            <>
                              <Loader2 size={14} className="animate-spin" />
                              <span>{stageMessage}</span>
                            </>
                          ) : (
                            <>
                              <span>Connect {currentItem.name}</span>
                              <ArrowRight size={14} />
                            </>
                          )}
                        </button>
                      </ClickSpark>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
