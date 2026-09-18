import Hero from "../ui/Hero";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import Thinking from "./Thinking";
import { Search, X, FileDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { exportChatPDF } from "../../utils/exportPdf";
import DatabaseStats from "./DatabaseStats";
import { getDatabaseInfo, getSuggestions } from "../../services/api";

interface ChatAreaProps {
  messages: any[];
  loading: boolean;
  sessions?: any[];
  activeSessionId?: string | null;
  onSend: (message: string) => void;
  onInsertSubmit?: (values: Record<string, string>, table: string) => void;
  onSessionClick?: (session: any) => void;
  uploadVersion?: number;
  onStop?: () => void;
  onConfirmQuery?: (sql: string) => void;
  onCancelQuery?: () => void;
  dbConnected?: boolean;
  dbType?: string | null;
  onOpenDatabase?: () => void;
  onConnectDatabase?: (type?: "sqlite" | "mysql" | "postgres") => void;
}

export default function ChatArea({
  messages,
  loading,
  sessions = [],
  activeSessionId,
  onSend,
  onInsertSubmit,
  onSessionClick,
  uploadVersion = 0,
  onStop,
  onConfirmQuery,
  onCancelQuery,
  dbConnected,
  dbType,
  onOpenDatabase,
  onConnectDatabase,
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showDbStats, setShowDbStats] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMatches, setSearchMatches] = useState<number>(0);
  const [showSearch, setShowSearch] = useState(false);
  const [, setSuggestions] = useState<string[]>([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchMatches(0);
      return;
    }

    const query = searchQuery.toLowerCase();
    const matches = messages.filter((msg) => {
      const content = (msg.content || "").toLowerCase();
      const sql = (msg.sql || "").toLowerCase();
      return content.includes(query) || sql.includes(query);
    });

    setSearchMatches(matches.length);
  }, [searchQuery, messages]);

  const clearSearch = () => {
    setSearchQuery("");
    setSearchMatches(0);
  };

  useEffect(() => {
    const fetchDbInfo = async () => {
      try {
        await getDatabaseInfo();
        setShowDbStats(true);
      } catch (error) {
        // silent
      }
    };

    if (uploadVersion > 0) {
      fetchDbInfo();
    }
  }, [uploadVersion]);

  useEffect(() => {
    const fetchSuggestions = async () => {
      try {
        const data = await getSuggestions();
        if (data.suggestions && Array.isArray(data.suggestions)) {
          setSuggestions(data.suggestions);
        }
      } catch (error) {
        // silent
      }
    };

    fetchSuggestions();
  }, []);

  const hasExportableContent = messages.some((msg) => {
    if (msg.role !== "assistant") return false;
    return !!(
      msg.generated_sql ||
      msg.chart ||
      msg.diagram ||
      msg.analytics ||
      (msg.result?.rows && msg.result.rows.length > 0)
    );
  });

  return (
    <main className="flex flex-col h-full bg-[#09090b] relative overflow-hidden">
      <AnimatePresence mode="wait">
        {messages.length === 0 ? (
          /* EMPTY CHAT STATE: Large centered hero composer */
          <motion.div
            key="empty-hero"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="flex-1 overflow-y-auto px-4 py-4 sm:py-6 min-h-0 flex flex-col justify-center items-center custom-scrollbar"
          >
            <Hero
              onSend={onSend}
              dbConnected={dbConnected}
              dbType={dbType}
              onConnect={onConnectDatabase || onOpenDatabase}
              onOpenDetails={onOpenDatabase}
              composer={
                <ChatInput
                  onSend={onSend}
                  disabled={loading}
                  onStop={onStop}
                  loading={loading}
                  variant="hero"
                  dbConnected={dbConnected}
                  dbType={dbType}
                />
              }
            />
          </motion.div>
        ) : (
          /* ACTIVE CHAT STATE: Conversation stream + Compact bottom composer */
          <motion.div
            key="active-chat"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="flex-1 flex flex-col min-h-0 overflow-hidden"
          >
            {/* Top search and export bar — Centered */}
            <div className="border-b border-white/[0.06] bg-[#09090b]/90 backdrop-blur-md px-4 sm:px-6 md:px-8 py-2 shrink-0 z-10">
              <div className="max-w-4xl xl:max-w-5xl mx-auto w-full flex items-center justify-between">
                <div className="flex-1">
                  {showSearch ? (
                    <div className="flex items-center gap-2.5 max-w-md">
                      <Search size={15} className="text-zinc-400 shrink-0" />
                      <input
                        type="text"
                        placeholder="Search within this conversation..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        autoFocus
                        className="flex-1 px-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-xs sm:text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500/60 font-sans"
                      />
                      {searchQuery && (
                        <span className="text-xs text-zinc-400 whitespace-nowrap font-mono">
                          {searchMatches}{" "}
                          {searchMatches === 1 ? "match" : "matches"}
                        </span>
                      )}
                      <button
                        onClick={() => {
                          clearSearch();
                          setShowSearch(false);
                        }}
                        className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-white/5"
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setShowSearch(true)}
                      className="flex items-center gap-2 text-xs sm:text-sm text-zinc-400 hover:text-zinc-200 font-medium transition-colors"
                    >
                      <Search size={15} />
                      <span>Search conversation</span>
                    </button>
                  )}
                </div>

                {hasExportableContent && (
                  <button
                    onClick={() => exportChatPDF(messages)}
                    className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs sm:text-sm font-semibold text-zinc-200 hover:text-white transition-all shadow-sm"
                    title="Export results as PDF"
                  >
                    <FileDown size={14} />
                    <span>Export Report</span>
                  </button>
                )}
              </div>
            </div>

            {/* Messages list — Centered readable container */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-6 md:px-8 py-5 sm:py-6 min-h-0 custom-scrollbar">
              <div className="max-w-4xl xl:max-w-5xl mx-auto w-full space-y-5">
                {messages.map((msg, index) => (
                  <div key={index} className="msg-fade-in w-full">
                    <MessageBubble
                      message={msg}
                      searchTerm={searchQuery}
                      onSend={onSend}
                      onInsertSubmit={onInsertSubmit}
                      isTyping={loading && index === messages.length - 1}
                      onConfirm={onConfirmQuery}
                      onCancel={onCancelQuery}
                      onConnectDatabase={onConnectDatabase}
                    />
                  </div>
                ))}
                {loading && <Thinking />}
                <div ref={bottomRef} className="h-4" />
              </div>
            </div>

            {/* Compact Bottom Composer — Centered container */}
            <div className="shrink-0 border-t border-white/[0.06] bg-[#09090b]/95 backdrop-blur-md px-4 sm:px-6 md:px-8 py-3 sm:py-3.5 z-20">
              <div className="max-w-4xl xl:max-w-5xl mx-auto w-full">
                <ChatInput
                  onSend={onSend}
                  disabled={loading}
                  onStop={onStop}
                  loading={loading}
                  variant="bottom"
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {showDbStats && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <DatabaseStats onClose={() => setShowDbStats(false)} />
        </div>
      )}
    </main>
  );
}
