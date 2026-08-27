import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  explanation: string;
}

export default function ExplanationCard({ explanation }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 overflow-hidden">
      <div className="px-4 py-2 border-b border-gray-200 dark:border-zinc-700 flex items-center gap-2">
        <span className="text-sm">🧠</span>
        <h3 className="text-sm font-semibold text-blue-600 dark:text-blue-400">
          AI Explanation
        </h3>
      </div>

      <div className="p-4 text-gray-700 dark:text-zinc-300 leading-7 prose prose-sm dark:prose-invert max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2 text-gray-900 dark:text-white">{children}</h1>,
            h2: ({ children }) => <h2 className="text-lg font-semibold mt-3 mb-2 text-gray-900 dark:text-gray-100">{children}</h2>,
            h3: ({ children }) => <h3 className="text-base font-semibold mt-2 mb-1 text-gray-900 dark:text-gray-200">{children}</h3>,
            p: ({ children }) => <p className="mb-3 text-gray-800 dark:text-gray-200 leading-relaxed">{children}</p>,
            strong: ({ children }) => <strong className="font-semibold text-gray-900 dark:text-white">{children}</strong>,
            em: ({ children }) => <em className="italic text-gray-800 dark:text-gray-300">{children}</em>,
            ul: ({ children }) => <ul className="list-disc list-inside mb-3 text-gray-800 dark:text-gray-200 space-y-1 pl-2">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside mb-3 text-gray-800 dark:text-gray-200 space-y-1 pl-2">{children}</ol>,
            li: ({ children }) => <li className="mb-1">{children}</li>,
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
            code: ({ children }) => <code className="text-gray-900 dark:text-gray-100 bg-gray-100 dark:bg-gray-800/60 px-1.5 py-0.5 rounded text-sm">{children}</code>,
            pre: ({ children }) => <pre className="bg-[#111827] text-gray-100 p-4 rounded-xl overflow-x-auto mb-4 text-sm leading-relaxed">{children}</pre>,
            blockquote: ({ children }) => (
              <blockquote className="pl-4 pr-3 py-3 rounded-r-lg my-3 italic text-gray-800 dark:text-gray-200 border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950/40">
                {children}
              </blockquote>
            ),
          }}
        >
          {explanation}
        </ReactMarkdown>
      </div>
    </div>
  );
}
