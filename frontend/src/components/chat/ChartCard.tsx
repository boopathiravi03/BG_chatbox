import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";
import { BarChart3 } from "lucide-react";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface Props {
  chart: {
    chart_type: string;
    title: string;
    labels: string[];
    values: number[];
  };
}

export default function ChartCard({ chart }: Props) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0e0e11] overflow-hidden shadow-md">
      <div className="px-4 py-2.5 border-b border-white/[0.06] flex items-center gap-2 bg-white/[0.02]">
        <BarChart3 size={14} className="text-indigo-400" />
        <h3 className="text-xs font-semibold text-zinc-200">{chart.title}</h3>
      </div>

      <div className="p-4">
        <Bar
          data={{
            labels: chart.labels,
            datasets: [
              {
                label: chart.title,
                data: chart.values,
                backgroundColor: "rgba(99, 102, 241, 0.7)",
                hoverBackgroundColor: "rgba(99, 102, 241, 0.9)",
                borderColor: "rgba(99, 102, 241, 1)",
                borderWidth: 1,
                borderRadius: 6,
              },
            ],
          }}
          options={{
            responsive: true,
            plugins: {
              legend: {
                labels: {
                  color: "#a1a1aa",
                  font: { size: 11 },
                },
              },
              tooltip: {
                backgroundColor: "#18181b",
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
                ticks: { color: "#71717a", font: { size: 10 } },
                grid: { color: "rgba(255, 255, 255, 0.04)" },
              },
            },
          }}
        />
      </div>
    </div>
  );
}
