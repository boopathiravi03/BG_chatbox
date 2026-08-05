export default function SchemaViewer({
  schema,
}: {
  schema?: { [table: string]: { [column: string]: string } };
}) {
  if (!schema) return null;

  return (
    <div className="mt-4 rounded-xl bg-[#0d0d0d] border border-white/10 p-4">
      <p className="text-xs text-gray-500 mb-3 font-mono">Database Schema</p>
      <div className="space-y-3">
        {Object.entries(schema).map(([table, columns]) => (
          <div key={table}>
            <p className="text-sm font-medium text-blue-400 mb-1">{table}</p>
            <div className="space-y-1 pl-4">
              {Object.entries(columns).map(([column, type]) => (
                <div key={column} className="flex items-center gap-2 text-xs">
                  <span className="text-gray-300">{column}</span>
                  <span className="text-gray-500">{type}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
