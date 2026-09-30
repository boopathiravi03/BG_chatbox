import React from "react";
import {
  LayoutDashboard,
  Search,
  BarChart3,
  Terminal,
  Activity,
  MessageSquare,
  FileText,
  Settings,
  Database,
  Unplug,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Plug,
  X,
} from "lucide-react";
import { useTheme } from "../../context/ThemeContext";

export type WorkspaceTab =
  | "overview"
  | "explorer"
  | "analytics"
  | "sqllab"
  | "health"
  | "chat"
  | "reports"
  | "settings";

interface WorkspaceSidebarProps {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  dbConnected: boolean;
  dbType: string | null;
  onConnectDatabase: () => void;
  onDisconnect: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

const navItems: { id: WorkspaceTab; label: string; icon: React.ElementType; badge?: string }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "explorer", label: "Data Explorer", icon: Search },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "sqllab", label: "SQL Lab", icon: Terminal },
  { id: "health", label: "Data Health", icon: Activity },
  { id: "chat", label: "AI Command", icon: MessageSquare, badge: "AI" },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "settings", label: "Settings", icon: Settings },
];

export default function WorkspaceSidebar({
  activeTab,
  onTabChange,
  collapsed,
  onToggleCollapse,
  dbConnected,
  dbType,
  onConnectDatabase,
  onDisconnect,
  mobileOpen,
  onCloseMobile,
}: WorkspaceSidebarProps) {
  const { theme } = useTheme();

  const dbLabel =
    dbType === "mysql"
      ? "MySQL"
      : dbType === "postgres"
      ? "PostgreSQL"
      : dbType === "sqlite"
      ? "SQLite"
      : null;

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#0d0d11] border-r border-white/[0.08] text-zinc-300 select-none">
      {/* Workspace Brand Header */}
      <div className="h-16 px-4 flex items-center justify-between border-b border-white/[0.06] shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center p-1 shadow-md shadow-indigo-600/10 shrink-0">
            <img src="/bg-logo.png" alt="BG AI" className="w-full h-full object-contain" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-sm text-white tracking-tight">BG AI</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/15 border border-indigo-500/25 text-indigo-300">
                  Workspace
                </span>
              </div>
              <p className="text-[10px] text-zinc-400 truncate">Data Intelligence Platform</p>
            </div>
          )}
        </div>

        {/* Mobile close button */}
        <button
          onClick={onCloseMobile}
          className="md:hidden p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] cursor-pointer"
        >
          <X size={18} />
        </button>

        {/* Desktop collapse toggle */}
        <button
          onClick={onToggleCollapse}
          className="hidden md:flex p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer shrink-0"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Database Connection Pill */}
      <div className="p-3 border-b border-white/[0.06] shrink-0">
        {dbConnected ? (
          <div
            className={`p-2.5 rounded-xl bg-emerald-500/[0.08] border border-emerald-500/25 flex items-center justify-between gap-2 ${
              collapsed ? "justify-center p-2" : ""
            }`}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="text-[11px] font-bold text-emerald-300 truncate">
                    {dbLabel || "Connected"}
                  </p>
                  <p className="text-[10px] text-emerald-400/80">Active Session</p>
                </div>
              )}
            </div>

            {!collapsed && (
              <button
                onClick={onDisconnect}
                title="Disconnect database"
                className="p-1 rounded text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer shrink-0"
              >
                <Unplug size={14} />
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={onConnectDatabase}
            className={`w-full p-2.5 rounded-xl bg-white/[0.03] hover:bg-indigo-600/15 border border-white/[0.08] hover:border-indigo-500/30 transition-all flex items-center gap-2 cursor-pointer group ${
              collapsed ? "justify-center p-2" : ""
            }`}
          >
            <Plug size={15} className="text-zinc-400 group-hover:text-indigo-400 shrink-0" />
            {!collapsed && (
              <div className="text-left min-w-0">
                <p className="text-xs font-semibold text-zinc-300 group-hover:text-white truncate">
                  Connect Database
                </p>
                <p className="text-[10px] text-zinc-400 truncate">SQLite, MySQL, Postgres</p>
              </div>
            )}
          </button>
        )}
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1 scrollbar-thin">
        {!collapsed && (
          <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-zinc-400">
            Workspace
          </p>
        )}

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => {
                onTabChange(item.id);
                if (mobileOpen) onCloseMobile();
              }}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-all cursor-pointer group ${
                isActive
                  ? "bg-indigo-600/20 text-indigo-200 border border-indigo-500/30 shadow-sm"
                  : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
              } ${collapsed ? "justify-center px-2" : ""}`}
            >
              <Icon
                size={16}
                className={`shrink-0 transition-colors ${
                  isActive ? "text-indigo-400" : "text-zinc-400 group-hover:text-zinc-200"
                }`}
              />

              {!collapsed && (
                <>
                  <span className="truncate flex-1 text-left">{item.label}</span>
                  {item.badge && (
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer Info */}
      {!collapsed && (
        <div className="p-3 border-t border-white/[0.06] text-[11px] text-zinc-400 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles size={13} className="text-indigo-400" />
            <span>AI Powered</span>
          </div>
          <span className="text-[10px] font-mono text-zinc-400">v2.0</span>
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:block shrink-0 transition-all duration-300 ease-in-out z-20 ${
          collapsed ? "w-16" : "w-64"
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar Overlay Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onCloseMobile}
          />
          <div className="relative w-72 max-w-[85vw] h-full shadow-2xl z-10">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
