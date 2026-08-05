import { Copy } from "lucide-react";
import { useState } from "react";

interface Props {
  sql: string;
}

export default function SqlCard({ sql }: Props) {
  const [copied, setCopied] = useState(false);

  const copySQL = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => {
      setCopied(false);
    }, 2000);
  };

  return (
    <div className="rounded-xl border border-zinc-700 bg-black overflow-hidden">
      <div className="flex justify-between items-center px-4 py-2 border-b border-zinc-700">
        <h3 className="font-semibold text-blue-400">
          Generated SQL
        </h3>

        <button
          onClick={copySQL}
          className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white"
        >
          <Copy size={15}/>
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      <pre className="p-4 text-green-400 overflow-x-auto">
        <code>{sql}</code>
      </pre>
    </div>
  );
}
