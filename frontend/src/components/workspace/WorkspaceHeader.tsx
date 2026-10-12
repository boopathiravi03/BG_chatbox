import React, { useState, useRef, useEffect } from "react";
import {
  Menu,
  Database,
  Unplug,
  Plug,
  Sparkles,
  Info,
  Layers,
  HardDrive,
  Activity,
  LogOut,
  User,
  ChevronDown,
  CheckCircle2,
  Plus,
  FileSpreadsheet,
  FileText,
  FileJson,
  Cpu,
} from "lucide-react";
import type { WorkspaceTab } from "./WorkspaceSidebar";
import type { DatabaseConnectionItem } from "../../types";
import ModelSelector from "../ui/ModelSelector";
import { useAuth } from "../../context/AuthContext";

interface WorkspaceHeaderProps {
  activeTab: WorkspaceTab;
  onOpenMobileMenu: () => void;
  dbConnected: boolean;
  dbType: string | null;
  dbInfo?: {
    database?: string;
    tables?: number;
    rows?: number;
    size?: string;
  };
  connections?: DatabaseConnectionItem[];
  activeConnectionId?: string | null;
  onSelectActiveConnection?: (connectionId: string) => void;
  onConnectDatabase: () => void;
  onDisconnect: () => void;
  onOpenAbout?: () => void;
  onOpenDatabaseDetails?: () => void;
  onNavigateTab?: (tab: WorkspaceTab) => void;
}

const tabTitles: Record<WorkspaceTab, { title: string; subtitle: string }> = {
  overview: {
    title: "Overview",
    subtitle: "Enterprise Data & Intelligence Center",
  },
  databases: {
    title: "Data Sources & Connectors",
    subtitle: "Manage Multi-Database Connections & Query Routing",
  },
  explorer: {
    title: "Data Explorer",
    subtitle: "Interactive Schema Tree & Column Profiler",
  },
  analytics: {
    title: "Analytics & Dashboards",
    subtitle: "Automated Visual Metric Charts & Dashboards",
  },
  forecasting: {
    title: "Forecasting Studio",
    subtitle: "Predictive Time-Series Projections & Statistical Confidence Intervals",
  },
  anomalies: {
    title: "Anomaly Center",
    subtitle: "Explainable Outlier Detection & Deviation Intelligence",
  },
  agents: {
    title: "AI Agent Center",
    subtitle: "Modular Specialist Agents & Human-Approved Safe Actions",
  },
  sqllab: {
    title: "AI SQL Lab",
    subtitle: "Interactive Query IDE, Optimization & Execution",
  },
  health: {
    title: "Data Health Doctor",
    subtitle: "Diagnostics, Quality Scores & AI Resolutions",
  },
  chat: {
    title: "AI Command",
    subtitle: "Conversational Intelligence & Data Assistant",
  },
  reports: {
    title: "Reports",
    subtitle: "Executive Business Reports & Exports",
  },
  settings: {
    title: "Settings & Connections",
    subtitle: "Database Engine, Security & Environment Configuration",
  },
};

