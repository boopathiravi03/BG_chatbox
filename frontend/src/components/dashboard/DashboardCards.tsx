import { useEffect, useState } from "react";
import { Users, Package, ShoppingCart, TrendingUp } from "lucide-react";

interface DashboardData {
  customers: number;
  products: number;
  orders: number;
  revenue: number;
}

const cards = [
  {
    key: "customers",
    label: "Customers",
    icon: Users,
    color: "from-blue-500 to-blue-600",
    border: "border-blue-500/20",
    textColor: "text-blue-400",
    prefix: "",
  },
  {
    key: "products",
    label: "Products",
    icon: Package,
    color: "from-emerald-500 to-emerald-600",
    border: "border-emerald-500/20",
    textColor: "text-emerald-400",
    prefix: "",
  },
  {
    key: "orders",
    label: "Orders",
    icon: ShoppingCart,
    color: "from-amber-500 to-amber-600",
    border: "border-amber-500/20",
    textColor: "text-amber-400",
    prefix: "",
  },
  {
    key: "revenue",
    label: "Revenue",
    icon: TrendingUp,
    color: "from-purple-500 to-purple-600",
    border: "border-purple-500/20",
    textColor: "text-purple-400",
    prefix: "₹",
  },
] as const;

interface Props {
  uploadVersion?: number;
}

export default function DashboardCards({ uploadVersion = 0 }: Props) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const response = await fetch("http://127.0.0.1:8001/dashboard");
        const json = await response.json();
        setData(json);
      } catch (error) {
        console.error("Failed to fetch dashboard:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [uploadVersion]);

  if (loading) {
    return (
      <div className="dark:bg-[#0f0f0f] bg-white border border-white/10 rounded-2xl p-6">
        <div className="flex items-center justify-center py-12">
          <div className="dark:text-gray-400 text-gray-700 text-sm">Loading dashboard...</div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const hasRealData =
    (data.customers || 0) > 0 ||
    (data.products || 0) > 0 ||
    (data.orders || 0) > 0 ||
    (data.revenue || 0) > 0;

  if (!hasRealData) return null;

  return (
    <div className="dark:bg-[#0f0f0f] bg-white border border-white/10 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold dark:text-white text-black flex items-center gap-2">
          📊 Database Dashboard
        </h2>
        <span className="text-xs text-green-400 bg-green-500/10 px-3 py-1 rounded-full border border-green-500/20">
          Connected Successfully
        </span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card) => {
          const Icon = card.icon;
          const value = data[card.key as keyof DashboardData];

          return (
            <div
              key={card.key}
              className={`bg-gradient-to-br ${card.color} rounded-xl p-5 border ${card.border} shadow-lg`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-white/80 text-sm font-medium">
                  {card.label}
                </span>
                <Icon size={20} className="text-white/80" />
              </div>
              <div className={`text-3xl font-bold text-white`}>
                {card.prefix || ""}
                {typeof value === "number" && card.key === "revenue"
                  ? value.toLocaleString("en-IN")
                  : (value ?? 0).toLocaleString()}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
