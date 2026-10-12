import React, { useState, useEffect } from "react";
import {
  X,
  Database,
  FileSpreadsheet,
  FileText,
  FileJson,
  Layers,
  Search,
  CheckCircle2,
  AlertCircle,
  Loader2,
  UploadCloud,
  ShieldCheck,
  Cpu,
} from "lucide-react";
import type { ConnectorCatalogItem } from "../../../types";
import {
  getConnectorCatalog,
  createDatabaseConnection,
  uploadFileSource,
} from "../../../services/api";
import { useToast } from "../../../context/ToastContext";

interface AddConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnectionCreated: () => void;
}

export default function AddConnectionModal({
  isOpen,
  onClose,
  onConnectionCreated,
}: AddConnectionModalProps) {
  const toast = useToast();
  const [catalog, setCatalog] = useState<ConnectorCatalogItem[]>([]);
  const [selectedConnector, setSelectedConnector] =
    useState<ConnectorCatalogItem | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // File Upload State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // Common Form Fields
  const [formData, setFormData] = useState({
    name: "",
    host: "localhost",
    port: "",
    database: "",
    username: "",
    password: "",
    ssl: false,
    filePath: "",
    apiKey: "",
    collectionName: "",
    tableName: "",
    isReadOnly: true,
  });

  const getConnType = (item: ConnectorCatalogItem): string =>
    item.id || item.connector_type || "";

  const getConnName = (item: ConnectorCatalogItem): string =>
    item.name || item.display_name || "";

  useEffect(() => {
    if (!isOpen) return;
    loadCatalog();
    setError(null);
  }, [isOpen]);

  const loadCatalog = async () => {
    setLoadingCatalog(true);
    try {
      const data = await getConnectorCatalog();
      setCatalog(data.catalog || []);
    } catch (err: any) {
      console.error("Failed to load catalog", err);
      toast.error("Failed to load connector catalog.");
    } finally {
      setLoadingCatalog(false);
    }
  };

  const handleSelectConnector = (item: ConnectorCatalogItem) => {
    setSelectedConnector(item);
    setError(null);
    setSelectedFile(null);

    const type = getConnType(item);
    const displayName = getConnName(item);

    // Initialize defaults based on connector
    let defaultPort = item.default_port ? String(item.default_port) : "";
    let defaultUser = "";
    let defaultDb = "";

    if (type === "postgres") {
      defaultUser = "postgres";
      defaultDb = "postgres";
    } else if (type === "mysql" || type === "mariadb") {
      defaultUser = "root";
      defaultDb = "bg_ai_db";
    } else if (type === "mssql") {
      defaultUser = "sa";
      defaultDb = "master";
    } else if (type === "mongodb") {
      defaultDb = "test";
    }

    setFormData({
      name: `${displayName} Source`,
      host: "localhost",
      port: defaultPort,
      database: defaultDb,
      username: defaultUser,
      password: "",
      ssl: false,
      filePath: "",
      apiKey: "",
      collectionName: "",
      tableName: "",
      isReadOnly: true,
    });
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelected = (file: File) => {
    setSelectedFile(file);
    const baseName = file.name.replace(/\.[^/.]+$/, "");
    if (!formData.name || formData.name.endsWith("Source")) {
      setFormData((prev) => ({
        ...prev,
        name: baseName,
        tableName: baseName.toLowerCase().replace(/[^a-z0-9_]/g, "_"),
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConnector) return;

    setSubmitting(true);
    setError(null);

    const type = getConnType(selectedConnector);
    const displayName = getConnName(selectedConnector);

    try {
      if (selectedConnector.category === "file") {
        if (!selectedFile) {
          throw new Error("Please select a file to upload.");
        }

        await uploadFileSource(
          selectedFile,
          formData.name,
          formData.isReadOnly
        );

        toast.success(`Connected to ${displayName} successfully!`);
        onConnectionCreated();
        onClose();
        return;
      }

      // SQLite connection
      if (type === "sqlite") {
        if (selectedFile) {
          // Uploaded sqlite file
          await uploadFileSource(
            selectedFile,
            formData.name,
            formData.isReadOnly
          );
          toast.success("SQLite database uploaded and connected!");
          onConnectionCreated();
          onClose();
          return;
        }

        if (!formData.filePath.trim()) {
          throw new Error("Please provide a SQLite database path or upload a file.");
        }

        await createDatabaseConnection({
          connector_type: "sqlite",
          name: formData.name.trim() || "SQLite DB",
          is_read_only: formData.isReadOnly,
          config: {
            database: formData.filePath.trim(),
          },
        });

        toast.success("Connected to SQLite database!");
        onConnectionCreated();
        onClose();
        return;
      }

      // Vector connectors (Qdrant, Chroma)
      if (selectedConnector.category === "vector") {
        await createDatabaseConnection({
          connector_type: type,
          name: formData.name.trim() || `${displayName} Index`,
          is_read_only: formData.isReadOnly,
          config: {
            host: formData.host.trim() || "localhost",
            port: formData.port ? parseInt(formData.port, 10) : selectedConnector.default_port,
            api_key: formData.apiKey ? formData.apiKey.trim() : undefined,
            collection_name: formData.collectionName.trim() || undefined,
          },
        });

        toast.success(`Connected to ${displayName}!`);
        onConnectionCreated();
        onClose();
        return;
      }

      // Relational & Document Connectors (Postgres, MySQL, MariaDB, MSSQL, MongoDB)
      const portNum = formData.port ? parseInt(formData.port, 10) : selectedConnector.default_port;
      await createDatabaseConnection({
        connector_type: type,
        name: formData.name.trim() || `${displayName} DB`,
        is_read_only: formData.isReadOnly,
        config: {
          host: formData.host.trim(),
          port: portNum,
          database: formData.database.trim(),
          username: formData.username.trim(),
          password: formData.password,
          ssl: formData.ssl,
        },
      });

      toast.success(`Connected to ${displayName}!`);
      onConnectionCreated();
      onClose();
    } catch (err: any) {
      console.error("Connection failed", err);
      const msg = err.message || "Failed to establish database connection.";
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const filteredCatalog = catalog.filter((item) => {
    const matchesCategory =
      activeCategory === "all" || item.category === activeCategory;
    const name = getConnName(item).toLowerCase();
    const type = getConnType(item).toLowerCase();
    const desc = (item.description || "").toLowerCase();
    const query = searchQuery.toLowerCase();
    const matchesSearch =
      !searchQuery ||
      name.includes(query) ||
      type.includes(query) ||
      desc.includes(query);
    return matchesCategory && matchesSearch;
  });

  const getConnectorIcon = (type: string, category: string) => {
    if (category === "file") {
      if (type === "csv") return <FileText className="w-5 h-5 text-emerald-400" />;
      if (type === "excel") return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
      return <FileJson className="w-5 h-5 text-amber-400" />;
    }
    if (category === "vector") {
      return <Cpu className="w-5 h-5 text-violet-400" />;
    }
    if (type === "mongodb") {
      return <Layers className="w-5 h-5 text-emerald-400" />;
    }
    return <Database className="w-5 h-5 text-indigo-400" />;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-[#0d0d12] border border-white/[0.08] rounded-2xl shadow-2xl flex flex-col overflow-hidden text-zinc-100">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] bg-[#141418]/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Database size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white tracking-tight">
                Connect New Data Source
              </h2>
              <p className="text-xs text-zinc-400">
                Add independent relational databases, document stores, vector indexes, or data files
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!selectedConnector ? (
            /* Step 1: Catalog Selection */
            <div className="space-y-5">
              {/* Filter Bar */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                <div className="flex items-center gap-1.5 p-1 bg-[#141418] rounded-xl border border-white/[0.06]">
                  {(
                    [
                      { id: "all", label: "All Connectors" },
                      { id: "relational", label: "Relational" },
                      { id: "document", label: "Document" },
                      { id: "vector", label: "Vector" },
                      { id: "file", label: "Files" },
                    ] as const
                  ).map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setActiveCategory(cat.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        activeCategory === cat.id
                          ? "bg-violet-600 text-white shadow-sm"
                          : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                      }`}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>

                <div className="relative flex-1 sm:max-w-xs">
                  <Search
                    size={14}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
                  />
                  <input
                    type="text"
                    placeholder="Search connectors..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-1.5 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Connectors Grid */}
              {loadingCatalog ? (
                <div className="py-16 flex flex-col items-center justify-center gap-3 text-zinc-400">
                  <Loader2 size={24} className="animate-spin text-violet-400" />
                  <span className="text-xs">Loading available connectors...</span>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filteredCatalog.map((item) => {
                    const type = getConnType(item);
                    const displayName = getConnName(item);

                    return (
                      <button
                        key={type}
                        onClick={() => handleSelectConnector(item)}
                        className="group flex flex-col text-left p-4 rounded-xl bg-[#141418]/60 hover:bg-[#1a1a22] border border-white/[0.06] hover:border-violet-500/40 transition-all cursor-pointer relative"
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.06] group-hover:scale-105 transition-transform">
                            {getConnectorIcon(type, item.category)}
                          </div>
                          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
                            {item.badge}
                          </span>
                        </div>
                        <span className="font-medium text-sm text-zinc-100 group-hover:text-violet-300 transition-colors">
                          {displayName}
                        </span>
                        <p className="text-[11px] text-zinc-400 mt-1 line-clamp-2">
                          {item.description}
                        </p>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            /* Step 2: Configuration Form */
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Selected Connector Header */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#141418] border border-white/[0.06]">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-white/[0.04]">
                    {getConnectorIcon(
                      getConnType(selectedConnector),
                      selectedConnector.category
                    )}
                  </div>
                  <div>
                    <span className="text-sm font-semibold text-white">
                      {getConnName(selectedConnector)}
                    </span>
                    <span className="text-xs text-zinc-400 ml-2">
                      ({selectedConnector.category})
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedConnector(null)}
                  className="text-xs text-violet-400 hover:text-violet-300 font-medium"
                >
                  Change Connector
                </button>
              </div>

              {error && (
                <div className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                  <AlertCircle size={16} className="shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {/* Display Name */}
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Connection Display Name
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="e.g. Production Analytics, User Store"
                  className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                />
              </div>

              {/* File Upload Mode */}
              {selectedConnector.category === "file" && (
                <div className="space-y-4">
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragActive(true);
                    }}
                    onDragLeave={() => setDragActive(false)}
                    onDrop={handleFileDrop}
                    className={`border-2 border-dashed rounded-2xl p-6 text-center transition-all ${
                      dragActive
                        ? "border-violet-500 bg-violet-500/10"
                        : "border-white/[0.1] bg-[#141418]/40 hover:border-white/[0.2]"
                    }`}
                  >
                    <UploadCloud className="w-8 h-8 mx-auto text-zinc-400 mb-2" />
                    <p className="text-xs font-medium text-zinc-200">
                      Drag & drop your {getConnName(selectedConnector)} file here, or{" "}
                      <label className="text-violet-400 hover:text-violet-300 cursor-pointer underline">
                        browse
                        <input
                          type="file"
                          className="hidden"
                          accept={
                            getConnType(selectedConnector) === "csv"
                              ? ".csv"
                              : getConnType(selectedConnector) === "excel"
                              ? ".xlsx,.xls"
                              : ".json"
                          }
                          onChange={(e) =>
                            e.target.files?.[0] &&
                            handleFileSelected(e.target.files[0])
                          }
                        />
                      </label>
                    </p>
                    <p className="text-[11px] text-zinc-500 mt-1">
                      Instantly queried via SQLite in-memory relational engine
                    </p>
                    {selectedFile && (
                      <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300">
                        <CheckCircle2 size={14} />
                        <span>
                          {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* SQLite Mode */}
              {getConnType(selectedConnector) === "sqlite" && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">
                      Local SQLite Database File Path
                    </label>
                    <input
                      type="text"
                      value={formData.filePath}
                      onChange={(e) =>
                        setFormData({ ...formData, filePath: e.target.value })
                      }
                      placeholder="e.g. data/app.db or C:/path/to/database.sqlite"
                      className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                    />
                  </div>

                  <div className="relative flex py-2 items-center">
                    <div className="flex-grow border-t border-white/[0.06]"></div>
                    <span className="flex-shrink mx-3 text-[11px] text-zinc-500 uppercase tracking-wider">
                      Or Upload SQLite File
                    </span>
                    <div className="flex-grow border-t border-white/[0.06]"></div>
                  </div>

                  <label className="flex items-center justify-center gap-2 p-3 rounded-xl bg-[#141418] hover:bg-[#1a1a22] border border-white/[0.08] text-xs text-zinc-300 cursor-pointer transition-colors">
                    <UploadCloud size={16} />
                    <span>
                      {selectedFile ? selectedFile.name : "Choose .sqlite / .db file"}
                    </span>
                    <input
                      type="file"
                      accept=".db,.sqlite,.sqlite3"
                      className="hidden"
                      onChange={(e) =>
                        e.target.files?.[0] && setSelectedFile(e.target.files[0])
                      }
                    />
                  </label>
                </div>
              )}

              {/* Vector Mode */}
              {selectedConnector.category === "vector" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">
                      Host
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.host}
                      onChange={(e) =>
                        setFormData({ ...formData, host: e.target.value })
                      }
                      placeholder="localhost"
                      className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">
                      Port
                    </label>
                    <input
                      type="number"
                      value={formData.port}
                      onChange={(e) =>
                        setFormData({ ...formData, port: e.target.value })
                      }
                      placeholder={String(selectedConnector.default_port || 6333)}
                      className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">
                      API Key (Optional)
                    </label>
                    <input
                      type="password"
                      value={formData.apiKey}
                      onChange={(e) =>
                        setFormData({ ...formData, apiKey: e.target.value })
                      }
                      placeholder="Optional vector service key"
                      className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">
                      Default Collection (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.collectionName}
                      onChange={(e) =>
                        setFormData({ ...formData, collectionName: e.target.value })
                      }
                      placeholder="Leave blank to discover all"
                      className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {/* Relational & Document Connectors */}
              {(selectedConnector.category === "relational" ||
                selectedConnector.category === "document") &&
                getConnType(selectedConnector) !== "sqlite" && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="sm:col-span-2">
                        <label className="block text-xs font-medium text-zinc-300 mb-1">
                          Host / IP
                        </label>
                        <input
                          type="text"
                          required
                          value={formData.host}
                          onChange={(e) =>
                            setFormData({ ...formData, host: e.target.value })
                          }
                          placeholder="localhost or 127.0.0.1"
                          className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-zinc-300 mb-1">
                          Port
                        </label>
                        <input
                          type="number"
                          required
                          value={formData.port}
                          onChange={(e) =>
                            setFormData({ ...formData, port: e.target.value })
                          }
                          placeholder={String(selectedConnector.default_port || "")}
                          className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-zinc-300 mb-1">
                          Database / Schema
                        </label>
                        <input
                          type="text"
                          required
                          value={formData.database}
                          onChange={(e) =>
                            setFormData({ ...formData, database: e.target.value })
                          }
                          placeholder="e.g. postgres, analytics_db"
                          className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-zinc-300 mb-1">
                          Username
                        </label>
                        <input
                          type="text"
                          required
                          value={formData.username}
                          onChange={(e) =>
                            setFormData({ ...formData, username: e.target.value })
                          }
                          placeholder="postgres / root"
                          className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-zinc-300 mb-1">
                          Password
                        </label>
                        <input
                          type="password"
                          value={formData.password}
                          onChange={(e) =>
                            setFormData({ ...formData, password: e.target.value })
                          }
                          placeholder="••••••••"
                          className="w-full px-3 py-2 bg-[#141418] border border-white/[0.08] focus:border-violet-500/50 rounded-xl text-xs text-white placeholder-zinc-600 focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <input
                        type="checkbox"
                        id="sslToggle"
                        checked={formData.ssl}
                        onChange={(e) =>
                          setFormData({ ...formData, ssl: e.target.checked })
                        }
                        className="rounded border-white/[0.1] bg-[#141418] text-violet-600 focus:ring-0"
                      />
                      <label htmlFor="sslToggle" className="text-xs text-zinc-300">
                        Enable SSL / TLS connection
                      </label>
                    </div>
                  </div>
                )}

              {/* Safety & Read-Only Protection */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-violet-500/5 border border-violet-500/20">
                <div className="flex items-center gap-2.5">
                  <ShieldCheck size={16} className="text-violet-400" />
                  <div>
                    <span className="text-xs font-semibold text-zinc-200">
                      Read-Only Enforced Mode
                    </span>
                    <p className="text-[11px] text-zinc-400">
                      Blocks mutations (DROP, INSERT, UPDATE, DELETE) automatically
                    </p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={formData.isReadOnly}
                  onChange={(e) =>
                    setFormData({ ...formData, isReadOnly: e.target.checked })
                  }
                  className="rounded border-white/[0.1] bg-[#141418] text-violet-600 focus:ring-0"
                />
              </div>

              {/* Form Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setSelectedConnector(null)}
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/[0.04] transition-colors"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-violet-600/50 text-xs font-semibold text-white shadow-lg shadow-violet-600/20 transition-all cursor-pointer"
                >
                  {submitting && <Loader2 size={14} className="animate-spin" />}
                  <span>Connect Source</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
