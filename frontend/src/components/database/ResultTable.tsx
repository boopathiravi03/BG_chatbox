export default function ResultTable({
  columns,
  rows,
}: {
  columns?: string[];
  rows?: any[][];
}) {
  if (!columns || !rows || rows.length === 0) return null;

  return (
    <div className="mt-4 rounded-xl bg-[#0d0d0d] border border-white/10 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {columns.map((col, i) => (
                <th key={i} className="px-4 py-3 text-left text-gray-400 font-medium">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                {row.map((cell, j) => (
                  <td key={j} className="px-4 py-3 text-gray-300">
                    {String(cell ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
