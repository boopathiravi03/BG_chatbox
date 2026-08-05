import React from "react";
import ReactMarkdown from "react-markdown";

import SQLBlock from "./SQLBlock";
import ResultTable from "./ResultTable";
import ChartRenderer from "./ChartRenderer";
import MermaidDiagram from "./MermaidDiagram";

import type { Message } from "../../types";

interface Props {
  message: Message;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={`mb-6 flex ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      <div
        className={`max-w-5xl rounded-xl p-4 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-zinc-900 text-zinc-100"
        }`}
      >
        <ReactMarkdown>
          {message.content}
        </ReactMarkdown>

        {!isUser && (
          <>
            <SQLBlock sql={message.sql} />

            <ResultTable result={message.result} />

            <ChartRenderer chart={message.chart} />

            <MermaidDiagram
              diagram={(message as any).diagram}
            />
          </>
        )}
      </div>
    </div>
  );
}
