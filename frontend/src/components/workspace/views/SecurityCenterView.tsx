import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Lock,
  Unlock,
  Key,
  RefreshCw,
  Eye,
  Database,
  Terminal,
  FileCode,
  Check,
  X,
  Info,
  Search,
  Activity,
  Play,
  FileCheck,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  Sparkles,
  SlidersHorizontal,
  Filter,
  CheckSquare,
  Square,
  HelpCircle,
  Globe,
  Radio,
} from "lucide-react";
import {
  getGovernanceSummary,
  listGovernanceSecurityEvents,
  listGovernancePolicies,
  setGovernancePolicyStatus,
  listGovernanceAudit,
  verifyAuditChain,
  scanDatabaseSecurity,
  explainSecurityFinding,
  getSchema,
  listIPThreats,
  queryIPReputation,
  unblockIP,
} from "../../../services/api";
import type {
  GovernanceSummaryItem,
  SecurityEventItem,
  GovernancePolicyItem,
  GovernanceAuditEventItem,
  SecurityPostureScanResult,
  SecurityPostureFinding,
  SecurityFindingExplanation,
  IPThreatBlockItem,
  IPReputationResult,
} from "../../../types";
import { useToast } from "../../../context/ToastContext";

interface SecurityCenterViewProps {
  dbConnected: boolean;
  activeConnectionId?: string | null;
  dbType?: string | null;
  onConnectDatabase: () => void;
  onTabChange?: (tab: any) => void;
}

type SubTab = "overview" | "findings" | "events" | "ip_threats" | "policies" | "audit";

