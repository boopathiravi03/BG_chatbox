import { Bar, Line, Pie, Doughnut } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

export default function ChartViewer({
  chart,
}: {
  chart?: {
    chart_type: string;
    title: string;
    labels: string[];
    values: number[];
  } | null;
}) {
  if (!chart) return null;

  const data = {
    labels: chart.labels,
    datasets: [
      {
        label: chart.title,
        data: chart.values,
        backgroundColor: [
          "rgba(59, 130, 246, 0.8)",
          "rgba(6, 182, 212, 0.8)",
          "rgba(99, 102, 241, 0.8)",
          "rgba(168, 85, 247, 0.8)",
          "rgba(236, 72, 153, 0.8)",
        ],
        borderColor: [
          "rgb(59, 130, 246)",
          "rgb(6, 182, 212)",
          "rgb(99, 102, 241)",
          "rgb(168, 85, 247)",
          "rgb(236, 72, 153)",
        ],
        borderWidth: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
    },
    scales: chart.chart_type === "pie" || chart.chart_type === "doughnut" ? {} : {
      y: {
        ticks: { color: "#9ca3af" },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
      x: {
        ticks: { color: "#9ca3af" },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
    },
  };

  const ChartComponent =
    chart.chart_type === "line"
      ? Line
      : chart.chart_type === "pie"
        ? Pie
        : chart.chart_type === "doughnut"
          ? Doughnut
          : Bar;

  return (
    <div className="mt-4 rounded-xl bg-[#0d0d0d] border border-white/10 p-4">
      <p className="text-xs text-gray-500 mb-3 font-mono">Chart</p>
      <div className="h-[300px]">
        <ChartComponent data={data} options={options} />
      </div>
    </div>
  );
}
