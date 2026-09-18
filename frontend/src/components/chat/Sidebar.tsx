import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database,
  Plus,
  Sun,
  Moon,
  X,
  Server,
  MoreHorizontal,
  Trash2,
  Search,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Info,
  PanelLeftClose,
  PanelLeftOpen,
  History,
} from "lucide-react";
import type { ChatSession } from "../../types";
import DatabaseUploader from "./DatabaseUploader";
import DatabasePopup from "./DatabasePopup";
import ConnectDatabaseModal from "./ConnectDatabaseModal";
import { getDatabaseType } from "../../services/api";
import { useTheme } from "../../context/ThemeContext";
import { dropdownVariants } from "../../lib/motion";
import ClickSpark from "../reactbits/ClickSpark";
import AnimatedList from "../reactbits/AnimatedList";

interface Props {
  onClose?: () => void;
  onNewChat?: () => void;
  sessions?: ChatSession[];
  activeSessionId?: string | null;
  onSessionClick?: (session: ChatSession) => void;
  onUploadComplete?: () => void;
  onDatabaseConnected?: () => void;
  onDeleteSession?: (id: string) => void;
  onDisconnect?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onOpenDatabase?: () => void;
  onOpenAbout?: () => void;
}

type DbType = "sqlite" | "mysql" | "postgres" | "none";

function formatDateLabel(createdAt?: string | number): string {
  if (!createdAt) return "Recent";
  const date = new Date(Number(createdAt) || createdAt);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const sessionDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );

  if (sessionDay.getTime() === today.getTime()) return "Today";
  if (sessionDay.getTime() === yesterday.getTime()) return "Yesterday";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}

/**
 * Premium floating tooltip for collapsed sidebar items
 */
