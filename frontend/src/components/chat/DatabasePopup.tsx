import { useState, useEffect } from "react";
import { Database, X, Table } from "lucide-react";
import { getSchema } from "../../services/api";

interface Props {
  onClose: () => void;
}

interface SchemaTable {
  table_name: string;
}

export default function DatabasePopup({ onClose }: Props) {
  const [schema, setSchema] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSchema = async () => {
      try {
        const data = await getSchema();
        setSchema(data || {});
      } catch (error) {
        console.error("Failed to fetch schema:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchSchema();
  }, []);

  const tables = Object.keys(schema);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="dark:bg-[#1a1a1a] bg-white border border-white/10 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Database size={20} />
            Current Database
          </h2>
          <button onClick={onClose} className="dark:text-gray-400 text-gray-700 hover:text-black dark:hover:text-white">
            <X size={20} />
          </button>
        </div>

        <div className="mb-4">
          <p className="text-sm dark:text-gray-400 text-gray-700 mb-2">Database</p>
          <p className="text-sm font-mono dark:bg-white/5 bg-gray-100 rounded-lg px-3 py-2 dark:text-white text-black">
            ecommerce.db
          </p>
        </div>

        <div>
          <p className="text-sm dark:text-gray-400 text-gray-700 mb-2 flex items-center gap-2">
            <Table size={14} />
            Tables
          </p>
          {loading ? (
            <p className="text-sm dark:text-gray-500 text-gray-500">Loading...</p>
          ) : tables.length === 0 ? (
            <p className="text-sm dark:text-gray-500 text-gray-500">No tables found</p>
          ) : (
            <div className="space-y-1 max-h-60 overflow-y-auto">
              {tables.map((table) => (
                <div
                  key={table}
                  className="text-sm dark:bg-white/5 bg-gray-100 rounded-lg px-3 py-2 dark:text-white text-black"
                >
                  {table}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
