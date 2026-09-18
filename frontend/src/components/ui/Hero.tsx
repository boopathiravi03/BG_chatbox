import {
  Database,
  BarChart3,
  LineChart,
  GitBranch,
  Search,
  Plug,
  ArrowRight,
} from "lucide-react";
import { motion } from "framer-motion";
import { staggerContainer, staggerItem } from "../../lib/motion";
import BlurText from "../reactbits/BlurText";
import SpotlightCard from "../reactbits/SpotlightCard";
import ClickSpark from "../reactbits/ClickSpark";

interface HeroProps {
  onSend?: (message: string) => void;
  dbConnected?: boolean;
  dbType?: string | null;
  onConnect?: () => void;
  onOpenDetails?: () => void;
  composer?: React.ReactNode;
}

const quickActions = [
  {
    icon: Search,
    label: "Show all customers",
    prompt: "Show all customers",
    desc: "Retrieve and view customer records",
  },
  {
    icon: BarChart3,
    label: "Analyze my database",
    prompt: "Analyze my database",
    desc: "Overview metrics & summary statistics",
  },
  {
    icon: LineChart,
    label: "Show monthly sales",
    prompt: "Show monthly sales",
    desc: "Generate an interactive revenue chart",
  },
  {
    icon: GitBranch,
    label: "Explain relationships",
    prompt: "Explain the database relationships",
    desc: "Schema map, keys & table connections",
  },
];

export default function Hero({
  onSend,
  dbConnected,
  dbType,
  onConnect,
  onOpenDetails,
  composer,
}: HeroProps) {
  const dbLabel =
    dbType === "mysql"
      ? "MySQL"
      : dbType === "postgres"
        ? "PostgreSQL"
        : dbType === "sqlite"
          ? "SQLite"
          : null;

  return (
    <motion.div
      className="text-center w-full max-w-3xl mx-auto px-4 py-2 sm:py-4"
      variants={staggerContainer}
      initial="hidden"
      animate="show"
    >
      {/* Badge */}
      <motion.div
        variants={staggerItem}
        className="inline-flex items-center gap-2.5 bg-white/[0.04] border border-white/[0.1] rounded-full px-4 py-1.5 mb-5 backdrop-blur-sm shadow-sm"
      >
        <Database size={15} className="text-indigo-400" />
        <span className="text-xs sm:text-sm font-medium text-zinc-200">
          Intelligent Database Intelligence & Visualization
        </span>
      </motion.div>

      {/* Main Heading with React Bits BlurText */}
      <motion.div variants={staggerItem} className="flex justify-center">
        <BlurText
          text="Intelligent Database Interaction. Simplified."
          className="text-3xl sm:text-5xl font-bold tracking-tight text-white leading-[1.15] justify-center"
          delay={40}
        />
      </motion.div>

      {/* Body Description (15px–17px) */}
      <motion.p
        variants={staggerItem}
        className="mt-3.5 text-base sm:text-lg text-zinc-300 max-w-xl mx-auto leading-relaxed"
      >
        Explore, query, analyze, and visualize your data using natural language.
      </motion.p>

      {/* Connection State / CTA */}
      <motion.div variants={staggerItem} className="mt-4">
        {dbConnected && dbLabel ? (
          <button
            onClick={onOpenDetails || onConnect}
            className="inline-flex items-center gap-2 rounded-full border border-teal-500/30 bg-teal-500/10 hover:bg-teal-500/15 px-3.5 py-1.5 text-xs sm:text-sm text-teal-300 font-semibold shadow-sm transition-colors cursor-pointer"
            title="View Connected Database Details & Schema"
          >
            <span className="h-2 w-2 rounded-full bg-teal-400 animate-pulse" />
            <span>Connected to {dbLabel}</span>
          </button>
        ) : (
          <ClickSpark sparkColor="#818cf8" sparkCount={6} sparkRadius={22}>
            <button
              onClick={onConnect}
              className="inline-flex items-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-600/20 hover:bg-indigo-600/30 px-4 py-2 text-xs sm:text-sm font-semibold text-indigo-200 hover:text-white transition-all shadow-md shadow-indigo-950/40 cursor-pointer"
              title="Open Database Connection Options"
            >
              <Plug size={15} className="text-indigo-400" />
              <span>Connect the Database</span>
              <ArrowRight size={14} className="text-indigo-400" />
            </button>
          </ClickSpark>
        )}
      </motion.div>

      {/* Centered Large Chat Composer */}
      {composer && (
        <motion.div
          variants={staggerItem}
          className="mt-7 mb-6 w-full text-left"
        >
          {composer}
        </motion.div>
      )}

      {/* Quick Action Suggestion Cards with React Bits SpotlightCard */}
      <motion.div
        variants={staggerItem}
        className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-3xl mx-auto text-left"
      >
        {quickActions.map((action) => (
          <SpotlightCard
            key={action.prompt}
            spotlightColor="rgba(99, 102, 241, 0.14)"
            className="rounded-xl border border-white/[0.08] bg-[#121215] hover:border-white/20 transition-all shadow-sm"
          >
            <button
              onClick={() => onSend?.(action.prompt)}
              className="group flex items-start gap-3.5 p-3.5 sm:p-4 w-full h-full text-left cursor-pointer"
            >
              <div className="p-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-zinc-300 group-hover:text-indigo-400 group-hover:bg-indigo-500/10 transition-colors shrink-0">
                <action.icon size={16} />
              </div>
              <div className="min-w-0">
                <p className="text-[15px] font-semibold text-zinc-200 group-hover:text-white transition-colors">
                  {action.label}
                </p>
                <p className="text-xs sm:text-sm text-zinc-400 mt-0.5 leading-normal truncate">
                  {action.desc}
                </p>
              </div>
            </button>
          </SpotlightCard>
        ))}
      </motion.div>
    </motion.div>
  );
}
