import { Sparkles } from "lucide-react";

export default function AnnouncementBadge() {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-xs sm:text-sm text-zinc-200 backdrop-blur-sm transition-colors hover:border-white/15">
      <Sparkles size={14} className="text-indigo-400" />
      <span className="font-semibold text-white">BG AI</span>
      <span className="text-zinc-500">•</span>
      <span className="text-zinc-300">Database Intelligence</span>
    </div>
  );
}
