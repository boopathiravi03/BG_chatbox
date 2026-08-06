import { Copy, Check, Sparkles } from "lucide-react";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { optimizeSQL } from "../../services/api";

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
  const [optimization, setOptimization] = useState<OptimizationResult | null>(null);
  const [showOptimization, setShowOptimization] = useState(false);

  if (!sql) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
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
        improvements: ["Optimization failed. Please try again."],
        estimated_improvement: "N/A",
      });
    } finally {
      setOptimizing(false);
    }
  };

  const handleCopyOptimized = async () => {
    if (optimization?.optimized_query) {
      await navigator.clipboard.writeText(optimization.optimized_query);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="mt-3 rounded-xl bg-zinc-900 dark:bg-zinc-900 border border-zinc-700 dark:border-zinc-700 overflow-hidden">
      <div className="px-4 py-2 border-b border-zinc-700 text-xs text-zinc-300 dark:text-zinc-400 flex items-center justify-between bg-zinc-800/50">
        <span className="font-medium">Generated SQL</span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleOptimize}
            disabled={optimizing}
            className="flex items-center gap-1 text-xs hover:text-white transition-colors disabled:opacity-50"
          >
            <Sparkles size={14} />
            {optimizing ? "Optimizing..." : "✨ Optimize SQL"}
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs hover:text-white transition-colors"
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      <SyntaxHighlighter
        language="sql"
        style={oneDark}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: "16px",
          fontSize: "13px",
          background: "#111827",
        }}
      >
        {String(sql)}
      </SyntaxHighlighter>

      {showOptimization && optimization && (
        <div className="border-t border-zinc-700">
          <div className="px-4 py-2 border-b border-zinc-700 text-xs text-zinc-300 dark:text-zinc-400 flex items-center justify-between bg-zinc-800/50">
            <span className="font-medium">🚀 SQL Optimization Report</span>
            <span className="text-xs text-emerald-400">{optimization.estimated_improvement}</span>
          </div>

          <div className="p-4 space-y-3">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Original Query</p>
              <SyntaxHighlighter
                language="sql"
                style={oneDark}
                customStyle={{
                  margin: 0,
                  borderRadius: "8px",
                  padding: "12px",
                  fontSize: "12px",
                  background: "#1f2937",
                }}
              >
                {String(optimization.original_query)}
              </SyntaxHighlighter>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-gray-500 dark:text-gray-400">Optimized Query</p>
                <button
                  onClick={handleCopyOptimized}
                  className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <SyntaxHighlighter
                language="sql"
                style={oneDark}
                customStyle={{
                  margin: 0,
                  borderRadius: "8px",
                  padding: "12px",
                  fontSize: "12px",
                  background: "#065f46",
                }}
              >
                {String(optimization.optimized_query)}
              </SyntaxHighlighter>
            </div>

            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Improvements</p>
              <ul className="space-y-1">
                {optimization.improvements.map((improvement, index) => (
                  <li key={index} className="text-xs text-gray-300 flex items-start gap-2">
                    <span className="text-emerald-400 mt-0.5">✅</span>
                    {improvement}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
