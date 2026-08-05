type Status = "ready" | "thinking" | "executing" | "done" | "error";

const statusConfig = {
  ready: { color: "bg-green-500", text: "text-green-400", label: "Ready" },
  thinking: { color: "bg-yellow-500", text: "text-yellow-400", label: "BG Thinking..." },
  executing: { color: "bg-blue-500", text: "text-blue-400", label: "Executing SQL..." },
  done: { color: "bg-green-500", text: "text-green-400", label: "Finished" },
  error: { color: "bg-red-500", text: "text-red-400", label: "Error" },
};

export default function StatusBar({ status }: { status: Status }) {
  const current = statusConfig[status];

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 dark:bg-[#0a0a0a]/80 bg-white/80 backdrop-blur-xl">
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${current.color} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${current.color}`}></span>
          </span>
          <span className={current.text}>{current.label}</span>
        </div>

        <div className="flex items-center gap-1 text-green-400">
          <span className="h-1.5 w-1.5 rounded-full bg-green-500"></span>
          BG Connected
        </div>

        <div className="flex items-center gap-1 text-green-400">
          <span className="h-1.5 w-1.5 rounded-full bg-green-500"></span>
          SQLite Connected
        </div>
      </div>

      <div className="text-xs dark:text-gray-500 text-gray-700">
        BG AI v1.0.0
      </div>
    </div>
  );
}
