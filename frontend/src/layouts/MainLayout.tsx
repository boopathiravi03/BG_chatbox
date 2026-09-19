import Sidebar from "../components/chat/Sidebar";
import Background from "../components/ui/Background";
import ModelSelector from "../components/ui/ModelSelector";
import DatabaseOverview from "../components/dashboard/DatabaseOverview";
import type { ChatSession } from "../types";
import { useState, useEffect } from "react";
import { Unplug, Menu, Info, PanelLeftOpen, Database } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type Status = "ready" | "thinking" | "executing" | "done" | "error";

interface MainLayoutProps {
  children: React.ReactNode;
  status: Status;
  onNewChat?: () => void;
  sessions?: ChatSession[];
  activeSessionId?: string | null;
  onSessionClick?: (session: ChatSession) => void;
  onUploadComplete?: () => void;
  dbConnected?: boolean;
  dbType?: string | null;
  onDatabaseConnected?: () => void;
  onDeleteSession?: (id: string) => void;
  onDisconnect?: () => void;
  onOpenDatabase?: () => void;
  onOpenAbout?: () => void;
  isAboutView?: boolean;
  onConnectDatabase?: () => void;
}

const statusConfig = {
  ready: { color: "bg-emerald-400", text: "text-emerald-400", label: "Ready" },
  thinking: {
    color: "bg-amber-400",
    text: "text-amber-400",
    label: "Thinking...",
  },
  executing: {
    color: "bg-indigo-400",
    text: "text-indigo-400",
    label: "Executing SQL...",
  },
  done: {
    color: "bg-emerald-400",
    text: "text-emerald-400",
    label: "Completed",
  },
  error: { color: "bg-rose-400", text: "text-rose-400", label: "Failed" },
};

