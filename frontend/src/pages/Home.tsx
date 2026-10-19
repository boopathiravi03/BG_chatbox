import { useState, useEffect, useRef, lazy, Suspense } from "react";
import ChatArea from "../components/chat/ChatArea";
import type { Message, ChatSession, DatabaseConnectionItem } from "../types/index";
import {
  sendMessage,
  confirmQuery,
  sendInsert,
  disconnectDatabase,
  getDatabaseInfo,
  getDatabaseType,
  getAuthToken,
  listDatabaseConnections,
  setActiveDatabaseConnection,
} from "../services/api";

import WorkspaceSidebar, {
  type WorkspaceTab,
} from "../components/workspace/WorkspaceSidebar";
import WorkspaceHeader from "../components/workspace/WorkspaceHeader";
import AICommandBar from "../components/workspace/AICommandBar";
import OverviewView from "../components/workspace/views/OverviewView";
import DataExplorerView from "../components/workspace/views/DataExplorerView";
import AnalyticsView from "../components/workspace/views/AnalyticsView";
import SqlLabView from "../components/workspace/views/SqlLabView";
import DataHealthView from "../components/workspace/views/DataHealthView";
import ReportsView from "../components/workspace/views/ReportsView";
import SettingsView from "../components/workspace/views/SettingsView";
import Background from "../components/ui/Background";

const DatabasePopup = lazy(() => import("../components/chat/DatabasePopup"));
const AboutModal = lazy(() => import("../components/ui/AboutModal"));
const ConnectDatabaseModal = lazy(
  () => import("../components/chat/ConnectDatabaseModal"),
);
const DisconnectConfirmationModal = lazy(
  () => import("../components/chat/DisconnectConfirmationModal"),
);
const ForecastingView = lazy(
  () => import("../components/workspace/views/ForecastingView"),
);
const AnomalyCenterView = lazy(
  () => import("../components/workspace/views/AnomalyCenterView"),
);
const AgentCenterView = lazy(
  () => import("../components/workspace/views/AgentCenterView"),
);
const DatabaseConnectionsManager = lazy(
  () => import("../components/workspace/database/DatabaseConnectionsManager"),
);
const SecurityCenterView = lazy(
  () => import("../components/workspace/views/SecurityCenterView"),
);

