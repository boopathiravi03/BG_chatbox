import Hero from "../ui/Hero";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import Thinking from "./Thinking";
import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
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
}

export default function ChatArea({ messages, loading, sessions = [], activeSessionId, onSend, onInsertSubmit, onSessionClick, uploadVersion = 0, onStop, onConfirmQuery, onCancelQuery }: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [suggestion, setSuggestion] = useState("");
  const [showDbStats, setShowDbStats] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMatches, setSearchMatches] = useState<number>(0);
  const [showSearch, setShowSearch] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);

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
        console.error("Failed to fetch database info:", error);
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
        console.error("Failed to fetch suggestions:", error);
      }
    };

    fetchSuggestions();
  }, []);

  const handleConfirm = async (sql: string) => {
    onConfirmQuery?.(sql);
  };

  const handleCancel = () => {
    onCancelQuery?.();
  };

  return (
    <main className="flex flex-col h-full">
      {messages.length === 0 ? (
        <div className="flex-1 overflow-y-auto px-4 py-6 min-h-0">
          <div className="max-w-4xl mx-auto">
            <div className="flex flex-col items-center justify-center py-20">
              <Hero />
              <div className="flex flex-wrap gap-3 mt-8 justify-center">
                {suggestions.map((item) => (
                  <button
                    key={item}
                    onClick={() => setSuggestion(item)}
                    className="px-4 py-2 rounded-full bg-gray-200 text-black dark:bg-white/5 dark:text-white border border-gray-300 dark:border-white/10 hover:bg-gray-300 dark:hover:bg-white/10 text-sm transition-colors"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="border-b border-white/5 bg-[#09090B] p-4 z-10">
            <div className="max-w-4xl mx-auto">
              {!showSearch ? (
                <div className="flex items-center justify-end">
                  <button
                    onClick={() => setShowSearch(true)}
                    className="p-2 rounded-lg hover:bg-zinc-800 transition"
                  >
                    <Search size={20} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 overflow-hidden transition-all duration-300 ease-in-out max-h-16 opacity-100">
                  <Search size={20} className="text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search conversation..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="flex-1 px-4 py-2 rounded-lg bg-[#1b1b1f] border border-white/10 text-sm text-white placeholder:text-gray-500 outline-none focus:border-blue-500"
                  />
                  {searchQuery && (
                    <span className="text-xs text-blue-400 font-medium whitespace-nowrap">
                      {searchMatches} {searchMatches === 1 ? "match" : "matches"} found
                    </span>
                  )}
                  <button
                    onClick={clearSearch}
                    className="p-2 hover:bg-zinc-800 rounded-lg text-gray-400 hover:text-white"
                  >
                    <X size={20} />
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-6 min-h-0">
            <div className="max-w-4xl mx-auto">

              {messages.map((msg, index) => (
                <div key={index} className="msg-fade-in">
                <MessageBubble
                  message={msg}
                  searchTerm={searchQuery}
                  onSend={onSend}
                  onInsertSubmit={onInsertSubmit}
                  isTyping={loading && index === messages.length - 1}
                  onConfirm={handleConfirm}
                  onCancel={handleCancel}
                />
                </div>
              ))}
              {loading && <Thinking />}
              <div ref={bottomRef} />
            </div>
          </div>
        </>
      )}
      <div className="sticky bottom-0 border-t border-white/5 bg-[#09090B] p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-end mb-3">
            {messages.some((msg) => {
              if (msg.role !== "assistant") return false;
              return !!(
                msg.generated_sql ||
                msg.chart ||
                msg.diagram ||
                msg.analytics ||
                (msg.result?.rows && msg.result.rows.length > 0)
              );
            }) && (
              <button
                onClick={() => exportChatPDF(messages)}
                disabled={messages.length === 0}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 rounded-lg text-white text-sm"
              >
                📄 Export PDF
              </button>
            )}
          </div>

          <ChatInput onSend={onSend} disabled={loading} initialMessage={suggestion} onStop={onStop} loading={loading} />
        </div>
      </div>

      {showDbStats && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-50">
          <DatabaseStats onClose={() => setShowDbStats(false)} />
        </div>
      )}
    </main>
  );
}