function SidebarTooltip({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div
      className="relative flex items-center justify-center w-full"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      <AnimatePresence>
        {visible && (
          <motion.div
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute left-full ml-3 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-lg bg-[#18181c] border border-white/10 text-xs font-medium text-zinc-100 shadow-xl shadow-black/80 whitespace-nowrap pointer-events-none z-50"
          >
            {label}
            <span className="absolute top-1/2 -left-1 -translate-y-1/2 border-4 border-transparent border-r-[#18181c]" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Sidebar({
  onClose,
  onNewChat,
  sessions = [],
  activeSessionId,
  onSessionClick,
  onUploadComplete,
  onDatabaseConnected,
  onDeleteSession,
  onDisconnect,
  collapsed = false,
  onToggleCollapse,
  onOpenDatabase,
  onOpenAbout,
}: Props) {
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showDatabase, setShowDatabase] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState<
    "sqlite" | "mysql" | "postgres" | null
  >(null);
  const [dbType, setDbType] = useState<DbType>("none");
  const [loadingDbInfo, setLoadingDbInfo] = useState(true);
  const [historySearch, setHistorySearch] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const { theme, toggleTheme } = useTheme();
  const uploadMenuRef = useRef<HTMLDivElement>(null);
  const collapsedUploadMenuRef = useRef<HTMLDivElement>(null);

  const fetchDbInfo = async () => {
    try {
      const typeData = await getDatabaseType();
      setDbType((typeData.db_type as DbType) || "none");
    } catch (error) {
      setDbType("none");
    } finally {
      setLoadingDbInfo(false);
    }
  };

  useEffect(() => {
    fetchDbInfo();
  }, []);

  // Keyboard shortcut Ctrl/Cmd + N for new chat, and Ctrl/Cmd + \ for sidebar toggle
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        onNewChat?.();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "\\") {
        e.preventDefault();
        onToggleCollapse?.();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onNewChat, onToggleCollapse]);

  // Click outside to close menus
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        uploadMenuRef.current &&
        !uploadMenuRef.current.contains(e.target as Node) &&
        collapsedUploadMenuRef.current &&
        !collapsedUploadMenuRef.current.contains(e.target as Node)
      ) {
        setShowUploadMenu(false);
      }
      setOpenMenuId(null);
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const getDbStatusLabel = () => {
    if (loadingDbInfo) return "Checking database...";
    switch (dbType) {
      case "sqlite":
        return "SQLite Connected";
      case "mysql":
        return "MySQL Connected";
      case "postgres":
        return "PostgreSQL Connected";
      default:
        return "No Database Connected";
    }
  };

  const isConnected = dbType !== "none";

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(historySearch.toLowerCase()),
  );

  const groupedSessions = filteredSessions.reduce<
    Record<string, ChatSession[]>
  >((acc, session) => {
    const label = formatDateLabel(session.createdAt);
    if (!acc[label]) acc[label] = [];
    acc[label].push(session);
    return acc;
  }, {});

  const groupOrder = [
    "Today",
    "Yesterday",
    ...new Set(
      Object.keys(groupedSessions).filter(
        (k) => k !== "Today" && k !== "Yesterday",
      ),
    ),
  ];

  return (
    <aside
      className={`h-full ${
        collapsed ? "w-[68px]" : "w-[240px]"
      } border-r border-white/[0.08] bg-[#0e0e11] text-zinc-200 flex flex-col select-none transition-[width] duration-300 ease-in-out relative z-30 shrink-0 overflow-hidden`}
    >
      {/* Brand Header */}
      <div
        className={`p-3.5 sm:p-4 flex items-center ${
          collapsed ? "justify-center flex-col gap-2.5" : "justify-between"
        } border-b border-white/[0.04] shrink-0`}
      >
        {!collapsed ? (
          <>
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-white/[0.04] border border-white/10 text-indigo-400 shadow-sm shrink-0">
                <Database size={18} />
              </div>
              <div className="truncate">
                <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
                  BG <span className="text-indigo-400 font-extrabold">AI</span>
                </h1>
                <p className="text-xs text-zinc-400 font-medium truncate">
                  Database Intelligence
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              {onToggleCollapse && (
                <button
                  onClick={onToggleCollapse}
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                  title="Collapse sidebar (Ctrl+\)"
                >
                  <PanelLeftClose size={17} />
                </button>
              )}
              {onClose && (
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                  title="Close sidebar"
                >
                  <X size={17} />
                </button>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <SidebarTooltip label="BG AI Database Intelligence">
              <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-white/[0.04] border border-white/10 text-indigo-400 shadow-sm">
                <Database size={18} />
              </div>
            </SidebarTooltip>

            {onToggleCollapse && (
              <SidebarTooltip label="Expand sidebar (Ctrl+\)">
                <button
                  onClick={onToggleCollapse}
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
                >
                  <PanelLeftOpen size={16} />
                </button>
              </SidebarTooltip>
            )}
          </div>
        )}
      </div>

      {!collapsed ? (
        /* EXPANDED VIEW */
        <>
          {/* Action Buttons */}
          <div className="p-3 space-y-2 shrink-0">
            {/* New Query Button */}
            <ClickSpark
              sparkColor="#818cf8"
              sparkCount={6}
              sparkRadius={18}
              className="w-full"
            >
              <button
                onClick={onNewChat}
                className="group flex items-center justify-between w-full px-3.5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
              >
                <div className="flex items-center gap-2.5">
                  <Plus size={16} />
                  <span>New Query</span>
                </div>
                <span className="text-[11px] font-mono text-indigo-200/90 bg-white/15 px-1.5 py-0.5 rounded-md">
                  ⌘N
                </span>
              </button>
            </ClickSpark>

            {/* Connect Database Dropdown Trigger */}
            <div className="relative" ref={uploadMenuRef}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowUploadMenu(!showUploadMenu);
                }}
                className={`flex items-center justify-between w-full px-3.5 py-2 rounded-xl border text-sm font-medium transition-all cursor-pointer ${
                  showUploadMenu
                    ? "bg-white/[0.08] border-white/20 text-white"
                    : "bg-white/[0.02] hover:bg-white/[0.06] border-white/[0.08] text-zinc-200"
                }`}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <Database size={15} className="text-zinc-400 shrink-0" />
                  <span className="truncate">Connect the Database</span>
                </div>
                <ChevronDown
                  size={14}
                  className={`text-zinc-400 transition-transform duration-200 shrink-0 ${
                    showUploadMenu ? "rotate-180" : ""
                  }`}
                />
              </button>

              {/* Animated Dropdown Menu */}
              <AnimatePresence>
                {showUploadMenu && (
                  <motion.div
                    variants={dropdownVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                    className="absolute top-full left-0 right-0 mt-1.5 p-1.5 rounded-xl bg-[#141418] border border-white/10 shadow-2xl shadow-black/80 z-50 text-sm"
                  >
                    <button
                      onClick={() => {
                        setShowUploadMenu(false);
                        setShowConnectModal("sqlite");
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors text-xs cursor-pointer"
                    >
                      <Database
                        size={14}
                        className="text-indigo-400 shrink-0"
                      />
                      <span>Upload SQLite (.db)</span>
                    </button>
                    <button
                      onClick={() => {
                        setShowUploadMenu(false);
                        setShowConnectModal("mysql");
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors text-xs cursor-pointer"
                    >
                      <Server size={14} className="text-teal-400 shrink-0" />
                      <span>Connect MySQL</span>
                    </button>
                    <button
                      onClick={() => {
                        setShowUploadMenu(false);
                        setShowConnectModal("postgres");
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors text-xs cursor-pointer"
                    >
                      <Server size={14} className="text-sky-400 shrink-0" />
                      <span>Connect PostgreSQL</span>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* History Section */}
          <div className="flex-1 overflow-y-auto px-3 py-1 space-y-3 min-h-0">
            <div className="relative">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none"
              />
              <input
                type="text"
                placeholder="Search history..."
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                className="w-full pl-8.5 pr-3 py-2 text-sm rounded-xl bg-white/[0.03] border border-white/[0.08] text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500/50 transition-colors font-sans"
              />
            </div>

            <nav className="space-y-3.5">
              {filteredSessions.length === 0 ? (
                <div className="py-8 text-center px-2">
                  <MessageSquare
                    size={22}
                    className="mx-auto text-zinc-600 mb-2"
                  />
                  <p className="text-xs sm:text-sm text-zinc-400 font-medium">
                    {historySearch
                      ? "No matching queries"
                      : "No query history yet"}
                  </p>
                </div>
              ) : (
                groupOrder.map((group) => {
                  const groupSessions = groupedSessions[group];
                  if (!groupSessions || groupSessions.length === 0) return null;
                  return (
                    <div key={group} className="space-y-1.5">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 px-2.5 mb-1.5">
                        {group}
                      </p>
                      <AnimatedList delay={0.03} className="space-y-1">
                        {groupSessions.map((session) => {
                          const isActive = session.id === activeSessionId;
                          const isMenuOpen = openMenuId === session.id;

                          return (
                            <div
                              key={session.id}
                              className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-sm transition-all ${
                                isActive
                                  ? "bg-white/[0.08] text-white font-medium border border-white/[0.08] shadow-sm"
                                  : "text-zinc-300 hover:text-white hover:bg-white/[0.04]"
                              }`}
                            >
                              <button
                                onClick={() => onSessionClick?.(session)}
                                className="flex-1 text-left truncate pr-2 cursor-pointer"
                                title={session.title}
                              >
                                {session.title}
                              </button>

                              {/* Three dots menu */}
                              <div className="relative">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setOpenMenuId(
                                      isMenuOpen ? null : session.id,
                                    );
                                  }}
                                  className={`p-1 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.08] transition-opacity cursor-pointer ${
                                    isMenuOpen
                                      ? "opacity-100"
                                      : "opacity-0 group-hover:opacity-100"
                                  }`}
                                >
                                  <MoreHorizontal size={14} />
                                </button>

                                <AnimatePresence>
                                  {isMenuOpen && (
                                    <motion.div
                                      variants={dropdownVariants}
                                      initial="hidden"
                                      animate="visible"
                                      exit="exit"
                                      className="absolute right-0 top-full mt-1 w-28 p-1 rounded-xl bg-[#18181c] border border-white/10 shadow-xl shadow-black/80 z-50 text-xs"
                                    >
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setOpenMenuId(null);
                                          onDeleteSession?.(session.id);
                                        }}
                                        className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors cursor-pointer"
                                      >
                                        <Trash2 size={13} />
                                        <span>Delete</span>
                                      </button>
                                    </motion.div>
                                  )}
                                </AnimatePresence>
                              </div>
                            </div>
                          );
                        })}
                      </AnimatedList>
                    </div>
                  );
                })
              )}
            </nav>
          </div>

          {/* Footer Controls */}
          <div className="p-3 border-t border-white/[0.06] space-y-2 shrink-0">
            {/* Status Button */}
            <button
              onClick={() => {
                if (isConnected) {
                  if (onOpenDatabase) onOpenDatabase();
                  else setShowDatabase(true);
                } else {
                  setShowConnectModal("sqlite");
                }
              }}
              className="flex items-center justify-between w-full px-3.5 py-2.5 rounded-xl text-sm bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] transition-colors group cursor-pointer"
            >
              <div className="flex items-center gap-2.5 truncate">
                <span className="relative flex h-2.5 w-2.5 shrink-0">
                  {isConnected && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  )}
                  <span
                    className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                      isConnected
                        ? "bg-emerald-400 shadow-sm shadow-emerald-500/50"
                        : "bg-zinc-600"
                    }`}
                  />
                </span>
                <span
                  className={`truncate ${
                    isConnected
                      ? "text-zinc-100 font-medium"
                      : "text-zinc-400 group-hover:text-zinc-200"
                  }`}
                >
                  {getDbStatusLabel()}
                </span>
              </div>
              <ChevronRight
                size={14}
                className="text-zinc-500 group-hover:translate-x-0.5 transition-transform shrink-0"
              />
            </button>

            {/* About BG AI */}
            <button
              onClick={onOpenAbout}
              className="flex items-center gap-2.5 w-full px-3.5 py-2 rounded-xl text-sm text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors group cursor-pointer"
            >
              <Info
                size={16}
                className="text-zinc-400 group-hover:text-indigo-400 transition-colors shrink-0"
              />
              <span>About BG AI</span>
            </button>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="flex items-center gap-2.5 w-full px-3.5 py-2 rounded-xl text-sm text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] transition-colors cursor-pointer"
            >
              {theme === "dark" ? (
                <Sun size={16} className="shrink-0" />
              ) : (
                <Moon size={16} className="shrink-0" />
              )}
              <span>
                {theme === "dark" ? "Light Appearance" : "Dark Appearance"}
              </span>
            </button>
          </div>
        </>
      ) : (
        /* COLLAPSED VIEW */
        <div className="flex-1 flex flex-col items-center justify-between py-3.5 px-2 overflow-y-auto">
          {/* Main Top Actions */}
          <div className="flex flex-col items-center gap-3 w-full">
            {/* New Query */}
            <SidebarTooltip label="New Query (⌘N / Ctrl+N)">
              <ClickSpark sparkColor="#818cf8" sparkCount={6} sparkRadius={16}>
                <button
                  onClick={onNewChat}
                  className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition-all flex items-center justify-center cursor-pointer"
                >
                  <Plus size={17} />
                </button>
              </ClickSpark>
            </SidebarTooltip>

            {/* Connect Database Button & Popover */}
            <div className="relative" ref={collapsedUploadMenuRef}>
              <SidebarTooltip label="Connect the Database">
                <button
                  onClick={() => setShowUploadMenu(!showUploadMenu)}
                  className="p-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.06] text-zinc-300 transition-all flex items-center justify-center cursor-pointer"
                >
                  <Database size={17} />
                </button>
              </SidebarTooltip>

              <AnimatePresence>
                {showUploadMenu && (
                  <motion.div
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -6 }}
                    transition={{ duration: 0.15 }}
                    className="absolute left-full ml-3 top-0 min-w-[200px] p-1.5 rounded-xl bg-[#141418] border border-white/10 shadow-2xl shadow-black/80 z-50 text-sm"
                  >
                    <div className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400 border-b border-white/[0.06] mb-1">
                      Connect Database
                    </div>
                    <button
                      onClick={() => {
                        setShowUploadMenu(false);
                        setShowConnectModal("sqlite");
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors text-xs cursor-pointer"
                    >
                      <Database
                        size={14}
                        className="text-indigo-400 shrink-0"
                      />
                      <span>Upload SQLite (.db)</span>
                    </button>
                    <button
                      onClick={() => {
                        setShowUploadMenu(false);
                        setShowConnectModal("mysql");
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors text-xs cursor-pointer"
                    >
                      <Server size={14} className="text-teal-400 shrink-0" />
                      <span>Connect MySQL</span>
                    </button>
                    <button
                      onClick={() => {
                        setShowUploadMenu(false);
                        setShowConnectModal("postgres");
                      }}
                      className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-left text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors text-xs cursor-pointer"
                    >
                      <Server size={14} className="text-sky-400 shrink-0" />
                      <span>Connect PostgreSQL</span>
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* History Toggle / Quick Access */}
            <SidebarTooltip label="Query History (Click to expand)">
              <button
                onClick={onToggleCollapse}
                className="p-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 transition-all flex items-center justify-center cursor-pointer"
              >
                <History size={17} />
              </button>
            </SidebarTooltip>
          </div>

          {/* Bottom Actions */}
          <div className="flex flex-col items-center gap-2.5 w-full pt-3 border-t border-white/[0.06]">
            {/* Database Status Button */}
            <SidebarTooltip
              label={
                isConnected
                  ? `${getDbStatusLabel()} (Click to inspect)`
                  : "Connect Database"
              }
            >
              <button
                onClick={() => {
                  if (isConnected) {
                    if (onOpenDatabase) onOpenDatabase();
                    else setShowDatabase(true);
                  } else {
                    setShowConnectModal("sqlite");
                  }
                }}
                className="relative p-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.06] text-zinc-300 transition-all flex items-center justify-center cursor-pointer"
              >
                <span className="relative flex h-2.5 w-2.5">
                  {isConnected && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  )}
                  <span
                    className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
                      isConnected
                        ? "bg-emerald-400 shadow-sm shadow-emerald-500/50"
                        : "bg-zinc-600"
                    }`}
                  />
                </span>
              </button>
            </SidebarTooltip>

            {/* About BG AI */}
            <SidebarTooltip label="About BG AI">
              <button
                onClick={onOpenAbout}
                className="p-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.06] text-zinc-400 hover:text-indigo-400 transition-all flex items-center justify-center cursor-pointer"
              >
                <Info size={17} />
              </button>
            </SidebarTooltip>

            {/* Theme Toggle */}
            <SidebarTooltip
              label={theme === "dark" ? "Light Appearance" : "Dark Appearance"}
            >
              <button
                onClick={toggleTheme}
                className="p-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 transition-all flex items-center justify-center cursor-pointer"
              >
                {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
              </button>
            </SidebarTooltip>
          </div>
        </div>
      )}

      {/* Modals triggered from sidebar */}
      {showUploader && (
        <DatabaseUploader
          onClose={() => setShowUploader(false)}
          onUploadComplete={() => {
            fetchDbInfo();
            onUploadComplete?.();
          }}
        />
      )}

      {showDatabase && (
        <DatabasePopup
          onClose={() => setShowDatabase(false)}
          onDisconnected={() => {
            fetchDbInfo();
            onDisconnect?.();
          }}
        />
      )}

      {showConnectModal && (
        <ConnectDatabaseModal
          defaultType={showConnectModal}
          onClose={() => setShowConnectModal(null)}
          onConnected={() => {
            fetchDbInfo();
            onDatabaseConnected?.();
          }}
        />
      )}
    </aside>
  );
}
