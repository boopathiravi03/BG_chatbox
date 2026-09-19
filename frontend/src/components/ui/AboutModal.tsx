import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Sparkles,
  Database,
  BrainCircuit,
  BarChart3,
  GitBranch,
  MessageSquare,
  ShieldCheck,
  Code2,
  Users,
  Search,
  BookOpen,
  ArrowRight,
  ArrowLeft,
  Server,
  CheckCircle2,
  Layers,
  Table,
  PlusCircle,
  Edit3,
  Trash2,
  HelpCircle,
} from "lucide-react";
import { smoothTransition } from "../../lib/motion";
import BlurText from "../reactbits/BlurText";
import SpotlightCard from "../reactbits/SpotlightCard";
import ScrollReveal from "../reactbits/ScrollReveal";
import ClickSpark from "../reactbits/ClickSpark";
import WorkflowFlowchart from "./WorkflowFlowchart";

interface AboutModalProps {
  onClose: () => void;
  isEmbedded?: boolean;
}

type TabType = "overview" | "guide" | "features" | "workflow" | "team";

const tabs: { id: TabType; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "guide", label: "User Guide" },
  { id: "features", label: "Features" },
  { id: "workflow", label: "Workflow" },
  { id: "team", label: "Meet the Team" },
];

export default function AboutModal({
  onClose,
  isEmbedded = false,
}: AboutModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("overview");

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Lock background scroll when open in modal mode
  useEffect(() => {
    if (isEmbedded) return;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isEmbedded]);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        className={
          isEmbedded
            ? "relative w-full h-full bg-[#09090b] text-zinc-100 flex flex-col overflow-y-auto select-text"
            : "fixed inset-0 z-50 bg-[#09090b] text-zinc-100 flex flex-col w-screen h-screen overflow-hidden select-text"
        }
      >
        {/* Full-Screen Header */}
        <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#0e0e12]/95 backdrop-blur-xl px-6 sm:px-10 md:px-12 lg:px-14 xl:px-16 py-4 flex items-center justify-between shrink-0 shadow-lg shadow-black/40">
          {/* Left: Branding & Back Button */}
          <div className="flex items-center gap-3 sm:gap-5">
            <ClickSpark sparkColor="#818cf8" sparkCount={6} sparkRadius={16}>
              <button
                onClick={onClose}
                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 hover:text-white text-sm font-medium transition-all group shadow-sm cursor-pointer"
                title="Return to Chat (Esc)"
              >
                <ArrowLeft
                  size={16}
                  className="group-hover:-translate-x-0.5 transition-transform"
                />
                <span className="hidden sm:inline">Back to Chat</span>
              </button>
            </ClickSpark>

            <div className="h-5 w-[1px] bg-white/[0.08] hidden sm:block" />

            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl overflow-hidden border border-white/15 bg-white/[0.06] p-1 shadow-md shrink-0">
                <img
                  src="/bg-logo.png"
                  alt="BG AI Logo"
                  className="w-full h-full object-contain rounded-lg"
                />
              </div>
              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight">
                    About BG <span className="text-indigo-400">AI</span>
                  </h1>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 font-mono font-bold">
                    v1.0.0
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-zinc-300 hidden md:block font-medium">
                  AI-Powered Conversational Database Intelligence &
                  Visualization
                </p>
              </div>
            </div>
          </div>

          {/* Center / Navigation Tabs (Desktop) */}
          <div className="hidden lg:flex items-center gap-1.5 bg-white/[0.03] p-1.5 rounded-xl border border-white/[0.06]">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                  activeTab === tab.id
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Right: Close button */}
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={onClose}
              className="p-2 sm:px-3 sm:py-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/[0.06] text-sm font-medium transition-colors flex items-center gap-1.5 cursor-pointer"
              title="Close (Esc)"
              aria-label="Close"
            >
              <X size={18} />
              <span className="hidden sm:inline text-xs text-zinc-500 font-mono">
                ESC
              </span>
            </button>
          </div>
        </header>

        {/* Mobile Sub-Navigation Bar */}
        <div className="lg:hidden flex items-center gap-1.5 px-4 sm:px-6 py-2.5 border-b border-white/[0.06] bg-[#0e0e12]/80 backdrop-blur-md overflow-x-auto scrollbar-none shrink-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap transition-all ${
                activeTab === tab.id
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Full-Screen Scrollable Content Canvas — Complete Available Width */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="w-full px-6 sm:px-10 md:px-12 lg:px-14 xl:px-16 py-8 sm:py-12 space-y-14 sm:space-y-16">
            {/* TAB: OVERVIEW */}
            {activeTab === "overview" && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={smoothTransition}
                className="space-y-14"
              >
                {/* Hero Showcase Banner */}
                <div className="relative rounded-3xl bg-gradient-to-br from-indigo-950/40 via-[#131318] to-[#0f0f13] border border-indigo-500/20 p-8 sm:p-12 md:p-16 overflow-hidden shadow-2xl shadow-black/60">
                  <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />
                  <div className="relative z-10 max-w-4xl lg:max-w-5xl space-y-6">
                    <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs sm:text-sm font-semibold">
                      <Sparkles size={14} />
                      Next-Generation Database UX
                    </div>

                    <div>
                      <BlurText
                        text="Intelligent Database Interaction. Simplified."
                        className="text-3xl sm:text-5xl md:text-6xl font-extrabold text-white tracking-tight leading-[1.15]"
                        delay={35}
                      />
                    </div>

                    <p className="text-base sm:text-xl text-zinc-300 leading-relaxed">
                      BG AI is an AI-powered conversational database
                      intelligence and visualization platform that helps users
                      explore, query, analyze, and understand databases using
                      natural language.
                    </p>

                    <div className="pt-2 flex flex-wrap gap-4">
                      <button
                        onClick={() => setActiveTab("guide")}
                        className="inline-flex items-center gap-2.5 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm sm:text-base font-semibold transition-all shadow-lg shadow-indigo-600/30"
                      >
                        <BookOpen size={18} />
                        Explore User Guide
                        <ArrowRight size={16} />
                      </button>

                      <button
                        onClick={() => setActiveTab("team")}
                        className="inline-flex items-center gap-2.5 px-6 py-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-zinc-200 text-sm sm:text-base font-semibold transition-all"
                      >
                        <Users size={18} />
                        Meet the Creators
                      </button>

                      <button
                        onClick={() => setActiveTab("features")}
                        className="inline-flex items-center gap-2.5 px-6 py-3 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-zinc-200 text-sm sm:text-base font-semibold transition-all"
                      >
                        <Layers size={18} />
                        View Capabilities
                      </button>
                    </div>
                  </div>
                </div>

                {/* What is BG AI & Why BG AI Cards with React Bits SpotlightCard & ScrollReveal */}
                <ScrollReveal>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* What is BG AI? */}
                    <SpotlightCard
                      spotlightColor="rgba(99, 102, 241, 0.16)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-8 space-y-4 shadow-xl"
                    >
                      <div className="flex items-center gap-3 text-white font-bold text-xl sm:text-2xl">
                        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                          <BrainCircuit size={22} />
                        </div>
                        <h3>What is BG AI?</h3>
                      </div>
                      <p className="text-base sm:text-[17px] text-zinc-300 leading-relaxed">
                        BG AI bridges the gap between users and databases by
                        allowing people to ask questions in natural language
                        instead of writing complex SQL queries manually.
                      </p>
                      <p className="text-sm sm:text-base text-zinc-400 leading-relaxed">
                        The platform is designed to make database interaction
                        more accessible, understandable, and efficient for
                        students, developers, analysts, business users, and
                        organizations.
                      </p>
                    </SpotlightCard>

                    {/* Why BG AI? */}
                    <SpotlightCard
                      spotlightColor="rgba(16, 185, 129, 0.14)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-8 space-y-4 shadow-xl"
                    >
                      <div className="flex items-center gap-3 text-white font-bold text-xl sm:text-2xl">
                        <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                          <ShieldCheck size={22} />
                        </div>
                        <h3>Why BG AI?</h3>
                      </div>
                      <p className="text-base sm:text-[17px] text-zinc-300 leading-relaxed">
                        BG AI aims to make database interaction more accessible
                        by combining conversational AI, structured data, and
                        visual insights in one platform.
                      </p>
                      <p className="text-sm sm:text-base text-zinc-400 leading-relaxed">
                        Instead of requiring users to navigate complex database
                        tools for every question, BG AI provides a
                        conversational approach to exploring and understanding
                        data.
                      </p>
                    </SpotlightCard>
                  </div>
                </ScrollReveal>

                {/* 3 Pillars Workflow */}
                <div className="space-y-6">
                  <h3 className="text-xl sm:text-2xl font-bold text-white">
                    Conversational Data Lifecycle
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="rounded-2xl bg-[#121216] border border-white/[0.06] p-6 space-y-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-base">
                        1
                      </div>
                      <h4 className="text-lg font-bold text-white">
                        Ask in Plain English
                      </h4>
                      <p className="text-sm sm:text-[15px] text-zinc-400 leading-relaxed">
                        Formulate everyday questions without memorizing table
                        schemas, join keys, or SQL dialect syntax.
                      </p>
                    </div>

                    <div className="rounded-2xl bg-[#121216] border border-white/[0.06] p-6 space-y-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-base">
                        2
                      </div>
                      <h4 className="text-lg font-bold text-white">
                        AI Generates & Verifies SQL
                      </h4>
                      <p className="text-sm sm:text-[15px] text-zinc-400 leading-relaxed">
                        Queries are synthesized against your actual database
                        schema with built-in safeguards for write operations.
                      </p>
                    </div>

                    <div className="rounded-2xl bg-[#121216] border border-white/[0.06] p-6 space-y-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-base">
                        3
                      </div>
                      <h4 className="text-lg font-bold text-white">
                        Visual Insights & Charts
                      </h4>
                      <p className="text-sm sm:text-[15px] text-zinc-400 leading-relaxed">
                        Instantly visualize results through interactive bar/line
                        charts, relationship maps, and exportable PDF summaries.
                      </p>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* TAB: USER GUIDE */}
            {/* TAB: USER GUIDE — PICTORIAL & BEGINNER-FRIENDLY */}
            {activeTab === "guide" && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={smoothTransition}
                className="space-y-16"
              >
                {/* SECTION A: What is BG AI? (Beginner Explanation) */}
                <div className="relative rounded-3xl bg-gradient-to-br from-indigo-950/40 via-[#131318] to-[#0f0f13] border border-indigo-500/20 p-8 sm:p-10 md:p-12 overflow-hidden shadow-2xl">
                  <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
                  <div className="relative z-10 space-y-4 max-w-4xl">
                    <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-xs sm:text-sm font-semibold">
                      <HelpCircle size={15} />
                      Beginner-Friendly Primer
                    </div>
                    <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
                      A. What is BG AI?
                    </h2>
                    <p className="text-base sm:text-lg text-zinc-300 leading-relaxed">
                      Databases usually require learning complex SQL code (
                      <code className="text-indigo-300 font-mono text-xs sm:text-sm bg-white/[0.06] px-1.5 py-0.5 rounded">
                        SELECT ... JOIN ... GROUP BY
                      </code>
                      ) to view, filter, or summarize records.
                    </p>
                    <p className="text-base sm:text-lg text-zinc-300 leading-relaxed">
                      <strong className="text-white">
                        BG AI bridges this gap
                      </strong>
                      : it allows anyone — whether you are a business owner,
                      student, manager, or seasoned developer — to converse with
                      any database using{" "}
                      <strong className="text-indigo-300">
                        everyday English
                      </strong>
                      . BG AI reads your database schema, automatically writes
                      and tests the required SQL behind the scenes, and responds
                      with plain-language explanations, interactive tables,
                      charts, and diagrams.
                    </p>
                    <div className="pt-2 flex flex-wrap gap-3 text-xs sm:text-sm font-medium">
                      <span className="px-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-zinc-300 flex items-center gap-2">
                        <CheckCircle2 size={15} className="text-emerald-400" />
                        No SQL expertise required
                      </span>
                      <span className="px-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-zinc-300 flex items-center gap-2">
                        <CheckCircle2 size={15} className="text-emerald-400" />
                        Live schema-aware AI
                      </span>
                      <span className="px-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-zinc-300 flex items-center gap-2">
                        <CheckCircle2 size={15} className="text-emerald-400" />
                        Rigorous safety safeguards
                      </span>
                    </div>
                  </div>
                </div>

                {/* SECTION B: Step-by-Step Pictorial Walkthrough */}
                <div className="space-y-6">
                  <div>
                    <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                      B. How to Use BG AI — Step-by-Step
                    </h3>
                    <p className="text-base sm:text-lg text-zinc-400 mt-1">
                      From connecting your first database to running queries and
                      viewing diagrams in 6 easy steps.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {/* Step 1 */}
                    <SpotlightCard
                      spotlightColor="rgba(99, 102, 241, 0.16)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-6 sm:p-7 space-y-4 shadow-xl flex flex-col justify-between"
                    >
                      <div className="space-y-3.5">
                        <div className="flex items-center justify-between">
                          <div className="w-11 h-11 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-extrabold text-lg">
                            1
                          </div>
                          <span className="text-[11px] font-mono uppercase px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                            Connection
                          </span>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <Database
                            size={18}
                            className="text-indigo-400 shrink-0"
                          />
                          <h4 className="text-lg font-bold text-white">
                            Connect Your Database
                          </h4>
                        </div>
                        <p className="text-sm sm:text-base text-zinc-300 leading-relaxed">
                          Click{" "}
                          <strong className="text-white">
                            Connect the Database
                          </strong>{" "}
                          in the sidebar or chat. Upload a SQLite (
                          <code className="text-indigo-300 font-mono text-xs">
                            .db
                          </code>
                          ) file, or enter your MySQL / PostgreSQL host
                          credentials.
                        </p>
                      </div>
                      <div className="pt-3 border-t border-white/[0.06]">
                        <span className="text-xs text-indigo-300/90 font-mono">
                          Supports: SQLite, MySQL, PostgreSQL
                        </span>
                      </div>
                    </SpotlightCard>

                    {/* Step 2 */}
                    <SpotlightCard
                      spotlightColor="rgba(99, 102, 241, 0.16)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-6 sm:p-7 space-y-4 shadow-xl flex flex-col justify-between"
                    >
                      <div className="space-y-3.5">
                        <div className="flex items-center justify-between">
                          <div className="w-11 h-11 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-extrabold text-lg">
                            2
                          </div>
                          <span className="text-[11px] font-mono uppercase px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                            Inspection
                          </span>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <Search
                            size={18}
                            className="text-indigo-400 shrink-0"
                          />
                          <h4 className="text-lg font-bold text-white">
                            Schema Auto-Inspection
                          </h4>
                        </div>
                        <p className="text-sm sm:text-base text-zinc-300 leading-relaxed">
                          BG AI automatically inspects all tables, columns,
                          constraints, foreign keys, and indexes without
                          modifying any data.
                        </p>
                      </div>
                      <div className="pt-3 border-t border-white/[0.06]">
                        <span className="text-xs text-teal-400 font-mono">
                          Instant context indexing
                        </span>
                      </div>
                    </SpotlightCard>

                    {/* Step 3 */}
                    <SpotlightCard
                      spotlightColor="rgba(99, 102, 241, 0.16)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-6 sm:p-7 space-y-4 shadow-xl flex flex-col justify-between"
                    >
                      <div className="space-y-3.5">
                        <div className="flex items-center justify-between">
                          <div className="w-11 h-11 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-extrabold text-lg">
                            3
                          </div>
                          <span className="text-[11px] font-mono uppercase px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                            Query
                          </span>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <MessageSquare
                            size={18}
                            className="text-indigo-400 shrink-0"
                          />
                          <h4 className="text-lg font-bold text-white">
                            Ask in Plain English
                          </h4>
                        </div>
                        <p className="text-sm sm:text-base text-zinc-300 leading-relaxed">
                          Type any question in natural language:{" "}
                          <em className="text-zinc-200">
                            "Show top 5 customers by revenue"
                          </em>{" "}
                          or{" "}
                          <em className="text-zinc-200">
                            "Count total orders by status"
                          </em>
                          .
                        </p>
                      </div>
                      <div className="pt-3 border-t border-white/[0.06]">
                        <span className="text-xs text-indigo-300 font-mono">
                          Example: "Show all customers"
                        </span>
                      </div>
                    </SpotlightCard>

                    {/* Step 4 */}
                    <SpotlightCard
                      spotlightColor="rgba(99, 102, 241, 0.16)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-6 sm:p-7 space-y-4 shadow-xl flex flex-col justify-between"
                    >
                      <div className="space-y-3.5">
                        <div className="flex items-center justify-between">
                          <div className="w-11 h-11 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-extrabold text-lg">
                            4
                          </div>
                          <span className="text-[11px] font-mono uppercase px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                            Visualization
                          </span>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <BarChart3
                            size={18}
                            className="text-indigo-400 shrink-0"
                          />
                          <h4 className="text-lg font-bold text-white">
                            View Results & Charts
                          </h4>
                        </div>
                        <p className="text-sm sm:text-base text-zinc-300 leading-relaxed">
                          Receive formatted tables, interactive bar/line/pie
                          charts, execution profiles, and generated SQL blocks
                          with one-click export to PDF or CSV.
                        </p>
                      </div>
                      <div className="pt-3 border-t border-white/[0.06]">
                        <span className="text-xs text-emerald-400 font-mono">
                          Interactive charts & tables
                        </span>
                      </div>
                    </SpotlightCard>

                    {/* Step 5 */}
                    <SpotlightCard
                      spotlightColor="rgba(245, 158, 11, 0.16)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-6 sm:p-7 space-y-4 shadow-xl flex flex-col justify-between"
                    >
                      <div className="space-y-3.5">
                        <div className="flex items-center justify-between">
                          <div className="w-11 h-11 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 font-extrabold text-lg">
                            5
                          </div>
                          <span className="text-[11px] font-mono uppercase px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-300">
                            Safeguards
                          </span>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <ShieldCheck
                            size={18}
                            className="text-amber-400 shrink-0"
                          />
                          <h4 className="text-lg font-bold text-white">
                            Safe CRUD Confirmation
                          </h4>
                        </div>
                        <p className="text-sm sm:text-base text-zinc-300 leading-relaxed">
                          For write queries (
                          <code className="text-amber-300 font-mono text-xs">
                            INSERT
                          </code>
                          ,{" "}
                          <code className="text-amber-300 font-mono text-xs">
                            UPDATE
                          </code>
                          ,{" "}
                          <code className="text-amber-300 font-mono text-xs">
                            DELETE
                          </code>
                          ), BG AI previews affected rows and requires explicit
                          human confirmation before altering data.
                        </p>
                      </div>
                      <div className="pt-3 border-t border-white/[0.06]">
                        <span className="text-xs text-amber-400 font-mono">
                          Zero accidental database writes
                        </span>
                      </div>
                    </SpotlightCard>

                    {/* Step 6 */}
                    <SpotlightCard
                      spotlightColor="rgba(16, 185, 129, 0.16)"
                      className="rounded-2xl bg-[#121216] border border-white/[0.08] p-6 sm:p-7 space-y-4 shadow-xl flex flex-col justify-between"
                    >
                      <div className="space-y-3.5">
                        <div className="flex items-center justify-between">
                          <div className="w-11 h-11 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-extrabold text-lg">
                            6
                          </div>
                          <span className="text-[11px] font-mono uppercase px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
                            Management
                          </span>
                        </div>
                        <div className="flex items-center gap-2.5">
                          <Server
                            size={18}
                            className="text-emerald-400 shrink-0"
                          />
                          <h4 className="text-lg font-bold text-white">
                            Disconnect & Switch DBs
                          </h4>
                        </div>
                        <p className="text-sm sm:text-base text-zinc-300 leading-relaxed">
                          When finished or switching projects, safely disconnect
                          via the database status indicator or sidebar to switch
                          cleanly to another SQLite, MySQL, or PostgreSQL
                          source.
                        </p>
                      </div>
                      <div className="pt-3 border-t border-white/[0.06]">
                        <span className="text-xs text-emerald-400 font-mono">
                          Safe sessions & easy switching
                        </span>
                      </div>
                    </SpotlightCard>
                  </div>
                </div>

                {/* SECTION C: Supported Database Connection Guide Table */}
                <div className="space-y-4">
                  <div>
                    <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
                      <Table size={24} className="text-indigo-400" />
                      <span>C. Supported Database Connection Guide</span>
                    </h3>
                    <p className="text-base sm:text-lg text-zinc-400 mt-1">
                      Clear instructions for each supported database engine in
                      BG AI.
                    </p>
                  </div>

                  <div className="rounded-2xl border border-white/[0.08] bg-[#121216] overflow-hidden shadow-xl">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-white/[0.08] bg-white/[0.02] text-xs sm:text-sm font-semibold uppercase tracking-wider text-zinc-400">
                            <th className="px-6 py-4">Database Engine</th>
                            <th className="px-6 py-4">How to Connect</th>
                            <th className="px-6 py-4">
                              Default Port / File Format
                            </th>
                            <th className="px-6 py-4">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.06] text-sm sm:text-base text-zinc-200">
                          <tr className="hover:bg-white/[0.02] transition-colors">
                            <td className="px-6 py-4 font-bold text-white flex items-center gap-2.5">
                              <Database
                                size={16}
                                className="text-indigo-400 shrink-0"
                              />
                              <span>SQLite</span>
                            </td>
                            <td className="px-6 py-4 text-zinc-300">
                              Upload or select a local database file using the
                              file picker or drag-and-drop dropzone.
                            </td>
                            <td className="px-6 py-4 font-mono text-xs sm:text-sm text-indigo-300">
                              .db / .sqlite
                            </td>
                            <td className="px-6 py-4">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 text-xs font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                                Ready
                              </span>
                            </td>
                          </tr>

                          <tr className="hover:bg-white/[0.02] transition-colors">
                            <td className="px-6 py-4 font-bold text-white flex items-center gap-2.5">
                              <Server
                                size={16}
                                className="text-teal-400 shrink-0"
                              />
                              <span>MySQL</span>
                            </td>
                            <td className="px-6 py-4 text-zinc-300">
                              Enter server Host, Port, Database name, Username,
                              and Password in the Connect Database modal.
                            </td>
                            <td className="px-6 py-4 font-mono text-xs sm:text-sm text-teal-300">
                              Port 3306
                            </td>
                            <td className="px-6 py-4">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 text-xs font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                                Ready
                              </span>
                            </td>
                          </tr>

                          <tr className="hover:bg-white/[0.02] transition-colors">
                            <td className="px-6 py-4 font-bold text-white flex items-center gap-2.5">
                              <Server
                                size={16}
                                className="text-sky-400 shrink-0"
                              />
                              <span>PostgreSQL</span>
                            </td>
                            <td className="px-6 py-4 text-zinc-300">
                              Enter server Host, Port, Database name, Username,
                              and Password in the Connect Database modal.
                            </td>
                            <td className="px-6 py-4 font-mono text-xs sm:text-sm text-sky-300">
                              Port 5432
                            </td>
                            <td className="px-6 py-4">
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 text-xs font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                                Ready
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {/* SECTION D: Example Prompts Grouped by Category */}
                <div className="space-y-6">
                  <div>
                    <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                      D. Example Prompts by Category
                    </h3>
                    <p className="text-base sm:text-lg text-zinc-400 mt-1">
                      Click or copy these natural language examples to start
                      exploring your database right away.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                    {/* Category: Explore Data */}
                    <div className="rounded-2xl bg-[#121216] border border-white/[0.08] p-5 space-y-3 shadow-lg">
                      <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                        <Search size={16} />
                        <span>Explore Data</span>
                      </div>
                      <p className="text-xs text-zinc-400">
                        Retrieve records and view raw table columns without
                        manual SELECT syntax.
                      </p>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] font-mono text-xs text-indigo-200">
                        "Show all customers"
                      </div>
                    </div>

                    {/* Category: Products & Catalog */}
                    <div className="rounded-2xl bg-[#121216] border border-white/[0.08] p-5 space-y-3 shadow-lg">
                      <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                        <Layers size={16} />
                        <span>Products & Catalog</span>
                      </div>
                      <p className="text-xs text-zinc-400">
                        Examine item inventories, stock counts, and categorized
                        collections.
                      </p>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] font-mono text-xs text-indigo-200">
                        "List all products"
                      </div>
                    </div>

                    {/* Category: Analytics & Trends */}
                    <div className="rounded-2xl bg-[#121216] border border-white/[0.08] p-5 space-y-3 shadow-lg">
                      <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                        <BarChart3 size={16} />
                        <span>Analytics & Metrics</span>
                      </div>
                      <p className="text-xs text-zinc-400">
                        Generate bar charts, line trends, and high-level
                        financial breakdowns.
                      </p>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] font-mono text-xs text-indigo-200">
                        "Analyze monthly sales"
                      </div>
                    </div>

                    {/* Category: Relationships & ER */}
                    <div className="rounded-2xl bg-[#121216] border border-white/[0.08] p-5 space-y-3 shadow-lg">
                      <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                        <GitBranch size={16} />
                        <span>Relationships & ER</span>
                      </div>
                      <p className="text-xs text-zinc-400">
                        Produce visual entity graphs and foreign key connection
                        maps.
                      </p>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] font-mono text-xs text-indigo-200">
                        "Explain the database relationships"
                      </div>
                    </div>

                    {/* Category: Create Records */}
                    <div className="rounded-2xl bg-[#121216] border border-emerald-500/20 bg-emerald-950/[0.08] p-5 space-y-3 shadow-lg">
                      <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
                        <PlusCircle size={16} />
                        <span>Create (INSERT)</span>
                      </div>
                      <p className="text-xs text-zinc-400">
                        Opens a guided form and previews columns before adding
                        new rows.
                      </p>
                      <div className="p-3 rounded-xl bg-black/40 border border-emerald-500/30 font-mono text-xs text-emerald-200">
                        "Add a new customer"
                      </div>
                    </div>

                    {/* Category: Update Records */}
                    <div className="rounded-2xl bg-[#121216] border border-amber-500/20 bg-amber-950/[0.08] p-5 space-y-3 shadow-lg">
                      <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                        <Edit3 size={16} />
                        <span>Update (MODIFY)</span>
                      </div>
                      <p className="text-xs text-zinc-400">
                        Previews modified values and requests verification prior
                        to execution.
                      </p>
                      <div className="p-3 rounded-xl bg-black/40 border border-amber-500/30 font-mono text-xs text-amber-200">
                        "Update a customer's email"
                      </div>
                    </div>

                    {/* Category: Delete Records */}
                    <div className="rounded-2xl bg-[#121216] border border-rose-500/20 bg-rose-950/[0.08] p-5 space-y-3 shadow-lg md:col-span-2">
                      <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm">
                        <Trash2 size={16} />
                        <span>Delete (REMOVE) — Safeguard Protected</span>
                      </div>
                      <p className="text-xs text-zinc-400">
                        Calculates matching records and displays a critical
                        warning alert requiring manual user approval before
                        deletion.
                      </p>
                      <div className="p-3 rounded-xl bg-black/40 border border-rose-500/30 font-mono text-xs text-rose-200">
                        "Delete a record"
                      </div>
                    </div>
                  </div>

                  {/* Safeguard Alert Box */}
                  <div className="rounded-2xl border border-amber-500/30 bg-amber-500/[0.05] p-5 flex items-start gap-4">
                    <ShieldCheck
                      size={22}
                      className="text-amber-400 shrink-0 mt-0.5"
                    />
                    <div className="space-y-1">
                      <h4 className="text-sm sm:text-base font-bold text-amber-300">
                        Safety Safeguard Notice
                      </h4>
                      <p className="text-xs sm:text-sm text-zinc-300 leading-relaxed">
                        All database modifications (
                        <code className="text-amber-300 font-mono">INSERT</code>
                        ,{" "}
                        <code className="text-amber-300 font-mono">UPDATE</code>
                        ,{" "}
                        <code className="text-amber-300 font-mono">DELETE</code>
                        ) require explicit user confirmation through the
                        existing safety flow. No write query executes
                        automatically without human verification.
                      </p>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* TAB: FEATURES */}
            {activeTab === "features" && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={smoothTransition}
                className="space-y-10"
              >
                <div>
                  <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
                    Platform Capabilities
                  </h2>
                  <p className="text-base sm:text-lg text-zinc-400 mt-2">
                    Eight core features engineered for conversational database
                    intelligence and visualization.
                  </p>
                </div>

                <ScrollReveal>
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 sm:gap-6">
                    {[
                      {
                        title: "Natural Language Queries",
                        desc: "Ask questions about your database using everyday language without writing manual SQL queries.",
                        icon: (
                          <MessageSquare
                            size={22}
                            className="text-indigo-400"
                          />
                        ),
                      },
                      {
                        title: "AI SQL Generation",
                        desc: "Generate optimized SQL queries tailored accurately to your database schema and tables.",
                        icon: <Code2 size={22} className="text-indigo-400" />,
                      },
                      {
                        title: "Database Analysis",
                        desc: "Explore database structures, tables, columns, constraints, and available metrics effortlessly.",
                        icon: <Search size={22} className="text-indigo-400" />,
                      },
                      {
                        title: "Data Visualization",
                        desc: "Generate charts, dashboards, and visual representations of query results dynamically.",
                        icon: (
                          <BarChart3 size={22} className="text-indigo-400" />
                        ),
                      },
                      {
                        title: "Relationship & ER Diagrams",
                        desc: "Understand complex database relationships through visual schema maps and entity relationship graphs.",
                        icon: (
                          <GitBranch size={22} className="text-indigo-400" />
                        ),
                      },
                      {
                        title: "Conversational AI",
                        desc: "Interact with your database through a responsive, ChatGPT-style conversational assistant.",
                        icon: (
                          <BrainCircuit size={22} className="text-indigo-400" />
                        ),
                      },
                      {
                        title: "Safe CRUD Operations",
                        desc: "Perform insert, update, and delete operations with built-in preview and safety confirmation workflows before any records are changed.",
                        icon: (
                          <ShieldCheck size={22} className="text-amber-400" />
                        ),
                      },
                      {
                        title: "Multi-Database Support",
                        desc: "Native support for SQLite (.db files), MySQL, and PostgreSQL with automatic schema parsing and dialect-specific SQL generation.",
                        icon: (
                          <Database size={22} className="text-emerald-400" />
                        ),
                      },
                      {
                        title: "Database Disconnect & Reconnection",
                        desc: "Easily disconnect active databases, switch between data sources, or attach new databases without losing session continuity.",
                        icon: <Server size={22} className="text-teal-400" />,
                      },
                    ].map((feat, idx) => (
                      <SpotlightCard
                        key={idx}
                        spotlightColor="rgba(99, 102, 241, 0.12)"
                        className="rounded-2xl bg-[#121216] border border-white/[0.08] p-7 hover:border-white/[0.18] transition-all space-y-3 shadow-xl group"
                      >
                        <div className="flex items-center gap-3.5">
                          <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0 group-hover:bg-indigo-500/10 group-hover:border-indigo-500/20 transition-colors">
                            {feat.icon}
                          </div>
                          <h3 className="text-lg sm:text-xl font-bold text-white">
                            {feat.title}
                          </h3>
                        </div>
                        <p className="text-sm sm:text-base text-zinc-300 leading-relaxed pl-15">
                          {feat.desc}
                        </p>
                      </SpotlightCard>
                    ))}
                  </div>
                </ScrollReveal>
              </motion.div>
            )}

            {/* TAB: DATABASE WORKFLOW */}
            {activeTab === "workflow" && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={smoothTransition}
                className="space-y-10"
              >
                <div className="max-w-4xl space-y-3">
                  <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-xs sm:text-sm font-code font-bold text-indigo-300">
                    <BrainCircuit size={16} />
                    <span>Deterministic & LLM Hybrid Architecture</span>
                  </div>
                  <h2 className="font-display text-3xl sm:text-5xl lg:text-6xl font-black text-white tracking-tight">
                    End-to-End Database Workflow
                  </h2>
                  <p className="font-body text-base sm:text-xl text-zinc-300 mt-2 leading-relaxed max-w-3xl">
                    How BG AI safely processes natural language questions into
                    verified queries, introspects tables, and produces
                    visualizations without risking data integrity.
                  </p>
                </div>

                <WorkflowFlowchart />
              </motion.div>
            )}

            {/* TAB: MEET THE CREATORS (Inspired by Uploaded Images) */}
            {activeTab === "team" && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={smoothTransition}
                className="space-y-12"
              >
                <div className="max-w-3xl">
                  <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">
                    Meet the Creators
                  </h2>
                  <p className="text-base sm:text-lg text-zinc-400 mt-2 leading-relaxed">
                    We are a dedicated team who love to design and build
                    products that solve real problems, combining conversational
                    AI and database intelligence to deliver intuitive digital
                    experiences.
                  </p>
                </div>

                {/* Primary Spotlight Cards with React Bits — Full-Width Horizontal Layout */}
                <ScrollReveal>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
                    {/* Founder & CEO Card */}
                    <SpotlightCard
                      spotlightColor="rgba(99, 102, 241, 0.18)"
                      className="rounded-3xl bg-gradient-to-b from-[#181820] to-[#111115] border border-white/[0.12] p-7 sm:p-8 relative overflow-hidden group hover:border-indigo-500/50 transition-all shadow-2xl flex flex-col justify-between"
                    >
                      <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

                      <div className="flex flex-col sm:flex-row items-start gap-6 relative z-10">
                        {/* Portrait Frame */}
                        <div className="relative shrink-0">
                          <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl bg-gradient-to-br from-indigo-500 via-indigo-600 to-zinc-900 p-0.5 shadow-xl">
                            <div className="w-full h-full rounded-[14px] bg-[#0c0c0f] flex items-center justify-center overflow-hidden">
                              <span className="text-3xl sm:text-4xl font-black tracking-tighter text-indigo-200 select-none">
                                BR
                              </span>
                            </div>
                          </div>
                          {/* LinkedIn Badge */}
                          <div
                            className="absolute -bottom-1.5 -right-1.5 w-7 h-7 rounded-lg bg-[#0077b5] text-white flex items-center justify-center shadow-lg text-xs font-bold font-mono cursor-pointer hover:scale-110 transition-transform"
                            title="LinkedIn Profile"
                          >
                            in
                          </div>
                        </div>

                        {/* Text & Roles */}
                        <div className="space-y-2 min-w-0 flex-1">
                          <div className="inline-block px-3 py-1 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 text-xs font-bold uppercase tracking-wider">
                            Founder & Leadership
                          </div>
                          <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                            Boopathi R
                          </h3>
                          <p className="text-base sm:text-lg font-semibold text-indigo-400">
                            CEO of BG
                          </p>
                          <p className="text-sm sm:text-[15px] text-zinc-300 leading-relaxed pt-1">
                            Boopathi R is the founder and CEO of BG, leading the
                            vision and development of BG AI as an intelligent
                            conversational database platform.
                          </p>
                        </div>
                      </div>

                      <div className="mt-6 pt-5 border-t border-white/[0.08] flex items-center justify-between text-sm text-zinc-400 relative z-10">
                        <span className="font-medium text-zinc-300">
                          Executive Leadership
                        </span>
                        <span className="text-indigo-400 font-semibold flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                          Founder & Vision
                        </span>
                      </div>
                    </SpotlightCard>

                    {/* BG Team Card */}
                    <SpotlightCard
                      spotlightColor="rgba(255, 255, 255, 0.1)"
                      className="rounded-3xl bg-gradient-to-b from-[#181820] to-[#111115] border border-white/[0.12] p-7 sm:p-8 relative overflow-hidden group hover:border-white/[0.25] transition-all shadow-2xl flex flex-col justify-between"
                    >
                      <div className="flex flex-col sm:flex-row items-start gap-6 relative z-10">
                        {/* Icon Frame */}
                        <div className="relative shrink-0">
                          <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-zinc-200 shadow-xl">
                            <Users size={44} className="text-indigo-400" />
                          </div>
                          <div
                            className="absolute -bottom-1.5 -right-1.5 w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-lg text-xs font-bold transition-transform"
                            title="BG Team"
                          >
                            <Sparkles size={13} />
                          </div>
                        </div>

                        {/* Text & Roles */}
                        <div className="space-y-2 min-w-0 flex-1">
                          <div className="inline-block px-3 py-1 rounded-full bg-white/[0.06] text-zinc-300 border border-white/[0.08] text-xs font-bold uppercase tracking-wider">
                            Product & Engineering
                          </div>
                          <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                            BG Team
                          </h3>
                          <p className="text-base sm:text-lg font-semibold text-zinc-400">
                            Engineering & AI Innovation
                          </p>
                          <p className="text-sm sm:text-[15px] text-zinc-300 leading-relaxed pt-1">
                            BG AI is developed by Boopathi R and the BG Team,
                            working together to build innovative AI-powered
                            solutions that simplify technology and improve user
                            experiences.
                          </p>
                        </div>
                      </div>

                      <div className="mt-6 pt-5 border-t border-white/[0.08] flex items-center justify-between text-sm text-zinc-400 relative z-10">
                        <span className="font-medium text-zinc-300">
                          BG AI Core Team
                        </span>
                        <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                          Active Development
                        </span>
                      </div>
                    </SpotlightCard>
                  </div>
                </ScrollReveal>

                {/* Modular Team Placeholders (Reference Image 1 style) */}
                <div className="space-y-4 pt-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                      Team Roles & Contributors [Editable Placeholders]
                    </h3>
                    <span className="text-xs text-zinc-500 font-mono">
                      Expandable Team Architecture
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
                    {[
                      {
                        role: "AI & ML Engineer",
                        dept: "LLM Orchestration & Prompt Optimization",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "Frontend Architect",
                        dept: "Design Systems & Motion Experience",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "Database Systems Specialist",
                        dept: "SQL Execution & Safety Safeguards",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "Backend & API Engineer",
                        dept: "FastAPI, Query Caching & Async Services",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "Data Visualization Specialist",
                        dept: "Interactive Charts, Diagrams & Analytics",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "Security & DevOps Engineer",
                        dept: "Authentication, Sandboxing & Infrastructure",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "UI/UX Product Designer",
                        dept: "User Experience, Ergonomics & Prototyping",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "QA & Verification Engineer",
                        dept: "Database Stress-Testing & Integrity Checks",
                        tag: "Editable Placeholder",
                      },
                      {
                        role: "Open Role / Contributor",
                        dept: "Engineering, Product & Community Innovation",
                        tag: "Editable Placeholder",
                      },
                    ].map((slot, i) => (
                      <SpotlightCard
                        key={i}
                        spotlightColor="rgba(99, 102, 241, 0.12)"
                        className="rounded-2xl bg-[#121216] border border-dashed border-white/[0.14] p-6 text-center hover:border-white/[0.28] transition-all shadow-md group"
                      >
                        <div className="w-14 h-14 rounded-2xl bg-white/[0.03] border border-white/[0.08] mx-auto flex items-center justify-center text-zinc-400 group-hover:text-indigo-400 group-hover:bg-indigo-500/10 transition-colors mb-3">
                          <Users size={22} />
                        </div>
                        <h4 className="text-base font-bold text-white group-hover:text-indigo-200 transition-colors">
                          {slot.role}
                        </h4>
                        <p className="text-xs sm:text-sm text-zinc-400 mt-1 leading-relaxed">
                          {slot.dept}
                        </p>
                        <span className="inline-block mt-3 text-xs px-2.5 py-0.5 rounded-full bg-white/[0.04] text-zinc-400 border border-white/[0.08] font-mono">
                          {slot.tag}
                        </span>
                      </SpotlightCard>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {/* Full-Screen Footer */}
            <footer className="pt-10 border-t border-white/[0.08] flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-zinc-400">
              <div>
                <span>BG AI — Built by </span>
                <strong className="text-white font-semibold">Boopathi R</strong>
                <span> & </span>
                <strong className="text-white font-semibold">BG Team</strong>
              </div>

              <div className="flex items-center gap-4">
                <ClickSpark
                  sparkColor="#818cf8"
                  sparkCount={6}
                  sparkRadius={16}
                >
                  <button
                    onClick={onClose}
                    className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-all shadow-md shadow-indigo-600/20 cursor-pointer"
                  >
                    Return to Chat
                  </button>
                </ClickSpark>
              </div>
            </footer>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
