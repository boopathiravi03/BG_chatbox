import {
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
      {/* Badge with Official Logo */}
      <motion.div
        variants={staggerItem}
        className="inline-flex items-center gap-2.5 bg-white/[0.05] border border-white/[0.12] rounded-full px-4 py-1.5 mb-5 backdrop-blur-sm shadow-md"
      >
        <div className="w-5 h-5 flex items-center justify-center rounded-md bg-indigo-500/20 p-0.5 shrink-0">
          <img
            src="/bg-logo.png"
            alt="BG AI Logo"
            className="w-full h-full object-contain filter drop-shadow-[0_1px_4px_rgba(99,102,241,0.6)]"
          />
        </div>
        <span className="text-xs sm:text-sm font-semibold text-zinc-200 tracking-wide">
          Conversational Database Intelligence & Visualization
        </span>
      </motion.div>

      {/* Main Heading with React Bits BlurText */}
      <motion.div variants={staggerItem} className="flex justify-center">
        <BlurText
          text="Intelligent Database Interaction. Simplified."
          className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight text-white leading-[1.12] justify-center"
          delay={35}
        />
      </motion.div>

      {/* Body Description (16px–20px) */}
      <motion.p
        variants={staggerItem}
        className="mt-4 text-base sm:text-xl text-zinc-200 max-w-2xl mx-auto leading-relaxed font-normal"
      >
        Explore, query, analyze, and visualize your data using natural language.
      </motion.p>

      {/* Connection State / CTA */}
      <motion.div variants={staggerItem} className="mt-5">
        {dbConnected && dbLabel ? (
          <button
            onClick={onOpenDetails || onConnect}
            className="inline-flex items-center gap-2 rounded-full border border-teal-500/35 bg-teal-500/15 hover:bg-teal-500/25 px-4 py-2 text-sm text-teal-200 font-semibold shadow-md transition-colors cursor-pointer"
            title="View Connected Database Details & Schema"
          >
            <span className="h-2.5 w-2.5 rounded-full bg-teal-400 animate-pulse" />
            <span>Connected to {dbLabel}</span>
          </button>
        ) : (
          <ClickSpark sparkColor="#818cf8" sparkCount={6} sparkRadius={22}>
            <button
              onClick={onConnect}
              className="inline-flex items-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-600/25 hover:bg-indigo-600/40 px-5 py-2.5 text-sm font-bold text-indigo-100 hover:text-white transition-all shadow-lg shadow-indigo-950/50 cursor-pointer"
              title="Open Database Connection Options"
            >
              <Plug size={16} className="text-indigo-400" />
              <span>Connect the Database</span>
              <ArrowRight size={15} className="text-indigo-400" />
            </button>
          </ClickSpark>
        )}
      </motion.div>

      {/* Centered Large Chat Composer */}
      {composer && (
        <motion.div
          variants={staggerItem}
          className="mt-8 mb-7 w-full text-left"
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
            spotlightColor="rgba(99, 102, 241, 0.16)"
            className="rounded-xl border border-white/[0.08] bg-[#121215] hover:border-white/20 transition-all shadow-sm"
          >
            <button
              onClick={() => onSend?.(action.prompt)}
              className="group flex items-start gap-3.5 p-4 w-full h-full text-left cursor-pointer"
            >
              <div className="p-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-zinc-300 group-hover:text-indigo-400 group-hover:bg-indigo-500/10 transition-colors shrink-0">
                <action.icon size={17} />
              </div>
              <div className="min-w-0">
                <p className="text-base font-bold text-white group-hover:text-indigo-300 transition-colors">
                  {action.label}
                </p>
                <p className="text-xs sm:text-sm text-zinc-300 mt-1 leading-normal truncate">
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