export default function SecurityCenterView({
  dbConnected,
  activeConnectionId,
  dbType,
  onConnectDatabase,
  onTabChange,
}: SecurityCenterViewProps) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Governance Data
  const [summary, setSummary] = useState<GovernanceSummaryItem | null>(null);
  const [securityEvents, setSecurityEvents] = useState<SecurityEventItem[]>([]);
  const [policies, setPolicies] = useState<GovernancePolicyItem[]>([]);
  const [auditEvents, setAuditEvents] = useState<GovernanceAuditEventItem[]>([]);

  // Audit Chain Verification
  const [verifyingChain, setVerifyingChain] = useState(false);
  const [chainResult, setChainResult] = useState<{
    verified?: boolean;
    events_verified?: number;
    error_detail?: string | null;
  } | null>(null);

  // Policy Modification Confirmation Modal
  const [pendingPolicy, setPendingPolicy] = useState<{
    policy: GovernancePolicyItem;
    targetState: boolean;
  } | null>(null);
  const [updatingPolicy, setUpdatingPolicy] = useState(false);

  // Scanner State
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<SecurityPostureScanResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  // Table Selection for Scans
  const [availableTables, setAvailableTables] = useState<string[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [customTableScope, setCustomTableScope] = useState(false);

  // Filters & Search
  const [findingsSearch, setFindingsSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [expandedFindingId, setExpandedFindingId] = useState<string | null>(null);

  // AI-Assisted Security Explanation Modal
  const [explainingFinding, setExplainingFinding] = useState<SecurityPostureFinding | null>(null);
  const [explanationData, setExplanationData] = useState<SecurityFindingExplanation | null>(null);
  const [explanationLoading, setExplanationLoading] = useState(false);

  // IP Threat Intelligence & Intrusion State
  const [ipThreatEvents, setIpThreatEvents] = useState<SecurityEventItem[]>([]);
  const [activeIPBlocks, setActiveIPBlocks] = useState<IPThreatBlockItem[]>([]);
  const [ipFilter, setIpFilter] = useState("");
  const [ipSeverityFilter, setIpSeverityFilter] = useState("ALL");
  const [threatTypeFilter, setThreatTypeFilter] = useState("ALL");
  const [reputationLoading, setReputationLoading] = useState(false);
  const [selectedReputation, setSelectedReputation] = useState<IPReputationResult | null>(null);
  const [unblockingIp, setUnblockingIp] = useState<string | null>(null);

  const toast = useToast();

  // Reset scan state on database switch to prevent stale cross-connection display
  useEffect(() => {
    setScanResult(null);
    setScanError(null);
    setExpandedFindingId(null);
    setExplainingFinding(null);
  }, [activeConnectionId]);

  // Load available schema tables for scope selection
  useEffect(() => {
    if (!dbConnected) {
      setAvailableTables([]);
      setSelectedTables([]);
      return;
    }
    getSchema(activeConnectionId || undefined)
      .then((schema) => {
        if (schema && typeof schema === "object" && !schema.error) {
          const tbls = Object.keys(schema).filter((k) => k !== "status");
          setAvailableTables(tbls);
        }
      })
      .catch(() => {});
  }, [dbConnected, activeConnectionId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, secRes, polRes, audRes, ipRes] = await Promise.allSettled([
        getGovernanceSummary(7),
        listGovernanceSecurityEvents({ limit: 50 }),
        listGovernancePolicies(),
        listGovernanceAudit({ limit: 50 }),
        listIPThreats({ limit: 50 }),
      ]);

      if (sumRes.status === "fulfilled" && sumRes.value?.status === "success" && sumRes.value.summary) {
        setSummary(sumRes.value.summary);
      }
      if (secRes.status === "fulfilled" && secRes.value?.status === "success" && secRes.value.security_events) {
        setSecurityEvents(secRes.value.security_events);
      }
      if (polRes.status === "fulfilled" && polRes.value?.status === "success" && polRes.value.policies) {
        setPolicies(polRes.value.policies);
      }
      if (audRes.status === "fulfilled" && audRes.value?.status === "success" && audRes.value.events) {
        setAuditEvents(audRes.value.events);
      }
      if (ipRes.status === "fulfilled" && ipRes.value?.status === "success") {
        setIpThreatEvents(ipRes.value.threat_events || []);
        setActiveIPBlocks(ipRes.value.active_blocks || []);
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load security and governance data.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCheckReputation = async (ip: string) => {
    setReputationLoading(true);
    try {
      const res = await queryIPReputation(ip);
      if (res.status === "success" && res.reputation) {
        setSelectedReputation(res.reputation);
      } else {
        toast.error(res.message || "Could not retrieve IP reputation.");
      }
    } catch (err: any) {
      toast.error(`Reputation query failed: ${err.message}`);
    } finally {
      setReputationLoading(false);
    }
  };

  const handleUnblockIP = async (ip: string) => {
    setUnblockingIp(ip);
    try {
      const res = await unblockIP(ip);
      if (res.status === "success") {
        toast.success(res.message);
        setActiveIPBlocks((prev) => prev.filter((b) => b.ip_address !== ip));
        loadData();
      } else {
        toast.error(res.message || "Failed to unblock IP.");
      }
    } catch (err: any) {
      toast.error(`Unblock failed: ${err.message}`);
    } finally {
      setUnblockingIp(null);
    }
  };

  useEffect(() => {
    loadData();
  }, [loadData, activeConnectionId]);

  const handleVerifyChain = async () => {
    setVerifyingChain(true);
    try {
      const res = await verifyAuditChain();
      setChainResult(res);
      if (res.verified) {
        toast.success(`Audit chain verified: ${res.events_verified} events cryptographically sound.`);
      } else {
        toast.error(`Audit chain verification issue: ${res.error_detail || res.message || "Unknown error"}`);
      }
    } catch (err: any) {
      toast.error(`Verification error: ${err.message}`);
    } finally {
      setVerifyingChain(false);
    }
  };

  const confirmPolicyChange = async () => {
    if (!pendingPolicy) return;
    setUpdatingPolicy(true);
    try {
      const res = await setGovernancePolicyStatus(pendingPolicy.policy.policy_id, pendingPolicy.targetState);
      if (res.status === "success") {
        setPolicies((prev) =>
          prev.map((p) =>
            p.policy_id === pendingPolicy.policy.policy_id
              ? { ...p, enabled: pendingPolicy.targetState }
              : p
          )
        );
        toast.success(`Policy '${pendingPolicy.policy.name}' updated.`);
        setPendingPolicy(null);
      } else {
        toast.error(res.message || "Failed to update policy status.");
      }
    } catch (err: any) {
      toast.error(err.message || "Network error while updating policy.");
    } finally {
      setUpdatingPolicy(false);
    }
  };

  const handleRunScan = async () => {
    if (!dbConnected) {
      toast.info("Connect a database to run a live security posture scan.");
      return;
    }
    if (scanning) return; // Prevent concurrent duplicate submissions
    setScanning(true);
    setScanError(null);
    try {
      const tablesToScan = customTableScope && selectedTables.length > 0 ? selectedTables : undefined;
      const res = await scanDatabaseSecurity(activeConnectionId || undefined, tablesToScan);
      if (res.status === "success") {
        setScanResult(res);
        toast.success(`Security scan completed. ${res.findings.length} findings evaluated.`);
        loadData().catch(() => {});
      } else {
        setScanError(res.message || "Security scan failed to complete.");
        toast.error(res.message || "Scan failed.");
      }
    } catch (err: any) {
      const msg = err?.message || "Error executing security scan.";
      setScanError(msg);
      toast.error(msg);
    } finally {
      setScanning(false);
    }
  };

  const handleExplainFinding = async (finding: SecurityPostureFinding) => {
    setExplainingFinding(finding);
    setExplanationData(null);
    setExplanationLoading(true);
    try {
      const res = await explainSecurityFinding(finding);
      if (res.status === "success" && res.explanation) {
        setExplanationData(res.explanation);
      } else {
        toast.error(res.message || "Could not retrieve AI explanation.");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to generate explanation.");
    } finally {
      setExplanationLoading(false);
    }
  };

  const toggleTableSelection = (tableName: string) => {
    setSelectedTables((prev) =>
      prev.includes(tableName)
        ? prev.filter((t) => t !== tableName)
        : prev.length < 15
        ? [...prev, tableName]
        : prev
    );
  };

  // Filtered Findings
  const filteredFindings = useMemo(() => {
    if (!scanResult?.findings) return [];
    return scanResult.findings.filter((f) => {
      const matchesSearch =
        !findingsSearch ||
        f.title.toLowerCase().includes(findingsSearch.toLowerCase()) ||
        (f.table && f.table.toLowerCase().includes(findingsSearch.toLowerCase())) ||
        (f.column && f.column.toLowerCase().includes(findingsSearch.toLowerCase())) ||
        f.evidence_summary.toLowerCase().includes(findingsSearch.toLowerCase());

      const matchesSeverity =
        severityFilter === "ALL" || f.severity.toUpperCase() === severityFilter.toUpperCase();

      const matchesCategory =
        categoryFilter === "ALL" || f.category.toUpperCase() === categoryFilter.toUpperCase();

      return matchesSearch && matchesSeverity && matchesCategory;
    });
  }, [scanResult, findingsSearch, severityFilter, categoryFilter]);

  const findingsCounts = useMemo(() => {
    const list = scanResult?.findings || [];
    return {
      critical: list.filter((f) => f.severity.toUpperCase() === "CRITICAL").length,
      high: list.filter((f) => f.severity.toUpperCase() === "HIGH").length,
      medium: list.filter((f) => f.severity.toUpperCase() === "MEDIUM").length,
      low: list.filter((f) => f.severity.toUpperCase() === "LOW").length,
    };
  }, [scanResult]);

  const getSeverityBadge = (severity: string) => {
    const s = severity?.toUpperCase();
    if (s === "CRITICAL") {
      return (
        <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-red-500/20 text-red-400 border border-red-500/30">
          CRITICAL
        </span>
      );
    }
    if (s === "HIGH") {
      return (
        <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
          HIGH
        </span>
      );
    }
    if (s === "MEDIUM") {
      return (
        <span className="px-2 py-0.5 text-[11px] font-medium rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
          MEDIUM
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 text-[11px] font-medium rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
        {s || "INFO"}
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#09090b] text-zinc-100 overflow-y-auto">
      {/* Top Banner & Header */}
      <div className="border-b border-white/[0.08] bg-[#0d0d11]/90 backdrop-blur-md px-6 py-5 shrink-0">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 max-w-7xl mx-auto">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-sm shadow-indigo-500/20">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                  Database Cybersecurity & Governance
                  <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                    PRODUCTION DEFENSE
                  </span>
                </h1>
                <p className="text-sm text-zinc-400 mt-0.5">
                  Real-time threat monitoring, sensitive data exposure scans, least-privilege audits, and cryptographic audit ledgers.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleRunScan}
              disabled={scanning || !dbConnected}
              className={`px-3.5 py-2 text-xs font-medium rounded-lg flex items-center gap-2 transition-all ${
                dbConnected && !scanning
                  ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 border border-indigo-500/40"
                  : "bg-zinc-800 text-zinc-500 border border-white/5 cursor-not-allowed"
              }`}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} />
              {scanning ? "Scanning Posture..." : "Run Security Scan"}
            </button>

            <button
              onClick={loadData}
              disabled={loading}
              className="p-2 text-zinc-400 hover:text-white bg-zinc-800/80 hover:bg-zinc-800 border border-white/[0.08] rounded-lg transition-colors"
              title="Refresh Security Status"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Sub Navigation Tabs */}
        <div className="flex items-center gap-1 mt-6 border-b border-white/[0.06] -mb-5 max-w-7xl mx-auto overflow-x-auto">
          <button
            onClick={() => setActiveSubTab("overview")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              activeSubTab === "overview"
                ? "border-indigo-500 text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
            Security Overview
          </button>

          <button
            onClick={() => setActiveSubTab("findings")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              activeSubTab === "findings"
                ? "border-indigo-500 text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            Findings & Sensitive Data
            {scanResult && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-500/20 text-indigo-300 font-mono">
                {scanResult.findings.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveSubTab("events")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              activeSubTab === "events"
                ? "border-indigo-500 text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            Threat Incidents
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-red-500/20 text-red-300 font-mono">
              {securityEvents.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab("ip_threats")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              activeSubTab === "ip_threats"
                ? "border-indigo-500 text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            IP Threats & Intrusion
            {activeIPBlocks.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-red-500 text-white font-mono animate-pulse">
                {activeIPBlocks.length} Blocked
              </span>
            )}
            {activeIPBlocks.length === 0 && ipThreatEvents.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-500/20 text-indigo-300 font-mono">
                {ipThreatEvents.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveSubTab("policies")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              activeSubTab === "policies"
                ? "border-indigo-500 text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Lock className="w-3.5 h-3.5" />
            Guardrail Policies
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-zinc-700 text-zinc-300">
              {policies.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab("audit")}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition-all flex items-center gap-2 whitespace-nowrap ${
              activeSubTab === "audit"
                ? "border-indigo-500 text-white"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <FileCheck className="w-3.5 h-3.5" />
            Tamper-Evident Audit Ledger
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 font-mono">
              SHA-256
            </span>
          </button>
        </div>
      </div>

      {/* Main Content Stage */}
      <div className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {loading && !summary && !scanResult ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin mb-4" />
            <p className="text-zinc-300 font-medium">Inspecting live security and governance engine...</p>
            <p className="text-xs text-zinc-500 mt-1">Verifying audit chains, threat logs, and policy registry</p>
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 shrink-0 text-red-400 mt-0.5" />
            <div>
              <p className="text-sm font-semibold">Security Services Unavailable</p>
              <p className="text-xs text-red-300/80 mt-1">{error}</p>
              <button
                onClick={loadData}
                className="mt-3 px-3 py-1 text-xs font-medium rounded bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-200"
              >
                Retry Connection
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* ── A. Security Overview Tab ─────────────────────────────────── */}
            {activeSubTab === "overview" && (
              <div className="space-y-6">
                {/* Top Metrics Row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* Posture Score Card */}
                  <div className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] relative overflow-hidden">
                    <div className="flex items-center justify-between text-zinc-400 mb-2">
                      <span className="text-xs font-medium flex items-center gap-1.5">
                        Security Posture Score
                        <span title={scanResult?.score_explanation || "Run a security scan to calculate posture score."}>
                          <HelpCircle className="w-3.5 h-3.5 text-zinc-500 cursor-help" />
                        </span>
                      </span>
                      <ShieldCheck className="w-4 h-4 text-indigo-400" />
                    </div>
                    <div className="flex items-baseline gap-2">
                      {scanResult?.posture_score !== undefined && scanResult.posture_score !== null ? (
                        <>
                          <span className={`text-3xl font-extrabold font-mono ${
                            scanResult.posture_score >= 85
                              ? "text-emerald-400"
                              : scanResult.posture_score >= 65
                              ? "text-yellow-400"
                              : "text-red-400"
                          }`}>
                            {scanResult.posture_score}
                          </span>
                          <span className="text-xs text-zinc-500 font-mono">/ 100</span>
                        </>
                      ) : (
                        <span className="text-sm font-medium text-zinc-400">Not Scanned Yet</span>
                      )}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-2">
                      {scanResult ? (
                        <span>Risk Level: <strong className="text-zinc-300">{scanResult.risk_level}</strong></span>
                      ) : (
                        <span>Click "Run Security Scan" to evaluate</span>
                      )}
                    </div>
                  </div>

                  {/* Findings Summary Card */}
                  <div className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] relative overflow-hidden">
                    <div className="flex items-center justify-between text-zinc-400 mb-2">
                      <span className="text-xs font-medium">Evaluated Findings</span>
                      <Search className="w-4 h-4 text-amber-400" />
                    </div>
                    <div className="text-3xl font-bold font-mono text-white">
                      {scanResult ? scanResult.findings.length : "—"}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-2 flex items-center gap-2">
                      <span className="text-red-400 font-mono">{findingsCounts.critical} Crit</span>
                      <span>•</span>
                      <span className="text-amber-400 font-mono">{findingsCounts.high} High</span>
                      <span>•</span>
                      <span className="text-yellow-400 font-mono">{findingsCounts.medium} Med</span>
                    </div>
                  </div>

                  {/* Threat Incidents Card */}
                  <div className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] relative overflow-hidden">
                    <div className="flex items-center justify-between text-zinc-400 mb-2">
                      <span className="text-xs font-medium">Logged Threat Incidents</span>
                      <ShieldAlert className="w-4 h-4 text-red-400" />
                    </div>
                    <div className="text-3xl font-bold font-mono text-white">
                      {securityEvents.length}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-2">
                      {summary?.high_critical_security_count || 0} critical/high interventions recorded
                    </div>
                  </div>

                  {/* Tamper-Evident Chain Status */}
                  <div className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] relative overflow-hidden">
                    <div className="flex items-center justify-between text-zinc-400 mb-2">
                      <span className="text-xs font-medium">Audit Ledger Integrity</span>
                      <FileCheck className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div className="text-base font-bold text-white flex items-center gap-1.5 mt-1">
                      {chainResult ? (
                        chainResult.verified ? (
                          <span className="text-emerald-400 flex items-center gap-1 text-sm font-semibold">
                            <Check className="w-4 h-4" /> Cryptographically Sound
                          </span>
                        ) : (
                          <span className="text-red-400 flex items-center gap-1 text-sm font-semibold">
                            <X className="w-4 h-4" /> Chain Mismatch Detected
                          </span>
                        )
                      ) : summary?.hash_chain_verified ? (
                        <span className="text-emerald-400 flex items-center gap-1 text-sm font-semibold">
                          <Check className="w-4 h-4" /> SHA-256 Verified
                        </span>
                      ) : (
                        <span className="text-zinc-400 text-sm">Unverified</span>
                      )}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-2">
                      {summary?.total_audit_events ?? auditEvents.length} immutable events in hash chain
                    </div>
                  </div>
                </div>

                {/* Database Connection Hardening Posture */}
                <div className="p-5 rounded-xl bg-[#0d0d11] border border-white/[0.08]">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
                    <div>
                      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                        <Database className="w-4 h-4 text-indigo-400" />
                        Active Database Hardening & Access Control
                      </h3>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        {dbConnected
                          ? `Inspecting active connector '${dbType?.toUpperCase() || "DATABASE"}' for transport security and least privilege.`
                          : "No active database connection selected."}
                      </p>
                    </div>

                    {!dbConnected && (
                      <button
                        onClick={onConnectDatabase}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white"
                      >
                        Connect Database
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                    <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="text-xs text-zinc-400">TLS Encryption</div>
                      <div className="text-sm font-semibold text-zinc-200 mt-1 flex items-center gap-2">
                        {scanResult ? (
                          scanResult.tls_status === "VERIFIED" ? (
                            <span className="text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-4 h-4" /> Verified TLS/SSL
                            </span>
                          ) : scanResult.tls_status === "DISABLED" ? (
                            <span className="text-amber-400 flex items-center gap-1">
                              <AlertTriangle className="w-4 h-4" /> Disabled / Plaintext
                            </span>
                          ) : (
                            <span className="text-zinc-400 flex items-center gap-1">
                              <Info className="w-4 h-4" /> {scanResult.tls_details || "Local / In-Process"}
                            </span>
                          )
                        ) : dbConnected ? (
                          <span className="text-zinc-400 flex items-center gap-1">
                            <Info className="w-4 h-4" /> Run scan to verify
                          </span>
                        ) : (
                          <span className="text-zinc-600">Disconnected</span>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1">
                        {scanResult?.tls_details || "Transport-layer security verification."}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="text-xs text-zinc-400">Account Privilege Posture</div>
                      <div className="text-sm font-semibold text-zinc-200 mt-1 flex items-center gap-2">
                        {scanResult ? (
                          scanResult.privilege_status === "LEAST_PRIVILEGE" ? (
                            <span className="text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-4 h-4" /> Standard Permissions
                            </span>
                          ) : scanResult.privilege_status === "SUPERUSER" ? (
                            <span className="text-amber-400 flex items-center gap-1">
                              <AlertTriangle className="w-4 h-4" /> Elevated / Superuser
                            </span>
                          ) : (
                            <span className="text-zinc-300">
                              {scanResult.privilege_details || "Standard Application Role"}
                            </span>
                          )
                        ) : dbConnected ? (
                          <span className="text-zinc-400">Run scan to evaluate</span>
                        ) : (
                          <span className="text-zinc-600">Disconnected</span>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1">
                        Ensures connection runs with appropriate least-privilege bounds.
                      </p>
                    </div>

                    <div className="p-3.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="text-xs text-zinc-400">Credential Redaction</div>
                      <div className="text-sm font-semibold text-emerald-400 mt-1 flex items-center gap-2">
                        <Lock className="w-4 h-4" /> Enforced by Architecture
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1">
                        Passwords, tokens, and raw secrets are sanitized before display or storage.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Priority Remediation Findings Callout */}
                {scanResult && scanResult.findings.filter((f) => f.severity === "CRITICAL" || f.severity === "HIGH").length > 0 && (
                  <div className="p-5 rounded-xl bg-red-500/[0.04] border border-red-500/20">
                    <div className="flex items-center gap-2 mb-3">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      <h4 className="text-xs font-bold text-red-300 uppercase tracking-wider">
                        High Priority Findings Requiring Attention
                      </h4>
                    </div>
                    <div className="space-y-2">
                      {scanResult.findings
                        .filter((f) => f.severity === "CRITICAL" || f.severity === "HIGH")
                        .slice(0, 3)
                        .map((f) => (
                          <div key={f.id} className="p-3 rounded-lg bg-[#0d0d11] border border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                {getSeverityBadge(f.severity)}
                                <span className="text-xs font-semibold text-white">{f.title}</span>
                                {f.table && (
                                  <span className="px-1.5 py-0.2 rounded text-[10px] bg-white/[0.04] text-zinc-400 font-mono">
                                    {f.table}{f.column ? `.${f.column}` : ""}
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-zinc-400 mt-0.5">{f.evidence_summary}</p>
                            </div>
                            <button
                              onClick={() => handleExplainFinding(f)}
                              className="px-2.5 py-1 text-[11px] font-medium rounded bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 flex items-center gap-1 shrink-0 self-start sm:self-center"
                            >
                              <Sparkles className="w-3 h-3 text-indigo-400" />
                              Explain with AI
                            </button>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── B. Findings & Sensitive Data Tab ─────────────────────────── */}
            {activeSubTab === "findings" && (
              <div className="space-y-4">
                {/* Table Scope Configuration Bar */}
                <div className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] flex flex-col gap-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                        <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
                        Scanner Scope Configuration
                      </h3>
                      <p className="text-[11px] text-zinc-500 mt-0.5">
                        Choose whether to inspect prioritized sensitive tables automatically or select specific tables (bounded to max 50 rows per table).
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCustomTableScope(!customTableScope)}
                        className={`px-3 py-1 text-xs font-medium rounded-lg border transition-all ${
                          customTableScope
                            ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40"
                            : "bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:text-white"
                        }`}
                      >
                        {customTableScope ? "Selecting Custom Tables" : "Auto Prioritize Tables"}
                      </button>
                    </div>
                  </div>

                  {customTableScope && availableTables.length > 0 && (
                    <div className="pt-2 border-t border-white/[0.06]">
                      <div className="text-[11px] text-zinc-400 mb-2 flex items-center justify-between">
                        <span>Select up to 15 tables to scan:</span>
                        <span className="font-mono text-zinc-500">{selectedTables.length} / 15 selected</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-1">
                        {availableTables.map((t) => {
                          const isSelected = selectedTables.includes(t);
                          return (
                            <button
                              key={t}
                              onClick={() => toggleTableSelection(t)}
                              className={`px-2 py-1 text-[11px] font-mono rounded border transition-all flex items-center gap-1.5 ${
                                isSelected
                                  ? "bg-indigo-600/30 text-indigo-200 border-indigo-500/50"
                                  : "bg-white/[0.02] text-zinc-400 border-white/[0.06] hover:border-white/20"
                              }`}
                            >
                              {isSelected ? <CheckSquare className="w-3 h-3 text-indigo-400" /> : <Square className="w-3 h-3 text-zinc-600" />}
                              {t}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Search & Filter Toolbar */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                  <div className="relative flex-1 max-w-md">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                    <input
                      type="text"
                      placeholder="Search findings by table, column, or pattern..."
                      value={findingsSearch}
                      onChange={(e) => setFindingsSearch(e.target.value)}
                      className="w-full bg-[#0d0d11] border border-white/[0.08] rounded-lg pl-9 pr-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={severityFilter}
                      onChange={(e) => setSeverityFilter(e.target.value)}
                      className="bg-[#0d0d11] border border-white/[0.08] text-xs text-zinc-300 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="ALL">All Severities</option>
                      <option value="CRITICAL">Critical</option>
                      <option value="HIGH">High</option>
                      <option value="MEDIUM">Medium</option>
                      <option value="LOW">Low</option>
                    </select>

                    <select
                      value={categoryFilter}
                      onChange={(e) => setCategoryFilter(e.target.value)}
                      className="bg-[#0d0d11] border border-white/[0.08] text-xs text-zinc-300 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="ALL">All Categories</option>
                      <option value="SENSITIVE_DATA_EXPOSURE">Sensitive Data Exposure</option>
                      <option value="ACCESS_CONTROL">Access Control</option>
                      <option value="CONNECTION_SECURITY">Connection Security</option>
                    </select>
                  </div>
                </div>

                {/* Findings List */}
                {!scanResult ? (
                  <div className="p-12 text-center rounded-xl bg-[#0d0d11] border border-white/[0.08]">
                    <Search className="w-10 h-10 text-indigo-400 mx-auto mb-3" />
                    <h4 className="text-sm font-medium text-white">No Scan Results Available</h4>
                    <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
                      Click the "Run Security Scan" button to perform a bounded, read-only inspection for unmasked credit cards, plain passwords, SSNs, and API keys.
                    </p>
                    <button
                      onClick={handleRunScan}
                      disabled={scanning || !dbConnected}
                      className="mt-4 px-4 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white"
                    >
                      {scanning ? "Scanning..." : "Start Security Scan"}
                    </button>
                  </div>
                ) : filteredFindings.length === 0 ? (
                  <div className="p-12 text-center rounded-xl bg-[#0d0d11] border border-white/[0.08]">
                    <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                    <h4 className="text-sm font-medium text-white">No Matching Findings</h4>
                    <p className="text-xs text-zinc-400 mt-1">
                      {scanResult.findings.length === 0
                        ? "Scanned bounded sample rows. No exposed plaintext credentials, payment cards, or keys were detected."
                        : "No findings matched your search and filter criteria."}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredFindings.map((finding) => {
                      const isExpanded = expandedFindingId === finding.id;
                      return (
                        <div
                          key={finding.id}
                          className="rounded-xl bg-[#0d0d11] border border-white/[0.08] hover:border-white/20 transition-all overflow-hidden"
                        >
                          <div
                            onClick={() => setExpandedFindingId(isExpanded ? null : finding.id)}
                            className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 cursor-pointer select-none"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                {getSeverityBadge(finding.severity)}
                                <span className="text-xs font-semibold text-white">{finding.title}</span>
                                {finding.table && (
                                  <span className="px-1.5 py-0.2 rounded text-[10px] bg-white/[0.04] text-zinc-300 font-mono border border-white/[0.06]">
                                    {finding.table}{finding.column ? `.${finding.column}` : ""}
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-zinc-400">{finding.evidence_summary}</p>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleExplainFinding(finding);
                                }}
                                className="px-2.5 py-1 text-xs font-medium rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 flex items-center gap-1.5 transition-colors"
                              >
                                <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                                Explain with AI
                              </button>
                              <div className="text-zinc-500">
                                {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                              </div>
                            </div>
                          </div>

                          {isExpanded && (
                            <div className="px-4 pb-4 pt-2 border-t border-white/[0.04] bg-white/[0.01] space-y-2 text-xs">
                              <div>
                                <strong className="text-zinc-400">Category:</strong>{" "}
                                <span className="text-zinc-200">{finding.category}</span>
                              </div>
                              <div>
                                <strong className="text-zinc-400">Recommended Remediation:</strong>{" "}
                                <span className="text-indigo-300">{finding.remediation}</span>
                              </div>
                              {finding.sample_count !== undefined && (
                                <div>
                                  <strong className="text-zinc-400">Pattern Matches in Sample:</strong>{" "}
                                  <span className="text-zinc-200 font-mono">{finding.sample_count}</span>
                                </div>
                              )}
                              <p className="text-[11px] text-zinc-500 italic mt-1">
                                Safeguard Note: Raw matched values are sanitized and never exposed to the frontend or application logs.
                              </p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ── C. Threat Incidents Tab ──────────────────────────────────── */}
            {activeSubTab === "events" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Security Threat & Incident Feed</h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Immutable record of query violations, prompt injection detections, and authentication guardrails.
                    </p>
                  </div>
                </div>

                {securityEvents.length === 0 ? (
                  <div className="p-12 text-center rounded-xl bg-[#0d0d11] border border-white/[0.08]">
                    <ShieldCheck className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                    <h4 className="text-sm font-medium text-white">No Security Incidents Detected</h4>
                    <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
                      All query executions, agent actions, and database transactions conform to active security policies.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {securityEvents.map((evt) => (
                      <div
                        key={evt.event_id}
                        className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] hover:border-white/20 transition-all flex flex-col md:flex-row md:items-start justify-between gap-4"
                      >
                        <div className="space-y-1.5 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {getSeverityBadge(evt.severity)}
                            <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.06]">
                              {evt.event_type}
                            </span>
                            <span className="text-xs text-zinc-500">
                              {new Date(evt.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-200 font-medium mt-1">{evt.description}</p>
                          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-400">
                            <span><strong className="text-zinc-500">Source:</strong> {evt.source}</span>
                            <span><strong className="text-zinc-500">Resource:</strong> {evt.resource}</span>
                            <span><strong className="text-zinc-500">Status:</strong> {evt.status}</span>
                          </div>
                          {evt.mitigation && (
                            <p className="text-[11px] text-indigo-300 mt-1 bg-indigo-500/10 px-2 py-1 rounded border border-indigo-500/20">
                              <strong>Guardrail Action:</strong> {evt.mitigation}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── C2. IP Threats & Intrusion Detection Tab ─────────────────── */}
            {activeSubTab === "ip_threats" && (
              <div className="space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.06]">
                  <div>
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Globe className="w-4 h-4 text-indigo-400" />
                      IP Threat Intelligence & Intrusion Detection
                    </h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Monitors suspicious access attempts, brute-force attacks, abusive bursts, and attributes threat activity to reliable client IP addresses.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={loadData}
                      disabled={loading}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 border border-white/[0.08] flex items-center gap-1.5 transition-all"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                      Refresh Alerts
                    </button>
                  </div>
                </div>

                {/* Active IP Blocks Banner */}
                {activeIPBlocks.length > 0 && (
                  <div className="p-4 rounded-xl bg-red-950/30 border border-red-500/30 text-white space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm font-semibold text-red-300">
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                        Active Temporary IP Blocks ({activeIPBlocks.length})
                      </div>
                      <span className="text-[11px] text-zinc-400 font-mono">Enforcing Automated Quarantine</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {activeIPBlocks.map((blk) => (
                        <div
                          key={blk.ip_address}
                          className="p-3 rounded-lg bg-black/40 border border-red-500/20 flex items-center justify-between gap-3"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono font-bold text-red-300">{blk.ip_address}</span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 font-mono">
                                {blk.rule_triggered}
                              </span>
                            </div>
                            <p className="text-[11px] text-zinc-400 mt-1">{blk.reason}</p>
                            <p className="text-[10px] text-zinc-500 font-mono mt-0.5">
                              Expires in: {Math.max(0, Math.floor(blk.remaining_seconds / 60))}m {blk.remaining_seconds % 60}s
                            </p>
                          </div>
                          <button
                            onClick={() => handleUnblockIP(blk.ip_address)}
                            disabled={unblockingIp === blk.ip_address}
                            className="px-2.5 py-1 text-xs font-medium rounded bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-500/40 shrink-0 transition-all"
                          >
                            {unblockingIp === blk.ip_address ? "Unblocking..." : "Unblock"}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Filter Toolbar */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                  <div className="relative flex-1 max-w-xs">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
                    <input
                      type="text"
                      placeholder="Filter by Source IP..."
                      value={ipFilter}
                      onChange={(e) => setIpFilter(e.target.value)}
                      className="w-full bg-[#0d0d11] border border-white/[0.08] rounded-lg pl-9 pr-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500 font-mono"
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={threatTypeFilter}
                      onChange={(e) => setThreatTypeFilter(e.target.value)}
                      className="bg-[#0d0d11] border border-white/[0.08] text-xs text-zinc-300 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="ALL">All Threat Categories</option>
                      <option value="BRUTE_FORCE_DETECTED">Brute Force Attacks</option>
                      <option value="INJECTION_PATTERN_DETECTED">SQL Injections</option>
                      <option value="DDL_BLOCKED">Destructive DDL</option>
                      <option value="SUSPICIOUS_BURST_DETECTED">Abnormal Bursts</option>
                      <option value="ENDPOINT_SCAN_DETECTED">Endpoint Scans</option>
                      <option value="IP_BLOCKED">Quarantine Blocks</option>
                    </select>

                    <select
                      value={ipSeverityFilter}
                      onChange={(e) => setIpSeverityFilter(e.target.value)}
                      className="bg-[#0d0d11] border border-white/[0.08] text-xs text-zinc-300 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="ALL">All Severities</option>
                      <option value="CRITICAL">Critical</option>
                      <option value="HIGH">High</option>
                      <option value="MEDIUM">Medium</option>
                      <option value="LOW">Low</option>
                    </select>
                  </div>
                </div>

                {/* Threat Events Feed */}
                {(() => {
                  const filtered = ipThreatEvents.filter((evt) => {
                    const meta = evt.metadata || {};
                    const sourceIp = meta.source_ip || "";
                    if (ipFilter && !sourceIp.toLowerCase().includes(ipFilter.toLowerCase()) && !evt.description.toLowerCase().includes(ipFilter.toLowerCase())) {
                      return false;
                    }
                    if (ipSeverityFilter !== "ALL" && evt.severity !== ipSeverityFilter) {
                      return false;
                    }
                    if (threatTypeFilter !== "ALL" && evt.event_type !== threatTypeFilter) {
                      return false;
                    }
                    return true;
                  });

                  if (filtered.length === 0) {
                    return (
                      <div className="p-12 text-center rounded-xl bg-[#0d0d11] border border-white/[0.08]">
                        <ShieldCheck className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                        <h4 className="text-sm font-medium text-white">No IP Threats Detected</h4>
                        <p className="text-xs text-zinc-400 mt-1 max-w-md mx-auto">
                          No intrusion alerts, brute-force patterns, or abnormal request bursts match the active filter criteria.
                        </p>
                      </div>
                    );
                  }

                  return (
                    <div className="space-y-3">
                      {filtered.map((evt) => {
                        const meta = evt.metadata || {};
                        const sourceIp = meta.source_ip || "unknown";
                        const isBlocked = activeIPBlocks.some((b) => b.ip_address === sourceIp);

                        return (
                          <div
                            key={evt.event_id}
                            className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] hover:border-white/20 transition-all flex flex-col md:flex-row md:items-start justify-between gap-4"
                          >
                            <div className="space-y-1.5 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                {getSeverityBadge(evt.severity)}
                                <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.06]">
                                  {evt.event_type}
                                </span>
                                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 flex items-center gap-1">
                                  <Radio className="w-3 h-3 text-indigo-400" />
                                  IP: {sourceIp}
                                </span>
                                {isBlocked && (
                                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/30">
                                    BLOCKED
                                  </span>
                                )}
                                <span className="text-xs text-zinc-500">
                                  {new Date(evt.timestamp).toLocaleString()}
                                </span>
                              </div>
                              <p className="text-xs text-zinc-200 font-medium mt-1">{evt.description}</p>
                              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-zinc-400">
                                <span><strong className="text-zinc-500">Endpoint:</strong> {evt.resource}</span>
                                <span><strong className="text-zinc-500">Outcome:</strong> {evt.status}</span>
                                {meta.attempt_count && (
                                  <span><strong className="text-zinc-500">Attempts:</strong> {meta.attempt_count}</span>
                                )}
                                {meta.target_account && (
                                  <span><strong className="text-zinc-500">Target Account:</strong> {meta.target_account}</span>
                                )}
                              </div>
                              {evt.mitigation && (
                                <p className="text-[11px] text-indigo-300 mt-1 bg-indigo-500/10 px-2 py-1 rounded border border-indigo-500/20">
                                  <strong>Remediation:</strong> {evt.mitigation}
                                </p>
                              )}
                            </div>

                            {sourceIp !== "unknown" && (
                              <div className="shrink-0 flex items-center gap-2 self-start md:self-auto">
                                <button
                                  onClick={() => handleCheckReputation(sourceIp)}
                                  disabled={reputationLoading}
                                  className="px-2.5 py-1 text-xs font-medium rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 border border-white/[0.08] flex items-center gap-1 transition-all"
                                  title="Inspect IP intelligence profile"
                                >
                                  <Info className="w-3.5 h-3.5 text-zinc-400" />
                                  Reputation
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            )}

            {/* ── D. Guardrail Policies Tab ─────────────────────────────────── */}
            {activeSubTab === "policies" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Operational Guardrail Policies</h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Enforce strict execution constraints on database queries, agent mutations, and sensitive operations.
                    </p>
                  </div>
                </div>

                {policies.length === 0 ? (
                  <div className="p-8 text-center text-zinc-500 text-sm">No security policies registered.</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {policies.map((policy) => (
                      <div
                        key={policy.policy_id}
                        className="p-4 rounded-xl bg-[#0d0d11] border border-white/[0.08] flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <span className="text-xs font-semibold text-white">{policy.name}</span>
                            <span
                              className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase font-mono ${
                                policy.enabled
                                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                  : "bg-zinc-700/50 text-zinc-400 border border-zinc-600"
                              }`}
                            >
                              {policy.enabled ? "ACTIVE" : "INACTIVE"}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400 leading-relaxed mb-3">{policy.description}</p>
                          <div className="text-[11px] text-zinc-500 space-y-1 mb-4 bg-white/[0.02] p-2.5 rounded border border-white/[0.04]">
                            <div><strong>Category:</strong> {policy.category}</div>
                            <div><strong>Default Decision:</strong> {policy.decision}</div>
                            <div><strong>Rationale:</strong> {policy.rationale}</div>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between">
                          <span className="text-[11px] text-zinc-400">Toggle Policy</span>
                          <button
                            onClick={() =>
                              setPendingPolicy({
                                policy,
                                targetState: !policy.enabled,
                              })
                            }
                            className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                              policy.enabled
                                ? "bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/30"
                                : "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                            }`}
                          >
                            {policy.enabled ? "Disable Policy" : "Enable Policy"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── E. Tamper-Evident Audit Ledger Tab ────────────────────────── */}
            {activeSubTab === "audit" && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/[0.06]">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Cryptographic Audit Ledger</h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Every database operation is chained with SHA-256 hashes to guarantee tamper resistance.
                    </p>
                  </div>

                  <button
                    onClick={handleVerifyChain}
                    disabled={verifyingChain}
                    className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5 shadow-md shadow-emerald-600/20 transition-all"
                  >
                    <FileCheck className={`w-3.5 h-3.5 ${verifyingChain ? "animate-spin" : ""}`} />
                    {verifyingChain ? "Verifying SHA-256..." : "Verify Audit Chain Integrity"}
                  </button>
                </div>

                {chainResult && (
                  <div
                    className={`p-4 rounded-xl border flex items-center gap-3 ${
                      chainResult.verified
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                        : "bg-red-500/10 border-red-500/30 text-red-300"
                    }`}
                  >
                    {chainResult.verified ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
                    )}
                    <div>
                      <p className="text-xs font-semibold">
                        {chainResult.verified
                          ? "Cryptographic Verification Passed"
                          : "Chain Verification Failed"}
                      </p>
                      <p className="text-[11px] opacity-90 mt-0.5">
                        {chainResult.events_verified ?? 0} events verified without hash mismatches or sequence gaps.
                        {chainResult.error_detail && ` Detail: ${chainResult.error_detail}`}
                      </p>
                    </div>
                  </div>
                )}

                {auditEvents.length === 0 ? (
                  <div className="p-8 text-center text-zinc-500 text-sm">No audit events recorded yet.</div>
                ) : (
                  <div className="rounded-xl bg-[#0d0d11] border border-white/[0.08] overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs text-zinc-300">
                        <thead className="bg-white/[0.03] text-zinc-400 border-b border-white/[0.06]">
                          <tr>
                            <th className="py-2.5 px-4 font-medium">Timestamp</th>
                            <th className="py-2.5 px-4 font-medium">Action</th>
                            <th className="py-2.5 px-4 font-medium">Actor</th>
                            <th className="py-2.5 px-4 font-medium">Resource</th>
                            <th className="py-2.5 px-4 font-medium">Result</th>
                            <th className="py-2.5 px-4 font-medium">SHA-256 Event Hash</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04]">
                          {auditEvents.map((evt) => (
                            <tr key={evt.event_id} className="hover:bg-white/[0.02]">
                              <td className="py-2 px-4 text-zinc-400 font-mono text-[11px] whitespace-nowrap">
                                {new Date(evt.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                              </td>
                              <td className="py-2 px-4 font-medium text-white">{evt.action}</td>
                              <td className="py-2 px-4 text-zinc-400">{evt.actor_type}</td>
                              <td className="py-2 px-4 text-zinc-300 font-mono text-[11px]">{evt.resource_id}</td>
                              <td className="py-2 px-4">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                    evt.result === "SUCCESS" || evt.result === "ALLOWED"
                                      ? "bg-emerald-500/20 text-emerald-400"
                                      : "bg-red-500/20 text-red-400"
                                  }`}
                                >
                                  {evt.result}
                                </span>
                              </td>
                              <td className="py-2 px-4 font-mono text-[10px] text-zinc-500 whitespace-nowrap">
                                {evt.event_hash ? evt.event_hash.substring(0, 16) + "..." : "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Confirmation Modal for Policy Modification */}
      {pendingPolicy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="bg-[#121217] border border-white/10 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-amber-400">
              <AlertTriangle className="w-6 h-6 shrink-0" />
              <h3 className="text-base font-bold text-white">Confirm Policy Modification</h3>
            </div>

            <p className="text-xs text-zinc-300 leading-relaxed">
              Are you sure you want to {pendingPolicy.targetState ? "ENABLE" : "DISABLE"} the policy:
              <br />
              <span className="font-semibold text-white mt-1 block">'{pendingPolicy.policy.name}'</span>
            </p>

            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 leading-relaxed">
              <strong>Impact Notice:</strong> This modification changes live execution guardrails across active database queries and agent mutations.
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setPendingPolicy(null)}
                disabled={updatingPolicy}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmPolicyChange}
                disabled={updatingPolicy}
                className={`px-4 py-1.5 text-xs font-medium rounded-lg text-white shadow-md transition-all ${
                  pendingPolicy.targetState
                    ? "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/20"
                    : "bg-red-600 hover:bg-red-500 shadow-red-600/20"
                }`}
              >
                {updatingPolicy ? "Applying..." : "Confirm & Apply"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI Explanation Modal */}
      {explainingFinding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="bg-[#121217] border border-white/10 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-bold text-white">AI Cybersecurity Advisory</h3>
              </div>
              <button
                onClick={() => setExplainingFinding(null)}
                className="text-zinc-500 hover:text-white p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {explanationLoading ? (
              <div className="py-12 text-center">
                <RefreshCw className="w-7 h-7 text-indigo-400 animate-spin mx-auto mb-3" />
                <p className="text-xs text-zinc-300 font-medium">Synthesizing threat analysis & remediation plan...</p>
                <p className="text-[11px] text-zinc-500 mt-1">Analyzing finding context without exposing sensitive data</p>
              </div>
            ) : explanationData ? (
              <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
                <div>
                  <div className="flex items-center gap-2">
                    {getSeverityBadge(explanationData.severity)}
                    <span className="text-xs font-bold text-white">{explanationData.title}</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 font-mono mt-0.5">{explanationData.location}</p>
                </div>

                <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-1.5">
                  <h4 className="text-xs font-semibold text-indigo-300">Why It Matters</h4>
                  <p className="text-xs text-zinc-300 leading-relaxed">{explanationData.why_it_matters}</p>
                </div>

                <div className="p-3 rounded-xl bg-red-500/[0.03] border border-red-500/10 space-y-1.5">
                  <h4 className="text-xs font-semibold text-red-300">Potential Business & Security Impact</h4>
                  <p className="text-xs text-zinc-300 leading-relaxed">{explanationData.potential_impact}</p>
                </div>

                <div className="p-3 rounded-xl bg-emerald-500/[0.03] border border-emerald-500/10 space-y-2">
                  <h4 className="text-xs font-semibold text-emerald-300">Prioritized Remediation Steps</h4>
                  <div className="space-y-1.5">
                    {explanationData.remediation_steps.map((step, idx) => (
                      <p key={idx} className="text-xs text-zinc-200 leading-relaxed">
                        {step}
                      </p>
                    ))}
                  </div>
                </div>

                <p className="text-[10px] text-zinc-500 italic">
                  {explanationData.uncertainty_and_limitations}
                </p>
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-red-400">
                Could not load explanation. Please try again.
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-white/[0.06]">
              <button
                onClick={() => setExplainingFinding(null)}
                className="px-4 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white"
              >
                Close Advisory
              </button>
            </div>
          </div>
        </div>
      )}

      {/* IP Reputation Modal */}
      {selectedReputation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-lg bg-[#111116] border border-white/[0.1] rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                  <Globe className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">IP Intelligence Profile</h3>
                  <p className="text-xs font-mono text-zinc-400 mt-0.5">{selectedReputation.ip_address}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedReputation(null)}
                className="p-1 rounded-lg hover:bg-white/[0.06] text-zinc-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-3 rounded-lg bg-[#0d0d11] border border-white/[0.06]">
                <span className="text-zinc-400">Classification</span>
                <span className={`font-mono font-bold uppercase px-2 py-0.5 rounded text-[11px] ${
                  selectedReputation.classification === "blocked"
                    ? "bg-red-500/20 text-red-300 border border-red-500/30"
                    : selectedReputation.classification === "internal_trusted"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "bg-zinc-700 text-zinc-300"
                }`}>
                  {selectedReputation.classification}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 rounded-lg bg-[#0d0d11] border border-white/[0.06]">
                  <span className="text-[11px] text-zinc-500 block">Telemetry Provider</span>
                  <span className="font-mono text-zinc-300 text-xs mt-0.5 block">{selectedReputation.provider}</span>
                </div>
                <div className="p-3 rounded-lg bg-[#0d0d11] border border-white/[0.06]">
                  <span className="text-[11px] text-zinc-500 block">Network Segment</span>
                  <span className="font-mono text-zinc-300 text-xs mt-0.5 block">
                    {selectedReputation.is_private_network ? "Private LAN / RFC-1918" : selectedReputation.is_loopback ? "Loopback Localhost" : "Public Internet"}
                  </span>
                </div>
              </div>

              {selectedReputation.reason && (
                <div className="p-3 rounded-lg bg-red-950/20 border border-red-500/20">
                  <span className="text-[11px] text-red-400 font-semibold block">Quarantine Trigger:</span>
                  <p className="text-zinc-300 mt-1">{selectedReputation.reason}</p>
                </div>
              )}

              <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-zinc-400 text-[11px] leading-relaxed">
                <strong>Privacy & Evidence Assurance:</strong> {selectedReputation.note}
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-white/[0.06]">
              <button
                onClick={() => setSelectedReputation(null)}
                className="px-4 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white"
              >
                Close Profile
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
