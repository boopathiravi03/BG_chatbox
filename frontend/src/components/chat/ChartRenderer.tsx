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

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
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

  if (!chart) {
    return <div>No chart received.</div>;
  }

  const downloadChart = () => {
    if (!chartRef.current) return;

    const url = chartRef.current.toBase64Image();

    const link = document.createElement("a");
    link.download = `${chart.title}.png`;
    link.href = url;
    link.click();
  };

  const data = {
    labels: chart.labels,
    datasets: [
      {
        label: chart.title,
        data: chart.values,

        backgroundColor: [
          "#3B82F6",
          "#10B981",
          "#F59E0B",
          "#EF4444",
          "#8B5CF6",
          "#06B6D4",
        ],

        borderColor: "#60A5FA",
        borderWidth: 2,
        borderRadius: 8,

        hoverBackgroundColor: "#2563EB",
        hoverBorderColor: "#93C5FD",
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
          color: "#ffffff",
        },
      },

      title: {
        display: true,
        text: chart.title,
        color: "#ffffff",
        font: {
          size: 18,
        },
      },
    },

    scales: {
      x: {
        ticks: {
          color: "#ffffff",
        },
        grid: {
          color: "rgba(255,255,255,0.15)",
        },
      },

      y: {
        beginAtZero: true,
        ticks: {
          color: "#ffffff",
        },
        grid: {
          color: "rgba(255,255,255,0.15)",
        },
      },
    },
  };

  return (
    <div className="mt-6 dark:bg-[#111] bg-white p-4 rounded-xl">
      <h3 className="text-lg font-semibold mb-3 dark:text-white text-gray-900">
        {chart.title}
      </h3>

      <div className="h-[350px]">
        <ChartComponent
          ref={chartRef}
          data={data}
          options={options}
        />
      </div>

      <button
        onClick={downloadChart}
        className="mt-3 px-4 py-2 bg-blue-600 rounded-lg hover:bg-blue-700 text-white text-sm"
      >
        Download PNG
      </button>
    </div>
  );
}
