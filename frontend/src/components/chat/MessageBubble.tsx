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
import { Copy, Check, Bot, User } from "lucide-react";
import { useState } from "react";

interface Props {
  message: Message;
  searchTerm?: string;
  onSend?: (message: string) => void;
  isTyping?: boolean;
}

export default function MessageBubble({ message, searchTerm, onSend, isTyping }: Props) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const copyResponse = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const getCalloutStyles = (children: any) => {
    const text = String(children).toLowerCase();
    if (text.includes("💡") || text.includes("tip")) {
      return "border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950/40";
    }
    if (text.includes("✅") || text.includes("success")) {
      return "border-l-4 border-green-500 bg-green-50 dark:bg-green-950/40";
    }
    if (text.includes("⚠") || text.includes("warning")) {
      return "border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-950/40";
    }
    if (text.includes("❌") || text.includes("error")) {
      return "border-l-4 border-red-500 bg-red-50 dark:bg-red-950/40";
    }
    return "border-l-4 border-gray-500 bg-gray-50 dark:bg-zinc-800/40";
  };

  return (
    <div
      className={`flex w-full mb-6 transition-all duration-300 opacity-100 ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`max-w-4xl rounded-2xl p-5 shadow-md transition-all ${
          isUser
            ? "bg-blue-600 text-white"
            : "dark:bg-zinc-900 bg-white dark:border-zinc-800 border border-gray-200 dark:text-zinc-100 text-gray-900"
        }`}
      >
        <div className="text-xs opacity-70 mb-2 flex items-center justify-between">
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

        <div className="whitespace-pre-wrap text-[15px]">
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="relative">
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
                  blockquote: ({ children }) => (
                    <blockquote className={`${getCalloutStyles(children)} pl-4 pr-3 py-3 rounded-r-lg my-3 italic text-gray-800 dark:text-gray-200`}>
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => <div className="overflow-auto mb-4"><table className="min-w-full border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">{children}</table></div>,
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
          )}
        </div>

        {!isUser && (() => {
          const hasData = !!(
            message.sql ||
            message.chart ||
            message.diagram ||
            message.analytics ||
            (message.result?.rows && message.result.rows.length > 0)
          );

          return (
            <>
              {message.sql && (
                <div className="mt-5">
                  <SQLBlock sql={message.sql} />
                </div>
              )}

              {message.result?.success && (message.result?.rows?.length || 0) > 0 && (
                <div className="mt-5">
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

              {message.explanation && (() => {
                const hasData = !!(
                  message.sql ||
                  message.chart ||
                  message.diagram ||
                  message.analytics ||
                  (message.result?.rows && message.result.rows.length > 0)
                );
                return hasData ? (
                  <div className="mt-5">
                    <ExplanationCard
                      explanation={message.explanation}
                    />
                  </div>
                ) : null;
              })()}

              {(() => {
                const hasData = !!(
                  message.sql ||
                  message.chart ||
                  message.diagram ||
                  message.analytics ||
                  (message.result?.rows && message.result.rows.length > 0)
                );
                return hasData && message.result?.success ? (
                  <div className="mt-4 rounded-lg border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900/60 p-4">
                    <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">⚡ Query Statistics</p>
                    <div className="grid grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-400">
                      <div>
                        <span className="block text-gray-500 dark:text-gray-400">Execution Time</span>
                        <span className="text-gray-900 dark:text-gray-100 font-medium">{message.result.execution_time_ms ?? 0} ms</span>
                      </div>
                      <div>
                        <span className="block text-gray-500 dark:text-gray-400">Rows Returned</span>
                        <span className="text-gray-900 dark:text-gray-100 font-medium">{message.result.rows_returned ?? 0}</span>
                      </div>
                      <div>
                        <span className="block text-gray-500 dark:text-gray-400">Database</span>
                        <span className="text-gray-900 dark:text-gray-100 font-medium">SQLite</span>
                      </div>
                      <div>
                        <span className="block text-gray-500 dark:text-gray-400">Status</span>
                        <span className="text-green-600 dark:text-green-400 font-medium">Success</span>
                      </div>
                    </div>
                  </div>
                ) : null;
              })()}

              {message.followups && message.followups.length > 0 && (
                <div className="mt-5">
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
           </>
         );
       })()}
      </div>
    </div>
  );
}
