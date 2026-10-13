import { useState, useEffect } from "react";
import { Sparkles, ChevronDown } from "lucide-react";

const BG_AI_MODEL_KEY = "bgai_selected_model";
export const BG_AI_INTELLIGENCE_MODEL = "bg-ai-core";

export default function ModelSelector() {
  const [model, setModel] = useState<string>(() => {
    try {
      const stored = localStorage.getItem(BG_AI_MODEL_KEY);
      return stored === BG_AI_INTELLIGENCE_MODEL ? stored : BG_AI_INTELLIGENCE_MODEL;
    } catch {
      return BG_AI_INTELLIGENCE_MODEL;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(BG_AI_MODEL_KEY, BG_AI_INTELLIGENCE_MODEL);
    } catch {
      // localStorage may be unavailable in some restricted environments
    }
  }, []);

  return (
    <div className="flex items-center gap-2 text-sm">
      <div className="relative inline-flex items-center">
        <select
          value={model}
          onChange={(e) => {
            const val = e.target.value === BG_AI_INTELLIGENCE_MODEL ? e.target.value : BG_AI_INTELLIGENCE_MODEL;
            setModel(val);
            try {
              localStorage.setItem(BG_AI_MODEL_KEY, val);
            } catch {
              // Ignore storage errors
            }
          }}
          className="appearance-none bg-[#141417] hover:bg-[#18181c] border border-white/10 rounded-xl pl-3 pr-8 py-1.5 text-xs font-medium text-zinc-200 outline-none focus:border-violet-500/50 transition-colors cursor-pointer"
          title="Select AI Reasoning Model"
        >
          <option value="bg-ai-core">BG AI Intelligence</option>
        </select>
        <ChevronDown
          size={13}
          className="absolute right-2.5 pointer-events-none text-zinc-400"
        />
      </div>

      <div className="hidden sm:inline-flex items-center gap-1.5 bg-violet-500/10 border border-violet-500/20 px-2.5 py-1.5 rounded-xl text-violet-300 font-medium text-xs">
        <Sparkles size={13} className="text-violet-400" />
        <span>BG LLM</span>
      </div>
    </div>
  );
}

