import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Database,
  BrainCircuit,
  Code2,
  ShieldCheck,
  BarChart3,
  Play,
  Pause,
  RotateCcw,
  ArrowRight,
  CheckCircle2,
  GitBranch,
  Zap,
  Lock,
  Unlock,
  Link2,
  Shield,
  Table,
  Cpu,
  FileSpreadsheet,
} from "lucide-react";
import ClickSpark from "../reactbits/ClickSpark";

interface FlowNode {
  id: number;
  stageNum: string;
  name: string;
  category: string;
  shortDesc: string;
  detailedText: string;
  icon: typeof Database;
  tag: string;
  accent: string;
  badgeClass: string;
  borderClass: string;
  glowColor: string;
}

const flowNodes: FlowNode[] = [
  {
    id: 1,
    stageNum: "01",
    name: "Schema Introspection & Knowledge Graph",
    category: "Ingestion Engine",
    shortDesc:
      "Automatic deep catalog scan across SQLite, MySQL, and PostgreSQL.",
    detailedText:
      "When a database is connected, BG AI introspects foreign keys, primary keys, indexes, data types, and nullability constraints. This schema context is indexed into an in-memory graph to ground AI prompts and prevent hallucinated tables or columns.",
    icon: Database,
    tag: "SCHEMA READY",
    accent: "text-sky-400",
    badgeClass: "bg-sky-500/10 text-sky-300 border-sky-500/25",
    borderClass: "border-sky-500/40",
    glowColor: "rgba(56, 189, 248, 0.35)",
  },
  {
    id: 2,
    stageNum: "02",
    name: "Semantic Intent & Branch Router",
    category: "AI Classifier",
    shortDesc:
      "Deterministic routing of Read queries vs. Guarded Write mutations.",
    detailedText:
      "User natural language queries are parsed through an intent classifier. Read questions (e.g., 'Show top customers by revenue') route directly to analytical formulation, while mutations (INSERT, UPDATE, DELETE) are segregated into guarded transactional workflows.",
    icon: BrainCircuit,
    tag: "INTENT CLASSIFIED",
    accent: "text-purple-400",
    badgeClass: "bg-purple-500/10 text-purple-300 border-purple-500/25",
    borderClass: "border-purple-500/40",
    glowColor: "rgba(192, 132, 252, 0.35)",
  },
  {
    id: 3,
    stageNum: "03",
    name: "SQL AST Synthesis & Security Guardrails",
    category: "Dialect Compiler",
    shortDesc: "High-performance dialect SQL with strict syntax blocklists.",
    detailedText:
      "The query synthesizer produces dialect-specific SQL (SQLite / MySQL / Postgres). Before driver execution, an Abstract Syntax Tree (AST) validation scan permanently rejects destructive statements (DROP, TRUNCATE, ALTER) and safely escapes parameters.",
    icon: Code2,
    tag: "AST VALIDATED",
    accent: "text-indigo-400",
    badgeClass: "bg-indigo-500/10 text-indigo-300 border-indigo-500/25",
    borderClass: "border-indigo-500/40",
    glowColor: "rgba(129, 140, 248, 0.35)",
  },
  {
    id: 4,
    stageNum: "04",
    name: "Human-in-the-Loop Safety Authorization",
    category: "Security Checkpoint",
    shortDesc:
      "Zero unattended table modifications. Explicit user confirmation.",
    detailedText:
      "Destructive mutations never execute silently. For any UPDATE or DELETE operation, BG AI queries the count of matching records and prompts the user with an explicit confirmation dialog and query preview. No data is changed without manual consent.",
    icon: ShieldCheck,
    tag: "HUMAN CONFIRMED",
    accent: "text-amber-400",
    badgeClass: "bg-amber-500/10 text-amber-300 border-amber-500/25",
    borderClass: "border-amber-500/40",
    glowColor: "rgba(251, 191, 36, 0.35)",
  },
  {
    id: 5,
    stageNum: "05",
    name: "Multi-Modal Execution & Visual Insights",
    category: "Output & Analytics",
    shortDesc:
      "Sub-millisecond driver query with auto-rendered charts and Excel grids.",
    detailedText:
      "Driver results are profiled for latency (ms), row volume, and column signatures. The platform dynamically renders interactive Chart.js graphs, exportable data tables, relationship flowcharts, and executive KPI highlight cards.",
    icon: BarChart3,
    tag: "RESULTS RENDERED",
    accent: "text-emerald-400",
    badgeClass: "bg-emerald-500/10 text-emerald-300 border-emerald-500/25",
    borderClass: "border-emerald-500/40",
    glowColor: "rgba(52, 211, 153, 0.35)",
  },
];

