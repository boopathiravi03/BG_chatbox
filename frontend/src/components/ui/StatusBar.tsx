type Status = "ready" | "thinking" | "executing" | "done" | "error";

const statusConfig = {
  ready: { color: "bg-emerald-400", text: "text-emerald-400", label: "Ready" },
  thinking: {
    color: "bg-amber-400",
    text: "text-amber-400",
    label: "Thinking...",
  },
  executing: {
    color: "bg-indigo-400",
    text: "text-indigo-400",
    label: "Executing SQL...",
  },
  done: {
    color: "bg-emerald-400",
    text: "text-emerald-400",
    label: "Completed",
  },
  error: { color: "bg-rose-400", text: "text-rose-400", label: "Failed" },
};

interface StatusBarProps {
  status: Status;
  dbConnected?: boolean;
  dbType?: string | null;
}

const dbTypeLabel = (type?: string | null) => {
  if (!type || type === "none") return null;
  return type === "mysql"
    ? "MySQL"
    : type === "postgres"
      ? "PostgreSQL"
      : type === "sqlite"
        ? "SQLite"
        : null;
};

export default function StatusBar({
  status,
  dbConnected,
  dbType,
}: StatusBarProps) {
  const current = statusConfig[status];
  const connectedDb = dbTypeLabel(dbType);

  return (
    <div className="flex items-center justify-between px-5 py-2.5 border-b border-white/[0.06] bg-[#09090b]/80 backdrop-blur-md">
      <div className="flex items-center gap-5 text-xs sm:text-sm font-medium">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${current.color}`}
            ></span>
          </span>
          <span className={current.text}>{current.label}</span>
        </div>

        <div className="flex items-center gap-2 text-zinc-300">
          <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
          <span>Engine Active</span>
        </div>

        {connectedDb && dbConnected && (
          <div className="flex items-center gap-2 text-zinc-200">
            <span className="h-2 w-2 rounded-full bg-teal-400"></span>
            <span>{connectedDb} Connected</span>
          </div>
        )}
      </div>

      <div className="text-xs text-zinc-400 font-mono">v1.0</div>
    </div>
  );
}
