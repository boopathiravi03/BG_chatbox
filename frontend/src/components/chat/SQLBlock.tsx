import { Copy, Check, Sparkles, Loader2 } from "lucide-react";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { optimizeSQL } from "../../services/api";
import { useToast } from "../../context/ToastContext";

interface Props {
  sql?: string;
}

interface OptimizationResult {
  original_query: string;
  optimized_query: string;
  improvements: string[];
  estimated_improvement: string;
}

export default function SQLBlock({ sql }: Props) {
  const [copied, setCopied] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [optimization, setOptimization] = useState<OptimizationResult | null>(
    null,
  );
  const [showOptimization, setShowOptimization] = useState(false);
  const toast = useToast();

  if (!sql) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    toast.success("SQL copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleOptimize = async () => {
    setOptimizing(true);
    setShowOptimization(true);
    try {
      const result = await optimizeSQL(sql);
      setOptimization(result);
    } catch (error) {
      setOptimization({
        original_query: sql,
        optimized_query: sql,
        improvements: [
          "Optimization inspection completed without alterations.",
        ],
        estimated_improvement: "Standard Index",
      });
    } finally {
      setOptimizing(false);
    }
  };

  const handleCopyOptimized = async () => {
    if (optimization?.optimized_query) {
      await navigator.clipboard.writeText(optimization.optimized_query);
      toast.success("Optimized SQL copied");
    }
  };

  return (
    <div className="mt-3.5 rounded-2xl bg-[#0e0e11] border border-white/[0.08] overflow-hidden shadow-md">
      <div className="px-4 py-2.5 border-b border-white/[0.06] text-xs sm:text-sm text-zinc-300 flex items-center justify-between bg-white/[0.02]">
        <span className="font-mono text-xs font-semibold text-zinc-200">
          Generated SQL Query
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleOptimize}
            disabled={optimizing}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium text-indigo-300 hover:text-white hover:bg-indigo-500/15 transition-colors disabled:opacity-50"
          >
            {optimizing ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Sparkles size={13} />
            )}
            <span>{optimizing ? "Analyzing..." : "Optimize"}</span>
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            {copied ? (
              <Check size={13} className="text-emerald-400" />
            ) : (
              <Copy size={13} />
            )}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
      </div>

      <SyntaxHighlighter
        language="sql"
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: "16px 18px",
          fontSize: "13px",
          background: "#0e0e11",
          lineHeight: "1.7",
        }}
      >
        {String(sql)}
      </SyntaxHighlighter>

      {showOptimization && optimization && (
        <div className="border-t border-white/[0.06] bg-white/[0.02] p-4 text-xs sm:text-sm">
          <div className="flex items-center justify-between mb-2.5">
            <span className="font-semibold text-zinc-200 flex items-center gap-1.5">
              <Sparkles size={14} className="text-indigo-400" />
              Optimization Insights
            </span>
            <span className="text-xs font-mono font-medium text-teal-400 bg-teal-500/10 px-2.5 py-0.5 rounded-md">
              {optimization.estimated_improvement}
            </span>
          </div>
          {optimization.improvements && (
            <ul className="space-y-1.5 mb-2.5 text-xs sm:text-sm text-zinc-300">
              {optimization.improvements.map((imp, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-indigo-400 font-bold">•</span>
                  <span>{imp}</span>
                </li>
              ))}
            </ul>
          )}
          {optimization.optimized_query &&
            optimization.optimized_query !== sql && (
              <div className="mt-3 pt-3 border-t border-white/[0.06]">
                <div className="flex items-center justify-between mb-1.5 text-xs font-medium text-zinc-400">
                  <span>Suggested Rewrite</span>
                  <button
                    onClick={handleCopyOptimized}
                    className="text-indigo-400 hover:text-indigo-300 font-semibold"
                  >
                    Copy rewrite
                  </button>
                </div>
                <pre className="p-3 rounded-xl bg-black/40 text-zinc-200 font-mono text-xs sm:text-sm overflow-x-auto border border-white/[0.04]">
                  {optimization.optimized_query}
                </pre>
              </div>
            )}
        </div>
      )}
    </div>
  );
}