export default function WorkspaceHeader({
  activeTab,
  onOpenMobileMenu,
  dbConnected,
  dbType,
  dbInfo,
  connections = [],
  activeConnectionId,
  onSelectActiveConnection,
  onConnectDatabase,
  onDisconnect,
  onOpenAbout,
  onOpenDatabaseDetails,
  onNavigateTab,
}: WorkspaceHeaderProps) {
  const current = tabTitles[activeTab] || tabTitles.overview;
  const { user, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const activeConn =
    connections.find((c) => c.connection_id === activeConnectionId || c.is_active) ||
    connections[0];

  const dbLabel =
    activeConn?.name ||
    (dbType === "mysql"
      ? "MySQL"
      : dbType === "postgres"
      ? "PostgreSQL"
      : dbType === "sqlite"
      ? "SQLite"
      : null);

  const getSmallIcon = (type?: string, category?: string) => {
    if (category === "file") {
      if (type === "csv") return <FileText size={12} className="text-emerald-400" />;
      if (type === "excel") return <FileSpreadsheet size={12} className="text-green-400" />;
      return <FileJson size={12} className="text-amber-400" />;
    }
    if (category === "vector") return <Cpu size={12} className="text-violet-400" />;
    if (type === "mongodb") return <Layers size={12} className="text-emerald-400" />;
    return <Database size={12} className="text-indigo-400" />;
  };

  return (
    <header className="h-16 px-4 sm:px-6 bg-[#09090b]/80 backdrop-blur-md border-b border-white/[0.08] flex items-center justify-between gap-4 shrink-0 z-10">
      {/* Left: Mobile Menu & Breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] cursor-pointer"
        >
          <Menu size={18} />
        </button>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-400">Workspace</span>
            <span className="text-xs text-zinc-600">/</span>
            <h1 className="text-sm sm:text-base font-bold text-white tracking-tight truncate">
              {current.title}
            </h1>
          </div>
          <p className="hidden sm:block text-[11px] text-zinc-400 truncate">
            {current.subtitle}
          </p>
        </div>
      </div>

      {/* Right: Database Pill & Actions */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {dbConnected || connections.length > 0 ? (
          <div className="relative flex items-center gap-1.5" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen((prev) => !prev)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-zinc-200 transition-all cursor-pointer"
              title="Switch or manage connected databases"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <div className="flex items-center gap-1.5 max-w-[140px] truncate">
                {activeConn && getSmallIcon(activeConn.connector_type, activeConn.category)}
                <span className="font-semibold text-white truncate">{dbLabel}</span>
              </div>
              {connections.length > 1 && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30">
                  {connections.length}
                </span>
              )}
              <ChevronDown size={13} className={`text-zinc-400 transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
            </button>

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <div className="absolute right-0 top-full mt-2 w-72 bg-[#141418] border border-white/[0.1] rounded-2xl shadow-2xl py-2 z-50 text-xs">
                <div className="px-3 py-1.5 border-b border-white/[0.06] flex items-center justify-between text-[11px] text-zinc-400 font-semibold uppercase tracking-wider">
                  <span>Connected Sources</span>
                  <span className="font-mono">{connections.length} total</span>
                </div>

                <div className="max-h-60 overflow-y-auto py-1 divide-y divide-white/[0.03]">
                  {connections.map((conn) => {
                    const isActive =
                      conn.connection_id === activeConnectionId || conn.is_active;

                    return (
                      <button
                        key={conn.connection_id}
                        onClick={() => {
                          onSelectActiveConnection?.(conn.connection_id);
                          setDropdownOpen(false);
                        }}
                        className={`w-full px-3 py-2 flex items-center justify-between text-left hover:bg-white/[0.04] transition-colors cursor-pointer ${
                          isActive ? "bg-violet-600/10" : ""
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="p-1 rounded bg-white/[0.04] shrink-0">
                            {getSmallIcon(conn.connector_type, conn.category)}
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-white truncate">
                              {conn.name}
                            </div>
                            <div className="text-[10px] text-zinc-400 font-mono truncate">
                              {conn.connector_type} • {conn.stats?.tables ? `${conn.stats.tables} tbls` : conn.status}
                            </div>
                          </div>
                        </div>

                        {isActive ? (
                          <CheckCircle2 size={14} className="text-violet-400 shrink-0 ml-2" />
                        ) : (
                          <span className="text-[10px] text-zinc-500 hover:text-zinc-300">Switch</span>
                        )}
                      </button>
                    );
                  })}
                </div>

                <div className="pt-1 mt-1 border-t border-white/[0.06] px-1 space-y-0.5">
                  <button
                    onClick={() => {
                      setDropdownOpen(false);
                      onConnectDatabase();
                    }}
                    className="w-full px-2.5 py-1.5 rounded-lg flex items-center gap-2 text-zinc-300 hover:text-white hover:bg-white/[0.04] transition-colors cursor-pointer"
                  >
                    <Plus size={13} className="text-violet-400" />
                    <span>Connect New Data Source</span>
                  </button>

                  {onNavigateTab && (
                    <button
                      onClick={() => {
                        setDropdownOpen(false);
                        onNavigateTab("databases");
                      }}
                      className="w-full px-2.5 py-1.5 rounded-lg flex items-center gap-2 text-zinc-300 hover:text-white hover:bg-white/[0.04] transition-colors cursor-pointer"
                    >
                      <Database size={13} className="text-zinc-400" />
                      <span>Manage Data Sources</span>
                    </button>
                  )}
                </div>
              </div>
            )}

            <button
              onClick={onDisconnect}
              className="p-1.5 rounded-xl text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 border border-white/[0.06] transition-all cursor-pointer"
              title="Disconnect active database"
            >
              <Unplug size={15} />
            </button>
          </div>
        ) : (
          <button
            onClick={onConnectDatabase}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-md shadow-violet-600/20 transition-all cursor-pointer"
          >
            <Plug size={14} />
            <span className="hidden sm:inline">Connect Database</span>
            <span className="sm:hidden">Connect</span>
          </button>
        )}

        {/* Model Selector */}
        <div className="hidden sm:block">
          <ModelSelector />
        </div>

        {/* About trigger */}
        {onOpenAbout && (
          <button
            onClick={onOpenAbout}
            className="p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/[0.06] border border-white/[0.06] transition-all cursor-pointer"
            title="About BG AI"
          >
            <Info size={16} />
          </button>
        )}

        {/* User + Logout */}
        {user && (
          <div className="flex items-center gap-2">
            <span className="hidden sm:flex items-center gap-1.5 text-xs text-zinc-500 font-mono">
              <User size={12} />
              {user.username}
            </span>
            <button
              onClick={logout}
              className="p-1.5 rounded-xl text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 border border-white/[0.06] transition-all cursor-pointer"
              title="Sign out"
            >
              <LogOut size={15} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
