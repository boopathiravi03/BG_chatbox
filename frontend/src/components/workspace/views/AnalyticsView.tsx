import React, { Suspense, lazy } from "react";
import { Sparkles, BarChart3, Database, Plug, RefreshCw } from "lucide-react";

const AnalyticsDashboard = lazy(
  () => import("../../dashboard/AnalyticsDashboard"),
);

interface AnalyticsViewProps {
  dbConnected: boolean;
  onRunAnalysis: () => void;
  onConnectDatabase: () => void;
}

export default function AnalyticsView({
  dbConnected,
  onRunAnalysis,
  onConnectDatabase,
}: AnalyticsViewProps) {
  if (!dbConnected) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mx-auto">
          <BarChart3 size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your database to generate live visual analytics, distributions,
          and automated business dashboards.
        </p>
        <button
          onClick={onConnectDatabase}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all cursor-pointer"
        >
          <Plug size={14} />
          <span>Connect Database</span>
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Analytics Header with AI Action */}
      <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            <BarChart3 size={18} className="text-indigo-400" />
            <span>Database Visual Analytics & Distributions</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Automated entity counts, distribution graphs, and relationship metrics.
          </p>
        </div>

        <button
          onClick={onRunAnalysis}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer shrink-0"
        >
          <Sparkles size={14} />
          <span>Analyze with BG AI</span>
        </button>
      </div>

      {/* Embedded Existing Analytics Dashboard */}
      <div className="bg-[#121216] border border-white/[0.08] rounded-2xl p-4 sm:p-6 overflow-hidden">
        <Suspense
          fallback={
            <div className="p-12 text-center text-zinc-400 text-xs flex items-center justify-center gap-2">
              <div className="w-4 h-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
              <span>Loading visual analytics...</span>
            </div>
          }
        >
          <AnalyticsDashboard />
        </Suspense>
      </div>
    </div>
  );
}
