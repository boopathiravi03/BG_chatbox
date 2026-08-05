import Sidebar from "../components/chat/Sidebar";
import Hero from "../components/ui/Hero";
import Background from "../components/ui/Background";
import AnnouncementBadge from "../components/ui/AnnouncementBadge";
import ModelSelector from "../components/ui/ModelSelector";
import StatusBar from "../components/ui/StatusBar";
import type { ChatSession } from "../types";

type Status = "ready" | "thinking" | "executing" | "done" | "error";

export default function MainLayout({ children, status, onNewChat, sessions, activeSessionId, onSessionClick, onUploadComplete }: { children: React.ReactNode; status: Status; onNewChat?: () => void; sessions?: ChatSession[]; activeSessionId?: string | null; onSessionClick?: (session: ChatSession) => void; onUploadComplete?: () => void }) {
  return (
    <div className="flex h-screen dark:bg-[#09090B] bg-gray-100 dark:text-white text-gray-900 relative overflow-hidden">
      <Background />
      <Sidebar onNewChat={onNewChat} sessions={sessions} activeSessionId={activeSessionId} onSessionClick={onSessionClick} onUploadComplete={onUploadComplete} />
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="relative z-10 flex flex-col h-full overflow-hidden">
          <header className="flex items-center justify-between p-4 border-b border-white/5 dark:bg-[#0f0f0f]/80 bg-white/80 backdrop-blur-xl">
            <AnnouncementBadge />
            <ModelSelector />
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
