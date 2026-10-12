import React, { useState } from "react";
import {
  Sparkles,
  ArrowRight,
  Command,
  Database,
  Layers,
  ChevronDown,
  Check,
} from "lucide-react";
import type { DatabaseConnectionItem } from "../../types";

interface AICommandBarProps {
  onSend: (message: string, selectedSourceIds?: string[]) => void;
  connections?: DatabaseConnectionItem[];
  activeConnectionId?: string | null;
  loading?: boolean;
  disabled?: boolean;
}

const QUICK_PROMPTS = [
  "Analyze my business performance",
  "Compare revenue across sources",
  "Show all tables",
  "Data health check",
  "Explain table relationships",
];

export default function AICommandBar({
  onSend,
  connections = [],
  activeConnectionId,
  loading = false,
  disabled = false,
}: AICommandBarProps) {
  const [query, setQuery] = useState("");
  const [selectedMode, setSelectedMode] = useState<"all" | string>("all");
  const [showSourceMenu, setShowSourceMenu] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading || disabled) return;

    const sourceIds =
      selectedMode === "all"
        ? undefined // Let CrossDatabaseEngine query all/route intelligently
        : [selectedMode];

    onSend(query.trim(), sourceIds);
    setQuery("");
  };

  const getSourceLabel = () => {
    if (selectedMode === "all") {
      return connections.length > 1
        ? `All Sources (${connections.length})`
        : "All Connected Sources";
    }
    const found = connections.find((c) => c.connection_id === selectedMode);
    return found ? found.name : "Active Source";
  };

  return (
    <div className="w-full bg-[#0d0d11]/90 backdrop-blur-md border-t border-white/[0.08] px-4 py-3 shrink-0 select-none">
      <div className="max-w-5xl mx-auto space-y-2">
        {/* Command Input Form */}
        <form
          onSubmit={handleSubmit}
          className="relative flex items-center bg-[#141418] border border-white/[0.1] focus-within:border-violet-500/50 rounded-xl px-3 py-2 shadow-lg shadow-black/40 transition-all"
        >
          {/* Source Selector Pill (if multiple connections exist) */}
          {connections.length > 1 ? (
            <div className="relative shrink-0 mr-1.5">
              <button
                type="button"
                onClick={() => setShowSourceMenu((prev) => !prev)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-[11px] font-medium text-zinc-300 hover:text-white transition-colors cursor-pointer"
                title="Select source target"
              >
                <Layers size={12} className="text-violet-400" />
                <span className="max-w-[110px] truncate">{getSourceLabel()}</span>
                <ChevronDown size={11} className="text-zinc-500" />
              </button>

              {showSourceMenu && (
                <div className="absolute bottom-full mb-2 left-0 w-56 bg-[#141418] border border-white/[0.1] rounded-xl shadow-2xl py-1.5 z-50 text-xs">
                  <div className="px-3 py-1 text-[10px] uppercase font-semibold text-zinc-500 tracking-wider">
                    Target Data Sources
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedMode("all");
                      setShowSourceMenu(false);
                    }}
                    className={`w-full px-3 py-1.5 flex items-center justify-between text-left hover:bg-white/[0.04] text-xs cursor-pointer ${
                      selectedMode === "all" ? "text-violet-300 font-semibold" : "text-zinc-300"
                    }`}
                  >
                    <span>All Sources (Cross-DB)</span>
                    {selectedMode === "all" && <Check size={12} className="text-violet-400" />}
                  </button>

                  <div className="my-1 border-t border-white/[0.04]" />

                  {connections.map((c) => (
                    <button
                      key={c.connection_id}
                      type="button"
                      onClick={() => {
                        setSelectedMode(c.connection_id);
                        setShowSourceMenu(false);
                      }}
                      className={`w-full px-3 py-1.5 flex items-center justify-between text-left hover:bg-white/[0.04] text-xs cursor-pointer truncate ${
                        selectedMode === c.connection_id
                          ? "text-violet-300 font-semibold"
                          : "text-zinc-300"
                      }`}
                    >
                      <span className="truncate">{c.name}</span>
                      {selectedMode === c.connection_id && (
                        <Check size={12} className="text-violet-400 shrink-0 ml-1" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-violet-400 pl-1 shrink-0">
              <Sparkles size={16} className={loading ? "animate-spin" : ""} />
            </div>
          )}

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              connections.length > 1
                ? "Ask across databases... (e.g. 'Compare sales with inventory', 'Find customer by email')"
                : "Ask BG AI anything about your data... (e.g. 'Analyze my business', 'Show customers')"
            }
            disabled={disabled || loading}
            className="flex-1 bg-transparent border-none text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none px-2 py-1 font-sans min-w-0"
          />

          <div className="flex items-center gap-1.5 shrink-0">
            <span className="hidden sm:inline-flex items-center gap-0.5 text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
              <Command size={10} /> Enter
            </span>
            <button
              type="submit"
              disabled={!query.trim() || loading || disabled}
              className="p-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white transition-all cursor-pointer disabled:cursor-not-allowed shrink-0"
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
              onClick={() => onSend(prompt, selectedMode === "all" ? undefined : [selectedMode])}
              disabled={disabled || loading}
              className="px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] hover:border-violet-500/30 text-[11px] text-zinc-300 hover:text-white transition-all cursor-pointer whitespace-nowrap shrink-0"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
