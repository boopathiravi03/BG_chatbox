import { Sparkles, ChevronDown } from "lucide-react";

export default function ModelSelector() {
  return (
    <div className="flex items-center gap-2.5 text-sm">
      <div className="relative inline-flex items-center">
        <select className="appearance-none bg-[#141417] hover:bg-[#18181c] border border-white/10 rounded-xl pl-3.5 pr-9 py-2 text-xs sm:text-sm font-medium text-zinc-200 outline-none focus:border-indigo-500/50 transition-colors cursor-pointer">
          <option>Default (SQLite)</option>
          <option>PostgreSQL</option>
          <option>MySQL</option>
        </select>
        <ChevronDown
          size={14}
          className="absolute right-3 pointer-events-none text-zinc-400"
        />
      </div>

      <div className="hidden sm:inline-flex items-center gap-1.5 bg-indigo-500/10 border border-indigo-500/20 px-3 py-2 rounded-xl text-indigo-300 font-medium text-xs sm:text-sm">
        <Sparkles size={14} className="text-indigo-400" />
        <span>BG LLM</span>
      </div>
    </div>
  );
}
