import { useEffect, useState } from "react";
import {
  Database,
  Table,
  FileText,
  Columns,
  HardDrive,
  ExternalLink,
} from "lucide-react";
import { getDatabaseInfo, getSchema } from "../../services/api";

interface DatabaseInfo {
  database?: string;
  tables?: number;
  rows?: number;
  columns?: number;
  size?: string;
  error?: string;
}

interface Props {
  onExplore?: () => void;
}

export default function DatabaseOverview({ onExplore }: Props) {
  const [info, setInfo] = useState<DatabaseInfo | null>(null);
  const [tableNames, setTableNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const [infoData, schemaData] = await Promise.all([
          getDatabaseInfo(),
          getSchema(),
        ]);
        setInfo(infoData);
        setTableNames(Object.keys(schemaData || {}));
      } catch (error) {
        setInfo({ error: "Failed to load database info" });
      } finally {
        setLoading(false);
      }
    };

    fetchInfo();
  }, []);

  if (loading) {
    return (
      <div className="rounded-2xl border border-white/[0.08] bg-[#121215] p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="h-4 w-32 bg-white/[0.06] rounded animate-pulse" />
          <div className="h-4 w-12 bg-white/[0.06] rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          <div className="h-16 bg-white/[0.04] border border-white/[0.04] rounded-xl animate-pulse" />
          <div className="h-16 bg-white/[0.04] border border-white/[0.04] rounded-xl animate-pulse" />
          <div className="h-16 bg-white/[0.04] border border-white/[0.04] rounded-xl animate-pulse" />
          <div className="h-16 bg-white/[0.04] border border-white/[0.04] rounded-xl animate-pulse" />
        </div>
        <div className="h-8 bg-white/[0.04] rounded-xl animate-pulse" />
      </div>
    );
  }

  if (info?.error || !info) {
    return (
      <div className="rounded-2xl border border-white/[0.08] bg-[#121215] p-5 text-center text-xs text-zinc-400">
        Database metrics unavailable.
      </div>
    );
  }

  const metrics = [
    { label: "Tables", value: info.tables ?? tableNames.length, icon: Table },
    { label: "Rows", value: (info.rows ?? 0).toLocaleString(), icon: FileText },
    { label: "Cols", value: info.columns ?? 0, icon: Columns },
    { label: "Size", value: info.size ?? "—", icon: HardDrive },
  ];

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#121215] p-4 sm:p-5 shadow-lg shadow-black/30">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <Database size={16} className="text-indigo-400" />
          <span className="truncate max-w-[170px]">
            {info.database || "Active Database"}
          </span>
        </div>
        {onExplore && (
          <button
            onClick={onExplore}
            className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-semibold transition-colors"
          >
            <span>Manage</span>
            <ExternalLink size={13} />
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2.5 mb-4">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3"
          >
            <div className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-zinc-400 mb-1 font-medium">
              <metric.icon size={13} className="text-indigo-400/90" />
              {metric.label}
            </div>
            <div className="text-base font-bold text-white font-mono">
              {metric.value}
            </div>
          </div>
        ))}
      </div>

      {tableNames.length > 0 && (
        <div>
          <p className="text-xs sm:text-sm font-semibold text-zinc-300 mb-2.5">
            Tables ({tableNames.length})
          </p>
          <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto pr-1">
            {tableNames.slice(0, 12).map((table) => (
              <span
                key={table}
                className="px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs font-mono text-zinc-200"
              >
                {table}
              </span>
            ))}
            {tableNames.length > 12 && (
              <span className="px-2.5 py-1 rounded-lg bg-white/[0.02] border border-white/[0.04] text-xs font-mono text-zinc-400">
                +{tableNames.length - 12} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
