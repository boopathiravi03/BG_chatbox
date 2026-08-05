import { AnimatePresence } from "framer-motion";
import ChatMessage from "./ChatMessage";

interface Message {
  role: "user" | "assistant";
  content: string;
  sql?: string;
  result?: any;
  explanation?: string;
  chart?: any;
  diagram?: string | null;
}

export default function ChatHistory({ messages }: { messages: Message[] }) {
  if (messages.length === 0) return null;

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-4xl mx-auto">
        <AnimatePresence>
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
