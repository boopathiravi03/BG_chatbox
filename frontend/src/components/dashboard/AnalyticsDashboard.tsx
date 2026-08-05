import { useEffect, useState } from "react";
import { Bar, Line, Pie } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

interface AnalyticsData {
  cards: {
    customers: number;
    orders: number;
    products: number;
    revenue: number;
  };
  bar: {
    labels: string[];
    values: number[];
  };
  line: {
    labels: string[];
    values: number[];
  };
  pie: {
    labels: string[];
    values: number[];
  };
}

interface Props {
  data?: AnalyticsData | null;
}

const cardColors = [
  "from-blue-500 to-blue-600",
  "from-emerald-500 to-emerald-600",
  "from-amber-500 to-amber-600",
  "from-purple-500 to-purple-600",
];

export default function AnalyticsDashboard({ data }: Props) {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(data || null);
  const [loading, setLoading] = useState(!data);

  useEffect(() => {
    if (data) {
      setAnalytics(data);
      setLoading(false);
      return;
    }

    const fetchAnalytics = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8001/analytics");
        const json = await response.json();
        setAnalytics(json);
      } catch (error) {
        console.error("Failed to fetch analytics:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [data]);

  if (loading) {
    return (
      <div className="dark:bg-[#0f0f0f] bg-white border border-white/10 rounded-2xl p-6">
        <div className="flex items-center justify-center py-12">
          <div className="dark:text-gray-400 text-gray-700 text-sm">Loading analytics...</div>
        </div>
      </div>
    );
  }

  if (!analytics) return null;

  const barData = {
    labels: analytics.bar.labels,
    datasets: [
      {
        label: "Sales",
        data: analytics.bar.values,
        backgroundColor: "#3B82F6",
        borderRadius: 8,
      },
    ],
  };

  const lineData = {
    labels: analytics.line.labels,
    datasets: [
      {
        label: "Trend",
        data: analytics.line.values,
        borderColor: "#60A5FA",
        backgroundColor: "#3B82F6",
        tension: 0.4,
      },
    ],
  };

  const pieData = {
    labels: analytics.pie.labels,
    datasets: [
      {
        label: "Distribution",
        data: analytics.pie.values,
        backgroundColor: ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"],
        borderWidth: 1,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: "#ffffff",
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
        ticks: {
          color: "#ffffff",
        },
        grid: {
          color: "rgba(255,255,255,0.15)",
        },
      },
    },
  };

  const pieOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: "#ffffff",
        },
      },
    },
  };

  const cards = [
    { label: "Customers", value: analytics.cards.customers },
    { label: "Orders", value: analytics.cards.orders },
    { label: "Revenue", value: `₹${(analytics.cards.revenue / 1000).toFixed(1)}K` },
    { label: "Products", value: analytics.cards.products },
  ];

  return (
    <div className="dark:bg-[#0f0f0f] bg-white border border-white/10 rounded-2xl p-6">
      <h2 className="text-xl font-semibold dark:text-white text-black mb-6">
        📈 BG AI Analytics Dashboard
      </h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((card, index) => (
          <div
            key={card.label}
            className={`bg-gradient-to-br ${cardColors[index]} rounded-xl p-5 shadow-lg`}
          >
            <div className="text-white/80 text-sm font-medium mb-2">
              {card.label}
            </div>
            <div className="text-3xl font-bold text-white">
              {card.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="dark:bg-[#111] bg-gray-100 p-4 rounded-xl">
          <h3 className="dark:text-white text-black font-semibold mb-3">Bar Chart</h3>
          <div className="h-[300px]">
            <Bar data={barData} options={chartOptions} />
          </div>
        </div>

        <div className="dark:bg-[#111] bg-gray-100 p-4 rounded-xl">
          <h3 className="dark:text-white text-black font-semibold mb-3">Pie Chart</h3>
          <div className="h-[300px]">
            <Pie data={pieData} options={pieOptions} />
          </div>
        </div>
      </div>

      <div className="dark:bg-[#111] bg-gray-100 p-4 rounded-xl">
        <h3 className="dark:text-white text-black font-semibold mb-3">Line Chart</h3>
        <div className="h-[300px]">
          <Line data={lineData} options={chartOptions} />
        </div>
      </div>
    </div>
  );
}
