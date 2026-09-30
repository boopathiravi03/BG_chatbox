import React, { useState } from "react";
import {
  FileText,
  Download,
  Calendar,
  Sparkles,
  CheckCircle,
  Database,
  Plug,
  Clock,
  Send,
  FileSpreadsheet,
} from "lucide-react";
import { getBusinessAnalysis } from "../../../services/api";
import { exportDocumentPDF } from "../../../utils/exportPdf";
import { useToast } from "../../../context/ToastContext";

interface ReportsViewProps {
  dbConnected: boolean;
  onConnectDatabase: () => void;
}

export default function ReportsView({
  dbConnected,
  onConnectDatabase,
}: ReportsViewProps) {
  const [generating, setGenerating] = useState(false);
  const [reportData, setReportData] = useState<any>(null);
  const toast = useToast();

  const handleGenerateReport = async () => {
    setGenerating(true);
    try {
      const data = await getBusinessAnalysis();
      setReportData(data);
      toast.success("Executive BI Report compiled successfully");
    } catch (err) {
      toast.error("Failed to generate report from database profile");
    } finally {
      setGenerating(false);
    }
  };

  const handleExportPDF = async () => {
    try {
      if (!reportData?.ai_summary) {
        toast.error("Generate a report first to export");
        return;
      }
      await exportDocumentPDF(
        "Executive Business Intelligence Summary",
        reportData.ai_summary,
        "BG_AI_Executive_Report.pdf",
      );
      toast.success("PDF report downloaded");
    } catch (err) {
      toast.error("Failed to generate PDF");
    }
  };

  if (!dbConnected) {
    return (
      <div className="p-8 max-w-xl mx-auto my-16 text-center space-y-4 bg-[#121216] border border-white/[0.08] rounded-2xl">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 mx-auto">
          <FileText size={24} />
        </div>
        <h3 className="text-lg font-bold text-white">No Database Connected</h3>
        <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
          Connect your database to compile executive reports, export audit summaries,
          and schedule automated intelligence.
        </p>
        <button
          onClick={onConnectDatabase}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all cursor-pointer"
        >
          <Plug size={14} />
          <span>Connect Database</span>
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Reports Header */}
      <div className="p-5 rounded-2xl bg-[#121216] border border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            <FileText size={18} className="text-indigo-400" />
            <span>AI Executive Reports & Exports</span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Compiled business summaries, KPIs, risk factors, and downloadable intelligence.
          </p>
        </div>

        <button
          onClick={handleGenerateReport}
          disabled={generating}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer shrink-0"
        >
          <Sparkles size={14} className={generating ? "animate-spin" : ""} />
          <span>{generating ? "Compiling Report..." : "Generate AI Business Report"}</span>
        </button>
      </div>

      {/* Report Document Container */}
      {reportData ? (
        <div className="space-y-4">
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={handleExportPDF}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-semibold text-white transition-all cursor-pointer"
            >
              <Download size={13} />
              <span>Download PDF</span>
            </button>
          </div>

          <div
            id="executive-report-document"
            className="p-8 rounded-2xl bg-[#121216] border border-white/[0.08] text-zinc-200 space-y-6 shadow-xl"
          >
            <div className="border-b border-white/[0.08] pb-4 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-bold">
                  Confidential &bull; BG AI Enterprise
                </span>
                <h3 className="text-xl font-black text-white mt-1">
                  Executive Business Intelligence Summary
                </h3>
              </div>
              <span className="text-xs font-mono text-zinc-500">
                {new Date().toLocaleDateString(undefined, { dateStyle: "long" })}
              </span>
            </div>

            <div className="prose prose-invert max-w-none text-xs leading-relaxed whitespace-pre-wrap">
              {reportData.ai_summary || "Report generated successfully."}
            </div>
          </div>
        </div>
      ) : (
        <div className="p-12 text-center text-xs text-zinc-400 bg-[#121216] border border-white/[0.06] rounded-2xl space-y-2">
          <FileText size={24} className="text-zinc-600 mx-auto" />
          <p className="text-sm font-semibold text-zinc-300">No Report Generated Yet</p>
          <p>Click "Generate AI Business Report" above to compile a comprehensive executive summary.</p>
        </div>
      )}

      {/* Scheduled Intelligence Placeholder */}
      <div className="p-5 rounded-2xl bg-[#121216]/60 border border-white/[0.06] space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-indigo-400" />
            <h4 className="text-xs font-bold text-white uppercase tracking-wider">
              Scheduled Intelligence Delivery
            </h4>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-semibold">
            COMING NEXT
          </span>
        </div>

        <p className="text-xs text-zinc-400 leading-relaxed max-w-3xl">
          Automate delivery of weekly executive intelligence reports directly to your team's
          Slack channel or executive email every Monday at 9 AM, highlighting growth signals,
          anomalies, and forecast projections.
        </p>
      </div>
    </div>
  );
}
