import { Mic, Square, Sparkles, ArrowUp } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getSuggestions } from "../../services/api";
import { dropdownVariants } from "../../lib/motion";
import ClickSpark from "../reactbits/ClickSpark";

interface ChatInputProps {
  onSend?: (message: string) => void;
  disabled?: boolean;
  onStop?: () => void;
  loading?: boolean;
  variant?: "hero" | "bottom";
  dbConnected?: boolean;
  dbType?: string | null;
}

export default function ChatInput({
  onSend,
  disabled,
  onStop,
  loading,
  variant = "bottom",
  dbConnected,
  dbType,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [filtered, setFiltered] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [listening, setListening] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isHero = variant === "hero";

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  useEffect(() => {
    const fetchSuggestions = async () => {
      try {
        const data = await getSuggestions();
        if (data.suggestions && Array.isArray(data.suggestions)) {
          setSuggestions(data.suggestions);
        }
      } catch (error) {
        // silent fail
      }
    };
    fetchSuggestions();
  }, []);

  const handleChange = (value: string) => {
    setMessage(value);

    // Auto-adjust textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const maxHeight = isHero ? 220 : 160;
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, maxHeight)}px`;
    }

    if (!value.trim()) {
      setFiltered([]);
      setShowSuggestions(false);
      return;
    }

    const results = suggestions.filter((item) =>
      item.toLowerCase().includes(value.toLowerCase()),
    );
    setFiltered(results.slice(0, 5));
    setShowSuggestions(results.length > 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!message.trim() || disabled || loading) return;
    onSend?.(message.trim());
    setMessage("");
    setShowSuggestions(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const startListening = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in your browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    setListening(true);

    recognition.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setMessage((prev) => (prev ? `${prev} ${text}` : text));
      setListening(false);
    };

    recognition.onerror = () => {
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognition.start();
  };

  return (
    <div
      className={`relative w-full ${isHero ? "max-w-4xl lg:max-w-5xl" : "w-full"} mx-auto`}
      ref={containerRef}
    >
      {/* Autocomplete suggestions popover */}
      <AnimatePresence>
        {showSuggestions && filtered.length > 0 && (
          <motion.div
            variants={dropdownVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="absolute bottom-full left-0 right-0 mb-2.5 p-2 rounded-2xl bg-[#141418] border border-white/10 shadow-2xl shadow-black/80 z-40 overflow-hidden"
          >
            <div className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
              <Sparkles size={13} className="text-indigo-400" />
              <span>Suggested Queries</span>
            </div>
            {filtered.map((item) => (
              <button
                key={item}
                onClick={() => {
                  setMessage(item);
                  setShowSuggestions(false);
                  onSend?.(item);
                }}
                className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-left text-sm font-medium rounded-xl text-zinc-200 hover:text-white hover:bg-white/[0.06] transition-colors truncate"
              >
                <span>{item}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Composer Box */}
      <div
        className={`relative flex flex-col rounded-2xl bg-[#121215] border transition-all ${
          isHero
            ? "border-white/[0.12] hover:border-white/[0.18] focus-within:border-indigo-500/60 focus-within:ring-2 focus-within:ring-indigo-500/20 shadow-2xl shadow-black/60"
            : "border-white/[0.08] hover:border-white/[0.14] focus-within:border-indigo-500/60 focus-within:ring-2 focus-within:ring-indigo-500/20 shadow-xl shadow-black/40"
        }`}
      >
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus={isHero}
          placeholder={
            isHero
              ? "Ask a question about your database, generate SQL, or analyze metrics..."
              : "Ask a follow-up question or request changes..."
          }
          disabled={disabled}
          rows={isHero ? 3 : 1}
          className={`w-full bg-transparent text-zinc-100 placeholder:text-zinc-400 outline-none resize-none leading-relaxed ${
            isHero
              ? "px-5 pt-4 pb-3 text-base sm:text-[16px] min-h-[105px] sm:min-h-[120px]"
              : "px-5 pt-4 pb-3 text-base sm:text-[16px] min-h-[56px] sm:min-h-[62px]"
          }`}
        />

        {/* Toolbar & Controls */}
        <div
          className={`flex items-center justify-between border-t border-white/[0.04] ${
            isHero ? "px-5 py-3" : "px-4 pb-3 pt-1.5"
          }`}
        >
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={startListening}
              className={`p-2 rounded-xl text-sm transition-colors ${
                listening
                  ? "bg-rose-500/20 text-rose-400 animate-pulse"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
              }`}
              title="Voice Input"
            >
              <Mic size={isHero ? 19 : 18} />
            </button>

            <span className="text-xs text-zinc-500 hidden sm:inline px-1 font-medium select-none">
              Enter to send, Shift+Enter for new line
            </span>

            {isHero && dbConnected && dbType && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-teal-500/10 border border-teal-500/20 text-[11px] font-medium text-teal-400">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
                {dbType}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {loading ? (
              <button
                type="button"
                onClick={onStop}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs sm:text-sm font-medium transition-colors cursor-pointer"
                title="Stop execution"
              >
                <Square size={13} className="fill-current" />
                <span>Stop</span>
              </button>
            ) : (
              <ClickSpark sparkColor="#a5b4fc" sparkCount={6} sparkRadius={16}>
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={!message.trim() || disabled}
                  className={`flex items-center justify-center rounded-xl text-white transition-all cursor-pointer ${
                    isHero
                      ? "h-11 w-11 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:hover:bg-indigo-600 shadow-md shadow-indigo-600/30"
                      : "h-10 w-10 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:hover:bg-indigo-600 shadow-md shadow-indigo-600/20"
                  }`}
                  title="Send query"
                >
                  <ArrowUp size={isHero ? 19 : 18} />
                </button>
              </ClickSpark>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
