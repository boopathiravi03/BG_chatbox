import { useState } from "react";
import { Database, Plus, Sun, Moon, Upload, X } from "lucide-react";
import type { ChatSession } from "../../types";
import DatabaseUploader from "./DatabaseUploader";
import DatabasePopup from "./DatabasePopup";
import { useTheme } from "../../context/ThemeContext";

interface Props {
  onClose?: () => void;
  onNewChat?: () => void;
  sessions?: ChatSession[];
  activeSessionId?: string | null;
  onSessionClick?: (session: ChatSession) => void;
  onUploadComplete?: () => void;
}

export default function Sidebar({ onClose, onNewChat, sessions = [], activeSessionId, onSessionClick, onUploadComplete }: Props) {
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [showDatabase, setShowDatabase] = useState(false);
  const { theme, toggleTheme } = useTheme();

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
                Upload SQLite
              </button>
              <button className="w-full text-left px-4 py-2.5 dark:hover:bg-white/5 hover:bg-gray-100 text-sm flex items-center gap-2 dark:text-gray-300 text-gray-700">
                <Upload size={14} />
                Upload CSV
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 mt-6">
        <p className="text-xs dark:text-gray-500 text-gray-500 mb-3 px-2">History</p>
        <nav className="space-y-1">
          {sessions.length === 0 ? (
            <p className="text-xs dark:text-gray-600 text-gray-500 px-2">No history yet</p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSessionClick?.(session)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors truncate ${
                  session.id === activeSessionId
                    ? "bg-white/10 dark:text-white text-gray-900"
                    : "dark:text-gray-400 text-gray-600 dark:hover:text-white hover:text-black dark:hover:bg-white/5 hover:bg-gray-100"
                }`}
              >
                {session.title}
              </button>
            ))
          )}
        </nav>
      </div>

      <div className="p-4 border-t border-white/10">
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
    </aside>
  );
}