export default function Home() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

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
  const [connectModalType, setConnectModalType] = useState<string>("sqlite");

  const [sqlLabInitialQuery, setSqlLabInitialQuery] = useState<string>("");

  const loadedRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [uploadVersion, setUploadVersion] = useState(0);
  const [dbConnected, setDbConnected] = useState(false);
  const [dbType, setDbType] = useState<string | null>(null);
  const [dbInfo, setDbInfo] = useState<{
    database?: string;
    tables?: number;
    rows?: number;
    size?: string;
  }>({});
  const [connections, setConnections] = useState<DatabaseConnectionItem[]>([]);
  const [activeConnectionId, setActiveConnectionId] = useState<string | null>(null);
  const [showDatabase, setShowDatabase] = useState(false);

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

  const refreshAllDatabaseState = async () => {
    if (!getAuthToken()) {
      setConnections([]);
      setActiveConnectionId(null);
      setDbConnected(false);
      setDbType(null);
      setDbInfo({});
      return;
    }

    try {
      // 1. Fetch connections from multi-database manager
      const connData = await listDatabaseConnections().catch(() => ({ connections: [], active_connection_id: null }));
      const conns = connData.connections || [];
      const activeId = connData.active_connection_id || null;
      setConnections(conns);
      setActiveConnectionId(activeId);

      // Find the active connector
      const activeConn = conns.find((c) => c.connection_id === activeId || c.is_active);

      // 2. Fetch database type and info
      const [info, typeData] = await Promise.all([
        getDatabaseInfo(activeId || undefined).catch(() => null),
        getDatabaseType(activeId || undefined).catch(() => null),
      ]);

      if (activeConn) {
        const isConn = activeConn.status === "connected";
        setDbConnected(isConn);
        setDbType(activeConn.connector_type);
        setDbInfo(
          info && (info.connected || (info.database && info.database !== "Not Connected"))
            ? info
            : {
                database: activeConn.name,
                db_type: activeConn.connector_type,
                connected: isConn,
                tables: activeConn.stats?.tables ?? activeConn.stats?.collections ?? 0,
                collections: activeConn.stats?.collections ?? 0,
                rows: activeConn.stats?.rows ?? activeConn.stats?.documents ?? 0,
                documents: activeConn.stats?.documents ?? 0,
              }
        );
      } else {
        const type = typeData?.db_type && typeData.db_type !== "none" ? typeData.db_type : null;
        const isConn = Boolean(typeData?.connected && type);
        setDbConnected(isConn);
        setDbType(type);
        setDbInfo(info || {});
      }
    } catch (err) {
      console.error("Error refreshing database state:", err);
      setDbConnected(false);
      setDbType(null);
      setDbInfo({});
    }
  };

  const refreshConnections = () => refreshAllDatabaseState();
  const refreshDbStatus = () => refreshAllDatabaseState();

  useEffect(() => {
    refreshAllDatabaseState();
  }, []);

  const handleSelectActiveConnection = async (connectionId: string) => {
    try {
      await setActiveDatabaseConnection(connectionId);
      setActiveConnectionId(connectionId);
      await refreshAllDatabaseState();
    } catch (err) {
      console.error("Failed to set active connection", err);
    }
  };

  // Track introduced database connections to avoid repeating introductory summaries in AI Command
  const introducedConnectionsRef = useRef<Set<string>>(new Set());

  // Restore previously introduced connections from sessionStorage
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem("bgai_introduced_connections");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          parsed.forEach((k) => introducedConnectionsRef.current.add(k));
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Bug 2 Fix: Connection-aware, once-per-connection introduction for AI Command
  useEffect(() => {
    if (activeTab !== "chat" || !dbConnected) return;

    // Build stable connection identity
    const dbName =
      dbInfo?.database && dbInfo.database !== "Not Connected"
        ? dbInfo.database
        : connections.find((c) => c.connection_id === activeConnectionId)?.name || "";

    if (!dbName && !activeConnectionId) return;

    const connectionKey = `${activeConnectionId || "default"}:${dbType || "unknown"}:${dbName}`;

    // Check if this connection was already introduced in this session
    if (introducedConnectionsRef.current.has(connectionKey)) return;

    // Check if current messages list already has an intro for this connectionKey
    if (messages.some((m) => m.intro_key === connectionKey)) {
      introducedConnectionsRef.current.add(connectionKey);
      return;
    }

    // Mark as introduced immediately to prevent React StrictMode duplicate execution
    introducedConnectionsRef.current.add(connectionKey);
    try {
      sessionStorage.setItem(
        "bgai_introduced_connections",
        JSON.stringify(Array.from(introducedConnectionsRef.current))
      );
    } catch {
      // ignore
    }

    const isDoc = dbType === "mongodb";
    const isKv = dbType === "redis";
    const isVec = dbType === "qdrant" || dbType === "chroma";

    const entityLabel = isDoc ? "collections" : isKv ? "namespaces" : isVec ? "vector collections" : "tables";
    const recordLabel = isDoc ? "documents" : isKv ? "keys" : isVec ? "embeddings" : "records";

    const entityCount = (dbInfo as any)?.collections ?? (dbInfo as any)?.tables ?? (dbInfo?.tables ?? 0);
    const recordCount = (dbInfo as any)?.documents ?? (dbInfo as any)?.rows ?? (dbInfo?.rows ?? 0);

    const displayName = dbName || `${(dbType || "Database").toUpperCase()} Data Source`;

    const summaryText =
      `**Connected to ${displayName}** (\`${(dbType || "sql").toLowerCase()}\`)\n\n` +
      `• **${entityLabel.charAt(0).toUpperCase() + entityLabel.slice(1)}:** ${entityCount.toLocaleString()} verified ${entityLabel}\n` +
      `• **Total ${recordLabel.charAt(0).toUpperCase() + recordLabel.slice(1)}:** ${recordCount.toLocaleString()} ${recordLabel}\n` +
      `• **Status:** Active & synchronized for natural language queries and AI analysis.\n\n` +
      `*Ask any question in plain English or select a suggestion.*`;

    const introMsg: Message = {
      role: "assistant",
      content: summaryText,
      is_intro: true,
      intro_key: connectionKey,
      connection_id: activeConnectionId || undefined,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => {
      if (prev.some((m) => m.intro_key === connectionKey)) return prev;
      return [...prev, introMsg];
    });
  }, [activeTab, dbConnected, activeConnectionId, dbType, dbInfo, connections, messages]);

  const [sessionId] = useState(() => {
    let id = localStorage.getItem("bg_ai_session_id");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("bg_ai_session_id", id);
    }
    return id;
  });

  const handleSend = async (content: string, selectedSourceIds?: string[]) => {
    if (loading) return;

    // If not currently in chat tab, switch to chat to show full conversation and results
    if (activeTab !== "chat") {
      setActiveTab("chat");
    }

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
      const data = await sendMessage(
        content,
        sessionId,
        undefined,
        false,
        undefined,
        selectedSourceIds
      );

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
    if (loading) return;

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
      refreshDbStatus().catch((err) => console.warn("Background status refresh:", err));
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
    setActiveTab("chat");
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
      setDbInfo({});
      setConnections([]);
      setActiveConnectionId(null);
      setMessages([]);
      setActiveSessionId(null);
      setSessions([]);
      localStorage.removeItem("bgai_sessions");
      localStorage.removeItem("bg_ai_session_id");
      setShowDatabase(false);
      setShowDisconnectModal(false);
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

  const handleConfirmQuery = async (options?: { fingerprint?: string; highRiskConfirmed?: boolean }) => {
    if (loading) return;
    setLoading(true);
    setStatus("executing");

    try {
      const data = await confirmQuery(sessionId, {
        fingerprint: options?.fingerprint,
        highRiskConfirmed: options?.highRiskConfirmed ?? false,
      });

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
      setStatus(data.success ? "done" : "error");

      // Asynchronous background status sync without freezing perceived responsiveness
      refreshDbStatus().catch((err) => console.warn("Background status refresh:", err));
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

  const handleOpenSqlLabWithTable = (tableName: string) => {
    setSqlLabInitialQuery(`SELECT * FROM "${tableName}" LIMIT 50;`);
    setActiveTab("sqllab");
  };

  const activeConnectionName =
    connections.find((c) => c.connection_id === activeConnectionId || c.is_active)?.name ||
    (dbInfo?.database && dbInfo.database !== "Not Connected" ? dbInfo.database : undefined);

  return (
    <div className="flex h-screen bg-[#09090b] text-[#f4f4f5] relative overflow-hidden font-sans">
      <Background />

      {/* Left Workspace Navigation Sidebar */}
      <WorkspaceSidebar
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          setShowAbout(false);
        }}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
        dbConnected={dbConnected}
        dbType={dbType}
        connectionName={
          connections.find((c) => c.connection_id === activeConnectionId || c.is_active)?.name ||
          (dbInfo?.database && dbInfo.database !== "Not Connected" ? dbInfo.database : undefined)
        }
        connectionsCount={connections.length}
        onConnectDatabase={() => {
          setConnectModalType("sqlite");
          setShowConnectModal(true);
        }}
        onDisconnect={() => setShowDisconnectModal(true)}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      {/* Main Workspace Stage */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative z-10">
        {/* Top Header Bar */}
        <WorkspaceHeader
          activeTab={activeTab}
          onOpenMobileMenu={() => setMobileSidebarOpen(true)}
          dbConnected={dbConnected}
          dbType={dbType}
          dbInfo={dbInfo}
          connections={connections}
          activeConnectionId={activeConnectionId}
          onSelectActiveConnection={handleSelectActiveConnection}
          onConnectDatabase={() => {
            setConnectModalType("sqlite");
            setShowConnectModal(true);
          }}
          onDisconnect={() => setShowDisconnectModal(true)}
          onOpenAbout={() => setShowAbout(true)}
          onOpenDatabaseDetails={() => setShowDatabase(true)}
          onNavigateTab={(tab) => setActiveTab(tab)}
        />

        {/* Viewport for Active Tab */}
        <main className="flex-1 overflow-y-auto relative flex flex-col">
          {activeTab === "overview" && (
            <OverviewView
              dbConnected={dbConnected}
              dbType={dbType}
              activeConnectionId={activeConnectionId}
              initialDbInfo={dbInfo}
              onTabChange={setActiveTab}
              onConnectDatabase={() => {
                setConnectModalType("sqlite");
                setShowConnectModal(true);
              }}
              onRunAnalysis={() =>
                handleSend("Analyze my business performance")
              }
            />
          )}

          {activeTab === "databases" && (
            <Suspense fallback={<div className="p-8 text-center text-zinc-400">Loading Data Sources...</div>}>
              <DatabaseConnectionsManager
                onConnectionsChanged={() => {
                  refreshConnections();
                  refreshDbStatus();
                }}
                onOpenSqlLabWithTable={(tbl, cid) => {
                  setSqlLabInitialQuery(`SELECT * FROM ${tbl} LIMIT 10;`);
                  setActiveTab("sqllab");
                }}
              />
            </Suspense>
          )}

          {activeTab === "explorer" && (
            <DataExplorerView
              dbConnected={dbConnected}
              connections={connections}
              activeConnectionId={activeConnectionId}
              onOpenSqlLabWithTable={handleOpenSqlLabWithTable}
              onConnectDatabase={() => {
                setConnectModalType("sqlite");
                setShowConnectModal(true);
              }}
            />
          )}

          {activeTab === "analytics" && (
            <AnalyticsView
              dbConnected={dbConnected}
              onRunAnalysis={() =>
                handleSend("Analyze my business performance")
              }
              onConnectDatabase={() => {
                setConnectModalType("sqlite");
                setShowConnectModal(true);
              }}
            />
          )}

          {activeTab === "forecasting" && (
            <Suspense fallback={<div className="p-8 text-center text-slate-400">Loading Forecasting Studio...</div>}>
              <ForecastingView
                dbConnected={dbConnected}
                onConnectDatabase={() => {
                  setConnectModalType("sqlite");
                  setShowConnectModal(true);
                }}
                onTabChange={setActiveTab}
                onOpenSqlLabWithQuery={(q) => {
                  setSqlLabInitialQuery(q);
                  setActiveTab("sqllab");
                }}
              />
            </Suspense>
          )}

          {activeTab === "anomalies" && (
            <Suspense fallback={<div className="p-8 text-center text-slate-400">Loading Anomaly Center...</div>}>
              <AnomalyCenterView
                dbConnected={dbConnected}
                activeConnectionId={activeConnectionId}
                activeDbName={activeConnectionName || (dbInfo?.database !== "Not Connected" ? dbInfo?.database : undefined)}
                onConnectDatabase={() => {
                  setConnectModalType("sqlite");
                  setShowConnectModal(true);
                }}
                onTabChange={setActiveTab}
                onOpenSqlLabWithQuery={(q) => {
                  setSqlLabInitialQuery(q);
                  setActiveTab("sqllab");
                }}
                onRunAnalysis={(q) => {
                  if (q) handleSend(q);
                }}
              />
            </Suspense>
          )}

          {activeTab === "agents" && (
            <Suspense fallback={<div className="p-8 text-center text-slate-400">Loading AI Agent Center...</div>}>
              <AgentCenterView
                dbConnected={dbConnected}
                dbType={dbType}
                onNavigateTab={(tab: WorkspaceTab, target?: string) => {
                  if (tab === "sqllab" && target) {
                    handleOpenSqlLabWithTable(target);
                  } else {
                    setActiveTab(tab);
                  }
                }}
              />
            </Suspense>
          )}

          {activeTab === "sqllab" && (
            <SqlLabView
              dbConnected={dbConnected}
              connections={connections}
              activeConnectionId={activeConnectionId}
              initialQuery={sqlLabInitialQuery}
              onConnectDatabase={() => {
                setConnectModalType("sqlite");
                setShowConnectModal(true);
              }}
            />
          )}

          {activeTab === "health" && (
            <DataHealthView
              dbConnected={dbConnected}
              activeConnectionId={activeConnectionId}
              onConnectDatabase={() => {
                setConnectModalType("sqlite");
                setShowConnectModal(true);
              }}
            />
          )}

          {activeTab === "security" && (
            <Suspense fallback={<div className="p-8 text-center text-zinc-400">Loading Cybersecurity Center...</div>}>
              <SecurityCenterView
                dbConnected={dbConnected}
                activeConnectionId={activeConnectionId}
                dbType={dbType}
                onConnectDatabase={() => {
                  setConnectModalType("sqlite");
                  setShowConnectModal(true);
                }}
                onTabChange={setActiveTab}
              />
            </Suspense>
          )}

          {activeTab === "chat" && (
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
              activeConnectionId={activeConnectionId}
              onOpenDatabase={() => setShowDatabase(true)}
              onConnectDatabase={(type?: "sqlite" | "mysql" | "postgres") => {
                setConnectModalType(type || "sqlite");
                setShowConnectModal(true);
              }}
            />
          )}

          {activeTab === "reports" && (
            <ReportsView
              dbConnected={dbConnected}
              onConnectDatabase={() => {
                setConnectModalType("sqlite");
                setShowConnectModal(true);
              }}
            />
          )}

          {activeTab === "settings" && (
            <SettingsView
              dbConnected={dbConnected}
              dbType={dbType}
              onConnectDatabase={() => {
                setConnectModalType("sqlite");
                setShowConnectModal(true);
              }}
              onDisconnect={() => setShowDisconnectModal(true)}
            />
          )}
        </main>

        {/* Global AI Command Bar (Rendered on non-chat views) */}
        {activeTab !== "chat" && (
          <AICommandBar
            onSend={handleSend}
            connections={connections}
            activeConnectionId={activeConnectionId}
            loading={loading}
          />
        )}
      </div>

      {/* Global Modals */}
      {showAbout && (
        <Suspense fallback={null}>
          <AboutModal isEmbedded={false} onClose={() => setShowAbout(false)} />
        </Suspense>
      )}

      {showDatabase && (
        <Suspense fallback={null}>
          <DatabasePopup
            connectionId={activeConnectionId || undefined}
            onClose={() => setShowDatabase(false)}
            onDisconnected={handleDisconnect}
          />
        </Suspense>
      )}

      {showConnectModal && (
        <Suspense fallback={null}>
          <ConnectDatabaseModal
            defaultType={connectModalType}
            onClose={() => setShowConnectModal(false)}
            onConnected={() => {
              handleUploadComplete();
              setShowConnectModal(false);
            }}
          />
        </Suspense>
      )}

      {showDisconnectModal && (
        <Suspense fallback={null}>
          <DisconnectConfirmationModal
            isOpen={showDisconnectModal}
            onClose={() => setShowDisconnectModal(false)}
            onConfirm={handleDisconnect}
            dbType={dbType}
          />
        </Suspense>
      )}
    </div>
  );
}
