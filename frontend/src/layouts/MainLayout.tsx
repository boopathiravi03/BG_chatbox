import Sidebar from "../components/chat/Sidebar";
import Hero from "../components/ui/Hero";
import Background from "../components/ui/Background";
import AnnouncementBadge from "../components/ui/AnnouncementBadge";
import ModelSelector from "../components/ui/ModelSelector";
import StatusBar from "../components/ui/StatusBar";
import type { ChatSession } from "../types";

type Status = "ready" | "thinking" | "executing" | "done" | "error";

export default function MainLayout({ children, status, onNewChat, sessions, activeSessionId, onSessionClick, onUploadComplete, dbConnected, dbType, onDatabaseConnected, onDeleteSession, onDisconnect }: { children: React.ReactNode; status: Status; onNewChat?: () => void; sessions?: ChatSession[]; activeSessionId?: string | null; onSessionClick?: (session: ChatSession) => void; onUploadComplete?: () => void; dbConnected?: boolean; dbType?: string | null; onDatabaseConnected?: () => void; onDeleteSession?: (id: string) => void; onDisconnect?: () => void }) {
  const dbLabel = dbType === "mysql" ? "MySQL" : dbType === "postgres" ? "PostgreSQL" : dbType === "sqlite" ? "SQLite" : null;

  return (
    <div className="flex h-screen dark:bg-[#09090B] bg-gray-100 dark:text-white text-gray-900 relative overflow-hidden">
      <Background />
      <Sidebar onNewChat={onNewChat} sessions={sessions} activeSessionId={activeSessionId} onSessionClick={onSessionClick} onUploadComplete={onUploadComplete} onDatabaseConnected={onDatabaseConnected} onDeleteSession={onDeleteSession} onDisconnect={onDisconnect} />
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="relative z-10 flex flex-col h-full overflow-hidden">
          <header className="flex items-center justify-between p-4 border-b border-white/5 dark:bg-[#0f0f0f]/80 bg-white/80 backdrop-blur-xl">
            <AnnouncementBadge />
            <div className="flex items-center gap-3">
              {dbConnected && dbLabel && (
                <span className="text-xs text-green-400 bg-green-500/10 px-3 py-1 rounded-full border border-green-500/20">
                  🟢 Connected · {dbLabel}
                </span>
              )}
              {dbConnected && onDisconnect && (
                <button
                  onClick={onDisconnect}
                  className="text-xs text-red-400 bg-red-500/10 hover:bg-red-500/20 px-3 py-1 rounded-full border border-red-500/20 transition-colors"
                >
                  Disconnect
                </button>
              )}
              <ModelSelector />
            </div>
          </header>
          <StatusBar status={status} />
          <div className="flex-1 overflow-hidden">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
