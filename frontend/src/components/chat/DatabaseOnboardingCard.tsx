import {
  Database,
  Server,
  HardDrive,
  BarChart3,
  ShieldCheck,
  Sparkles,
  ArrowRight,
  Terminal,
  Layers,
  HelpCircle,
  FileSpreadsheet,
  CheckCircle2,
  Plug,
} from "lucide-react";
import ClickSpark from "../reactbits/ClickSpark";
import SpotlightCard from "../reactbits/SpotlightCard";

interface DatabaseOnboardingCardProps {
  onConnectDatabase?: (type?: "sqlite" | "mysql" | "postgres") => void;
  onSend?: (message: string) => void;
}

export default function DatabaseOnboardingCard({
  onConnectDatabase,
  onSend,
}: DatabaseOnboardingCardProps) {
  const samplePrompts = [
    "Show all customers",
    "List top products by sales",
    "Analyze monthly revenue",
    "Explain table relationships",
  ];

  const educationalQuestions = [
    "What is a primary key?",
    "How does SQL SELECT work?",
    "What databases does BG AI support?",
    "How do CRUD safeguards work?",
  ];

  return (
    <div className="space-y-6 text-zinc-100">
      {/* 1. INTRO PICTORIAL HERO */}
      <div className="p-5 sm:p-6 rounded-2xl bg-gradient-to-b from-indigo-950/40 via-[#14141a] to-[#121216] border border-indigo-500/20 shadow-xl shadow-black/40">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 shadow-lg shadow-indigo-500/10">
            <Sparkles size={24} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
                Hello! Welcome to BG AI
              </h2>
              <span className="px-2 py-0.5 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-[11px] font-semibold text-indigo-300">
                Database Intelligence
              </span>
            </div>
            <p className="text-xs sm:text-sm text-zinc-300 leading-relaxed mt-1">
              Your conversational data assistant. Ask questions in plain
              English, and BG AI generates queries, introspects schemas, and
              renders interactive charts.
            </p>
          </div>
        </div>

        {/* 3 Pictorial Capabilities */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-5 pt-4 border-t border-white/[0.06]">
          <SpotlightCard
            spotlightColor="rgba(99, 102, 241, 0.15)"
            className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-indigo-500/30 transition-colors"
          >
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-2.5">
              <Terminal size={16} />
            </div>
            <h4 className="text-xs sm:text-sm font-bold text-white">
              Conversational SQL
            </h4>
            <p className="text-[11px] text-zinc-400 mt-1 leading-normal">
              Ask in English, get verified queries without memorizing SQL
              syntax.
            </p>
          </SpotlightCard>

          <SpotlightCard
            spotlightColor="rgba(20, 184, 166, 0.15)"
            className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-teal-500/30 transition-colors"
          >
            <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 mb-2.5">
              <BarChart3 size={16} />
            </div>
            <h4 className="text-xs sm:text-sm font-bold text-white">
              Visual Analytics
            </h4>
            <p className="text-[11px] text-zinc-400 mt-1 leading-normal">
              Auto-generate bar charts, trend lines, and interactive ER
              diagrams.
            </p>
          </SpotlightCard>

          <SpotlightCard
            spotlightColor="rgba(244, 63, 94, 0.15)"
            className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-rose-500/30 transition-colors"
          >
            <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 mb-2.5">
              <ShieldCheck size={16} />
            </div>
            <h4 className="text-xs sm:text-sm font-bold text-white">
              Safe CRUD Workflows
            </h4>
            <p className="text-[11px] text-zinc-400 mt-1 leading-normal">
              Zero-risk modifications with preview modals and confirmation
              alerts.
            </p>
          </SpotlightCard>
        </div>
      </div>

      {/* CURRENT STATUS CALLOUT */}
      <div className="p-4 rounded-xl bg-amber-500/[0.06] border border-amber-500/20 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-2.5 h-2.5 rounded-full bg-amber-400 shrink-0" />
          <div>
            <p className="text-xs sm:text-sm font-semibold text-amber-200">
              No database connected to this session
            </p>
            <p className="text-[11px] text-amber-300/80 leading-normal">
              Connect a database below to retrieve records, inspect tables, and
              execute queries.
            </p>
          </div>
        </div>

        {onConnectDatabase && (
          <ClickSpark sparkColor="#818cf8" sparkCount={6} sparkRadius={16}>
            <button
              onClick={() => onConnectDatabase("sqlite")}
              className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold whitespace-nowrap transition-all shadow-md shadow-indigo-900/30 cursor-pointer shrink-0"
            >
              Connect Now
            </button>
          </ClickSpark>
        )}
      </div>

      {/* 2. USER-FRIENDLY STEP-BY-STEP WORKFLOW */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-zinc-200 tracking-tight flex items-center gap-2">
            <span>Quick Start Steps</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.06] text-zinc-400">
              3 Simple Steps
            </span>
          </h3>
        </div>

        {/* STEP 1: Connect Database */}
        <div className="p-5 rounded-xl bg-[#141418] border border-white/[0.08] space-y-4">
          <div className="flex items-center gap-3">
            <span className="w-7 h-7 rounded-lg bg-indigo-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-md shadow-indigo-600/30">
              1
            </span>
            <div>
              <h4 className="text-sm font-bold text-white">
                Connect your Database
              </h4>
              <p className="text-xs text-zinc-400">
                Select your database engine and configure connection parameters.
              </p>
            </div>
          </div>

          {/* Supported Engines Comparison Table */}
          <div className="overflow-x-auto rounded-xl border border-white/[0.08] bg-black/20">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/[0.08] bg-white/[0.02] text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                  <th className="px-4 py-2.5">Engine</th>
                  <th className="px-4 py-2.5">Method</th>
                  <th className="px-4 py-2.5">Default Config</th>
                  <th className="px-4 py-2.5 text-right">Quick Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-3 font-semibold text-white flex items-center gap-2">
                    <HardDrive size={15} className="text-indigo-400" />
                    <span>SQLite</span>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    Upload local{" "}
                    <span className="font-mono text-zinc-200">.db</span> file
                  </td>
                  <td className="px-4 py-3 text-zinc-400 font-mono">
                    Zero-config sandbox
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onConnectDatabase?.("sqlite")}
                      className="px-2.5 py-1 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/30 text-indigo-300 hover:text-white font-medium text-[11px] transition-all cursor-pointer"
                    >
                      Attach .db
                    </button>
                  </td>
                </tr>

                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-3 font-semibold text-white flex items-center gap-2">
                    <Server size={15} className="text-teal-400" />
                    <span>MySQL</span>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    Network TCP/IP socket
                  </td>
                  <td className="px-4 py-3 text-zinc-400 font-mono">
                    localhost : 3306
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onConnectDatabase?.("mysql")}
                      className="px-2.5 py-1 rounded-lg bg-teal-500/15 hover:bg-teal-500/25 border border-teal-500/30 text-teal-300 hover:text-white font-medium text-[11px] transition-all cursor-pointer"
                    >
                      Connect MySQL
                    </button>
                  </td>
                </tr>

                <tr className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-4 py-3 font-semibold text-white flex items-center gap-2">
                    <Layers size={15} className="text-sky-400" />
                    <span>PostgreSQL</span>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">
                    Object-Relational instance
                  </td>
                  <td className="px-4 py-3 text-zinc-400 font-mono">
                    localhost : 5432
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onConnectDatabase?.("postgres")}
                      className="px-2.5 py-1 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/30 text-sky-300 hover:text-white font-medium text-[11px] transition-all cursor-pointer"
                    >
                      Connect Postgres
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* STEP 2: Ask Questions in Plain English */}
        <div className="p-5 rounded-xl bg-[#141418] border border-white/[0.08] space-y-3">
          <div className="flex items-center gap-3">
            <span className="w-7 h-7 rounded-lg bg-teal-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-md shadow-teal-600/30">
              2
            </span>
            <div>
              <h4 className="text-sm font-bold text-white">
                Ask in Plain English
              </h4>
              <p className="text-xs text-zinc-400">
                No complex queries or syntax to memorize. Click any sample
                prompt to test:
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            {samplePrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => onSend?.(prompt)}
                className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.06] hover:border-indigo-500/30 text-left transition-all text-xs font-medium text-zinc-200 hover:text-white group cursor-pointer"
              >
                <span className="truncate">"{prompt}"</span>
                <ArrowRight
                  size={13}
                  className="text-zinc-500 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-all shrink-0 ml-2"
                />
              </button>
            ))}
          </div>
        </div>

        {/* STEP 3: Instant SQL & Visual Results */}
        <div className="p-5 rounded-xl bg-[#141418] border border-white/[0.08] flex items-center gap-4">
          <span className="w-7 h-7 rounded-lg bg-sky-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-md shadow-sky-600/30">
            3
          </span>
          <div>
            <h4 className="text-sm font-bold text-white">
              Instant SQL, Data Tables & Visual Charts
            </h4>
            <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">
              BG AI parses your request, runs safe read queries, returns
              formatted tables, renders analytics charts, and maps relationships
              automatically.
            </p>
          </div>
        </div>
      </div>

      {/* 3. PRIMARY ACTION & EDUCATIONAL PILLS */}
      <div className="pt-2 border-t border-white/[0.06] space-y-3">
        {onConnectDatabase && (
          <ClickSpark
            sparkColor="#818cf8"
            sparkCount={8}
            sparkRadius={20}
            className="w-full sm:w-auto"
          >
            <button
              onClick={() => onConnectDatabase("sqlite")}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-semibold shadow-lg shadow-indigo-600/20 transition-all cursor-pointer group"
            >
              <Plug
                size={15}
                className="text-indigo-200 group-hover:rotate-[-10deg] transition-transform"
              />
              <span>Connect the Database</span>
              <ArrowRight
                size={14}
                className="group-hover:translate-x-0.5 transition-transform"
              />
            </button>
          </ClickSpark>
        )}

        <div>
          <p className="text-xs font-semibold text-zinc-400 mb-2 flex items-center gap-1.5">
            <HelpCircle size={13} className="text-zinc-500" />
            <span>Curious to learn? Ask BG AI directly:</span>
          </p>
          <div className="flex flex-wrap gap-2">
            {educationalQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => onSend?.(q)}
                className="px-3 py-1.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/20 text-xs font-medium text-zinc-300 hover:text-white transition-all cursor-pointer"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
