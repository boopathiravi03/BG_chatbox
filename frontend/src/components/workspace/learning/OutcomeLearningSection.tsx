import React, { useState, useEffect } from "react";
import {
  GraduationCap,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  XCircle,
  ThumbsUp,
  ThumbsDown,
  RotateCcw,
  PlusCircle,
  Layers,
  Sparkles,
  Info,
  Clock,
  Send,
} from "lucide-react";
import {
  getLearningSummary,
  getOutcomes,
  recordOutcome,
  recordFeedback,
  getAuthToken,
} from "../../../services/api";
import type {
  OutcomeRecord,
  LearningSummary,
  OutcomeStatusType,
} from "../../../types";

interface OutcomeLearningSectionProps {
  dbConnected: boolean;
  activeQuestion?: string | null;
  activeDecisionId?: string | null;
}

export default function OutcomeLearningSection({
  dbConnected,
  activeQuestion,
  activeDecisionId,
}: OutcomeLearningSectionProps) {
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [outcomes, setOutcomes] = useState<OutcomeRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // New Outcome Form State
  const [showRecordModal, setShowRecordModal] = useState<boolean>(false);
  const [formActionType, setFormActionType] = useState<string>("INVESTIGATE");
  const [formExpected, setFormExpected] = useState<string>("");
  const [formActual, setFormActual] = useState<string>("");
  const [formStatus, setFormStatus] = useState<OutcomeStatusType>("SUCCESSFUL");
  const [formNotes, setFormNotes] = useState<string>("");
  const [savingOutcome, setSavingOutcome] = useState<boolean>(false);

  // Inline Feedback State
  const [feedbackSent, setFeedbackSent] = useState<boolean>(false);
  const [sendingFeedback, setSendingFeedback] = useState<boolean>(false);

  const fetchData = async () => {
    if (!getAuthToken()) return;
    setLoading(true);
    setErrorMessage(null);
    try {
      const [sumResp, outResp] = await Promise.all([
        getLearningSummary(),
        getOutcomes({ limit: 20 }),
      ]);
      if (sumResp && sumResp.status === "success" && sumResp.summary) {
        setSummary(sumResp.summary);
      }
      if (outResp && outResp.status === "success" && outResp.outcomes) {
        setOutcomes(outResp.outcomes);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load outcome and learning data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (getAuthToken()) {
      fetchData();
    }
  }, []);

  const handleSendFeedback = async (useful: boolean) => {
    if (!getAuthToken() || sendingFeedback) return;
    setSendingFeedback(true);
    try {
      await recordFeedback({
        target_type: "DECISION",
        target_id: activeDecisionId || undefined,
        question: activeQuestion || undefined,
        useful,
        accepted: useful,
      });
      setFeedbackSent(true);
      fetchData();
    } catch {
      // silent
    } finally {
      setSendingFeedback(false);
    }
  };

  const handleSaveOutcome = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formExpected.trim() || !formActual.trim() || savingOutcome) return;
    setSavingOutcome(true);
    try {
      await recordOutcome({
        action_type: formActionType,
        expected_outcome: formExpected.trim(),
        actual_outcome: formActual.trim(),
        status: formStatus,
        question: activeQuestion || undefined,
        decision_id: activeDecisionId || undefined,
        notes: formNotes.trim() || undefined,
      });
      setShowRecordModal(false);
      setFormExpected("");
      setFormActual("");
      setFormNotes("");
      fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to record outcome.");
    } finally {
      setSavingOutcome(false);
    }
  };

  const getStatusBadge = (status: OutcomeStatusType) => {
    switch (status) {
      case "SUCCESSFUL":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={11} /> SUCCESSFUL
          </span>
        );
      case "PARTIAL":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle size={11} /> PARTIAL
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <XCircle size={11} /> FAILED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-500/10 text-zinc-400 border border-zinc-500/20">
            <HelpCircle size={11} /> UNKNOWN
          </span>
        );
    }
  };

  return (
    <div className="space-y-4 pt-2">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-[#0f0f13] border border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500/15 border border-violet-500/30 flex items-center justify-center text-violet-400">
            <GraduationCap size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-white">Outcome & Learning Intelligence</h2>
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-violet-500/10 text-violet-300 border border-violet-500/20">
                Phase 8.5
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Closed-loop decision verification: plan, act, record real outcomes, and refine future guidance.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRecordModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-sm transition"
          >
            <PlusCircle size={14} /> Record Outcome
          </button>
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-white border border-white/[0.06] transition"
            title="Refresh learning summary"
          >
            <RotateCcw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Decision Feedback Prompt (if active question exists) */}
      {activeQuestion && (
        <div className="p-3.5 rounded-xl bg-indigo-950/20 border border-indigo-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div className="flex items-center gap-2.5">
            <Sparkles size={16} className="text-indigo-400 shrink-0" />
            <div className="text-xs">
              <span className="text-zinc-400">Was this decision analysis helpful for </span>
              <span className="text-indigo-300 font-medium">"{activeQuestion}"</span>
              <span className="text-zinc-400">?</span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {feedbackSent ? (
              <span className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                <CheckCircle2 size={13} /> Feedback recorded
              </span>
            ) : (
              <>
                <button
                  onClick={() => handleSendFeedback(true)}
                  disabled={sendingFeedback}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs transition"
                >
                  <ThumbsUp size={12} /> Useful
                </button>
                <button
                  onClick={() => handleSendFeedback(false)}
                  disabled={sendingFeedback}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 text-xs transition"
                >
                  <ThumbsDown size={12} /> Not Useful
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <AlertCircle size={14} /> {errorMessage}
        </div>
      )}

      {/* Metric Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <span className="text-[11px] text-zinc-400 font-medium">Recorded Outcomes</span>
          <div className="text-xl font-bold text-white font-mono">
            {summary ? summary.total_outcomes : 0}
          </div>
          <span className="text-[10px] text-zinc-400">Real executions logged</span>
        </div>

        <div className="p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <span className="text-[11px] text-emerald-400 font-medium">Successful</span>
          <div className="text-xl font-bold text-emerald-400 font-mono">
            {summary ? summary.successful_count : 0}
          </div>
          <span className="text-[10px] text-zinc-400">Goals fully achieved</span>
        </div>

        <div className="p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <span className="text-[11px] text-amber-400 font-medium">Partial / Unknown</span>
          <div className="text-xl font-bold text-amber-400 font-mono">
            {summary ? summary.partial_count + summary.unknown_count : 0}
          </div>
          <span className="text-[10px] text-zinc-400">Pending or mixed results</span>
        </div>

        <div className="p-3.5 rounded-xl bg-[#121216] border border-white/[0.06] space-y-1">
          <span className="text-[11px] text-indigo-400 font-medium">User Feedback</span>
          <div className="text-xl font-bold text-indigo-400 font-mono">
            {summary ? summary.total_feedbacks : 0}
          </div>
          <span className="text-[10px] text-zinc-400">
            {summary && summary.useful_count > 0 ? `${summary.useful_count} positive ratings` : "No ratings yet"}
          </span>
        </div>
      </div>

      {/* Learning Status Banner */}
      {summary && summary.insufficient_data ? (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/25 space-y-2">
          <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs">
            <Info size={15} />
            <span>Insufficient Historical Outcome Data (Cold Start)</span>
          </div>
          <p className="text-xs text-amber-200/80 leading-relaxed">
            The learning engine requires at least 3 real recorded action outcomes before synthesizing recurring
            decision patterns. Currently, <strong>{summary.total_outcomes}/3</strong> outcomes are logged.
          </p>
          {summary.areas_with_insufficient_data.length > 0 && (
            <div className="pt-1 space-y-1">
              <span className="text-[10px] uppercase font-bold text-amber-300/80 tracking-wider">
                Identified Data Gaps
              </span>
              <ul className="text-xs text-zinc-400 list-disc list-inside space-y-0.5">
                {summary.areas_with_insufficient_data.slice(0, 3).map((gap, idx) => (
                  <li key={idx}>{gap}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : summary && (
        <div className="p-4 rounded-xl bg-violet-500/10 border border-violet-500/25 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-violet-300 font-semibold text-xs">
              <Sparkles size={15} />
              <span>Learned Empirical Decision Patterns</span>
            </div>
            <span className="text-[10px] text-zinc-400 italic">
              Based on {summary.total_outcomes} verified historical outcomes
            </span>
          </div>

          {summary.successful_patterns.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {summary.successful_patterns.map((pat) => (
                <div key={pat.pattern_id} className="p-3 rounded-lg bg-black/40 border border-white/[0.06] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white">{pat.action_type}</span>
                    <span className="text-[10px] text-emerald-400 font-semibold">{pat.evidence_support}</span>
                  </div>
                  <p className="text-xs text-zinc-300">{pat.description}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-400">
              No strong recurring patterns detected yet across action types. Continue logging real outcomes.
            </p>
          )}

          <p className="text-[10px] text-zinc-400 border-t border-white/[0.04] pt-2">
            <strong>Caveat:</strong> {summary.disclaimer}
          </p>
        </div>
      )}

      {/* Outcome History */}
      <div className="p-4 rounded-2xl bg-[#0f0f13] border border-white/[0.08] space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={15} className="text-zinc-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Outcome History ({outcomes.length})
            </h3>
          </div>
          <span className="text-[11px] text-zinc-400">Strictly isolated to your account</span>
        </div>

        {outcomes.length === 0 ? (
          <div className="p-6 text-center rounded-xl bg-black/20 border border-white/[0.04] space-y-1.5">
            <p className="text-xs text-zinc-400">No decision outcomes recorded yet.</p>
            <p className="text-[11px] text-zinc-400">
              When you complete investigations or apply safe actions, click "Record Outcome" to log real operational results.
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
            {outcomes.map((out) => (
              <div
                key={out.outcome_id}
                className="p-3 rounded-xl bg-[#121216] border border-white/[0.06] hover:border-white/[0.12] transition space-y-1.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white font-mono">[{out.action_type}]</span>
                    {getStatusBadge(out.status)}
                  </div>
                  <span className="text-[10px] text-zinc-400">
                    {new Date(out.created_at).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>

                <div className="text-xs space-y-0.5">
                  <p className="text-zinc-300">
                    <strong className="text-zinc-400">Expected:</strong> {out.expected_outcome}
                  </p>
                  <p className="text-zinc-300">
                    <strong className="text-zinc-400">Actual:</strong> {out.actual_outcome}
                  </p>
                  {out.notes && (
                    <p className="text-[11px] text-zinc-400 italic">
                      Note: {out.notes}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Record Outcome Modal */}
      {showRecordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl bg-[#141418] border border-white/[0.12] shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <PlusCircle size={18} className="text-violet-400" />
                <h3 className="text-sm font-bold text-white">Record Action Outcome</h3>
              </div>
              <button
                onClick={() => setShowRecordModal(false)}
                className="p-1 rounded-lg text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveOutcome} className="space-y-3 text-xs">
              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 uppercase font-semibold">Action Type</label>
                <select
                  value={formActionType}
                  onChange={(e) => setFormActionType(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/[0.1] text-white focus:outline-none focus:border-violet-500"
                >
                  <option value="INVESTIGATE">INVESTIGATE (Data Analysis / Deep-dive)</option>
                  <option value="AUDIT">AUDIT (Data Quality / Pipeline Check)</option>
                  <option value="COMPARE">COMPARE (Cross-Table Correlation)</option>
                  <option value="REMEDIATE">REMEDIATE (Database Update / Safe Action)</option>
                  <option value="MANUAL">MANUAL (Operational / Business Adjustment)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 uppercase font-semibold">Outcome Status</label>
                <div className="grid grid-cols-4 gap-1.5">
                  {(["SUCCESSFUL", "PARTIAL", "FAILED", "UNKNOWN"] as OutcomeStatusType[]).map((st) => (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setFormStatus(st)}
                      className={`py-1.5 rounded-lg text-[10px] font-bold border transition ${
                        formStatus === st
                          ? "bg-violet-600 text-white border-violet-500"
                          : "bg-black/40 text-zinc-400 border-white/[0.08] hover:text-white"
                      }`}
                    >
                      {st}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 uppercase font-semibold">Expected Outcome</label>
                <input
                  type="text"
                  value={formExpected}
                  onChange={(e) => setFormExpected(e.target.value)}
                  placeholder="e.g. Isolate declining SKU revenue contribution"
                  required
                  className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/[0.1] text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 uppercase font-semibold">Actual Outcome</label>
                <textarea
                  rows={2}
                  value={formActual}
                  onChange={(e) => setFormActual(e.target.value)}
                  placeholder="e.g. Category Electronics represented 74% of the contraction"
                  required
                  className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/[0.1] text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 uppercase font-semibold">Optional Notes</label>
                <input
                  type="text"
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                  placeholder="Any operational constraints or observations"
                  className="w-full px-3 py-2 rounded-xl bg-black/50 border border-white/[0.1] text-white placeholder-zinc-500 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRecordModal(false)}
                  className="px-3 py-1.5 rounded-xl text-zinc-400 hover:text-white text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingOutcome}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow transition disabled:opacity-50"
                >
                  <Send size={13} /> {savingOutcome ? "Saving..." : "Save Outcome"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
