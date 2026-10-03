import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  FileCode2,
  Play,
  XCircle,
  Eye,
  RefreshCw,
  Plus,
  ArrowRight,
  Database,
  Lock,
  Layers,
  Check,
  AlertCircle,
} from "lucide-react";
import {
  listActions,
  proposeAction,
  previewAction,
  confirmAction,
  executeAction,
  cancelAction,
  getAuthToken,
} from "../../../services/api";
import type { ActionProposal } from "../../../types";

interface ActionProposalSectionProps {
  dbConnected: boolean;
  onConnectDatabase?: () => void;
}

export default function ActionProposalSection({
  dbConnected,
  onConnectDatabase,
}: ActionProposalSectionProps) {
  const [actions, setActions] = useState<ActionProposal[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // New action proposal form modal state
  const [showProposeModal, setShowProposeModal] = useState<boolean>(false);
  const [actionType, setActionType] = useState<"UPDATE" | "INSERT" | "DELETE">("UPDATE");
  const [targetTable, setTargetTable] = useState<string>("");
  const [columnName, setColumnName] = useState<string>("");
  const [proposedValue, setProposedValue] = useState<string>("");
  const [conditionSql, setConditionSql] = useState<string>("");
  const [paramKey, setParamKey] = useState<string>("");
  const [paramVal, setParamVal] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [submittingProposal, setSubmittingProposal] = useState<boolean>(false);

  // Action execution / confirmation states
  const [selectedAction, setSelectedAction] = useState<ActionProposal | null>(null);
  const [highRiskAcknowledged, setHighRiskAcknowledged] = useState<Record<string, boolean>>({});
  const [processingId, setProcessingId] = useState<string | null>(null);

  const fetchActions = useCallback(async () => {
    if (!dbConnected || !getAuthToken()) {
      setActions([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await listActions({ limit: 30 });
      if (resp && Array.isArray(resp.actions)) {
        setActions(resp.actions);
      } else {
        setActions([]);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load action proposals.");
    } finally {
      setLoading(false);
    }
  }, [dbConnected]);

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  const handlePropose = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetTable) {
      setError("Target table is required.");
      return;
    }
    setSubmittingProposal(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const params: Record<string, any> = {};
      if (paramKey && paramVal) {
        params[paramKey] = isNaN(Number(paramVal)) ? paramVal : Number(paramVal);
      }

      const changes =
        actionType === "DELETE"
          ? []
          : [
              {
                column: columnName || "status",
                proposed_value: isNaN(Number(proposedValue))
                  ? proposedValue
                  : Number(proposedValue),
              },
            ];

      const resp = await proposeAction({
        action_type: actionType,
        target_table: targetTable.trim(),
        changes,
        condition_sql: conditionSql.trim() || undefined,
        condition_params: Object.keys(params).length > 0 ? params : undefined,
        reason: reason.trim() || "Administrative action via workspace UI",
      });

      if (resp && resp.action) {
        setSuccessMsg(`Action proposal created: ${resp.action.action_id}`);
        setShowProposeModal(false);
        // Reset form
        setTargetTable("");
        setColumnName("");
        setProposedValue("");
        setConditionSql("");
        setParamKey("");
        setParamVal("");
        setReason("");
        await fetchActions();
      }
    } catch (err: any) {
      setError(err.message || "Failed to create action proposal.");
    } finally {
      setSubmittingProposal(false);
    }
  };

  const handlePreview = async (actionId: string) => {
    setProcessingId(actionId);
    setError(null);
    try {
      const resp = await previewAction(actionId);
      if (resp && resp.action) {
        setActions((prev) =>
          prev.map((a) => (a.action_id === actionId ? resp.action : a))
        );
        setSuccessMsg(`Impact preview computed for ${actionId}`);
      }
    } catch (err: any) {
      setError(err.message || "Failed to preview action impact.");
    } finally {
      setProcessingId(null);
    }
  };

  const handleConfirm = async (action: ActionProposal) => {
    if (action.risk === "HIGH" && !highRiskAcknowledged[action.action_id]) {
      setError("High-risk actions require explicit acknowledgment checkbox before confirmation.");
      return;
    }
    setProcessingId(action.action_id);
    setError(null);
    try {
      const resp = await confirmAction(action.action_id, {
        high_risk_acknowledged: Boolean(highRiskAcknowledged[action.action_id]),
      });
      if (resp && resp.action) {
        setActions((prev) =>
          prev.map((a) => (a.action_id === action.action_id ? resp.action : a))
        );
        setSuccessMsg(`Action confirmed. Ready for execution.`);
      }
    } catch (err: any) {
      setError(err.message || "Confirmation failed.");
    } finally {
      setProcessingId(null);
    }
  };

  const handleExecute = async (action: ActionProposal) => {
    if (!action.confirmation?.confirmation_token) {
      setError("Action has no confirmation token. Please confirm first.");
      return;
    }
    setProcessingId(action.action_id);
    setError(null);
    try {
      const resp = await executeAction(action.action_id, {
        confirmation_token: action.confirmation.confirmation_token,
      });
      if (resp && resp.action) {
        setActions((prev) =>
          prev.map((a) => (a.action_id === action.action_id ? resp.action : a))
        );
        setSuccessMsg(`Action executed and verified successfully! Transaction: ${resp.execution?.transaction_id || 'committed'}`);
      }
    } catch (err: any) {
      setError(err.message || "Execution failed.");
    } finally {
      setProcessingId(null);
    }
  };

  const handleCancel = async (actionId: string) => {
    setProcessingId(actionId);
    setError(null);
    try {
      const resp = await cancelAction(actionId);
      if (resp && resp.action) {
        setActions((prev) =>
          prev.map((a) => (a.action_id === actionId ? resp.action : a))
        );
        setSuccessMsg(`Action ${actionId} cancelled.`);
      }
    } catch (err: any) {
      setError(err.message || "Failed to cancel action.");
    } finally {
      setProcessingId(null);
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case "LOW":
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            LOW RISK
          </span>
        );
      case "MEDIUM":
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/10 border border-amber-500/30 text-amber-400">
            MEDIUM RISK
          </span>
        );
      case "HIGH":
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/10 border border-rose-500/30 text-rose-400">
            HIGH RISK
          </span>
        );
      case "BLOCKED":
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-red-500/20 border border-red-500/40 text-red-300">
            BLOCKED
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "PROPOSED":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-blue-500/15 border border-blue-500/30 text-blue-300">
            PROPOSED
          </span>
        );
      case "PREVIEWED":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
            PREVIEWED
          </span>
        );
      case "CONFIRMED":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-amber-500/15 border border-amber-500/30 text-amber-300">
            CONFIRMED
          </span>
        );
      case "EXECUTED":
      case "VERIFIED":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
            {status}
          </span>
        );
      case "CANCELLED":
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-zinc-700/40 border border-zinc-600/40 text-zinc-400">
            CANCELLED
          </span>
        );
      case "FAILED":
      default:
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-red-500/20 border border-red-500/40 text-red-400">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-[#0c0d12] p-5 shadow-2xl space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Lock size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Controlled Business Actions & Action Intelligence
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
                Phase 8.8
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Zero autonomous mutation • Impact preview • HMAC confirmation • Transactional execution • Immutable audit
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchActions}
            disabled={loading || !dbConnected}
            className="p-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-white border border-white/[0.06] transition-colors disabled:opacity-40"
            title="Refresh action proposals"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
          <button
            onClick={() => setShowProposeModal(true)}
            disabled={!dbConnected}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 transition-colors disabled:opacity-40"
          >
            <Plus size={14} />
            Propose Action
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
            <XCircle size={14} />
          </button>
        </div>
      )}
      {successMsg && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Check size={14} />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-300">
            <XCircle size={14} />
          </button>
        </div>
      )}

      {/* DB Disconnected Alert */}
      {!dbConnected && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle className="text-amber-400" size={18} />
            <div>
              <p className="text-xs font-semibold text-amber-300">No Database Connected</p>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                Connect a database to propose safe business actions, preview impact, and execute transactions.
              </p>
            </div>
          </div>
          {onConnectDatabase && (
            <button
              onClick={onConnectDatabase}
              className="px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs font-semibold border border-amber-500/40 transition-colors"
            >
              Connect Database
            </button>
          )}
        </div>
      )}

      {/* Action Proposals List */}
      {dbConnected && (
        <div className="space-y-4">
          {actions.length === 0 && !loading && (
            <div className="py-8 text-center border border-dashed border-white/[0.08] rounded-xl text-zinc-500 text-xs">
              No business actions proposed yet. Click &quot;Propose Action&quot; above to create a safe mutation proposal.
            </div>
          )}

          {actions.map((act) => {
            const isProcessing = processingId === act.action_id;
            const canPreview = ["PROPOSED"].includes(act.status);
            const canConfirm = ["PROPOSED", "PREVIEWED"].includes(act.status);
            const canExecute = act.status === "CONFIRMED";
            const canCancel = ["PROPOSED", "PREVIEWED", "CONFIRMED"].includes(act.status);
            const isCompleted = ["EXECUTED", "VERIFIED"].includes(act.status);

            return (
              <div
                key={act.action_id}
                className="p-4 rounded-xl border border-white/[0.06] bg-black/40 space-y-4 hover:border-white/[0.12] transition-colors"
              >
                {/* Header row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-white">
                      {act.action_id}
                    </span>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-white/[0.06] text-zinc-300 border border-white/[0.08]">
                      {act.action_type}
                    </span>
                    <span className="font-mono text-xs text-indigo-400">
                      table: {act.target.table}
                    </span>
                    {getRiskBadge(act.risk)}
                    {getStatusBadge(act.status)}
                  </div>
                  <span className="text-[11px] text-zinc-500 font-mono">
                    {new Date(act.created_at).toLocaleTimeString()}
                  </span>
                </div>

                {/* Reason & Strategy */}
                <div className="text-xs text-zinc-300 bg-white/[0.02] p-2.5 rounded-lg border border-white/[0.04]">
                  <span className="text-zinc-500 font-semibold uppercase tracking-wider text-[10px] block mb-1">
                    Business Rationale
                  </span>
                  {act.reason}
                </div>

                {/* Proposed Changes */}
                {act.changes && act.changes.length > 0 && (
                  <div className="space-y-1.5">
                    <span className="text-zinc-500 font-semibold uppercase tracking-wider text-[10px] block">
                      Target Changes
                    </span>
                    <div className="rounded-lg border border-white/[0.06] bg-black/50 overflow-hidden text-xs">
                      <table className="w-full text-left font-mono">
                        <thead className="bg-white/[0.03] text-zinc-400 text-[11px] border-b border-white/[0.06]">
                          <tr>
                            <th className="p-2">Column</th>
                            <th className="p-2">Current Value</th>
                            <th className="p-2">Proposed Value</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/[0.04] text-zinc-300">
                          {act.changes.map((ch, idx) => (
                            <tr key={idx} className="hover:bg-white/[0.02]">
                              <td className="p-2 text-indigo-300">{ch.column}</td>
                              <td className="p-2 text-zinc-500">
                                {ch.current_value !== undefined ? String(ch.current_value) : "(sample)"}
                              </td>
                              <td className="p-2 text-emerald-400 font-bold">
                                {String(ch.proposed_value)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* SQL Drawer */}
                <div className="space-y-1">
                  <span className="text-zinc-500 font-semibold uppercase tracking-wider text-[10px] block">
                    Parameterized SQL Execution Plan
                  </span>
                  <div className="p-3 rounded-lg bg-black/60 border border-white/[0.06] font-mono text-xs text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                    {act.parameterized_sql || act.sql_preview}
                  </div>
                  {act.parameters && Object.keys(act.parameters).length > 0 && (
                    <div className="text-[11px] font-mono text-zinc-400 px-1">
                      Bound Parameters:{" "}
                      <span className="text-zinc-200">
                        {JSON.stringify(act.parameters)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Validation Status */}
                {act.validation && (
                  <div className="p-2.5 rounded-lg border border-white/[0.04] bg-white/[0.01] text-xs space-y-1">
                    <div className="flex items-center gap-2">
                      {act.validation.is_valid ? (
                        <CheckCircle2 size={13} className="text-emerald-400" />
                      ) : (
                        <AlertTriangle size={13} className="text-rose-400" />
                      )}
                      <span className="font-semibold text-zinc-300">
                        Validation: {act.validation.is_valid ? "PASSED" : "FAILED / BLOCKED"}
                      </span>
                    </div>
                    {act.validation.blocked_reason && (
                      <p className="text-rose-400 text-[11px] font-mono">
                        Blocked: {act.validation.blocked_reason}
                      </p>
                    )}
                    {act.validation.passed_checks && (
                      <div className="text-[10px] text-zinc-500 flex flex-wrap gap-2 pt-0.5">
                        {act.validation.passed_checks.map((pc, i) => (
                          <span key={i} className="text-zinc-400">✓ {pc}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Impact Preview details */}
                {act.impact && (
                  <div className="p-3 rounded-lg border border-indigo-500/20 bg-indigo-500/5 text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-indigo-300 flex items-center gap-1.5">
                        <Eye size={13} />
                        Impact Preview
                      </span>
                      <span className="font-mono text-zinc-300">
                        Estimated affected rows:{" "}
                        <strong className="text-emerald-400 font-bold">
                          {act.impact.estimated_rows}
                        </strong>
                      </span>
                    </div>
                    {act.impact.warnings && act.impact.warnings.length > 0 && (
                      <div className="text-amber-300 text-[11px] flex flex-col gap-1">
                        {act.impact.warnings.map((w, idx) => (
                          <div key={idx} className="flex items-center gap-1.5">
                            <AlertTriangle size={13} className="shrink-0" />
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {act.impact.related_records_count && Object.keys(act.impact.related_records_count).length > 0 && (
                      <div className="text-zinc-400 text-[11px] flex flex-wrap gap-2 pt-1 border-t border-indigo-500/10">
                        <span>Related records:</span>
                        {Object.entries(act.impact.related_records_count).map(([tbl, cnt]) => (
                          <span key={tbl} className="text-indigo-300 font-mono">
                            {tbl}: {cnt}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Confirmation info */}
                {act.confirmation && (
                  <div className="p-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5 text-xs flex items-center justify-between">
                    <div className="space-y-0.5">
                      <p className="font-semibold text-amber-300">Action Confirmed by User</p>
                      <p className="text-[11px] font-mono text-zinc-400">
                        Token: {act.confirmation.confirmation_token.substring(0, 16)}... (Expires: {new Date(act.confirmation.expires_at).toLocaleTimeString()})
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      HMAC Validated
                    </span>
                  </div>
                )}

                {/* Completed execution result */}
                {isCompleted && act.execution_result && (
                  <div className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-xs space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-emerald-400 font-bold">
                        <ShieldCheck size={14} />
                        <span>Execution Succeeded & Committed</span>
                      </div>
                      <span className="text-[11px] font-mono text-zinc-400">
                        TX: {act.execution_result.transaction_id}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-300">
                      Actual rows modified: <strong>{act.execution_result.actual_rows_affected}</strong>
                    </p>
                    {act.verification && (
                      <div className="pt-1.5 border-t border-emerald-500/20 text-[11px] text-zinc-400 space-y-0.5">
                        <p className="text-emerald-300 font-semibold">Post-Execution Verification:</p>
                        <p className="font-mono text-zinc-300">{act.verification.details}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Action Buttons Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-white/[0.04]">
                  {/* High risk acknowledgement checkbox */}
                  {act.risk === "HIGH" && canConfirm && (
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-rose-300 bg-rose-500/10 px-3 py-1.5 rounded-lg border border-rose-500/20">
                      <input
                        type="checkbox"
                        checked={Boolean(highRiskAcknowledged[act.action_id])}
                        onChange={(e) =>
                          setHighRiskAcknowledged((prev) => ({
                            ...prev,
                            [act.action_id]: e.target.checked,
                          }))
                        }
                        className="rounded border-rose-500 text-rose-600 focus:ring-rose-500"
                      />
                      <span>I acknowledge this is a high-risk mutation.</span>
                    </label>
                  )}

                  <div className="flex items-center gap-2 ml-auto">
                    {canCancel && (
                      <button
                        onClick={() => handleCancel(act.action_id)}
                        disabled={isProcessing}
                        className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-white text-xs font-semibold border border-white/[0.06] transition-colors disabled:opacity-40"
                      >
                        Cancel
                      </button>
                    )}

                    {canPreview && (
                      <button
                        onClick={() => handlePreview(act.action_id)}
                        disabled={isProcessing}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 text-xs font-semibold border border-indigo-500/30 transition-colors disabled:opacity-40"
                      >
                        <Eye size={13} />
                        Preview Impact
                      </button>
                    )}

                    {canConfirm && (
                      <button
                        onClick={() => handleConfirm(act)}
                        disabled={
                          isProcessing ||
                          (act.risk === "HIGH" && !highRiskAcknowledged[act.action_id])
                        }
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold transition-colors disabled:opacity-40"
                      >
                        <Check size={13} />
                        Confirm Action
                      </button>
                    )}

                    {canExecute && (
                      <button
                        onClick={() => handleExecute(act)}
                        disabled={isProcessing}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/20 transition-colors disabled:opacity-40"
                      >
                        <Play size={13} />
                        Execute Transaction
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Propose Action Modal */}
      {showProposeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl bg-[#0f1117] border border-white/[0.1] p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <Lock size={16} className="text-indigo-400" />
                <h3 className="text-sm font-bold text-white">Propose Controlled Business Action</h3>
              </div>
              <button
                onClick={() => setShowProposeModal(false)}
                className="text-zinc-400 hover:text-white"
              >
                <XCircle size={18} />
              </button>
            </div>

            <form onSubmit={handlePropose} className="space-y-3 text-xs">
              <div>
                <label className="text-zinc-400 font-semibold block mb-1">Action Type</label>
                <div className="grid grid-cols-3 gap-2">
                  {(["UPDATE", "INSERT", "DELETE"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setActionType(t)}
                      className={`py-2 rounded-lg font-mono font-semibold border text-center transition-colors ${
                        actionType === t
                          ? "bg-indigo-600/20 border-indigo-500 text-indigo-300"
                          : "bg-white/[0.02] border-white/[0.06] text-zinc-400 hover:bg-white/[0.06]"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-zinc-400 font-semibold block mb-1">Target Table *</label>
                <input
                  type="text"
                  placeholder="e.g. products, customers, orders"
                  value={targetTable}
                  onChange={(e) => setTargetTable(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-black/50 border border-white/[0.08] text-white focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              {actionType !== "DELETE" && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-zinc-400 font-semibold block mb-1">Column to Mutate</label>
                    <input
                      type="text"
                      placeholder="e.g. price, status"
                      value={columnName}
                      onChange={(e) => setColumnName(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-black/50 border border-white/[0.08] text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-zinc-400 font-semibold block mb-1">Proposed Value</label>
                    <input
                      type="text"
                      placeholder="e.g. 199.99, active"
                      value={proposedValue}
                      onChange={(e) => setProposedValue(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-black/50 border border-white/[0.08] text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              )}

              {actionType !== "INSERT" && (
                <div>
                  <label className="text-zinc-400 font-semibold block mb-1">
                    WHERE Condition SQL * (Must be restrictive)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. product_id = :id or category = :cat"
                    value={conditionSql}
                    onChange={(e) => setConditionSql(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-black/50 border border-white/[0.08] text-white font-mono focus:outline-none focus:border-indigo-500"
                    required
                  />
                  <span className="text-[10px] text-zinc-500">
                    Mandatory: Unrestricted mutations without WHERE or with tautologies (1=1) are strictly blocked.
                  </span>
                </div>
              )}

              {actionType !== "INSERT" && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-zinc-400 font-semibold block mb-1">Parameter Key</label>
                    <input
                      type="text"
                      placeholder="e.g. id, cat"
                      value={paramKey}
                      onChange={(e) => setParamKey(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-black/50 border border-white/[0.08] text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-zinc-400 font-semibold block mb-1">Parameter Value</label>
                    <input
                      type="text"
                      placeholder="e.g. 101, Electronics"
                      value={paramVal}
                      onChange={(e) => setParamVal(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-black/50 border border-white/[0.08] text-white font-mono focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="text-zinc-400 font-semibold block mb-1">Business Reason</label>
                <textarea
                  rows={2}
                  placeholder="Why is this modification being proposed?"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-black/50 border border-white/[0.08] text-white focus:outline-none focus:border-indigo-500 resize-none"
                />
              </div>

              <div className="pt-3 border-t border-white/[0.06] flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowProposeModal(false)}
                  className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingProposal}
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 disabled:opacity-40"
                >
                  {submittingProposal ? "Validating..." : "Submit Proposal"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
