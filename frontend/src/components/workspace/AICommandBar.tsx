import React, { useState } from "react";
import { Sparkles, ArrowRight, CornerDownLeft, Command } from "lucide-react";

interface AICommandBarProps {
  onSend: (message: string) => void;
  loading?: boolean;
  disabled?: boolean;
}

const QUICK_PROMPTS = [
  "Analyze my business performance",
  "Show all tables",
  "Data health check",
  "Explain table relationships",
  "What is SQL?",
];

export default function AICommandBar({
  onSend,
  loading = false,
  disabled = false,
}: AICommandBarProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading || disabled) return;
    onSend(query.trim());
    setQuery("");
  };

  return (
    <div className="w-full bg-[#0d0d11]/90 backdrop-blur-md border-t border-white/[0.08] px-4 py-3 shrink-0">
      <div className="max-w-5xl mx-auto space-y-2">
        {/* Command Input Form */}
        <form
          onSubmit={handleSubmit}
          className="relative flex items-center bg-[#141418] border border-white/[0.1] focus-within:border-indigo-500/50 rounded-xl px-3 py-2 shadow-lg shadow-black/40 transition-all"
        >
          <div className="flex items-center gap-2 text-indigo-400 pl-1 shrink-0">
            <Sparkles size={16} className={loading ? "animate-spin" : ""} />
          </div>

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask BG AI anything about your data... (e.g. 'Analyze my business', 'Show customers', 'What is SQL?')"
            disabled={disabled || loading}
            className="flex-1 bg-transparent border-none text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none px-3 py-1 font-sans min-w-0"
          />

          <div className="flex items-center gap-1.5 shrink-0">
            <span className="hidden sm:inline-flex items-center gap-0.5 text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
              <Command size={10} /> Enter
            </span>
            <button
              type="submit"
              disabled={!query.trim() || loading || disabled}
              className="p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white transition-all cursor-pointer disabled:cursor-not-allowed shrink-0"
              title="Submit command"
            >
              <ArrowRight size={14} />
            </button>
          </div>
        </form>

        {/* Quick Suggestion Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pt-0.5">
          <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider shrink-0 mr-1">
            Quick:
          </span>
          {QUICK_PROMPTS.map((prompt, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSend(prompt)}
              disabled={disabled || loading}
              className="px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] hover:border-indigo-500/30 text-[11px] text-zinc-300 hover:text-white transition-all cursor-pointer whitespace-nowrap shrink-0"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
