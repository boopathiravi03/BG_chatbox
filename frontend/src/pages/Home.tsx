import { useState, useEffect, useRef } from "react";
import MainLayout from "../layouts/MainLayout";
import ChatArea from "../components/chat/ChatArea";
import type { Message, ChatSession } from "../types/index";
import { sendMessage } from "../services/api";

const SUGGESTIONS = [
  "Show all customers",
  "Monthly sales",
  "Revenue chart",
  "ER Diagram",
  "Show products",
  "Top customers",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"ready" | "thinking" | "executing" | "done" | "error">("ready");
  const loadedRef = useRef(false);

  useEffect(() => {
    const saved = localStorage.getItem("bgai_sessions");

    if (saved) {
      const parsed = JSON.parse(saved) as ChatSession[];
      setSessions(parsed);

      const id = localStorage.getItem("bgai_active");

      if (id) {
        const chat = parsed.find((s) => s.id === id);

        if (chat) {
          setMessages(chat.messages);
          setActiveSessionId(chat.id);
        }
      }
    }

    loadedRef.current = true;
  }, []);

  useEffect(() => {
    if (!loadedRef.current) return;

    localStorage.setItem("bgai_sessions", JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem("bgai_active", activeSessionId);
    }
  }, [activeSessionId]);

  const handleNewChat = () => {
    setMessages([]);
    setActiveSessionId(null);
    setStatus("ready");
  };

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setLoading(true);
    setStatus("thinking");

    try {
      setStatus("executing");
      const data = await sendMessage(content);

      const assistantMessage: Message = {
        role: "assistant",
        content: data.explanation || "Here are the results.",
        sql: data.generated_sql,
        result: data.result,
        explanation: data.explanation,
        chart: data.chart,
        diagram: data.diagram,
        analytics: data.analytics,
        followups: data.followups,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      const completedMessages = [...nextMessages, assistantMessage];
      setMessages(completedMessages);
      setStatus("done");

      if (activeSessionId === null) {
        const newSession: ChatSession = {
          id: Date.now().toString(),
          title: content,
          messages: completedMessages,
          createdAt: Date.now(),
        };
        setSessions((prev) => [newSession, ...prev]);
        setActiveSessionId(newSession.id);
      } else {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSessionId
              ? { ...s, messages: completedMessages }
              : s
          )
        );
      }
    } catch (error) {
      const errorMessage: Message = {
        role: "assistant",
        content: "Sorry, something went wrong. Please try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setStatus("error");
    } finally {
      setLoading(false);
      setTimeout(() => setStatus("ready"), 3000);
    }
  };

  const handleHistoryClick = (session: ChatSession) => {
    setActiveSessionId(session.id);
    setMessages(session.messages);
  };

  const [uploadVersion, setUploadVersion] = useState(0);

  const handleUploadComplete = () => {
    setUploadVersion((prev) => prev + 1);
  };

  return (
    <MainLayout
      status={status}
      onNewChat={handleNewChat}
      sessions={sessions}
      activeSessionId={activeSessionId}
      onSessionClick={handleHistoryClick}
      onUploadComplete={handleUploadComplete}
    >
      <ChatArea
        messages={messages}
        loading={loading}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSend={handleSend}
        onSessionClick={handleHistoryClick}
        uploadVersion={uploadVersion}
      />
    </MainLayout>
  );
}
