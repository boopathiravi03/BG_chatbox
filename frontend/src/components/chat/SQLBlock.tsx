import { Copy, Check } from "lucide-react";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Props {
  sql?: string;
}

export default function SQLBlock({ sql }: Props) {
  const [copied, setCopied] = useState(false);

  if (!sql) return null;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mt-3 rounded-xl bg-zinc-900 dark:bg-zinc-900 border border-zinc-700 dark:border-zinc-700 overflow-hidden">
      <div className="px-4 py-2 border-b border-zinc-700 text-xs text-zinc-300 dark:text-zinc-400 flex items-center justify-between bg-zinc-800/50">
        <span className="font-medium">Generated SQL</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs hover:text-white transition-colors"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </button>
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
    </div>
  );
}
