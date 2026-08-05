import {
  Bar
} from "react-chartjs-2";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend
);

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
    <div className="rounded-xl border border-zinc-700 bg-zinc-900">
      <div className="px-4 py-2 border-b border-zinc-700">
        <h3 className="text-sm font-semibold text-blue-400">
          {chart.title}
        </h3>
      </div>

      <div className="p-5">
        <Bar
          data={{
            labels: chart.labels,
            datasets: [
              {
                label: chart.title,
                data: chart.values
              }
            ]
          }}
        />
      </div>
    </div>
  );
}
