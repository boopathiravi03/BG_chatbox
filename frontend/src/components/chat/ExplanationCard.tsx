import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles } from "lucide-react";

interface Props {
  explanation: string;
}

export default function ExplanationCard({ explanation }: Props) {
  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#0e0e11] overflow-hidden shadow-md">
      <div className="px-5 py-3 border-b border-white/[0.06] flex items-center gap-2 bg-white/[0.02]">
        <Sparkles size={16} className="text-indigo-400" />
        <h3 className="text-sm font-semibold text-white">
          Analysis & Explanation
        </h3>
      </div>

      <div className="p-5 text-zinc-200 leading-relaxed text-sm sm:text-[15px] prose prose-invert max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => (
              <h1 className="text-xl font-bold mt-4 mb-2 text-white">
                {children}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-lg font-bold mt-3 mb-2 text-zinc-100">
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-base font-semibold mt-2 mb-1 text-zinc-200">
                {children}
              </h3>
            ),
            p: ({ children }) => (
              <p className="mb-3 leading-relaxed text-zinc-200">{children}</p>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-white">{children}</strong>
            ),
            em: ({ children }) => (
              <em className="italic text-zinc-200">{children}</em>
            ),
            ul: ({ children }) => (
              <ul className="list-disc list-inside mb-3 text-zinc-200 space-y-1.5 pl-1">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal list-inside mb-3 text-zinc-200 space-y-1.5 pl-1">
                {children}
              </ol>
            ),
            li: ({ children }) => <li className="mb-0.5">{children}</li>,
            table: ({ children }) => (
              <div className="overflow-x-auto mb-3.5 rounded-xl border border-white/[0.08]">
                <table className="min-w-full text-sm">{children}</table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-white/[0.05] text-zinc-200 border-b border-white/[0.08]">
                {children}
              </thead>
            ),
            tbody: ({ children }) => (
              <tbody className="divide-y divide-white/[0.04]">{children}</tbody>
            ),
            tr: ({ children }) => (
              <tr className="hover:bg-white/[0.02] transition-colors">
                {children}
              </tr>
            ),
            th: ({ children }) => (
              <th className="px-3.5 py-2.5 text-left font-semibold text-zinc-200">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-3.5 py-2.5 text-zinc-200 font-mono text-xs sm:text-sm">
                {children}
              </td>
            ),
            hr: () => <hr className="border-white/[0.08] my-4" />,
            a: ({ children, href }) => (
              <a
                href={href}
                className="text-indigo-400 hover:text-indigo-300 underline transition-colors font-medium"
              >
                {children}
              </a>
            ),
            code: ({ children }) => (
              <code className="text-indigo-300 bg-white/[0.06] px-1.5 py-0.5 rounded font-mono text-xs sm:text-sm">
                {children}
              </code>
            ),
            pre: ({ children }) => (
              <pre className="bg-black/50 text-zinc-200 p-3.5 rounded-xl overflow-x-auto mb-3 font-mono text-xs sm:text-sm border border-white/[0.06]">
                {children}
              </pre>
            ),
            blockquote: ({ children }) => (
              <blockquote className="pl-4 pr-3 py-2.5 rounded-r-lg my-2.5 italic text-zinc-200 border-l-2 border-indigo-500 bg-indigo-500/[0.06] text-sm">
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
