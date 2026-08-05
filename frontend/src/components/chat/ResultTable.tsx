import * as XLSX from "xlsx";
import { saveAs } from "file-saver";

interface Props {
  result?: {
    success: boolean;
    columns?: string[];
    rows?: any[][];
  };
}

export default function ResultTable({ result }: Props) {
  if (!result?.success) return null;

  const exportExcel = () => {
    if (!result?.rows?.length) return;

    const data = result.rows.map((row) => {
      const obj: Record<string, any> = {};

      result.columns?.forEach((column, index) => {
        obj[column] = row[index];
      });

      return obj;
    });

    const worksheet = XLSX.utils.json_to_sheet(data);

    const workbook = XLSX.utils.book_new();

    XLSX.utils.book_append_sheet(
      workbook,
      worksheet,
      "Results"
    );

    const excelBuffer = XLSX.write(workbook, {
      bookType: "xlsx",
      type: "array",
    });

    const blob = new Blob([excelBuffer], {
      type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    saveAs(blob, `BGAI_${new Date().toISOString().slice(0, 10)}.xlsx`);
  };

  return (
    <div className="overflow-auto mt-4">
      <table className="min-w-full border border-gray-200 dark:border-zinc-700">
        <thead className="bg-gray-100 dark:bg-zinc-800">
          <tr>
            {result.columns?.map((col, index) => (
              <th
                key={`${col}-${index}`}
                className="border border-gray-200 dark:border-zinc-700 px-3 py-2 text-left text-gray-900 dark:text-gray-100"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {result.rows?.map((row, i) => (
            <tr key={i} className="bg-white dark:bg-zinc-900">
              {row.map((cell, cellIndex) => (
                <td
                  key={`${i}-${cellIndex}`}
                  className="border border-gray-200 dark:border-zinc-700 px-3 py-2 text-gray-700 dark:text-gray-200"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-4 flex gap-3">
        <button
          onClick={exportExcel}
          className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white"
        >
          📗 Export Excel
        </button>
      </div>
    </div>
  );
}
