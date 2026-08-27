import type { Message } from "../../types";
import ReactMarkdown from "react-markdown";
import Highlighter from "react-highlight-words";
import SQLBlock from "./SQLBlock";
import ResultTable from "./ResultTable";
import ChartRenderer from "./ChartRenderer";
import ExplanationCard from "./ExplanationCard";
import MermaidChart from "./MermaidChart";
import RelationshipGraph from "./RelationshipGraph";
import AnalyticsDashboard from "../dashboard/AnalyticsDashboard";
import InsertForm from "./InsertForm";
import { Copy, Check, Bot, User, ChevronDown, ChevronRight, BarChart3, Database, Clock, CheckCircle2, XCircle, Table2, Sparkles } from "lucide-react";
import { useState } from "react";

interface Props {
  message: Message;
  searchTerm?: string;
  onSend?: (message: string) => void;
  onInsertSubmit?: (values: Record<string, string>, table: string) => void;
  isTyping?: boolean;
  onConfirm?: (sql: string) => void;
  onCancel?: () => void;
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

export default function MessageBubble({ message, searchTerm, onSend, onInsertSubmit, isTyping, onConfirm, onCancel }: Props) {
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

  return (
    <div
      className={`flex w-full mb-6 transition-all duration-300 opacity-100 ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`max-w-4xl rounded-2xl shadow-md transition-all ${
          isUser
            ? "bg-blue-600 text-white p-5"
            : "dark:bg-zinc-900 bg-white dark:border-zinc-800 border border-gray-200 dark:text-zinc-100 text-gray-900 p-5"
        }`}
      >
        <div className="text-xs opacity-70 mb-3 flex items-center justify-between">
          <span className="flex items-center gap-2">
            {isUser ? (
              <>
                <User size={16} />
                <span>You</span>
              </>
            ) : (
              <>
                <Bot size={16} />
                <span>BG AI</span>
              </>
            )}
          </span>
          {message.timestamp && (
            <span className="text-[10px] opacity-60">{message.timestamp}</span>
          )}
        </div>

        {isUser ? (
          <p className="whitespace-pre-wrap text-[15px]">{message.content}</p>
        ) : (dataAvailable || message.input_request) ? (
          <div>
            {message.result?.pending_confirmation && (
              <div className="mb-4 rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4">
                <div className="flex items-center gap-2 text-yellow-400 font-semibold">
                  ⚠️ Database change requires confirmation
                </div>
                <p className="mt-2 text-sm text-gray-300">
                  This operation will modify your database. Review the SQL before continuing.
                </p>
                {message.sql && (
                  <div className="mt-3">
                    <SQLBlock sql={message.sql} />
                  </div>
                )}
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => onConfirm?.(message.sql || "")}
                    className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500"
                  >
                    ✓ Confirm
                  </button>
                  <button
                    onClick={() => onCancel?.()}
                    className="rounded-lg bg-gray-700 px-4 py-2 text-sm font-medium text-white hover:bg-gray-600"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {message.input_request && (
              <div className="mb-4">
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

            <div className="flex items-center gap-2 mb-4">
              <Sparkles size={18} className="text-blue-600 dark:text-blue-400" />
              <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">Query Result</h3>
              {rowCount > 0 && (
                <span className="ml-auto text-xs font-medium px-2.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                  {rowCount} {rowCount === 1 ? "row" : "rows"}
                </span>
              )}
            </div>

            {rowCount > 0 && (
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-gray-50 dark:bg-zinc-800/50 p-3 text-center">
                  <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{rowCount}</div>
                  <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400 mt-0.5">Records</div>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-gray-50 dark:bg-zinc-800/50 p-3 text-center">
                  <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{columnCount}</div>
                  <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400 mt-0.5">Columns</div>
                </div>
                <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-gray-50 dark:bg-zinc-800/50 p-3 text-center">
                  <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {isSuccess ? (
                      <span className="text-green-600 dark:text-green-400">●</span>
                    ) : (
                      <span className="text-red-600 dark:text-red-400">●</span>
                    )}
                  </div>
                  <div className="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400 mt-0.5">
                    {isSuccess ? "Success" : "Failed"}
                  </div>
                </div>
              </div>
            )}

            {rowCount > 0 && (
              <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 overflow-hidden mb-4">
                <div className="px-4 py-2.5 border-b border-gray-200 dark:border-zinc-700 flex items-center justify-between bg-gray-50 dark:bg-zinc-800/50">
                  <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
                    {columns[0]?.replace(/_/g, " ").toUpperCase() || "DATA"}
                  </span>
                </div>
                <ResultTable result={message.result} />
              </div>
            )}

            {message.chart && (
              <div className="mt-4">
                <ChartRenderer chart={message.chart} />
              </div>
            )}

            {message.diagram && (
              <div className="mt-4">
                {typeof message.diagram === "string" ? (
                  <MermaidChart chart={message.diagram} />
                ) : (
                  <RelationshipGraph graph={message.diagram} />
                )}
              </div>
            )}

            {message.analytics && (
              <div className="mt-4">
                <AnalyticsDashboard data={message.analytics} />
              </div>
            )}

            {message.explanation && (
              <div className="mt-4">
                <ExplanationCard explanation={message.explanation} />
              </div>
            )}

            {(message.sql || result) && (
              <div className="mt-4 rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 overflow-hidden">
                <button
                  onClick={() => setShowTechnical(!showTechnical)}
                  className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors"
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                    <Database size={16} />
                    Technical Details
                  </span>
                  {showTechnical ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
                {showTechnical && (
                  <div className="px-4 pb-4 space-y-3 border-t border-gray-200 dark:border-zinc-700">
                    {message.sql && (
                      <div className="mt-3">
                        <SQLBlock sql={message.sql} />
                      </div>
                    )}
                    {result && (
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div className="rounded-lg border border-gray-200 dark:border-zinc-700 p-3">
                          <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 mb-1">
                            <Clock size={12} />
                            <span>Execution Time</span>
                          </div>
                          <span className="text-gray-900 dark:text-gray-100 font-medium">{result.execution_time_ms ?? 0} ms</span>
                        </div>
                        <div className="rounded-lg border border-gray-200 dark:border-zinc-700 p-3">
                          <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 mb-1">
                            <BarChart3 size={12} />
                            <span>Rows Returned</span>
                          </div>
                          <span className="text-gray-900 dark:text-gray-100 font-medium">{result.rows_returned ?? 0}</span>
                        </div>
                        <div className="rounded-lg border border-gray-200 dark:border-zinc-700 p-3">
                          <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 mb-1">
                            <Database size={12} />
                            <span>Database</span>
                          </div>
                          <span className="text-gray-900 dark:text-gray-100 font-medium">SQLite</span>
                        </div>
                        <div className="rounded-lg border border-gray-200 dark:border-zinc-700 p-3">
                          <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 mb-1">
                            {isSuccess ? <CheckCircle2 size={12} className="text-green-600" /> : <XCircle size={12} className="text-red-600" />}
                            <span>Status</span>
                          </div>
                          <span className={`font-medium ${isSuccess ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
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
              <div className="mt-4">
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">💡 Suggested Follow-up Questions</p>
                <div className="flex flex-wrap gap-2">
                  {message.followups.map((item, i) => (
                    <button
                      key={i}
                      onClick={() => onSend?.(item)}
                      className="px-3 py-2 rounded-full bg-zinc-100 dark:bg-zinc-800 hover:bg-blue-600 dark:hover:bg-blue-600 transition text-sm text-gray-900 dark:text-gray-100"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={copyResponse}
              className="mt-4 text-sm dark:bg-zinc-800 bg-gray-200 dark:hover:bg-zinc-700 hover:bg-gray-300 px-3 py-2 rounded-lg flex items-center gap-2 dark:text-white text-gray-900"
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
              {copied ? "Copied" : "Copy Response"}
            </button>
          </div>
        ) : (
          <div className="relative">
            <div className="whitespace-pre-wrap text-[15px]">
              <ReactMarkdown
                components={{
                  h1: ({ children }) => <h1 className="text-2xl font-extrabold mt-4 mb-3 text-gray-900 dark:text-white">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-xl font-bold mt-3 mb-2 text-gray-900 dark:text-gray-100">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-lg font-bold mt-2 mb-1 text-gray-900 dark:text-gray-200">{children}</h3>,
                  p: ({ children }) => {
                    const content =
                      typeof children === "string" ? (
                        <Highlighter
                          searchWords={searchTerm ? [searchTerm] : []}
                          autoEscape
                          textToHighlight={children}
                          highlightStyle={{
                            backgroundColor: "#facc15",
                            color: "#000",
                            borderRadius: "3px",
                            padding: "1px 2px",
                          }}
                        />
                      ) : (
                        children
                      );
                    return <p className="mb-3 text-gray-800 dark:text-gray-200 leading-relaxed">{content}</p>;
                  },
                  strong: ({ children }) => <strong className="font-semibold text-gray-900 dark:text-white">{children}</strong>,
                  em: ({ children }) => <em className="italic text-gray-800 dark:text-gray-300">{children}</em>,
                  code: ({ children }) => <code className="text-gray-900 dark:text-gray-100 bg-gray-100 dark:bg-gray-800/60 px-1.5 py-0.5 rounded text-sm">{children}</code>,
                  pre: ({ children }) => <pre className="bg-[#111827] text-gray-100 p-4 rounded-xl overflow-x-auto mb-4 text-sm leading-relaxed">{children}</pre>,
                  ul: ({ children }) => <ul className="list-disc list-inside mb-3 text-gray-800 dark:text-gray-200 space-y-1.5 pl-2">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal list-inside mb-3 text-gray-800 dark:text-gray-200 space-y-1.5 pl-2">{children}</ol>,
                  li: ({ children }) => <li className="mb-1">{children}</li>,
                  blockquote: ({ children }) => {
                    const text = String(children).toLowerCase();
                    let className = "pl-4 pr-3 py-3 rounded-r-lg my-3 italic text-gray-800 dark:text-gray-200";
                    if (text.includes("💡") || text.includes("tip")) className += " border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950/40";
                    else if (text.includes("✅") || text.includes("success")) className += " border-l-4 border-green-500 bg-green-50 dark:bg-green-950/40";
                    else if (text.includes("⚠") || text.includes("warning")) className += " border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-950/40";
                    else if (text.includes("❌") || text.includes("error")) className += " border-l-4 border-red-500 bg-red-50 dark:bg-red-950/40";
                    else className += " border-l-4 border-gray-500 bg-gray-50 dark:bg-zinc-800/40";
                    return <blockquote className={className}>{children}</blockquote>;
                  },
                  table: ({ children }) => (
                    <div className="overflow-auto mb-4 rounded-xl border border-gray-200 dark:border-gray-700">
                      <table className="min-w-full">{children}</table>
                    </div>
                  ),
                  thead: ({ children }) => <thead className="bg-blue-600 text-white">{children}</thead>,
                  tbody: ({ children }) => <tbody className="divide-y divide-gray-200 dark:divide-gray-700">{children}</tbody>,
                  tr: ({ children }) => <tr className="hover:bg-gray-50 dark:hover:bg-zinc-800/50 transition-colors">{children}</tr>,
                  th: ({ children }) => <th className="px-4 py-3 text-left text-sm font-semibold border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white">{children}</th>,
                  td: ({ children }) => <td className="px-4 py-3 text-sm text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-700">{children}</td>,
                  hr: () => <hr className="border-gray-200 dark:border-gray-700 my-6" />,
                  a: ({ children, href }) => (
                    <a href={href} className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 underline transition-colors">
                      {children}
                    </a>
                  ),
                }}
              >
                {message.content}
              </ReactMarkdown>
              {isTyping && (
                <span className="inline-block w-2 h-5 ml-1 bg-blue-400 animate-pulse align-middle" />
              )}
            </div>
            <button
              onClick={copyResponse}
              className="mt-4 text-sm dark:bg-zinc-800 bg-gray-200 dark:hover:bg-zinc-700 hover:bg-gray-300 px-3 py-2 rounded-lg flex items-center gap-2 dark:text-white text-gray-900"
            >
              {copied ? <Check size={16} /> : <Copy size={16} />}
              {copied ? "Copied" : "Copy Response"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
