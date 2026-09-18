import type { Message } from "../../types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Highlighter from "react-highlight-words";
import SQLBlock from "./SQLBlock";
import ResultTable from "./ResultTable";
import ChartRenderer from "./ChartRenderer";
import ExplanationCard from "./ExplanationCard";
import MermaidChart from "./MermaidChart";
import RelationshipGraph from "./RelationshipGraph";
import AnalyticsDashboard from "../dashboard/AnalyticsDashboard";
import InsertForm from "./InsertForm";
import DatabaseOnboardingCard from "./DatabaseOnboardingCard";
import {
  Copy,
  Check,
  Bot,
  User,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Database,
  Clock,
  CheckCircle2,
  XCircle,
  Sparkles,
  AlertTriangle,
  Plug,
  ArrowRight,
} from "lucide-react";
import { useState } from "react";
import { motion } from "framer-motion";
import { messageBubbleVariants } from "../../lib/motion";
import ClickSpark from "../reactbits/ClickSpark";

interface Props {
  message: Message;
  searchTerm?: string;
  onSend?: (message: string) => void;
  onInsertSubmit?: (values: Record<string, string>, table: string) => void;
  isTyping?: boolean;
  onConfirm?: (sql: string) => void;
  onCancel?: () => void;
  onConnectDatabase?: (type?: "sqlite" | "mysql" | "postgres") => void;
}

function hasData(message: Message) {
  return !!(
    message.sql ||
    message.chart ||
    message.diagram ||
    message.analytics ||
    (message.result?.rows && message.result.rows.length > 0)
  );
}

