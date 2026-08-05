export default function SQLViewer({ sql }: { sql?: string }) {
  if (!sql) return null;

  return (
    <div className="mt-4 rounded-xl bg-[#0d0d0d] border border-white/10 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 font-mono">Generated SQL</span>
        <button
          onClick={() => navigator.clipboard.writeText(sql)}
          className="text-xs text-gray-400 hover:text-white transition-colors"
        >
          Copy
        </button>
      </div>
      <pre className="text-sm text-blue-400 font-mono overflow-x-auto whitespace-pre-wrap">
        {sql}
      </pre>
    </div>
  );
}
