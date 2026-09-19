import { useState, useEffect, useRef } from "react";
import MainLayout from "../layouts/MainLayout";
import ChatArea from "../components/chat/ChatArea";
import type { Message, ChatSession } from "../types/index";
import {
  sendMessage,
  confirmQuery,
  sendInsert,
  disconnectDatabase,
  getDatabaseInfo,
  getDatabaseType,
} from "../services/api";
import DatabasePopup from "../components/chat/DatabasePopup";
import AboutModal from "../components/ui/AboutModal";
import ConnectDatabaseModal from "../components/chat/ConnectDatabaseModal";
import DisconnectConfirmationModal from "../components/chat/DisconnectConfirmationModal";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<
    "ready" | "thinking" | "executing" | "done" | "error"
  >("ready");
  const [showAbout, setShowAbout] = useState(false);
  const [showDisconnectModal, setShowDisconnectModal] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [connectModalType, setConnectModalType] = useState<
    "sqlite" | "mysql" | "postgres"
  >("sqlite");
  const loadedRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

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
    setShowAbout(false);
  };

  const [sessionId] = useState(() => {
    let id = localStorage.getItem("bg_ai_session_id");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("bg_ai_session_id", id);
    }
    return id;
  });

  const handleSend = async (content: string) => {
    const userMessage: Message = {
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setLoading(true);
    setStatus("thinking");

    abortControllerRef.current = new AbortController();

    try {
      setStatus("executing");
      const data = await sendMessage(content, sessionId);

      const assistantMessage: Message = {
        role: "assistant",
        content:
          data.message ||
          data.explanation ||
          data.error ||
          "Here are the results.",
        sql: data.generated_sql,
        result: data.result,
        explanation: data.explanation,
        chart: data.chart,
        diagram: data.diagram,
        analytics: data.analytics,
        followups: data.followups,
        input_request: data.input_request ?? null,
        requires_confirmation:
          data.requires_confirmation ??
          data.result?.pending_confirmation ??
          false,
        operation: data.operation ?? data.result?.operation,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
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
              : s,
          ),
        );
      }
    } catch (error) {
      const errorMessage: Message = {
        role: "assistant",
        content: "Sorry, something went wrong. Please try again.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setStatus("error");
    } finally {
      setLoading(false);
      setTimeout(() => setStatus("ready"), 3000);
    }
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
    setLoading(false);
    setStatus("ready");
  };

  const handleInsertSubmit = async (
    values: Record<string, string>,
    table: string,
  ) => {
    const userMessage: Message = {
      role: "user",
      content: Object.entries(values)
        .map(([key, value]) => `${key}: ${value}`)
        .join(", "),
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setLoading(true);
    setStatus("thinking");

    try {
      setStatus("executing");
      const data = await sendInsert(values, table, sessionId);

      const assistantMessage: Message = {
        role: "assistant",
        content:
          data.message ||
          data.explanation ||
          data.error ||
          "Here are the results.",
        sql: data.generated_sql,
        result: data.result,
        explanation: data.explanation,
        chart: data.chart,
        diagram: data.diagram,
        analytics: data.analytics,
        followups: data.followups,
        input_request: data.input_request ?? null,
        requires_confirmation:
          data.requires_confirmation ??
          data.result?.pending_confirmation ??
          false,
        operation: data.operation ?? data.result?.operation,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      const completedMessages = [...nextMessages, assistantMessage];
      setMessages(completedMessages);
      setStatus("done");

      if (activeSessionId === null) {
        const newSession: ChatSession = {
          id: Date.now().toString(),
          title: `Insert into ${table}`,
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
              : s,
          ),
        );
      }
    } catch (error) {
      const errorMessage: Message = {
        role: "assistant",
        content: "Failed to submit the record. Please try again.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
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
    setShowAbout(false);
  };

  const [uploadVersion, setUploadVersion] = useState(0);
  const [dbConnected, setDbConnected] = useState(false);
  const [dbType, setDbType] = useState<string | null>(null);
  const [showDatabase, setShowDatabase] = useState(false);

  const refreshDbStatus = async () => {
    try {
      const [info, typeData] = await Promise.all([
        getDatabaseInfo(),
        getDatabaseType(),
      ]);

      const type = typeData.db_type || "none";

      setDbType(type);
      setDbConnected(type !== "none");
    } catch {
      setDbConnected(false);
      setDbType(null);
    }
  };

  const handleUploadComplete = () => {
    setUploadVersion((prev) => prev + 1);
    setDbConnected(true);
    refreshDbStatus();
  };

  const handleDatabaseConnected = () => {
    setDbConnected(true);
    refreshDbStatus();
  };

  const handleDisconnect = async () => {
    try {
      await disconnectDatabase();
      setDbConnected(false);
      setDbType(null);
      setMessages([]);
      setActiveSessionId(null);
      setSessions([]);
      localStorage.removeItem("bgai_sessions");
      localStorage.removeItem("bg_ai_session_id");
      setShowDatabase(false);
    } catch (error) {
      console.error("Failed to disconnect:", error);
    }
  };

  const handleDeleteSession = (id: string) => {
    const updated = sessions.filter((s) => s.id !== id);
    setSessions(updated);
    localStorage.setItem("bgai_sessions", JSON.stringify(updated));

    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
    }
  };

  const handleCancelQuery = () => {
    const cancelMessage: Message = {
      role: "assistant",
      content: "Operation cancelled. The query was not executed.",
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };
    setMessages((prev) => [...prev, cancelMessage]);
  };

  const handleConfirmQuery = async () => {
    setLoading(true);
    setStatus("executing");

    try {
      const data = await confirmQuery(sessionId);

      const resultMessage: Message = {
        role: "assistant",
        content:
          data.message ||
          data.explanation ||
          data.error ||
          "Database operation completed.",
        sql: data.sql || "",
        result: data,
        explanation: data.message || data.explanation || data.error || "",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, resultMessage]);

      await refreshDbStatus();

      setStatus(data.success ? "done" : "error");
    } catch (error) {
      const errorMessage: Message = {
        role: "assistant",
        content: "The database operation could not be completed.",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, errorMessage]);

      setStatus("error");
    } finally {
      setLoading(false);

      setTimeout(() => setStatus("ready"), 3000);
    }
  };

  return (
    <MainLayout
      status={status}
      onNewChat={handleNewChat}
      sessions={sessions}
      activeSessionId={activeSessionId}
      onSessionClick={handleHistoryClick}
      onUploadComplete={handleUploadComplete}
      dbConnected={dbConnected}
      dbType={dbType}
      onDatabaseConnected={handleDatabaseConnected}
      onDeleteSession={handleDeleteSession}
      onDisconnect={() => setShowDisconnectModal(true)}
      onConnectDatabase={() => {
        setConnectModalType("sqlite");
        setShowConnectModal(true);
      }}
      onOpenDatabase={() => setShowDatabase(true)}
      onOpenAbout={() => setShowAbout(true)}
      isAboutView={showAbout}
    >
      {showAbout ? (
        <AboutModal isEmbedded={true} onClose={() => setShowAbout(false)} />
      ) : (
        <ChatArea
          messages={messages}
          loading={loading}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSend={handleSend}
          onInsertSubmit={handleInsertSubmit}
          onSessionClick={handleHistoryClick}
          uploadVersion={uploadVersion}
          onStop={handleStop}
          onConfirmQuery={handleConfirmQuery}
          onCancelQuery={handleCancelQuery}
          dbConnected={dbConnected}
          dbType={dbType}
          onOpenDatabase={() => setShowDatabase(true)}
          onConnectDatabase={(type?: "sqlite" | "mysql" | "postgres") => {
            setConnectModalType(type || "sqlite");
            setShowConnectModal(true);
          }}
        />
      )}

      {showDatabase && (
        <DatabasePopup
          onClose={() => setShowDatabase(false)}
          onDisconnected={handleDisconnect}
        />
      )}

      {showConnectModal && (
        <ConnectDatabaseModal
          defaultType={connectModalType}
          onClose={() => setShowConnectModal(false)}
          onConnected={() => {
            handleUploadComplete();
            setShowConnectModal(false);
          }}
        />
      )}

      <DisconnectConfirmationModal
        isOpen={showDisconnectModal}
        onClose={() => setShowDisconnectModal(false)}
        onConfirm={handleDisconnect}
        dbType={dbType}
      />
    </MainLayout>
  );
}