export default function MessageBubble({
  message,
  searchTerm,
  onSend,
  onInsertSubmit,
  isTyping,
  onConfirm,
  onCancel,
  onConnectDatabase,
}: Props) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [showTechnical, setShowTechnical] = useState(false);

  const copyResponse = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const dataAvailable = hasData(message);
  const result = message.result;
  const rows = result?.rows || [];
  const columns = result?.columns || [];
  const isSuccess = result?.success !== false;
  const rowCount = rows.length;
  const columnCount = columns.length;

  const isIntroOrNoDb =
    !isUser &&
    !dataAvailable &&
    !message.requires_confirmation &&
    !message.input_request &&
    (message.content
      .toLowerCase()
      .includes("friendly ai-powered database assistant") ||
      message.content
        .toLowerCase()
        .includes("friendly, intelligent ai-powered database assistant") ||
      message.content.toLowerCase().includes("welcome to bg ai") ||
      (message.content.toLowerCase().includes("no database") &&
        (message.content.toLowerCase().includes("show the database") ||
          message.content.toLowerCase().includes("supported engines") ||
          message.content.toLowerCase().includes("connect a database") ||
          message.content.toLowerCase().includes("let's get started") ||
          message.content.toLowerCase().includes("connect the database"))));

  return (
    <motion.div
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}
      variants={messageBubbleVariants}
      initial="hidden"
      animate="visible"
    >
      <div
        className={`rounded-2xl transition-all ${
          isUser
            ? "max-w-[88%] sm:max-w-2xl md:max-w-3xl bg-[#1c1c22] text-zinc-100 border border-white/[0.08] px-4.5 py-3 sm:px-5 sm:py-3.5 shadow-md shadow-black/20"
            : "w-full bg-[#121215] text-zinc-100 border border-white/[0.07] p-4.5 sm:p-6 shadow-lg shadow-black/30"
        }`}
      >
        {/* Bubble Header */}
        <div className="text-xs sm:text-sm text-zinc-400 mb-3 flex items-center justify-between gap-4 border-b border-white/[0.04] pb-2">
          <span className="flex items-center gap-2 font-semibold">
            {isUser ? (
              <>
                <User size={15} className="text-zinc-400" />
                <span className="text-zinc-200">You</span>
              </>
            ) : (
              <>
                <div className="flex items-center justify-center w-5 h-5 rounded-md bg-indigo-500/20 text-indigo-400">
                  <Bot size={13} />
                </div>
                <span className="text-white font-bold tracking-tight">
                  BG AI
                </span>
              </>
            )}
          </span>
          {message.timestamp && (
            <span className="text-xs text-zinc-400 font-mono">
              {message.timestamp}
            </span>
          )}
        </div>

        {isUser ? (
          <p className="whitespace-pre-wrap text-[15px] sm:text-base leading-relaxed text-zinc-100">
            {message.content}
          </p>
        ) : dataAvailable ||
          message.input_request ||
          message.requires_confirmation ? (
          <div>
            {/* Confirmation Alert */}
            {message.requires_confirmation && (
              <div className="mb-5 rounded-2xl border border-amber-500/30 bg-amber-500/[0.04] p-4 sm:p-5">
                <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm sm:text-base">
                  <AlertTriangle size={17} />
                  <span>Database Modification Requires Confirmation</span>
                </div>
                <p className="mt-2 text-xs sm:text-sm text-zinc-200 leading-relaxed">
                  {message.operation === "delete"
                    ? "The following record(s) will be permanently deleted from the database."
                    : message.operation === "update"
                      ? "The specified record(s) will be modified."
                      : "A new record will be inserted into the database."}
                </p>
                {message.affected_rows_preview !== undefined && (
                  <div className="mt-3 rounded-xl bg-black/40 p-3 text-xs sm:text-sm text-zinc-200">
                    <span>Matching records: </span>
                    <span className="font-bold text-amber-400 text-sm">
                      {message.affected_rows_preview}
                    </span>
                  </div>
                )}
                {message.sql && (
                  <div className="mt-3.5">
                    <SQLBlock sql={message.sql} />
                  </div>
                )}
                <div className="mt-4 flex items-center gap-2.5">
                  <button
                    onClick={() => onConfirm?.(message.sql || "")}
                    className="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs sm:text-sm font-semibold text-white transition-colors shadow-sm"
                  >
                    Confirm {message.operation || "Execution"}
                  </button>
                  <button
                    onClick={() => onCancel?.()}
                    className="rounded-xl bg-white/[0.06] hover:bg-white/10 px-4 py-2 text-xs sm:text-sm font-medium text-zinc-300 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {message.input_request && (
              <div className="mb-5">
                <InsertForm
                  title={message.input_request.title}
                  message={message.input_request.message}
                  fields={message.input_request.fields}
                  onSubmit={(values) => {
                    onInsertSubmit?.(values, message.input_request!.table);
                  }}
                  onCancel={onCancel}
                />
              </div>
            )}

            <div className="flex items-center gap-2 mb-3.5">
              <Sparkles size={16} className="text-indigo-400" />
              <h3 className="text-base font-semibold text-zinc-100">
                Query Result
              </h3>
              {rowCount > 0 && (
                <span className="ml-auto text-xs font-mono px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.06] text-zinc-300">
                  {rowCount} {rowCount === 1 ? "row" : "rows"}
                </span>
              )}
            </div>

            {rowCount > 0 && (
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-center">
                  <div className="text-xl sm:text-2xl font-bold text-white">
                    {rowCount}
                  </div>
                  <div className="text-xs uppercase tracking-wider text-zinc-400 mt-0.5 font-medium">
                    Records
                  </div>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-center">
                  <div className="text-xl sm:text-2xl font-bold text-white">
                    {columnCount}
                  </div>
                  <div className="text-xs uppercase tracking-wider text-zinc-400 mt-0.5 font-medium">
                    Columns
                  </div>
                </div>
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-center">
                  <div className="text-xl sm:text-2xl font-bold">
                    {isSuccess ? (
                      <span className="text-emerald-400">✓</span>
                    ) : (
                      <span className="text-rose-400">✕</span>
                    )}
                  </div>
                  <div className="text-xs uppercase tracking-wider text-zinc-400 mt-0.5 font-medium">
                    {isSuccess ? "Success" : "Failed"}
                  </div>
                </div>
              </div>
            )}

            {rowCount > 0 && (
              <div className="rounded-xl border border-white/[0.06] bg-[#0e0e11] overflow-hidden mb-5">
                <ResultTable result={message.result} />
              </div>
            )}

            {message.chart && (
              <div className="mt-5">
                <ChartRenderer chart={message.chart} />
              </div>
            )}

            {message.diagram && (
              <div className="mt-5">
                {typeof message.diagram === "string" ? (
                  <MermaidChart chart={message.diagram} />
                ) : (
                  <RelationshipGraph graph={message.diagram} />
                )}
              </div>
            )}

            {message.analytics && (
              <div className="mt-5">
                <AnalyticsDashboard data={message.analytics} />
              </div>
            )}

            {message.explanation && (
              <div className="mt-5">
                <ExplanationCard explanation={message.explanation} />
              </div>
            )}

            {(message.sql || result) && (
              <div className="mt-5 rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                <button
                  onClick={() => setShowTechnical(!showTechnical)}
                  className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-white/[0.03] transition-colors"
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
                    <Database size={15} className="text-indigo-400" />
                    Technical Details & Execution Profile
                  </span>
                  {showTechnical ? (
                    <ChevronDown size={15} className="text-zinc-400" />
                  ) : (
                    <ChevronRight size={15} className="text-zinc-400" />
                  )}
                </button>
                {showTechnical && (
                  <div className="px-4 pb-4 space-y-3.5 border-t border-white/[0.06]">
                    {message.sql && (
                      <div className="mt-3.5">
                        <SQLBlock sql={message.sql} />
                      </div>
                    )}
                    {result && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs sm:text-sm pt-1">
                        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                          <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs">
                            <Clock size={13} />
                            <span>Execution</span>
                          </div>
                          <span className="text-zinc-100 font-mono font-semibold">
                            {result.execution_time_ms ?? 0} ms
                          </span>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                          <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs">
                            <BarChart3 size={13} />
                            <span>Rows</span>
                          </div>
                          <span className="text-zinc-100 font-mono font-semibold">
                            {result.rows_returned ?? 0}
                          </span>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                          <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs">
                            <Database size={13} />
                            <span>Engine</span>
                          </div>
                          <span className="text-zinc-100 font-semibold">
                            Relational
                          </span>
                        </div>
                        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                          <div className="flex items-center gap-1.5 text-zinc-400 mb-1 text-xs">
                            {isSuccess ? (
                              <CheckCircle2
                                size={13}
                                className="text-emerald-400"
                              />
                            ) : (
                              <XCircle size={13} className="text-rose-400" />
                            )}
                            <span>State</span>
                          </div>
                          <span
                            className={`font-semibold ${isSuccess ? "text-emerald-400" : "text-rose-400"}`}
                          >
                            {isSuccess ? "Success" : "Failed"}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {message.followups && message.followups.length > 0 && (
              <div className="mt-5">
                <p className="text-xs sm:text-sm font-semibold text-zinc-300 mb-2.5">
                  Suggested follow-ups
                </p>
                <div className="flex flex-wrap gap-2">
                  {message.followups.map((item, i) => (
                    <button
                      key={i}
                      onClick={() => onSend?.(item)}
                      className="px-3.5 py-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-xs sm:text-sm font-medium text-zinc-200 hover:text-white transition-colors"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={copyResponse}
              className="mt-5 text-xs sm:text-sm font-medium bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] px-3.5 py-2 rounded-xl flex items-center gap-2 text-zinc-300 hover:text-white transition-colors"
            >
              {copied ? (
                <Check size={14} className="text-emerald-400" />
              ) : (
                <Copy size={14} />
              )}
              <span>{copied ? "Copied" : "Copy Response"}</span>
            </button>
          </div>
        ) : isIntroOrNoDb ? (
          <div>
            <DatabaseOnboardingCard
              onConnectDatabase={onConnectDatabase}
              onSend={onSend}
            />

            <button
              onClick={copyResponse}
              className="mt-5 text-xs sm:text-sm font-medium bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] px-3.5 py-2 rounded-xl flex items-center gap-2 text-zinc-300 hover:text-white transition-colors cursor-pointer"
            >
              {copied ? (
                <Check size={14} className="text-emerald-400" />
              ) : (
                <Copy size={14} />
              )}
              <span>{copied ? "Copied" : "Copy Response"}</span>
            </button>
          </div>
        ) : (
          <div className="relative">
            <div className="text-[15px] sm:text-base leading-relaxed text-zinc-200">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => (
                    <h1 className="text-xl sm:text-2xl font-bold mt-4 mb-2.5 text-white">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-lg sm:text-xl font-semibold mt-3 mb-2 text-zinc-100">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base sm:text-lg font-semibold mt-2.5 mb-1 text-zinc-100">
                      {children}
                    </h3>
                  ),
                  p: ({ children }) => {
                    const content =
                      typeof children === "string" ? (
                        <Highlighter
                          searchWords={searchTerm ? [searchTerm] : []}
                          autoEscape
                          textToHighlight={children}
                          highlightStyle={{
                            backgroundColor: "rgba(99, 102, 241, 0.4)",
                            color: "#fff",
                            borderRadius: "3px",
                            padding: "1px 2px",
                          }}
                        />
                      ) : (
                        children
                      );
                    return (
                      <p className="mb-3 leading-relaxed text-zinc-200">
                        {content}
                      </p>
                    );
                  },
                  table: ({ children }) => (
                    <div className="my-4 overflow-x-auto rounded-xl border border-white/10 bg-white/[0.02] shadow-sm">
                      <table className="w-full text-left text-xs sm:text-sm border-collapse">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-white/[0.05] border-b border-white/10 text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
                      {children}
                    </thead>
                  ),
                  th: ({ children }) => (
                    <th className="px-4 py-2.5 font-semibold text-zinc-200">
                      {children}
                    </th>
                  ),
                  tbody: ({ children }) => (
                    <tbody className="divide-y divide-white/[0.04]">
                      {children}
                    </tbody>
                  ),
                  tr: ({ children }) => (
                    <tr className="hover:bg-white/[0.02] transition-colors">
                      {children}
                    </tr>
                  ),
                  td: ({ children }) => (
                    <td className="px-4 py-2.5 text-zinc-300">{children}</td>
                  ),
                  strong: ({ children }) => {
                    const text = String(children);
                    if (
                      onConnectDatabase &&
                      (text.toLowerCase().includes("connect the database") ||
                        text.toLowerCase().includes("connect database"))
                    ) {
                      return (
                        <button
                          type="button"
                          onClick={() => onConnectDatabase()}
                          className="inline-flex items-center gap-1.5 px-2 py-0.5 mx-1 rounded-md bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/40 text-indigo-200 hover:text-white font-semibold text-xs sm:text-sm transition-all align-middle cursor-pointer"
                          title="Open Database Connection Options"
                        >
                          <Plug size={12} className="text-indigo-400" />
                          <span>{children}</span>
                        </button>
                      );
                    }
                    return (
                      <strong className="font-semibold text-white">
                        {children}
                      </strong>
                    );
                  },
                  em: ({ children }) => (
                    <em className="italic text-zinc-200">{children}</em>
                  ),
                  code: ({ children }) => (
                    <code className="text-indigo-300 bg-white/[0.06] px-1.5 py-0.5 rounded text-xs sm:text-sm font-mono">
                      {children}
                    </code>
                  ),
                  pre: ({ children }) => (
                    <pre className="bg-[#09090b] text-zinc-200 p-3.5 rounded-xl overflow-x-auto mb-3.5 text-xs sm:text-sm border border-white/[0.08] font-mono leading-relaxed">
                      {children}
                    </pre>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside mb-3 text-zinc-200 space-y-1.5 pl-1">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="my-3 space-y-2.5 pl-0 list-none">
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li className="flex items-start gap-2.5 text-sm sm:text-base text-zinc-200 leading-relaxed">
                      <span className="w-5 h-5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                        •
                      </span>
                      <div className="flex-1 min-w-0">{children}</div>
                    </li>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="pl-4 pr-3 py-2.5 rounded-r-lg my-3 italic text-zinc-200 border-l-2 border-indigo-500 bg-indigo-500/[0.06] text-sm">
                      {children}
                    </blockquote>
                  ),
                  a: ({ children, href }) => (
                    <a
                      href={href}
                      className="text-indigo-400 hover:text-indigo-300 underline transition-colors font-medium"
                    >
                      {children}
                    </a>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
              {isTyping && (
                <span className="inline-block w-2 h-4.5 ml-1 bg-indigo-400 animate-pulse align-middle" />
              )}
            </div>

            {/* If the message mentions connecting a database and onConnectDatabase is available, provide a clean action button */}
            {onConnectDatabase &&
              message.content.toLowerCase().includes("connect") &&
              message.content.toLowerCase().includes("database") && (
                <div className="mt-4 pt-3.5 border-t border-white/[0.06]">
                  <ClickSpark
                    sparkColor="#818cf8"
                    sparkCount={6}
                    sparkRadius={18}
                  >
                    <button
                      type="button"
                      onClick={() => onConnectDatabase()}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600/25 hover:bg-indigo-600/35 border border-indigo-500/40 text-xs sm:text-sm font-semibold text-indigo-200 hover:text-white transition-all shadow-md shadow-indigo-950/40 cursor-pointer"
                      title="Open Database Connection Options"
                    >
                      <Plug size={14} className="text-indigo-400" />
                      <span>Connect the Database</span>
                      <ArrowRight size={13} className="text-indigo-400" />
                    </button>
                  </ClickSpark>
                </div>
              )}

            {message.followups && message.followups.length > 0 && (
              <div className="mt-4">
                <p className="text-xs sm:text-sm font-semibold text-zinc-300 mb-2">
                  Suggested follow-ups
                </p>
                <div className="flex flex-wrap gap-2">
                  {message.followups.map((item, i) => (
                    <button
                      key={i}
                      onClick={() => onSend?.(item)}
                      className="px-3 py-1.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] text-xs sm:text-sm font-medium text-zinc-200 hover:text-white transition-colors"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={copyResponse}
              className="mt-4 text-xs sm:text-sm font-medium bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] px-3.5 py-2 rounded-xl flex items-center gap-2 text-zinc-300 hover:text-white transition-colors cursor-pointer"
            >
              {copied ? (
                <Check size={14} className="text-emerald-400" />
              ) : (
                <Copy size={14} />
              )}
              <span>{copied ? "Copied" : "Copy Response"}</span>
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
}
