import * as XLSX from "xlsx";
import { saveAs } from "file-saver";
import { FileSpreadsheet } from "lucide-react";
import { useToast } from "../../context/ToastContext";

interface Props {
  result?: {
    success: boolean;
    columns?: string[];
    rows?: any[];
  };
}

export default function ResultTable({ result }: Props) {
  const toast = useToast();

  if (!result?.success || !result.columns || result.columns.length === 0)
    return null;

  const exportExcel = () => {
    if (!result?.rows?.length) return;

    try {
      const data = result.rows.map((row) => {
        const values = Array.isArray(row) ? row : Object.values(row);
        const obj: Record<string, any> = {};

        result.columns?.forEach((column, index) => {
          obj[column] = values[index];
        });

        return obj;
      });

      const worksheet = XLSX.utils.json_to_sheet(data);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Results");

      const excelBuffer = XLSX.write(workbook, {
        bookType: "xlsx",
        type: "array",
      });

      const blob = new Blob([excelBuffer], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      saveAs(blob, `BGAI_Export_${new Date().toISOString().slice(0, 10)}.xlsx`);
      toast.success("Excel sheet exported successfully");
    } catch {
      toast.error("Failed to export Excel document");
    }
  };

  return (
    <div className="w-full">
      <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
        <table className="min-w-full text-left border-collapse text-sm">
          <thead className="sticky top-0 bg-[#16161b] z-10 border-b border-white/[0.08]">
            <tr>
              {result.columns.map((col, index) => (
                <th
                  key={`${col}-${index}`}
                  className="px-4 py-3 font-semibold text-zinc-100 font-mono text-xs uppercase tracking-wider whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-white/[0.04]">
            {result.rows?.map((row, i) => {
              const values = Array.isArray(row) ? row : Object.values(row);

              return (
                <tr key={i} className="hover:bg-white/[0.03] transition-colors">
                  {values.map((cell, cellIndex) => (
                    <td
                      key={`${i}-${cellIndex}`}
                      className="px-4 py-2.5 text-zinc-200 font-mono text-xs sm:text-sm whitespace-nowrap"
                    >
                      {cell === null || cell === undefined ? (
                        <span className="text-zinc-500 italic">null</span>
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="p-3.5 border-t border-white/[0.06] bg-white/[0.02] flex items-center justify-between">
        <span className="text-xs sm:text-sm text-zinc-400 font-mono">
          {result.rows?.length || 0}{" "}
          {(result.rows?.length || 0) === 1 ? "record" : "records"} returned
        </span>

        <button
          onClick={exportExcel}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs sm:text-sm font-semibold text-white transition-colors shadow-sm"
        >
          <FileSpreadsheet size={15} className="text-teal-400" />
          <span>Export to Excel</span>
        </button>
      </div>
    </div>
  );
}
