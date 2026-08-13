import { useState, useEffect } from "react";
import { Database, Plus, Sun, Moon, Upload, X, Server, MoreHorizontal, Trash2 } from "lucide-react";
import type { ChatSession } from "../../types";
import DatabaseUploader from "./DatabaseUploader";
import DatabasePopup from "./DatabasePopup";
import ConnectDatabaseModal from "./ConnectDatabaseModal";
import { getDatabaseInfo, getDatabaseType } from "../../services/api";
import { useTheme } from "../../context/ThemeContext";

interface Props {
  onClose?: () => void;
  onNewChat?: () => void;
  sessions?: ChatSession[];
  activeSessionId?: string | null;
  onSessionClick?: (session: ChatSession) => void;
  onUploadComplete?: () => void;
  onDatabaseConnected?: () => void;
  onDeleteSession?: (id: string) => void;
}

type DbType = "sqlite" | "mysql" | "postgres" | "none";

function formatDateLabel(createdAt?: string): string {
  if (!createdAt) return "";
  const date = new Date(createdAt);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const sessionDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  if (sessionDay.getTime() === today.getTime()) return "Today";
  if (sessionDay.getTime() === yesterday.getTime()) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined });
}

export default function Sidebar({ onClose, onNewChat, sessions = [], activeSessionId, onSessionClick, onUploadComplete, onDatabaseConnected, onDeleteSession }: Props) {
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showDatabase, setShowDatabase] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState<"mysql" | "postgres" | null>(null);
  const [dbType, setDbType] = useState<DbType>("none");
  const [loadingDbInfo, setLoadingDbInfo] = useState(true);
  const [historySearch, setHistorySearch] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const { theme, toggleTheme } = useTheme();

  const fetchDbInfo = async () => {
    try {
      const typeData = await getDatabaseType();
      setDbType(typeData.db_type as DbType);
    } catch (error) {
      console.error("Failed to fetch database type:", error);
      setDbType("none");
    } finally {
      setLoadingDbInfo(false);
    }
  };

  useEffect(() => {
    fetchDbInfo();
  }, []);

  useEffect(() => {
    const handleClickOutside = () => setOpenMenuId(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const getDbStatusLabel = () => {
    if (loadingDbInfo) return "Loading...";
    switch (dbType) {
      case "sqlite":
        return "SQLite Connected";
      case "mysql":
        return "MySQL Connected";
      case "postgres":
        return "PostgreSQL Connected";
      default:
        return "Not Connected";
    }
  };

  const isConnected = dbType !== "none";

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(historySearch.toLowerCase())
  );

  const groupedSessions = filteredSessions.reduce<Record<string, ChatSession[]>>((acc, session) => {
    const label = formatDateLabel(String(session.createdAt));
    if (!acc[label]) acc[label] = [];
    acc[label].push(session);
    return acc;
  }, {});

  const groupOrder = ["Today", "Yesterday", ...new Set(Object.keys(groupedSessions).filter((k) => k !== "Today" && k !== "Yesterday"))];

  return (
    <aside className="w-72 border-r border-white/10 dark:bg-[#111111] bg-white dark:text-white text-gray-900 flex flex-col">
      <div className="p-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">
            BG <span className="text-blue-500">AI</span>
          </h1>
          <p className="dark:text-gray-400 text-gray-600 text-sm mt-2">
            AI Database Assistant
          </p>
        </div>
        {onClose && (
          <button onClick={onClose} className="lg:hidden p-1 dark:text-gray-400 text-gray-600 hover:text-black">
            <X size={20} />
          </button>
        )}
      </div>

      <div className="px-4 space-y-3">
        <button
          onClick={onNewChat}
          className="flex items-center gap-3 w-full rounded-xl bg-blue-600 hover:bg-blue-700 p-3 font-medium transition-colors text-white"
        >
          <Plus size={18} />
          New Chat
        </button>

        <div className="relative">
          <button
            onClick={() => setShowUploadMenu(!showUploadMenu)}
            className="flex items-center gap-3 w-full rounded-xl border border-white/10 dark:hover:bg-white/5 hover:bg-gray-100 p-3 transition-colors"
          >
            <Upload size={18} />
            Upload Database
            <span className="ml-auto text-xs dark:text-gray-500 text-gray-500">▼</span>
          </button>
          {showUploadMenu && (
            <div className="absolute top-full left-0 right-0 mt-1 dark:bg-[#1a1a1a] bg-white border border-white/10 rounded-xl overflow-hidden z-50 shadow-xl">
              <button
                onClick={() => {
                  setShowUploadMenu(false);
                  setShowUploader(true);
                }}
                className="w-full text-left px-4 py-2.5 dark:hover:bg-white/5 hover:bg-gray-100 text-sm flex items-center gap-2 dark:text-gray-300 text-gray-700"
              >
                <Database size={14} />
                SQLite
              </button>
              <button
                onClick={() => {
                  setShowUploadMenu(false);
                  setShowConnectModal("mysql");
                }}
                className="w-full text-left px-4 py-2.5 dark:hover:bg-white/5 hover:bg-gray-100 text-sm flex items-center gap-2 dark:text-gray-300 text-gray-700"
              >
                <Server size={14} />
                MySQL
              </button>
              <button
                onClick={() => {
                  setShowUploadMenu(false);
                  setShowConnectModal("postgres");
                }}
                className="w-full text-left px-4 py-2.5 dark:hover:bg-white/5 hover:bg-gray-100 text-sm flex items-center gap-2 dark:text-gray-300 text-gray-700"
              >
                <Server size={14} />
                PostgreSQL
              </button>
              <button className="w-full text-left px-4 py-2.5 dark:hover:bg-white/5 hover:bg-gray-100 text-sm flex items-center gap-2 dark:text-gray-300 text-gray-700">
                <Upload size={14} />
                CSV
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 mt-4">
        <p className="text-xs dark:text-gray-500 text-gray-500 mb-2 px-2">History</p>
        <div className="px-2 mb-3">
          <input
            type="text"
            placeholder="Search chats..."
            value={historySearch}
            onChange={(e) => setHistorySearch(e.target.value)}
            className="w-full px-3 py-1.5 text-xs rounded-lg dark:bg-zinc-800 bg-gray-100 border border-white/10 dark:text-white text-gray-900 placeholder:text-gray-500 outline-none focus:border-blue-500 transition"
          />
        </div>
        <nav className="space-y-2">
          {filteredSessions.length === 0 ? (
            <p className="text-xs dark:text-gray-600 text-gray-500 px-2">
              {historySearch ? "No matching chats" : "No history yet"}
            </p>
          ) : (
            groupOrder.map((group) => {
              const groupSessions = groupedSessions[group];
              if (!groupSessions) return null;
              return (
                <div key={group}>
                  <p className="text-[10px] uppercase tracking-wider dark:text-gray-500 text-gray-400 mb-1 px-2 font-medium">{group}</p>
                  <div className="space-y-1">
                    {groupSessions.map((session) => (
                      <div
                        key={session.id}
                        className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-zinc-800 group relative"
                      >
                        <button
                          onClick={() => onSessionClick?.(session)}
                          className={`flex-1 text-left truncate text-sm transition-colors ${
                            session.id === activeSessionId
                              ? "bg-white/10 dark:text-white text-gray-900"
                              : "dark:text-gray-400 text-gray-600 dark:hover:text-white hover:text-black"
                          }`}
                        >
                          {session.title}
                        </button>
                        {onDeleteSession && (
                          <div className="relative">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setOpenMenuId(openMenuId === session.id ? null : session.id);
                              }}
                              className="opacity-0 group-hover:opacity-100 dark:text-gray-400 text-gray-500 hover:text-white transition p-1"
                              title="More"
                            >
                              <MoreHorizontal size={14} />
                            </button>
                            {openMenuId === session.id && (
                              <div className="absolute right-0 top-full mt-1 dark:bg-[#1a1a1a] bg-white border border-white/10 rounded-lg shadow-xl z-50 min-w-[140px] overflow-hidden">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteSession(session.id);
                                    setOpenMenuId(null);
                                  }}
                                  className="w-full text-left px-3 py-2 text-sm dark:hover:bg-white/5 hover:bg-gray-100 flex items-center gap-2 dark:text-red-400 text-red-600"
                                >
                                  <Trash2 size={14} />
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </nav>
      </div>

      <div className="p-4 border-t border-white/10">
        <div className="flex items-center gap-2 mb-3 px-1">
          <span className={`text-xs font-medium ${isConnected ? "text-green-400" : "text-gray-500"}`}>
            {isConnected ? "🟢" : "⚪"} {getDbStatusLabel()}
          </span>
        </div>
        <nav className="space-y-2">
          <button
            onClick={() => setShowDatabase(true)}
            className="flex items-center gap-3 p-3 rounded-xl dark:hover:bg-white/5 hover:bg-gray-100 w-full text-sm"
          >
            <Database size={18} />
            Database
          </button>
          <button
            onClick={toggleTheme}
            className="flex items-center gap-3 p-3 rounded-xl dark:hover:bg-white/5 hover:bg-gray-100 w-full text-sm"
          >
            {theme === "dark" ? (
              <>
                <Sun size={18} />
                Light Mode
              </>
            ) : (
              <>
                <Moon size={18} />
                Dark Mode
              </>
            )}
          </button>
        </nav>
      </div>

      {showUploader && (
        <DatabaseUploader onClose={() => setShowUploader(false)} onUploadComplete={onUploadComplete} />
      )}

      {showDatabase && (
        <DatabasePopup onClose={() => setShowDatabase(false)} />
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