export default function MainLayout({
  children,
  status,
  onNewChat,
  sessions,
  activeSessionId,
  onSessionClick,
  onUploadComplete,
  dbConnected,
  dbType,
  onDatabaseConnected,
  onDeleteSession,
  onDisconnect,
  onOpenDatabase,
  onOpenAbout,
  isAboutView = false,
  onConnectDatabase,
}: MainLayoutProps) {
  const dbLabel =
    dbType === "mysql"
      ? "MySQL"
      : dbType === "postgres"
        ? "PostgreSQL"
        : dbType === "sqlite"
          ? "SQLite"
          : null;
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const currentStatus = statusConfig[status] || statusConfig.ready;

  // Keyboard shortcut Ctrl/Cmd + \ to toggle sidebar collapse and Escape for drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && mobileSidebarOpen) {
        setMobileSidebarOpen(false);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") {
        e.preventDefault();
        setSidebarCollapsed((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileSidebarOpen]);

  return (
    <div className="flex h-screen bg-[#09090b] text-[#f4f4f5] relative overflow-hidden font-sans">
      <Background />

      {/* Desktop Sidebar */}
      <div className="hidden md:flex h-full shrink-0 z-30">
        <Sidebar
          onNewChat={onNewChat}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSessionClick={onSessionClick}
          onUploadComplete={onUploadComplete}
          onDatabaseConnected={onDatabaseConnected}
          onDeleteSession={onDeleteSession}
          onDisconnect={onDisconnect}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onOpenDatabase={onOpenDatabase}
          onOpenAbout={onOpenAbout}
        />
      </div>

      {/* Mobile Drawer Overlay */}
      <AnimatePresence>
        {mobileSidebarOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
              onClick={() => setMobileSidebarOpen(false)}
            />
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="relative w-72 max-w-[80vw] h-full z-50 bg-[#0e0e11] shadow-2xl"
            >
              <Sidebar
                onClose={() => setMobileSidebarOpen(false)}
                onNewChat={() => {
                  onNewChat?.();
                  setMobileSidebarOpen(false);
                }}
                sessions={sessions}
                activeSessionId={activeSessionId}
                onSessionClick={(s) => {
                  onSessionClick?.(s);
                  setMobileSidebarOpen(false);
                }}
                onUploadComplete={() => {
                  onUploadComplete?.();
                  setMobileSidebarOpen(false);
                }}
                onDatabaseConnected={() => {
                  onDatabaseConnected?.();
                  setMobileSidebarOpen(false);
                }}
                onDeleteSession={onDeleteSession}
                onDisconnect={() => {
                  onDisconnect?.();
                  setMobileSidebarOpen(false);
                }}
                onOpenDatabase={() => {
                  onOpenDatabase?.();
                  setMobileSidebarOpen(false);
                }}
                onOpenAbout={() => {
                  onOpenAbout?.();
                  setMobileSidebarOpen(false);
                }}
              />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
        {/* Render clean top bar only in chat mode (About view has its own dedicated header) */}
        {!isAboutView && (
          <header className="flex items-center justify-between px-6 sm:px-10 md:px-12 lg:px-14 xl:px-16 py-2.5 border-b border-white/[0.06] bg-[#09090b]/90 backdrop-blur-md shrink-0 z-20">
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => setMobileSidebarOpen(true)}
                className="md:hidden p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
                title="Open Menu"
              >
                <Menu size={18} />
              </button>

              {/* Desktop Expand Sidebar Toggle & Brand Pill */}
              {sidebarCollapsed && (
                <div className="hidden md:flex items-center gap-3">
                  <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-indigo-600/15 border border-indigo-500/30 shadow-sm">
                    <img
                      src="/bg-logo.png"
                      alt="BG AI Logo"
                      className="w-7 h-7 rounded-lg object-contain filter drop-shadow-[0_1px_6px_rgba(99,102,241,0.5)]"
                    />
                    <span className="text-base font-black text-white tracking-tight">
                      BG <span className="text-indigo-400">AI</span>
                    </span>
                  </div>
                  <button
                    onClick={() => setSidebarCollapsed(false)}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-zinc-300 hover:text-white text-xs font-medium transition-all group shadow-sm"
                    title="Expand sidebar (Ctrl+\)"
                  >
                    <PanelLeftOpen
                      size={15}
                      className="text-zinc-400 group-hover:text-indigo-400 transition-colors"
                    />
                    <span className="hidden lg:inline">Expand Sidebar</span>
                  </button>
                </div>
              )}

              {/* Status Indicator Pill */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs sm:text-sm font-semibold">
                <span className="relative flex h-2 w-2">
                  <span
                    className={`relative inline-flex rounded-full h-2 w-2 ${currentStatus.color} ${
                      status === "thinking" || status === "executing"
                        ? "animate-pulse"
                        : ""
                    }`}
                  />
                </span>
                <span className={currentStatus.text}>
                  {currentStatus.label}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              {onOpenAbout && (
                <button
                  onClick={onOpenAbout}
                  className="text-sm font-semibold text-zinc-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] px-3.5 py-1.5 rounded-xl border border-white/10 transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                  title="About BG AI"
                >
                  <Info
                    size={15}
                    className="text-zinc-400 group-hover:text-indigo-400"
                  />
                  <span className="hidden sm:inline">About</span>
                </button>
              )}

              {/* IF CONNECTED: Active Database Pill with glowing radar/ping */}
              {dbConnected && dbLabel ? (
                <button
                  onClick={onOpenDatabase}
                  className="text-sm font-semibold text-emerald-300 bg-emerald-500/15 hover:bg-emerald-500/20 px-3.5 py-1.5 rounded-xl border border-emerald-500/30 flex items-center gap-2 transition-all cursor-pointer shadow-sm group"
                  title="View Database Catalog & Details"
                >
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
                  </span>
                  <span>{dbLabel} Connected</span>
                </button>
              ) : (
                /* IF NOT CONNECTED: Quick Connect Database button in header */
                onConnectDatabase && (
                  <button
                    onClick={onConnectDatabase}
                    className="text-sm font-semibold text-indigo-200 hover:text-white bg-indigo-500/15 hover:bg-indigo-500/25 px-3.5 py-1.5 rounded-xl border border-indigo-500/30 flex items-center gap-2 transition-all cursor-pointer shadow-sm group"
                    title="Connect SQLite, MySQL, or PostgreSQL"
                  >
                    <Database
                      size={14}
                      className="text-indigo-400 group-hover:scale-110 transition-transform"
                    />
                    <span>Connect Database</span>
                  </button>
                )
              )}

              {dbConnected && onDisconnect && (
                <button
                  onClick={onDisconnect}
                  className="text-sm font-semibold text-zinc-300 hover:text-rose-400 bg-white/[0.04] hover:bg-rose-500/10 px-3.5 py-1.5 rounded-xl border border-white/10 hover:border-rose-500/30 transition-all flex items-center gap-1.5 cursor-pointer group"
                  title="Disconnect Database Session"
                >
                  <Unplug
                    size={14}
                    className="text-zinc-400 group-hover:text-rose-400 group-hover:rotate-[-10deg] transition-all"
                  />
                  <span className="hidden sm:inline">Disconnect</span>
                </button>
              )}

              <ModelSelector />
            </div>
          </header>
        )}

        <div className="flex-1 overflow-hidden relative min-h-0">
          {children}
        </div>
      </main>

      {/* Optional Right Overview Drawer on ultra-wide screens only */}
      {dbConnected && !isAboutView && (
        <aside className="w-80 border-l border-white/[0.06] bg-[#0e0e11] flex-col hidden 2xl:flex overflow-y-auto shrink-0 z-20">
          <div className="p-4 border-b border-white/[0.06]">
            <p className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-3">
              Database Overview
            </p>
            <DatabaseOverview onExplore={onOpenDatabase} />
          </div>
        </aside>
      )}
    </div>
  );
}