const samplePrompts = [
  {
    label: "Show monthly sales by product tier",
    type: "read" as const,
    targetStep: 3,
    title: "Read / Analytical Flow",
  },
  {
    label: "Update status of order 410 to 'shipped'",
    type: "write" as const,
    targetStep: 4,
    title: "Guarded Mutation Flow",
  },
  {
    label: "Inspect customers schema & foreign keys",
    type: "read" as const,
    targetStep: 1,
    title: "Schema Introspection Flow",
  },
];

export default function WorkflowFlowchart() {
  const [activeId, setActiveId] = useState<number>(1);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [queryMode, setQueryMode] = useState<"read" | "write">("read");
  const [userConfirmedMutation, setUserConfirmedMutation] =
    useState<boolean>(false);
  const [activePrompt, setActivePrompt] = useState<string>(
    samplePrompts[0].label,
  );

  const activeNode = flowNodes.find((n) => n.id === activeId) || flowNodes[0];

  // Auto-simulation loop
  useEffect(() => {
    if (!isSimulating) return;

    const interval = setInterval(() => {
      setActiveId((prev) => {
        if (queryMode === "read" && prev === 2) {
          return 3;
        }
        if (queryMode === "read" && prev === 3) {
          return 5;
        }
        if (prev >= 5) {
          setIsSimulating(false);
          return 1;
        }
        return prev + 1;
      });
    }, 2500);

    return () => clearInterval(interval);
  }, [isSimulating, queryMode]);

  const handleSelectNode = (id: number) => {
    setIsSimulating(false);
    setActiveId(id);
  };

  const handlePromptSelect = (prompt: (typeof samplePrompts)[0]) => {
    setIsSimulating(false);
    setActivePrompt(prompt.label);
    setQueryMode(prompt.type);
    setUserConfirmedMutation(false);
    setActiveId(prompt.targetStep);
  };

  const toggleSimulation = () => {
    if (isSimulating) {
      setIsSimulating(false);
    } else {
      if (activeId === 5) setActiveId(1);
      setUserConfirmedMutation(false);
      setIsSimulating(true);
    }
  };

  return (
    <div className="w-full space-y-10">
      {/* Top Interactive Simulation Bar */}
      <div className="p-6 sm:p-8 rounded-3xl bg-[#111116] border border-white/[0.1] shadow-2xl backdrop-blur-xl flex flex-col xl:flex-row xl:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2.5">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500" />
            </span>
            <span className="font-code font-bold text-xs sm:text-sm tracking-wider uppercase text-indigo-400">
              Interactive Execution Engine
            </span>
          </div>
          <h3 className="font-heading font-bold text-2xl sm:text-3xl text-white tracking-tight">
            Live Architecture Simulator
          </h3>
          <p className="font-body text-base sm:text-lg text-zinc-300 max-w-2xl leading-relaxed">
            Trace how natural language questions travel through intent analysis,
            AST validation, safety gates, and dynamic database visualizations.
          </p>
        </div>

        {/* Controls: Branch Switch, Run Simulator, Reset */}
        <div className="flex flex-wrap items-center gap-3 shrink-0">
          {/* Query Mode Switch */}
          <div className="flex items-center bg-black/60 p-1.5 rounded-2xl border border-white/[0.08]">
            <button
              onClick={() => {
                setQueryMode("read");
                setUserConfirmedMutation(false);
              }}
              className={`px-4 py-2 rounded-xl font-heading text-sm font-semibold transition-all cursor-pointer ${
                queryMode === "read"
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/30"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Analytical Read (SELECT)
            </button>
            <button
              onClick={() => {
                setQueryMode("write");
                setUserConfirmedMutation(false);
              }}
              className={`px-4 py-2 rounded-xl font-heading text-sm font-semibold transition-all cursor-pointer ${
                queryMode === "write"
                  ? "bg-amber-600 text-white shadow-lg shadow-amber-600/30"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Guarded Write (UPDATE/DELETE)
            </button>
          </div>

          {/* Simulate Button */}
          <ClickSpark sparkColor="#818cf8" sparkCount={8} sparkRadius={20}>
            <button
              onClick={toggleSimulation}
              className={`px-5 py-3 rounded-2xl font-heading font-bold text-sm sm:text-base tracking-wide flex items-center gap-2.5 transition-all cursor-pointer shadow-xl ${
                isSimulating
                  ? "bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/30"
                  : "bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white shadow-indigo-600/30"
              }`}
            >
              {isSimulating ? (
                <>
                  <Pause size={18} />
                  <span>Pause Simulation</span>
                </>
              ) : (
                <>
                  <Play size={18} className="fill-current" />
                  <span>Run Live Flow</span>
                </>
              )}
            </button>
          </ClickSpark>

          {/* Reset */}
          <button
            onClick={() => {
              setIsSimulating(false);
              setActiveId(1);
              setUserConfirmedMutation(false);
            }}
            className="p-3 rounded-2xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-400 hover:text-white transition-all cursor-pointer"
            title="Reset to Stage 01"
          >
            <RotateCcw size={18} />
          </button>
        </div>
      </div>

      {/* Preset Quick-Test Prompts */}
      <div className="space-y-3">
        <div className="font-code text-xs sm:text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
          <Zap size={14} className="text-amber-400" />
          <span>Click a sample user prompt to test flow routing:</span>
        </div>
        <div className="flex flex-wrap gap-2.5">
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handlePromptSelect(p)}
              className={`px-4 py-2.5 rounded-xl border font-body text-sm sm:text-base font-medium transition-all cursor-pointer flex items-center gap-2 ${
                activePrompt === p.label
                  ? "bg-indigo-600/20 border-indigo-500/50 text-white shadow-md shadow-indigo-500/10"
                  : "bg-[#111116] border-white/[0.08] text-zinc-300 hover:border-white/[0.2] hover:text-white"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${p.type === "read" ? "bg-indigo-400" : "bg-amber-400"}`}
              />
              <span>&ldquo;{p.label}&rdquo;</span>
              <span className="font-code text-xs px-2 py-0.5 rounded bg-white/[0.06] text-zinc-400">
                {p.type.toUpperCase()}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TRENDING MOTION FLOWCHART CANVAS (Visual Architectural Diagram with SVG Wires) */}
      {/* ========================================================================= */}
      <div className="relative rounded-3xl bg-[#0d0d12] border border-white/[0.1] p-6 sm:p-10 shadow-2xl overflow-hidden">
        {/* Subtle Architectural Grid Background */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

        {/* Section Headline */}
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-6 border-b border-white/[0.08]">
          <div>
            <div className="font-code text-xs sm:text-sm text-indigo-400 font-bold uppercase tracking-wider">
              System Pipeline Architecture
            </div>
            <h4 className="font-display font-bold text-2xl sm:text-3xl text-white tracking-tight mt-1">
              Deterministic & AI Flowchart
            </h4>
          </div>
          <div className="flex items-center gap-2 text-xs sm:text-sm font-code text-zinc-400">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>
              Active Station: Stage 0{activeId} ({activeNode.tag})
            </span>
          </div>
        </div>

        {/* Desktop Interactive Flow Nodes (Horizontal Flowchart Layout) */}
        <div className="relative z-10 grid grid-cols-1 md:grid-cols-5 gap-4 lg:gap-6 items-stretch">
          {flowNodes.map((node) => {
            const isActive = activeId === node.id;
            const isPassed = activeId > node.id;
            const Icon = node.icon;

            return (
              <motion.div
                key={node.id}
                onClick={() => handleSelectNode(node.id)}
                whileHover={{ scale: 1.03, y: -4 }}
                transition={{ type: "spring", stiffness: 350, damping: 25 }}
                className={`relative rounded-2xl p-5 sm:p-6 border transition-all cursor-pointer flex flex-col justify-between select-none ${
                  isActive
                    ? "bg-[#181822] border-indigo-500 shadow-2xl shadow-indigo-500/25 ring-2 ring-indigo-500/40"
                    : isPassed
                      ? "bg-[#121218] border-emerald-500/30 hover:border-emerald-500/50"
                      : "bg-[#101015] border-white/[0.08] hover:border-white/[0.18] hover:bg-[#14141c]"
                }`}
                style={{
                  boxShadow: isActive
                    ? `0 0 35px ${node.glowColor}`
                    : undefined,
                }}
              >
                {/* Active Glowing Pulse Corner */}
                {isActive && (
                  <div className="absolute -top-1 -right-1 flex h-4 w-4">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-4 w-4 bg-indigo-500 border border-white text-[9px] font-bold text-white items-center justify-center">
                      ✓
                    </span>
                  </div>
                )}

                <div className="space-y-4">
                  {/* Top Node Header: Icon & Number */}
                  <div className="flex items-center justify-between">
                    <div
                      className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all ${
                        isActive
                          ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/40 scale-110"
                          : isPassed
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : "bg-white/[0.04] text-zinc-400 border border-white/[0.08]"
                      }`}
                    >
                      <Icon size={24} />
                    </div>
                    <span className="font-display font-black text-2xl sm:text-3xl text-white/40">
                      {node.stageNum}
                    </span>
                  </div>

                  {/* Stage Category & Name */}
                  <div className="space-y-1.5">
                    <div className="font-code text-xs font-bold uppercase tracking-wider text-indigo-400">
                      {node.category}
                    </div>
                    <div className="font-heading font-bold text-base sm:text-lg text-white leading-snug">
                      {node.name.split(" ")[0]} {node.name.split(" ")[1]}
                    </div>
                  </div>

                  {/* Short Summary */}
                  <p className="font-body text-xs sm:text-sm text-zinc-400 line-clamp-2 leading-relaxed">
                    {node.shortDesc}
                  </p>
                </div>

                {/* Bottom Node Tag */}
                <div className="pt-4 mt-2 border-t border-white/[0.06] flex items-center justify-between">
                  <span
                    className={`font-code text-[11px] font-semibold px-2 py-0.5 rounded border ${node.badgeClass}`}
                  >
                    {node.tag}
                  </span>
                  <span className="font-code text-[11px] text-zinc-400">
                    {isActive ? "ACTIVE" : "INSPECT"}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Dynamic Animated Connector Path (SVG Beam) */}
        <div className="hidden md:block relative z-10 my-8 py-3 px-2">
          <div className="relative h-2.5 rounded-full bg-white/[0.06] overflow-hidden">
            {/* Moving Laser Beam */}
            <motion.div
              className="absolute top-0 bottom-0 h-full rounded-full bg-gradient-to-r from-indigo-500 via-sky-400 to-emerald-400 shadow-[0_0_18px_#818cf8]"
              animate={{
                width: `${(activeId / 5) * 100}%`,
              }}
              transition={{
                type: "spring",
                stiffness: 140,
                damping: 20,
              }}
            />
          </div>
          <div className="flex justify-between text-xs font-code text-zinc-400 mt-2 px-1">
            <span>01 Schema Ingest</span>
            <span>02 Intent Engine</span>
            <span>03 AST Guard</span>
            <span>04 Safety Gate</span>
            <span>05 Visual Insights</span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* EXPANDED STAGE WORKSTATION INSPECTOR WITH PICTORIAL ARCHITECTURAL INFOGRAPHICS */}
      {/* ========================================================================= */}
      <div className="rounded-3xl bg-[#121218] border border-white/[0.12] p-6 sm:p-10 shadow-2xl space-y-8">
        {/* Stage Header Info */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.08]">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-code text-xs sm:text-sm font-bold px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300">
                STAGE {activeNode.stageNum} •{" "}
                {activeNode.category.toUpperCase()}
              </span>
              <span className="font-code text-xs sm:text-sm px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-300">
                STATUS: {activeNode.tag}
              </span>
              {activeNode.id === 2 && (
                <span className="font-code text-xs sm:text-sm px-3 py-1 rounded-full bg-purple-500/10 border border-purple-500/30 text-purple-300 flex items-center gap-1.5">
                  <GitBranch size={13} />
                  BRANCH: {queryMode.toUpperCase()}
                </span>
              )}
            </div>

            <h3 className="font-heading font-black text-3xl sm:text-4xl text-white tracking-tight">
              {activeNode.name}
            </h3>
          </div>

          <div className="shrink-0 flex items-center gap-3">
            <span className="font-display font-black text-4xl sm:text-5xl text-white/30">
              0{activeNode.id}
            </span>
          </div>
        </div>

        {/* Narrative Description in High-Legibility Font */}
        <p className="font-body text-base sm:text-xl text-zinc-200 leading-relaxed max-w-5xl">
          {activeNode.detailedText}
        </p>

        {/* ======================================================================= */}
        {/* PICTORIAL ARCHITECTURAL INFOGRAPHIC VISUALIZATIONS (STAGE SPECIFIC) */}
        {/* ======================================================================= */}

        {/* PICTORIAL 1: Ingestion & Knowledge Graph */}
        {activeNode.id === 1 && (
          <div className="rounded-2xl bg-gradient-to-br from-sky-950/25 via-[#0d0d12] to-indigo-950/20 border border-sky-500/25 p-6 sm:p-8 space-y-6">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-sky-400 animate-pulse" />
                <span className="font-code text-xs sm:text-sm font-bold text-sky-400 uppercase tracking-wider">
                  Pictorial Architecture • Multi-Database Introspection
                </span>
              </div>
              <span className="font-code text-xs px-2.5 py-1 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">
                Grounding Engine
              </span>
            </div>

            {/* Pictorial Diagram Canvas */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Left Column: Database Engines */}
              <div className="lg:col-span-4 space-y-3">
                <div className="font-heading text-xs font-bold text-zinc-400 uppercase tracking-wider">
                  1. Supported Data Sources
                </div>

                <div className="p-3.5 rounded-xl bg-black/40 border border-sky-500/20 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-sky-500/15 border border-sky-500/30 text-sky-400 flex items-center justify-center">
                    <Database size={18} />
                  </div>
                  <div className="flex-1">
                    <div className="font-heading font-bold text-sm text-white">
                      SQLite (.db)
                    </div>
                    <div className="font-code text-[11px] text-zinc-400">
                      Embedded Serverless Engine
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-black/40 border border-indigo-500/20 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 flex items-center justify-center">
                    <Database size={18} />
                  </div>
                  <div className="flex-1">
                    <div className="font-heading font-bold text-sm text-white">
                      MySQL (Port 3306)
                    </div>
                    <div className="font-code text-[11px] text-zinc-400">
                      Production Relational RDBMS
                    </div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-black/40 border border-emerald-500/20 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center">
                    <Database size={18} />
                  </div>
                  <div className="flex-1">
                    <div className="font-heading font-bold text-sm text-white">
                      PostgreSQL (Port 5432)
                    </div>
                    <div className="font-code text-[11px] text-zinc-400">
                      Enterprise ACID Compliant
                    </div>
                  </div>
                </div>
              </div>

              {/* Center Column: Data Ingestion Pipe */}
              <div className="lg:col-span-2 flex lg:flex-col items-center justify-center py-2">
                <div className="w-10 h-10 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 flex items-center justify-center animate-pulse">
                  <ArrowRight size={20} className="lg:rotate-0" />
                </div>
                <span className="font-code text-[10px] text-zinc-400 mt-2 text-center">
                  Deep Catalog Introspect
                </span>
              </div>

              {/* Right Column: Schema Knowledge Graph */}
              <div className="lg:col-span-6 space-y-3">
                <div className="font-heading text-xs font-bold text-zinc-400 uppercase tracking-wider">
                  2. In-Memory Knowledge Graph (Entities & Relations)
                </div>

                <div className="p-4 rounded-xl bg-black/50 border border-white/[0.08] space-y-3">
                  {/* Entity: Customers */}
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-sky-500/30 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-code font-bold text-xs text-sky-300 flex items-center gap-1.5">
                        <Table size={13} />
                        customers
                      </span>
                      <span className="font-code text-[10px] px-2 py-0.5 rounded bg-sky-500/20 text-sky-300">
                        Primary Key: id
                      </span>
                    </div>
                    <div className="font-code text-[11px] text-zinc-400 flex flex-wrap gap-2">
                      <span className="text-zinc-200">id (INT)</span>
                      <span>name (VARCHAR)</span>
                      <span>email (VARCHAR)</span>
                    </div>
                  </div>

                  {/* Relationship Link Wire */}
                  <div className="flex items-center gap-2 pl-6 py-0.5 text-indigo-400 font-code text-[11px]">
                    <Link2 size={13} className="text-indigo-400" />
                    <span>
                      FK: orders.customer_id ➔ customers.id (1-to-Many)
                    </span>
                  </div>

                  {/* Entity: Orders */}
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-indigo-500/30 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-code font-bold text-xs text-indigo-300 flex items-center gap-1.5">
                        <Table size={13} />
                        orders
                      </span>
                      <span className="font-code text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300">
                        Foreign Key Linked
                      </span>
                    </div>
                    <div className="font-code text-[11px] text-zinc-400 flex flex-wrap gap-2">
                      <span className="text-zinc-200">id (INT)</span>
                      <span className="text-indigo-300">customer_id (FK)</span>
                      <span>amount (DECIMAL)</span>
                      <span>status (VARCHAR)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PICTORIAL 2: Semantic Intent & Branch Router */}
        {activeNode.id === 2 && (
          <div className="rounded-2xl bg-gradient-to-br from-purple-950/25 via-[#0d0d12] to-indigo-950/20 border border-purple-500/25 p-6 sm:p-8 space-y-6">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse" />
                <span className="font-code text-xs sm:text-sm font-bold text-purple-400 uppercase tracking-wider">
                  Pictorial Architecture • Semantic Decision Tree
                </span>
              </div>
              <span className="font-code text-xs px-2.5 py-1 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                Branching Engine
              </span>
            </div>

            {/* Decision Tree Visual */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Input Bubble */}
              <div className="lg:col-span-4 p-4 rounded-xl bg-black/50 border border-white/[0.1] space-y-2">
                <div className="font-heading text-xs font-bold text-zinc-400 uppercase tracking-wider">
                  Natural Language Input
                </div>
                <div className="p-3 rounded-lg bg-white/[0.04] border border-white/[0.08] font-body text-sm text-white">
                  &ldquo;{activePrompt}&rdquo;
                </div>
                <div className="font-code text-[11px] text-zinc-400">
                  Tokens parsed & evaluated by AI Classifier
                </div>
              </div>

              {/* Neural Brain Node */}
              <div className="lg:col-span-3 flex flex-col items-center justify-center p-4 rounded-2xl bg-purple-950/30 border border-purple-500/30 text-center space-y-2">
                <div className="w-12 h-12 rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-400 flex items-center justify-center animate-pulse">
                  <BrainCircuit size={24} />
                </div>
                <div className="font-heading font-bold text-sm text-white">
                  Neural Intent Classifier
                </div>
                <div className="font-code text-[11px] text-purple-300">
                  Confidence: 99.8%
                </div>
              </div>

              {/* Fork Branches */}
              <div className="lg:col-span-5 space-y-3">
                <div
                  onClick={() => setQueryMode("read")}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    queryMode === "read"
                      ? "bg-indigo-600/20 border-indigo-500 text-white shadow-lg shadow-indigo-600/25"
                      : "bg-black/30 border-white/[0.06] text-zinc-400 hover:text-white"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-heading font-bold text-sm">
                      🟢 Route A: Analytical Query
                    </span>
                    <span className="font-code text-xs px-2 py-0.5 rounded bg-indigo-500/30 text-indigo-200">
                      SELECT
                    </span>
                  </div>
                  <div className="font-body text-xs text-zinc-300 mt-1">
                    Safe Read path ➔ Directly passes to AST compilation and
                    Chart.js rendering.
                  </div>
                </div>

                <div
                  onClick={() => setQueryMode("write")}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    queryMode === "write"
                      ? "bg-amber-600/20 border-amber-500 text-white shadow-lg shadow-amber-600/25"
                      : "bg-black/30 border-white/[0.06] text-zinc-400 hover:text-white"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-heading font-bold text-sm">
                      🟠 Route B: Mutation Operation
                    </span>
                    <span className="font-code text-xs px-2 py-0.5 rounded bg-amber-500/30 text-amber-200">
                      MUTATION
                    </span>
                  </div>
                  <div className="font-body text-xs text-zinc-300 mt-1">
                    Guarded Write path ➔ Routes into Stage 04 Human-in-the-Loop
                    authorization gate.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PICTORIAL 3: SQL AST Synthesis & Security Guardrails */}
        {activeNode.id === 3 && (
          <div className="rounded-2xl bg-gradient-to-br from-indigo-950/25 via-[#0d0d12] to-sky-950/20 border border-indigo-500/25 p-6 sm:p-8 space-y-6">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse" />
                <span className="font-code text-xs sm:text-sm font-bold text-indigo-400 uppercase tracking-wider">
                  Pictorial Architecture • AST Defense Gate
                </span>
              </div>
              <span className="font-code text-xs px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                Security Scanner
              </span>
            </div>

            {/* AST Defense Visualization */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Raw Generated SQL */}
              <div className="lg:col-span-5 p-4 rounded-xl bg-black/50 border border-white/[0.08] space-y-2">
                <div className="font-heading text-xs font-bold text-zinc-400 uppercase tracking-wider flex items-center justify-between">
                  <span>Synthesized Dialect Query</span>
                  <span className="text-indigo-400 font-code">
                    Dialect: SQLite / MySQL
                  </span>
                </div>
                <pre className="font-code text-xs text-indigo-200 bg-black/80 p-3 rounded-lg border border-white/[0.06] overflow-x-auto leading-relaxed">
                  {queryMode === "read"
                    ? `SELECT c.name, SUM(o.amount)\nFROM customers c\nJOIN orders o ON c.id = o.customer_id\nGROUP BY 1 ORDER BY 2 DESC;`
                    : `UPDATE orders\nSET status = 'shipped'\nWHERE id = 410;`}
                </pre>
              </div>

              {/* Center Cyber Shield Gate */}
              <div className="lg:col-span-4 p-4 rounded-xl bg-gradient-to-b from-indigo-950/40 to-black/60 border border-indigo-500/30 space-y-3">
                <div className="flex items-center gap-2 font-heading font-bold text-sm text-white">
                  <Shield size={16} className="text-indigo-400" />
                  <span>AST Lexer & Syntax Blocklist</span>
                </div>

                <div className="space-y-1.5">
                  <div className="p-2 rounded bg-rose-500/10 border border-rose-500/25 flex items-center justify-between font-code text-xs text-rose-300">
                    <span>DROP TABLE / TRUNCATE</span>
                    <span className="font-bold">DEFLECTED ✗</span>
                  </div>
                  <div className="p-2 rounded bg-rose-500/10 border border-rose-500/25 flex items-center justify-between font-code text-xs text-rose-300">
                    <span>ALTER TABLE / SCHEMA CHANGE</span>
                    <span className="font-bold">DEFLECTED ✗</span>
                  </div>
                  <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-between font-code text-xs text-emerald-300">
                    <span>Parametric Value Quoting</span>
                    <span className="font-bold">ALLOWED ✓</span>
                  </div>
                </div>
              </div>

              {/* Right Output: Clean Executable */}
              <div className="lg:col-span-3 p-4 rounded-xl bg-emerald-950/20 border border-emerald-500/30 text-center space-y-2">
                <div className="w-10 h-10 mx-auto rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center">
                  <CheckCircle2 size={20} />
                </div>
                <div className="font-heading font-bold text-sm text-white">
                  Validated Abstract Tree
                </div>
                <div className="font-code text-[11px] text-emerald-300">
                  Ready for Driver Execution
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PICTORIAL 4: Human-in-the-Loop Safety Authorization */}
        {activeNode.id === 4 && (
          <div className="rounded-2xl bg-gradient-to-br from-amber-950/25 via-[#0d0d12] to-orange-950/20 border border-amber-500/25 p-6 sm:p-8 space-y-6">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
                <span className="font-code text-xs sm:text-sm font-bold text-amber-400 uppercase tracking-wider">
                  Pictorial Architecture • Transaction Lock & Consent Vault
                </span>
              </div>
              <span className="font-code text-xs px-2.5 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                Safety Quarantine
              </span>
            </div>

            {/* Safety Vault Visualization */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Target Mutation Cell */}
              <div className="lg:col-span-4 p-4 rounded-xl bg-black/50 border border-amber-500/25 space-y-2">
                <div className="font-heading text-xs font-bold text-zinc-400 uppercase tracking-wider">
                  1. Dry-Run Impact Analysis
                </div>
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-1">
                  <div className="font-code text-xs text-amber-300 font-bold">
                    Target: orders (id = 410)
                  </div>
                  <div className="font-code text-[11px] text-zinc-300">
                    Row Impact: Exactly 1 record affected
                  </div>
                  <div className="font-code text-[11px] text-zinc-400">
                    Previous: &lsquo;pending&rsquo; ➔ Next:
                    &lsquo;shipped&rsquo;
                  </div>
                </div>
              </div>

              {/* Center Digital Vault Padlock */}
              <div className="lg:col-span-4 flex flex-col items-center justify-center p-5 rounded-2xl bg-black/60 border border-amber-500/30 text-center space-y-3">
                <div
                  className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-all ${
                    userConfirmedMutation
                      ? "bg-emerald-600/30 border border-emerald-500 text-emerald-400"
                      : "bg-amber-600/30 border border-amber-500 text-amber-400 animate-bounce"
                  }`}
                >
                  {userConfirmedMutation ? (
                    <Unlock size={28} />
                  ) : (
                    <Lock size={28} />
                  )}
                </div>

                <div className="space-y-0.5">
                  <div className="font-heading font-bold text-sm text-white">
                    {userConfirmedMutation
                      ? "Transaction Unlocked ✓"
                      : "Quarantine Lock Engaged"}
                  </div>
                  <div className="font-code text-[11px] text-zinc-400">
                    {userConfirmedMutation
                      ? "User authorization registered"
                      : "Awaiting explicit human signature"}
                  </div>
                </div>
              </div>

              {/* Right Manual Authorization Action */}
              <div className="lg:col-span-4 p-4 rounded-xl bg-black/50 border border-white/[0.08] space-y-3 text-center">
                <div className="font-heading text-xs font-bold text-zinc-400 uppercase tracking-wider">
                  2. Manual Human Authorization
                </div>

                <button
                  type="button"
                  onClick={() =>
                    setUserConfirmedMutation(!userConfirmedMutation)
                  }
                  className={`w-full py-3 px-4 rounded-xl font-heading font-bold text-sm transition-all cursor-pointer shadow-lg ${
                    userConfirmedMutation
                      ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30"
                      : "bg-amber-600 hover:bg-amber-500 text-white shadow-amber-600/30"
                  }`}
                >
                  {userConfirmedMutation
                    ? "Authorized by User ✓"
                    : "Click to Authorize Mutation"}
                </button>

                <div className="font-code text-[10px] text-zinc-400">
                  Zero unattended mutations. No database writes happen without
                  this click.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PICTORIAL 5: Multi-Modal Dynamic Output Engine */}
        {activeNode.id === 5 && (
          <div className="rounded-2xl bg-gradient-to-br from-emerald-950/25 via-[#0d0d12] to-teal-950/20 border border-emerald-500/25 p-6 sm:p-8 space-y-6">
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-code text-xs sm:text-sm font-bold text-emerald-400 uppercase tracking-wider">
                  Pictorial Architecture • Multi-Channel Output Projector
                </span>
              </div>
              <span className="font-code text-xs px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                Dynamic Visuals
              </span>
            </div>

            {/* Output Visual Channels */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Channel 1: Chart.js Visualizer */}
              <div className="p-4 rounded-xl bg-black/50 border border-emerald-500/30 space-y-3">
                <div className="flex items-center gap-2 text-emerald-400 font-heading font-bold text-sm">
                  <BarChart3 size={16} />
                  <span>Channel A: Chart.js Visualizer</span>
                </div>

                {/* Mini SVG Bar Chart */}
                <div className="space-y-2 pt-1">
                  {[
                    { label: "Acme Corp", val: 90, color: "bg-indigo-500" },
                    { label: "Stark Labs", val: 72, color: "bg-sky-400" },
                    { label: "Wayne Tech", val: 55, color: "bg-emerald-400" },
                  ].map((item, i) => (
                    <div key={i} className="space-y-1">
                      <div className="flex justify-between font-code text-[11px] text-zinc-300">
                        <span>{item.label}</span>
                        <span className="font-bold">{item.val * 150}k</span>
                      </div>
                      <div className="h-2 rounded-full bg-white/[0.08] overflow-hidden">
                        <motion.div
                          className={`h-full ${item.color} rounded-full`}
                          initial={{ width: 0 }}
                          animate={{ width: `${item.val}%` }}
                          transition={{ duration: 0.6, delay: i * 0.1 }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Channel 2: Tabular Data Grid */}
              <div className="p-4 rounded-xl bg-black/50 border border-indigo-500/30 space-y-3">
                <div className="flex items-center gap-2 text-indigo-400 font-heading font-bold text-sm">
                  <FileSpreadsheet size={16} />
                  <span>Channel B: Data Table & Excel Export</span>
                </div>

                <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] font-code text-[11px] space-y-1 text-zinc-300">
                  <div className="flex justify-between text-zinc-400 border-b border-white/[0.06] pb-1 font-bold">
                    <span>CUSTOMER</span>
                    <span>SPENT</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Acme Corp</span>
                    <span className="text-emerald-300">$135,000</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Stark Labs</span>
                    <span className="text-emerald-300">$108,000</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Wayne Tech</span>
                    <span className="text-emerald-300">$82,500</span>
                  </div>
                </div>
                <div className="font-code text-[10px] text-zinc-400">
                  Sticky headers • Excel / CSV Export enabled
                </div>
              </div>

              {/* Channel 3: Execution Latency HUD */}
              <div className="p-4 rounded-xl bg-black/50 border border-sky-500/30 space-y-3">
                <div className="flex items-center gap-2 text-sky-400 font-heading font-bold text-sm">
                  <Cpu size={16} />
                  <span>Channel C: Latency Profiler</span>
                </div>

                <div className="p-3 rounded-lg bg-sky-950/20 border border-sky-500/20 text-center space-y-1">
                  <div className="font-display font-black text-2xl text-sky-300">
                    12.4 ms
                  </div>
                  <div className="font-code text-[11px] text-zinc-400">
                    Sub-millisecond driver latency
                  </div>
                </div>

                <div className="flex items-center justify-between font-code text-[11px] text-zinc-300 pt-1">
                  <span>Engine: Async Driver</span>
                  <span className="text-emerald-400 font-bold">
                    Status: 200 OK
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Stage Navigation Stepper Footer */}
        <div className="flex items-center justify-between pt-6 border-t border-white/[0.08]">
          <div className="font-code text-xs sm:text-sm text-zinc-400">
            Station {activeNode.id} of 5 • {activeNode.tag}
          </div>

          {activeNode.id < 5 ? (
            <button
              type="button"
              onClick={() => setActiveId(activeNode.id + 1)}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-heading font-semibold text-sm sm:text-base flex items-center gap-2 transition-all cursor-pointer shadow-lg shadow-indigo-600/30"
            >
              <span>Next Stage: 0{activeNode.id + 1}</span>
              <ArrowRight size={16} />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setActiveId(1)}
              className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-heading font-semibold text-sm sm:text-base flex items-center gap-2 transition-all cursor-pointer shadow-lg shadow-emerald-600/30"
            >
              <RotateCcw size={16} />
              <span>Replay Pipeline from Stage 01</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
