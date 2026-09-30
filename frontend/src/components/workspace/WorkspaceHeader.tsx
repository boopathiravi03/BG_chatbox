import React from "react";
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
} from "lucide-react";
import type { WorkspaceTab } from "./WorkspaceSidebar";
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
  onConnectDatabase: () => void;
  onDisconnect: () => void;
  onOpenAbout?: () => void;
  onOpenDatabaseDetails?: () => void;
}

const tabTitles: Record<WorkspaceTab, { title: string; subtitle: string }> = {
  overview: {
    title: "Overview",
    subtitle: "Enterprise Data & Intelligence Center",
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
  onConnectDatabase,
  onDisconnect,
  onOpenAbout,
  onOpenDatabaseDetails,
}: WorkspaceHeaderProps) {
  const current = tabTitles[activeTab] || tabTitles.overview;
  const { user, logout } = useAuth();


  const dbLabel =
    dbType === "mysql"
      ? "MySQL"
      : dbType === "postgres"
      ? "PostgreSQL"
      : dbType === "sqlite"
      ? "SQLite"
      : null;

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
        {dbConnected ? (
          <div className="flex items-center gap-2">
            <button
              onClick={onOpenDatabaseDetails}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-medium text-zinc-200 transition-all cursor-pointer"
              title="View database details"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="font-semibold text-white">{dbLabel}</span>
              {dbInfo?.tables !== undefined && (
                <span className="hidden lg:inline text-zinc-400 text-[11px] font-mono">
                  ({dbInfo.tables} tables)
                </span>
              )}
            </button>

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
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
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
