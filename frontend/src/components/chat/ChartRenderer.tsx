import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";
import { useRef } from "react";
import { Download, BarChart2 } from "lucide-react";
import { useToast } from "../../context/ToastContext";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface Props {
  chart?: {
    chart_type: string;
    title: string;
    labels: string[];
    values: number[];
  } | null;
}

export default function ChartRenderer({ chart }: Props) {
  const chartRef = useRef<any>(null);
  const toast = useToast();

  if (!chart) {
    return (
      <div className="text-xs text-zinc-500 py-2">No chart data available.</div>
    );
  }

  const downloadChart = () => {
    if (!chartRef.current) return;
    try {
      const url = chartRef.current.toBase64Image();
      const link = document.createElement("a");
      link.download = `${chart.title || "chart"}.png`;
      link.href = url;
      link.click();
      toast.success("Chart exported as PNG");
    } catch {
      toast.error("Failed to export chart image");
    }
  };

  const data = {
    labels: chart.labels,
    datasets: [
      {
        label: chart.title,
        data: chart.values,
        backgroundColor: [
          "rgba(99, 102, 241, 0.75)",
          "rgba(20, 184, 166, 0.75)",
          "rgba(245, 158, 11, 0.75)",
          "rgba(139, 92, 246, 0.75)",
          "rgba(244, 63, 94, 0.75)",
          "rgba(14, 165, 233, 0.75)",
        ],
        borderColor: "rgba(255, 255, 255, 0.2)",
        borderWidth: 1,
        borderRadius: 6,
        hoverBackgroundColor: "rgba(99, 102, 241, 0.95)",
      },
    ],
  };

  const ChartComponent = chart.chart_type === "line" ? Line : Bar;

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: "#a1a1aa",
          font: { size: 11 },
        },
      },
      tooltip: {
        backgroundColor: "#141418",
        titleColor: "#f4f4f5",
        bodyColor: "#e4e4e7",
        borderColor: "rgba(255, 255, 255, 0.1)",
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        ticks: { color: "#71717a", font: { size: 10 } },
        grid: { color: "rgba(255, 255, 255, 0.04)" },
      },
      y: {
        beginAtZero: true,
        ticks: { color: "#71717a", font: { size: 10 } },
        grid: { color: "rgba(255, 255, 255, 0.04)" },
      },
    },
  };

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0e0e11] overflow-hidden shadow-md">
      <div className="px-4 py-2.5 border-b border-white/[0.06] flex items-center justify-between bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <BarChart2 size={14} className="text-indigo-400" />
          <h3 className="text-xs font-semibold text-zinc-200">{chart.title}</h3>
        </div>

        <button
          onClick={downloadChart}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] text-[11px] font-medium text-zinc-300 hover:text-white transition-colors"
        >
          <Download size={12} />
          <span>Save PNG</span>
        </button>
      </div>

      <div className="p-4 h-[320px]">
        <ChartComponent ref={chartRef} data={data} options={options} />
      </div>
    </div>
  );
}
